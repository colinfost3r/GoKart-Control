#!/usr/bin/env python3
"""Upload a Core2 application using the installed official ESP32 espota.py.

All four inputs are explicit. Credentials JSON must be private (0600) and contain
an ota_password string. The password stays off process arguments and logs. This
uploads only an application image; it never sends VESC or kart-control commands.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile


# A 1.4 MB image reached kart 3 at 3 to 8 kB/s on 2026-11-13 and took about three minutes.
# The default stays short; a longer deadline is an explicit choice for a measured slow link.
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 480


class UploadError(Exception):
    pass


def read_password(path):
    try:
        mode = path.stat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_mode & 0o077:
            raise UploadError('Credentials must be a private regular file (chmod 600).')
        if hasattr(os, 'getuid') and mode.st_uid != os.getuid():
            raise UploadError('Credentials must belong to the current user.')
        if mode.st_size > 65536:
            raise UploadError('Credentials JSON is too large.')
        value = json.loads(path.read_text(encoding='utf-8'))
        password = value.get('ota_password') if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        raise UploadError('Cannot read credentials JSON.') from None
    if not isinstance(password, str) or not password.strip() or len(password) > 128:
        raise UploadError('Credentials require a nonempty ota_password string, at most 128 characters.')
    if any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise UploadError('OTA password cannot contain control characters.')
    return password


def snapshot_image(source, destination):
    """Hash exactly the bytes passed to espota, even if a new build replaces source."""
    digest = hashlib.sha256()
    size = 0
    try:
        if not stat.S_ISREG(source.stat().st_mode):
            raise UploadError('Application image must be a regular file.')
        with source.open('rb') as src, destination.open('xb') as dst:
            os.chmod(destination, 0o600)
            header = src.read(40)
            # ESP32 image + chip ID 0 + application descriptor (not S3, bootloader or merged flash).
            if (len(header) < 40 or header[0] != 0xE9 or header[12:14] != b'\x00\x00'
                    or header[32:36] != b'\x32\x54\xcd\xab'):
                raise UploadError('Require an ESP32 application .bin for Core2; empty, other-chip and non-app images are refused.')
            chunk = header
            while chunk:
                size += len(chunk)
                if size > 16 * 1024 * 1024:
                    raise UploadError('Application image exceeds 16 MiB.')
                dst.write(chunk)
                digest.update(chunk)
                chunk = src.read(65536)
    except OSError:
        raise UploadError('Cannot read the application image or create its private snapshot.') from None
    return size, digest.hexdigest()


def upload_worker(espota_path, image_path, request):
    """Import the official uploader without putting its authentication in argv."""
    authenticated = False
    acknowledged = False
    refused_no_auth = False

    class ResultHandler(logging.Handler):
        def emit(self, record):
            nonlocal acknowledged
            # espota also returns 0 for some unexpected replies. Require its explicit ACK path.
            if record.msg == 'Success' and not record.args:
                acknowledged = True

    with open(os.devnull, 'w') as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
        try:
            spec = importlib.util.spec_from_file_location('gokart_official_espota', espota_path)
            if spec is None or spec.loader is None:
                raise UploadError('Cannot load the official espota.py.')
            espota = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(espota)
            espota.TIMEOUT = 3
            espota.PROGRESS = False
            root = logging.getLogger()
            root.handlers = [ResultHandler()]
            root.setLevel(logging.INFO)
            invite = espota.send_invitation_and_get_auth_challenge
            authenticate = espota.authenticate

            def require_auth(*args, **kwargs):
                nonlocal refused_no_auth
                success, challenge, error = invite(*args, **kwargs)
                if success:
                    fields = challenge.split() if isinstance(challenge, str) else []
                    if (len(fields) != 2 or fields[0] != 'AUTH' or len(fields[1]) != 64
                            or any(c not in '0123456789abcdefABCDEF' for c in fields[1])):
                        refused_no_auth = True
                        return False, None, 'A current password-authenticated OTA challenge is required.'
                return success, challenge, error

            def record_auth(*args, **kwargs):
                nonlocal authenticated
                # This helper targets the pinned modern Core2 build; do not silently downgrade.
                if kwargs.get('use_md5_password') or kwargs.get('use_old_protocol'):
                    return False, 'Legacy password authentication is not enabled.'
                result = authenticate(*args, **kwargs)
                authenticated |= result[0] is True
                return result

            espota.send_invitation_and_get_auth_challenge = require_auth
            espota.authenticate = record_auth
            code = espota.serve(request['host'], '0.0.0.0', 3232,
                                10000 + secrets.randbelow(50001), request['password'],
                                False, str(image_path), espota.FLASH)
        except Exception:
            return {'ok': False, 'error': 'OTA uploader failed; check the host, firmware and network.'}
    if refused_no_auth:
        return {'ok': False, 'error': 'Target did not require the expected password authentication; upload refused.'}
    if code != 0 or not authenticated or not acknowledged:
        return {'ok': False, 'error': 'OTA was not authenticated and explicitly acknowledged; verify device status before retrying.'}
    return {'ok': True}


def run_upload(espota_path, image_path, host, password, timeout):
    # The child receives the password on a pipe, never argv/environment. Killing it bounds even
    # the official uploader's long final-result wait and closes its network sockets.
    process = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()), '--worker',
                                str(espota_path), str(image_path)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
    try:
        output, _ = process.communicate(json.dumps({'host': host, 'password': password}), timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise UploadError('OTA deadline reached; verify device status before retrying. No automatic retry was sent.') from None
    except BaseException:
        process.kill()
        process.communicate()
        raise
    try:
        result = json.loads(output)
    except (ValueError, UnicodeError):
        raise UploadError('OTA worker failed without a valid result; verify device status.') from None
    if process.returncode != 0 or not isinstance(result, dict) or result.get('ok') is not True:
        # Only our worker's fixed messages are displayed; never raw uploader output or traceback.
        error = result.get('error') if isinstance(result, dict) else None
        raise UploadError(error or 'OTA upload failed; verify device status.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Core2 hostname or IPv4 address (OTA UDP 3232).')
    parser.add_argument('--image', required=True, type=Path, help='Compiled Core2 application .bin, not merged flash.')
    parser.add_argument('--credentials', required=True, type=Path, help='Private JSON file containing ota_password.')
    parser.add_argument('--espota', required=True, type=Path, help='Official tools/espota.py from the installed ESP32 core.')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                        help=f'Total upload deadline, 1–{MAX_TIMEOUT} seconds (default {DEFAULT_TIMEOUT}).')
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= MAX_TIMEOUT:
        parser.error(f'--timeout must be 1–{MAX_TIMEOUT} seconds')
    if not args.host or any(c.isspace() or ord(c) < 33 for c in args.host) or '/' in args.host:
        parser.error('--host must be a hostname or IPv4 address')
    try:
        password = read_password(args.credentials)
        if not args.espota.is_file():
            raise UploadError('Official espota.py was not found at --espota.')
        with tempfile.TemporaryDirectory(prefix='gokart-core2-ota-') as temporary:
            image = Path(temporary) / 'core2-application.bin'
            size, digest = snapshot_image(args.image, image)
            print(f'Core2 OTA target: {args.host}:3232', flush=True)
            print(f'Application: {size} bytes; SHA-256 {digest}', flush=True)
            run_upload(args.espota.resolve(), image, args.host, password, args.timeout)
        print('Authenticated upload acknowledged. Verify the Core2 firmware and live telemetry after reboot.')
        return 0
    except UploadError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except OSError:
        print('Error: OTA helper could not start or access its required files.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('OTA interrupted; verify the Core2 firmware before retrying.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        try:
            result = upload_worker(Path(sys.argv[2]), Path(sys.argv[3]), json.load(sys.stdin))
        except Exception:
            result = {'ok': False, 'error': 'OTA worker could not read its input.'}
        print(json.dumps(result))
        sys.exit(0 if result.get('ok') else 1)
    sys.exit(main())
