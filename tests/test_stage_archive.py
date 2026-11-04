"""Meaningful ingestion safety checks, independent of unavailable SEC archives."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('stage_archive', Path(__file__).resolve().parents[1] / 'scripts/stage_archive.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'input.zip'

    def write_archive(self, entries):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, payload in entries:
                archive.writestr(name, payload)

    def test_stages_exact_bytes_with_manifest_and_refuses_overwrite(self):
        self.write_archive([('experiment/main.py', 'print(42)\n'), ('results/facts.json', '[]\n')])
        destination = self.root / 'stage'
        report = module.stage_archive(self.archive, destination, self.archive.stat().st_size)
        self.assertEqual((destination / 'experiment/main.py').read_bytes(), b'print(42)\n')
        self.assertEqual(json.loads((destination / '_import_manifest.json').read_text()), report)
        self.assertEqual(len(report['sha256']), 64)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            module.stage_archive(self.archive, destination)

    def test_rejects_paths_and_reserved_manifest_without_output(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'a\\b', 'a/../b',
                     './a', 'a//b', '_import_manifest.json'):
            with self.subTest(name=name):
                self.write_archive([(name, 'bad')])
                with self.assertRaises(ValueError):
                    module.stage_archive(self.archive, self.root / 'stage')
                self.assertFalse((self.root / 'stage').exists())

    def test_rejects_symlink(self):
        info = zipfile.ZipInfo('symlink')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr(info, '/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            module.audit_archive(self.archive)

    def test_rejects_cache_and_credentials(self):
        for name, payload in [('cache/facts.json', '{}'), ('.env', 'secret'),
                              ('cookies.json', '{}'), ('notes.txt', '-----BEGIN PRIVATE KEY-----')]:
            with self.subTest(name=name):
                self.write_archive([(name, payload)])
                with self.assertRaises(ValueError):
                    module.audit_archive(self.archive)

    def test_rejects_duplicate_and_file_directory_conflicts(self):
        for entries in [[('A.txt', '1'), ('a.txt', '2')], [('a', 'file'), ('a/b', 'child')]]:
            self.write_archive(entries)
            with self.assertRaises(ValueError):
                module.audit_archive(self.archive)

    def test_size_and_uncompressed_limits(self):
        self.write_archive([('facts.json', '1234567890')])
        with self.assertRaisesRegex(ValueError, 'size mismatch'):
            module.audit_archive(self.archive, expected_size=1)
        previous = module.MAX_FILE
        try:
            module.MAX_FILE = 5
            with self.assertRaisesRegex(ValueError, 'size limit'):
                module.audit_archive(self.archive)
        finally:
            module.MAX_FILE = previous


if __name__ == '__main__':
    unittest.main()
