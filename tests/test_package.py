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
