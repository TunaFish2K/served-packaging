import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('update_recipe', ROOT / 'scripts/update.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class RecipeTests(unittest.TestCase):
    def test_recipe_and_source_metadata_match_without_executing_pkgbuild(self):
        package = ROOT / 'aur/served-bin'
        state = json.loads((package / 'upstream.json').read_text())
        self.assertEqual((package / 'PKGBUILD').read_text(), u.recipe(state['tag'], state['sha256'], state['pkgrel']))
        fields = {}
        for line in (package / '.SRCINFO').read_text().splitlines():
            if '=' in line:
                key, value = map(str.strip, line.split('=', 1))
                fields.setdefault(key, []).append(value)
        self.assertEqual(fields['pkgver'], [state['tag'][1:]])
        self.assertEqual(fields['pkgrel'], [str(state['pkgrel'])])
        self.assertEqual(fields['arch'], ['x86_64'])
        expected = [state['sha256']] + [hashlib.sha256((package / name).read_bytes()).hexdigest() for name in u.LOCAL_FILES]
        self.assertEqual(fields['sha256sums'], expected)
        self.assertEqual(fields['source'][1:], u.LOCAL_FILES)
