"""Security tests for the approved My Office binary importer."""
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / 'import_my_office_assets.py'
spec=importlib.util.spec_from_file_location('my_office_import', SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class OriginalIntegrityTests(unittest.TestCase):
    def test_missing_source_does_not_create_any_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'public'
            with self.assertRaisesRegex(ValueError,'missing input ZIP'):
                mod.install(Path(tmp)/'missing.zip',dest)
            self.assertFalse(dest.exists())
    def test_incomplete_archive_does_not_create_any_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'assets.zip';dest=Path(tmp)/'public'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('irrelevant.txt',b'unrelated')
            with self.assertRaisesRegex(ValueError,'missing approved asset'):
                mod.install(path,dest)
            self.assertFalse(dest.exists())
    def test_tampered_originals_refused_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'assets.zip';dest=Path(tmp)/'public'
            with zipfile.ZipFile(path,'w') as z:
                for source in mod.RECORDS:
                    z.writestr(source,b'not-approved')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                mod.install(path,dest)
            self.assertFalse(dest.exists())
    def test_all_originals_have_unique_declared_hashes(self):
        hashes=[x[1] for x in mod.RECORDS.values()]
        self.assertEqual(len(hashes),8)
        self.assertEqual(len(set(hashes)),8)
        self.assertTrue(all(len(h)==64 for h in hashes))

if __name__=='__main__':
    unittest.main()
