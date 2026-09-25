import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('updater', Path(__file__).resolve().parents[1] / 'scripts/update.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class UpdateTests(unittest.TestCase):
    def release(self):
        name = 'served-linux-amd64-v0.15.1-full.tar.gz'
        base = 'https://github.com/TunaFish2K/served/releases/download/v0.15.1/'
        return {'draft': False, 'prerelease': False, 'tag_name': 'v0.15.1',
                'assets': [{'name': n, 'browser_download_url': base + n} for n in [name, name + '.sha256']]}

    def test_only_complete_stable_assets(self):
        r = self.release()
        self.assertIn('full.tar.gz', u.select_assets(r)[0])
        for field in ['draft', 'prerelease']:
            with self.assertRaises(ValueError):
                u.select_assets(dict(r, **{field: True}))
        for tag in ['v1.0.0-rc1', 'v1.0.0;echo bad', '1.0.0']:
            with self.assertRaises(ValueError):
                u.version(tag)
        r['assets'].pop()
        with self.assertRaises(ValueError):
            u.select_assets(r)

    def test_checksums_and_asset_names(self):
        data = b'archive'
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(u.verified_digest('asset', data, f'{digest}  asset\n'.encode()), digest)
        for sidecar in [f'{digest}  other', '0' * 64 + '  asset', digest + '  asset\nextra']:
            with self.assertRaises(ValueError):
                u.verified_digest('asset', data, sidecar.encode())

    def test_version_monotonicity_and_immutable_assets(self):
        previous = {'tag': 'v0.15.1', 'sha256': 'original'}
        u.validate_transition(previous, 'v0.15.1', 'original')
        u.validate_transition(previous, 'v0.15.2', 'new')
        for tag, digest in [('v0.15.0', 'old'), ('v0.15.1', 'replaced')]:
            with self.assertRaises(ValueError):
                u.validate_transition(previous, tag, digest)

    def test_release_workflow_must_succeed(self):
        for conclusion, expected in [('success', True), ('failure', False), (None, False)]:
            with patch.object(u, 'api', side_effect=[{'object': {'type': 'commit', 'sha': 'abc'}},
                    {'workflow_runs': [{'run_number': 1, 'run_attempt': 1, 'conclusion': conclusion}]}]):
                self.assertEqual(u.completed(self.release()), expected)

    def test_annotated_tag_and_latest_rerun(self):
        with patch.object(u, 'api', side_effect=[{'object': {'type': 'tag', 'sha': 'tag'}},
                {'object': {'type': 'commit', 'sha': 'abc'}}, {'workflow_runs': [
                    {'run_number': 1, 'run_attempt': 1, 'conclusion': 'success'},
                    {'run_number': 1, 'run_attempt': 2, 'conclusion': 'failure'}]}]):
            self.assertFalse(u.completed(self.release()))
