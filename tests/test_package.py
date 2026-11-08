import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package_skill import package, SOURCE


class PackageTests(unittest.TestCase):
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
