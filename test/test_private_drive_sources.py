import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from private_drive_sources import is_monroe_model, stage  # noqa: E402


class PrivateDriveSourcesTests(unittest.TestCase):
    def test_copy_is_verified_and_newer_drive_version_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.json'
            target = root / 'drive' / 'model.json'
            source.write_bytes(b'original')
            self.assertTrue(stage(source, target))
            self.assertEqual(target.read_bytes(), b'original')
            self.assertFalse(stage(source, target))
            target.write_bytes(b'newer private Drive edit')
            newer = source.stat().st_mtime + 10
            os.utime(target, (newer, newer))
            self.assertFalse(stage(source, target))
            self.assertEqual(target.read_bytes(), b'newer private Drive edit')

    def test_only_monroe_export_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / 'model.json'
            model.write_text('{"project":{"projectName":"Fernando"}}')
            self.assertFalse(is_monroe_model(model))
            model.write_text('{"project":{"projectName":"206 Monroe Drive"}}')
            self.assertTrue(is_monroe_model(model))
