import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package_skill import package, SOURCE
from package_source import package_source


class PackageTests(unittest.TestCase):
    @unittest.skipUnless((SOURCE.parents[1] / '.git').exists(), 'Source repackaging provenance requires a Git checkout')
    def test_source_review_archive_contains_evidence_and_provenance_without_git_internals(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'source1.zip', Path(tmp) / 'source2.zip'
            manifest = package_source(first)
            package_source(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertTrue(any('/tests/fixtures/' in name for name in names))
                self.assertTrue(any('/.github/workflows/' in name for name in names))
                self.assertIn('mole-source/docs/reviews/rc1-static-review-ru.md', names)
                self.assertIn('mole-source/REVIEW-PROVENANCE.json', names)
                self.assertFalse(any('/.git/' in name or '/artifacts/' in name for name in names))
                provenance = json.loads(archive.read('mole-source/REVIEW-PROVENANCE.json'))
                self.assertEqual(provenance['revision'],manifest['revision'])

    def test_working_tree_archive_includes_new_sources_and_renamed_plans(self):
        import unittest.mock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'skills/mole/molekit').mkdir(parents=True)
            (root / 'skills/mole/molekit/new.py').write_text('# new source\n')
            (root / 'MOLE-0.1.0-IMPLEMENTATION-PLAN.md').write_text('# 0.1.0\n')
            (root / 'private.txt').write_text('not source')
            def fake_git(*args, **kwargs):
                if args[0] == 'ls-files':
                    if '--deleted' in args:
                        return b'skills/mole/removed.py\0'
                    return b'skills/mole/removed.py\0skills/mole/molekit/new.py\0MOLE-0.1.0-IMPLEMENTATION-PLAN.md\0private.txt\0'
                if args[0] == 'for-each-ref':
                    return b'feature/test abc123\n'
                if args[0] == 'rev-parse':
                    return b'abc123\n'
                return b'?? skills/mole/molekit/new.py\n'
            with unittest.mock.patch('package_source.git', side_effect=fake_git):
                manifest = package_source(root / 'review.zip', root)
            with zipfile.ZipFile(root / 'review.zip') as archive:
                self.assertIn('mole-source/skills/mole/molekit/new.py', archive.namelist())
                self.assertIn('mole-source/MOLE-0.1.0-IMPLEMENTATION-PLAN.md', archive.namelist())
                self.assertNotIn('mole-source/private.txt', archive.namelist())
                self.assertNotIn('mole-source/skills/mole/removed.py', archive.namelist())
            self.assertTrue(manifest['workingTreeDirty'])

    def test_reproducible_archive_and_clean_extracted_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a.zip", root / "b.zip"
            manifest = package(a)
            package(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertLess(a.stat().st_size, 1024 * 1024)
            with zipfile.ZipFile(a) as archive:
                self.assertTrue(all(name.startswith("mole/") and ".." not in Path(name).parts for name in archive.namelist()))
                self.assertFalse(any("__pycache__" in name for name in archive.namelist()))
                archive.extractall(root / "installed")
            entry = root / "installed/mole/scripts/mole.py"
            result = subprocess.run([sys.executable, "-I", "-S", "-B", str(entry), "doctor", "--json"],
                                    cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["engineVersion"], manifest["version"])
            self.assertIn('version: "' + manifest["version"] + '"', (SOURCE / "SKILL.md").read_text())
