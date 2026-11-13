import binascii
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_rx_filter', ROOT / 'tools/vesc/prepare_rx_filter.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gk-repl-plan-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exact_deployed_artifacts_and_independent_chunk_reconstruction(self):
        compact, plan_bytes, plan = p.reviewed_artifacts()
        self.assertEqual(p.sha256(plan_bytes), 'c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805')
        self.assertEqual(p.sha256(compact), 'd530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc')
        self.assertEqual((len(compact), len(plan['steps']), plan['max_payload']), (3732, 24, 397))
        reconstructed = b''
        for step in plan['steps']:
            self.assertEqual(step['payload_length'], len(step['expression'].encode('ascii')) + 2)
            self.assertLessEqual(step['payload_length'], 512)
            if step['kind'] != 'chunk':
                continue
            match = re.search(r'\(bufcpy gk-rx-load-buffer (\d+) ("(?:\\.|[^"\\])*") 0 (\d+)\)', step['expression'])
            self.assertIsNotNone(match)
            offset, encoded, count = match.groups()
            piece = json.loads(encoded).encode('ascii')
            self.assertEqual(int(offset), len(reconstructed))
            self.assertEqual(int(count), len(piece))
            reconstructed += piece
            self.assertEqual(step['expected_line'], f'(gk-rx-load-chunk {len(reconstructed)} {binascii.crc_hqx(reconstructed, 0)})')
        self.assertEqual(reconstructed, compact)
        self.assertEqual(plan['steps'][-2]['expected_line'], '(gk-rx-load-ready nil nil -1 -1)')
        self.assertEqual(plan['steps'][-1]['expected_line'], 'gk-rx-load-clean')

    def test_compaction_refuses_strings_nul_and_non_ascii(self):
        for source in (b'(print "a;b")', b'(print "hello")', b'(print\0 1)', b'(print \xff)'):
            with self.assertRaises((ValueError, UnicodeError)):
                p.compact_source(source)

    def test_changed_human_source_refuses_before_output_creation(self):
        changed = self.root / 'changed.lisp'
        changed.write_bytes(p.HUMAN_SOURCE.read_bytes() + b'; change\n')
        out = self.root / 'out'
        with patch.object(p, 'HUMAN_SOURCE', changed):
            with self.assertRaisesRegex(ValueError, 'Human candidate'):
                p.prepare(out)
        self.assertFalse(out.exists())

    def test_committed_compact_mismatch_refuses(self):
        changed = self.root / 'changed.lisp'
        changed.write_bytes(p.COMPACT_SOURCE.read_bytes().replace(b'0.12', b'0.99'))
        with patch.object(p, 'COMPACT_SOURCE', changed):
            with self.assertRaisesRegex(ValueError, 'Committed compact'):
                p.prepare()

    def test_plan_mismatch_refuses(self):
        changed = self.root / 'changed.json'
        changed.write_bytes(p.LOAD_PLAN.read_bytes() + b' ')
        with patch.object(p, 'LOAD_PLAN', changed):
            with self.assertRaisesRegex(ValueError, 'Committed plan'):
                p.prepare()

    def test_review_output_preserves_exact_plan_and_refuses_existing_directory(self):
        out = self.root / 'review'
        result = p.prepare(out)
        self.assertFalse(result['hardware_accessed'])
        self.assertEqual((out / 'rx-filter-load-plan.json').read_bytes(), p.LOAD_PLAN.read_bytes())
        self.assertEqual((out / 'rx-filter-candidate.compact.lisp').read_bytes(), p.COMPACT_SOURCE.read_bytes())
        with self.assertRaises(FileExistsError):
            p.prepare(out)
        self.assertEqual((out / 'manifest.json').read_text(), json.dumps(result, indent=2) + '\n')

    def test_portable_checkout_without_original_workspace_or_cwd_dependency(self):
        clone = self.root / 'different collaborator checkout'
        tool = clone / 'tools/vesc/prepare_rx_filter.py'
        tool.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'tools/vesc/prepare_rx_filter.py', tool)
        artifacts = clone / 'firmware/vesc-lisp/reverse-input'
        artifacts.mkdir(parents=True)
        for source in (p.HUMAN_SOURCE, p.COMPACT_SOURCE, p.LOAD_PLAN):
            shutil.copyfile(source, artifacts / source.name)
        result = subprocess.run([sys.executable, '-B', str(tool)], cwd=self.root,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['plan_sha256'], p.PLAN_SHA256)


if __name__ == '__main__':
    unittest.main()
