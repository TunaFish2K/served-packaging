import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / 'scripts/publish_aur.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PublishTests(unittest.TestCase):
    def test_disabled_needs_no_credentials(self):
        with patch.dict(os.environ, {'AUR_PUBLISH_ENABLED': 'false'}), patch.object(p, 'git') as git:
            p.main()
            git.assert_not_called()

    def test_retry_after_push_and_remote_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'package'
            package.mkdir()
            for name in p.FILES:
                (package / name).write_text(name + '\n')
            (package / 'upstream.json').write_text(json.dumps({'tag': 'v1.0.0', 'pkgrel': 1}))
            remote = root / 'aur.git'
            subprocess.run(['git', 'init', '--bare', '--initial-branch=master', str(remote)], check=True, capture_output=True)
            original_git = p.git
            def local_git(cwd, *args, **kwargs):
                if args[0] == 'clone':
                    args = ('clone', str(remote), args[2])
                return original_git(cwd, *args, **kwargs)
            state = package / 'aur-published.json'
            with patch.object(p, 'PACKAGE', package), patch.object(p, 'STATE', state), patch.object(p, 'git', local_git), patch.dict(os.environ, {'AUR_PUBLISH_ENABLED': 'true', 'GIT_SSH_COMMAND': 'unused-local-test'}):
                p.main()
                first = json.loads(state.read_text())['commit']
                state.unlink()  # Push succeeded but GitHub state commit was interrupted.
                p.main()
                self.assertEqual(json.loads(state.read_text())['commit'], first)
                (package / 'PKGBUILD').write_text('second recipe\n')
                p.main()
                second = json.loads(state.read_text())['commit']
                self.assertNotEqual(first, second)
                other = root / 'other'
                original_git(root, 'clone', str(remote), str(other))
                original_git(other, 'config', 'user.name', 'Another maintainer')
                original_git(other, 'config', 'user.email', 'test@example.invalid')
                (other / 'PKGBUILD').write_text('remote edit\n')
                original_git(other, 'add', 'PKGBUILD')
                original_git(other, 'commit', '-m', 'Independent change')
                original_git(other, 'push', 'origin', 'master')
                with self.assertRaisesRegex(ValueError, 'unrecognized changes'):
                    p.main()
                self.assertEqual(json.loads(state.read_text())['commit'], second)

    def test_publish_requires_explicit_ssh_config(self):
        with patch.dict(os.environ, {'AUR_PUBLISH_ENABLED': 'true'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'SSH'):
                p.main()
