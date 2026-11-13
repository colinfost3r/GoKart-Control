"""Core2 OTA helper tests with a fake espota module: no sockets, ports or hardware."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'tools/m5/ota_core2.py'
spec = importlib.util.spec_from_file_location('core2_ota_helper', HELPER)
ota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ota)

FAKE_ESPOTA = """
import logging
import sys
import time
FLASH = 0

def send_invitation_and_get_auth_challenge(*args):
    return True, CHALLENGE, None

def authenticate(*args, **kwargs):
    return True, None

def serve(host, local, port, local_port, password, md5_target, image, command):
    assert host == 'gokart-display-3.local' and local == '0.0.0.0' and port == 3232
    assert 10000 <= local_port <= 60000 and command == FLASH and not md5_target
    assert password == 'private-test-password'
    # Even output from a changed uploader must not leak credentials through this wrapper.
    print(password)
    print(password, file=sys.stderr)
    success, challenge, error = send_invitation_and_get_auth_challenge(host, port, 'invite')
    if not success:
        return 1
    ok, error = authenticate(host, port, password, use_md5_password=LEGACY,
                             use_old_protocol=False, filename=image, content_size=100,
                             file_md5='unused', nonce='a' * 64)
    if not ok:
        return 1
    time.sleep(DELAY)
    if ACK:
        logging.info('Success')
    return 0
"""


class Core2OtaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        header = bytearray(40)
        header[0] = 0xE9
        header[32:36] = bytes.fromhex('3254cdab')
        self.image = self.folder / 'core2.ino.bin'
        self.image.write_bytes(header + b'application-test-payload')
        self.credentials = self.folder / 'credentials.json'
        self.credentials.write_text(json.dumps({'ota_password': 'private-test-password'}))
        os.chmod(self.credentials, 0o600)
        self.espota = self.folder / 'espota.py'
        self.fake()

    def fake(self, *, challenge='AUTH ' + 'a' * 64, ack=True, legacy=False, delay=0):
        config = f'CHALLENGE={challenge!r}\nACK={ack!r}\nLEGACY={legacy!r}\nDELAY={delay!r}\n'
        self.espota.write_text(config + FAKE_ESPOTA)

    def cli(self):
        return subprocess.run([sys.executable, '-I', str(HELPER),
            '--host', 'gokart-display-3.local', '--image', str(self.image),
            '--credentials', str(self.credentials), '--espota', str(self.espota), '--timeout', '3'],
            capture_output=True, text=True, timeout=5)

    def test_authenticated_acknowledged_snapshot_and_no_secret_output(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(hashlib.sha256(self.image.read_bytes()).hexdigest(), result.stdout)
        self.assertIn('Authenticated upload acknowledged', result.stdout)
        self.assertNotIn('private-test-password', result.stdout + result.stderr)
        destination = self.folder / 'snapshot.bin'
        size, digest = ota.snapshot_image(self.image, destination)
        self.image.write_bytes(b'new build replaces input')
        self.assertEqual(size, destination.stat().st_size)
        self.assertEqual(digest, hashlib.sha256(destination.read_bytes()).hexdigest())

    def test_unauthenticated_or_legacy_target_is_refused(self):
        for options in ({'challenge': 'OK'}, {'challenge': 'AUTH ' + 'a' * 32}, {'legacy': True}):
            with self.subTest(options=options):
                self.fake(**options)
                result = self.cli()
                self.assertEqual(result.returncode, 1)
                self.assertNotIn('Authenticated upload acknowledged', result.stdout)
                self.assertNotIn('private-test-password', result.stdout + result.stderr)

    def test_official_zero_exit_without_explicit_ack_is_not_success(self):
        self.fake(ack=False)
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn('not authenticated and explicitly acknowledged', result.stderr)

    def test_private_credentials_and_core2_application_required(self):
        os.chmod(self.credentials, 0o644)
        with self.assertRaises(ota.UploadError):
            ota.read_password(self.credentials)
        os.chmod(self.credentials, 0o600)
        for value in ({}, {'ota_password': ''}, {'ota_password': '  '}, {'ota_password': 'a\nb'}):
            with self.subTest(credentials=value):
                self.credentials.write_text(json.dumps(value))
                with self.assertRaises(ota.UploadError):
                    ota.read_password(self.credentials)
        original = bytearray(self.image.read_bytes())
        s3 = original.copy(); s3[12:14] = b'\x09\x00'
        bootloader = original.copy(); bootloader[32:36] = b'\x00' * 4
        for index, value in enumerate((b'', b'not firmware', s3, bootloader)):
            with self.subTest(image=index):
                self.image.write_bytes(value)
                with self.assertRaises(ota.UploadError):
                    ota.snapshot_image(self.image, self.folder / f'rejected-{index}.bin')

    def test_upload_deadline_kills_worker_without_retry(self):
        self.fake(delay=3)
        start = time.monotonic()
        with self.assertRaisesRegex(ota.UploadError, 'No automatic retry'):
            ota.run_upload(self.espota, self.image, 'gokart-display-3.local',
                           'private-test-password', 0.2)
        self.assertLess(time.monotonic() - start, 2)

    def test_cli_timeout_is_bounded_and_short_by_default(self):
        def run(*timeout):
            return subprocess.run([sys.executable, '-I', str(HELPER), '--host', 'x',
                '--image', 'x', '--credentials', 'x', '--espota', 'x', *timeout],
                capture_output=True, text=True, timeout=2)
        for bad in ('481', '0', '-5'):
            result = run('--timeout', bad)
            self.assertEqual(result.returncode, 2, bad)
            self.assertIn('1–480 seconds', result.stderr)
        # A slow link may be given longer explicitly; the request then stops at the next check, not the bound.
        result = run('--timeout', '480')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Cannot read credentials JSON', result.stderr)
        self.assertEqual((ota.DEFAULT_TIMEOUT, ota.MAX_TIMEOUT), (120, 480))


if __name__ == '__main__':
    unittest.main()
