#!/usr/bin/env python3
"""Discover a completed upstream release and refresh an AUR recipe without executing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'aur/served-bin'
UPSTREAM = 'TunaFish2K/served'
LOCAL_FILES = ['served-install', 'served-pacman', '90-served-reload.hook', '10-served-stop.hook', 'MIGRATION.md']


def version(tag):
    match = re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag)
    if not match:
        raise ValueError(f'not a stable version: {tag}')
    return tuple(map(int, match.groups()))


def api(path):
    request = urllib.request.Request(f'https://api.github.com/repos/{UPSTREAM}/{path}', headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'served-packaging'})
    if os.environ.get('GH_TOKEN'):
        request.add_header('Authorization', 'Bearer ' + os.environ['GH_TOKEN'])
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def select_assets(release):
    if release['draft'] or release['prerelease']:
        raise ValueError('draft and prerelease releases are not eligible')
    version(release['tag_name'])
    name = f"served-linux-amd64-{release['tag_name']}-full.tar.gz"
    assets = {a['name']: a for a in release['assets']}
    if name not in assets or name + '.sha256' not in assets:
        raise ValueError('release assets are incomplete')
    expected = f"https://github.com/{UPSTREAM}/releases/download/{release['tag_name']}/"
    for key in [name, name + '.sha256']:
        if assets[key]['browser_download_url'] != expected + key:
            raise ValueError('unexpected asset URL')
    return name, assets[name]['browser_download_url'], assets[name + '.sha256']['browser_download_url']


def completed(release):
    tag = release['tag_name']
    ref = api(f'git/ref/tags/{tag}')['object']
    while ref['type'] == 'tag':
        ref = api('git/tags/' + ref['sha'])['object']
    runs = api(f"actions/workflows/release.yml/runs?head_sha={ref['sha']}&event=push&per_page=100")['workflow_runs']
    return bool(runs) and max(runs, key=lambda r: (r['run_number'], r.get('run_attempt', 1)))['conclusion'] == 'success'


def download(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'served-packaging'}), timeout=120) as response:
        return response.read()


def verified_digest(name, data, sidecar):
    fields = sidecar.decode('ascii').strip().split()
    if len(fields) != 2 or fields[1].lstrip('*') != name or not re.fullmatch('[0-9a-fA-F]{64}', fields[0]):
        raise ValueError('invalid checksum sidecar')
    digest = hashlib.sha256(data).hexdigest()
    if digest != fields[0].lower():
        raise ValueError('asset checksum mismatch')
    return digest


def validate_transition(previous, tag, digest):
    if previous and version(tag) < version(previous['tag']):
        raise ValueError('automatic downgrade is forbidden')
    if previous and tag == previous['tag'] and digest != previous['sha256']:
        raise ValueError('same-version upstream asset changed; manual investigation required')


def recipe(tag, digest, pkgrel):
    pkgver = tag[1:]
    hashes = [digest] + [hashlib.sha256((PACKAGE / f).read_bytes()).hexdigest() for f in LOCAL_FILES]
    sources = '\n        '.join("'" + f + "'" for f in LOCAL_FILES)
    checksums = '\n            '.join("'" + h + "'" for h in hashes)
    return f'''# Maintainer: TunaFish2K <i@2kb.fish>
pkgname=served-bin
pkgver={pkgver}
pkgrel={pkgrel}
pkgdesc='Lightweight per-user service manager with terminal UI and PTY attach'
arch=('x86_64')
url='https://github.com/TunaFish2K/served'
license=('Unlicense')
depends=('glibc' 'bash')
optdepends=('systemd: manage per-user manager instances at boot')
provides=("served=$pkgver")
conflicts=('served')
options=('!strip' '!debug')
install=served-install
source=("https://github.com/TunaFish2K/served/releases/download/v${{pkgver}}/served-linux-amd64-v${{pkgver}}-full.tar.gz"
        {sources})
sha256sums=({checksums})

package() {{
    local root="$srcdir/served-linux-amd64-v${{pkgver}}-full"
    install -Dm755 "$root/served" "$pkgdir/usr/bin/served"
    install -Dm644 "$root/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    install -Dm644 "$root/share/man/man1/served.1" "$pkgdir/usr/share/man/man1/served.1"
    install -Dm644 "$root/share/man/man5/served.5" "$pkgdir/usr/share/man/man5/served.5"
    install -dm755 "$pkgdir/usr/lib/systemd/system"
    sed 's|/usr/local/bin/served|/usr/bin/served|g' "$root/served@.service" > "$pkgdir/usr/lib/systemd/system/served@.service"
    install -dm755 "$pkgdir/usr/share/served/skills"
    cp -r "$root/share/served/skills/served" "$pkgdir/usr/share/served/skills/"
    install -Dm755 "$srcdir/served-pacman" "$pkgdir/usr/lib/served/served-pacman"
    install -Dm644 "$srcdir/90-served-reload.hook" "$pkgdir/usr/share/libalpm/hooks/90-served-reload.hook"
    install -Dm644 "$srcdir/10-served-stop.hook" "$pkgdir/usr/share/libalpm/hooks/10-served-stop.hook"
    install -Dm644 "$srcdir/MIGRATION.md" "$pkgdir/usr/share/doc/$pkgname/MIGRATION.md"
}}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', help='explicit stable release, still subject to downgrade and release checks')
    parser.add_argument('--refresh', action='store_true', help='refresh local packaging changes and increment pkgrel when needed')
    args = parser.parse_args()
    if args.tag:
        version(args.tag)
    release = api('releases/tags/' + args.tag if args.tag else 'releases/latest')
    name, url, checksum_url = select_assets(release)
    if not completed(release):
        raise ValueError('upstream release workflow has not completed successfully')
    digest = verified_digest(name, download(url), download(checksum_url))
    state_path = PACKAGE / 'upstream.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else None
    tag = release['tag_name']
    validate_transition(previous, tag, digest)
    pkgrel = previous['pkgrel'] if previous and tag == previous['tag'] else 1
    text = recipe(tag, digest, pkgrel)
    pkgbuild = PACKAGE / 'PKGBUILD'
    changed = not pkgbuild.exists() or pkgbuild.read_text() != text
    if changed and previous and tag == previous['tag']:
        if not args.refresh:
            raise ValueError('local recipe changed; run --refresh to bump pkgrel')
        pkgrel += 1
        text = recipe(tag, digest, pkgrel)
    if changed:
        pkgbuild.write_text(text)
        result = subprocess.run(['makepkg', '--printsrcinfo'], cwd=PACKAGE, check=True, capture_output=True, text=True)
        (PACKAGE / '.SRCINFO').write_text(result.stdout)
        state_path.write_text(json.dumps({'tag': tag, 'sha256': digest, 'pkgrel': pkgrel}, indent=2) + '\n')
    print(f'{tag}-{pkgrel}: ' + ('updated' if changed else 'unchanged'))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f'changed={str(changed).lower()}\nversion={tag}-{pkgrel}\n')


if __name__ == '__main__':
    main()
