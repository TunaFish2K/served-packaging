#!/usr/bin/env python3
"""Export the validated recipe into AUR's own Git history; never force-push."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'aur/served-bin'
FILES = ['PKGBUILD', '.SRCINFO', 'served-install', 'served-pacman', '90-served-reload.hook', '10-served-stop.hook', 'MIGRATION.md']
STATE = PACKAGE / 'aur-published.json'


def git(cwd, *args, check=True):
    return subprocess.run(['git', '-C', str(cwd), *args], check=check, capture_output=True, text=True)


def content_digest(directory):
    value = hashlib.sha256()
    for name in FILES:
        value.update(name.encode() + b'\0')
        path = directory / name
        value.update(path.read_bytes() if path.is_file() else b'<missing>')
    return value.hexdigest()


def main():
    if os.environ.get('AUR_PUBLISH_ENABLED') != 'true':
        print('AUR publication disabled: register an account and configure its dedicated SSH key first.')
        return
    if not os.environ.get('GIT_SSH_COMMAND'):
        raise ValueError('explicit SSH configuration with pinned host key is required')
    previous = json.loads(STATE.read_text()) if STATE.exists() else None
    with tempfile.TemporaryDirectory(prefix='served-aur-') as root:
        root = Path(root)
        git(root, 'clone', 'ssh://aur@aur.archlinux.org/served-bin.git', 'aur')
        repo = root / 'aur'
        current = git(repo, 'rev-parse', 'HEAD', check=False)
        head = current.stdout.strip() if current.returncode == 0 else None
        same = content_digest(repo) == content_digest(PACKAGE)
        if head and not same and (not previous or head != previous['commit']):
            raise ValueError('AUR has unrecognized changes; reconcile manually, no files were pushed')
        extras = set(git(repo, 'ls-files').stdout.splitlines()) - set(FILES)
        if extras:
            raise ValueError(f'unexpected tracked AUR files: {sorted(extras)}')
        if not same:
            for name in FILES:
                source = PACKAGE / name
                target = repo / name
                target.write_bytes(source.read_bytes())
                target.chmod(source.stat().st_mode & 0o777)
            git(repo, 'config', 'user.name', 'TunaFish2K packaging')
            git(repo, 'config', 'user.email', 'i@2kb.fish')
            git(repo, 'add', '--', *FILES)
            version = json.loads((PACKAGE / 'upstream.json').read_text())
            git(repo, 'commit', '-m', f"Update served-bin to {version['tag']}-{version['pkgrel']}")
            git(repo, 'push', 'origin', 'HEAD:master')
            head = git(repo, 'rev-parse', 'HEAD').stdout.strip()
        STATE.write_text(json.dumps({'commit': head, 'digest': content_digest(PACKAGE)}, indent=2) + '\n')
        print(f'AUR synchronized at {head}')


if __name__ == '__main__':
    main()
