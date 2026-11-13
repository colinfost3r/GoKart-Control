#!/usr/bin/env python3
"""Read the stored Lisp code blob on a UUID-pinned VESC 6.02 (commands 0 and 130 only).

This does not start, stop, evaluate, erase or write Lisp, change configuration,
reset the controller or dump raw flash. The returned blob excludes the eight-byte
size/CRC/flags header: autostart flags and execution state remain UNKNOWN. A zero
size is recorded as no_valid_blob, not proof of erased/blank flash. Reads are not
atomic; close VESC Tool and other clients, and do not edit code during capture.

Example (kart 3; choose an explicitly new output directory):
  python3 tools/vesc/read_lisp.py --port /dev/cu.usbmodemXXXX \
    --expected-uuid 37004e000951343037353739 --out /path/to/new-backup

Only Python's standard library is needed. POSIX serial setup does not manipulate
DTR/RTS; HUPCL stays disabled on close to avoid requesting a hangup/reset.
Protocol source: vedderb/bldc at f7c2b34e1cff2234cae98be3abf0cd50e249558f:
  datatypes.h (COMM_LISP_READ_CODE=130), comm/commands.c (READ_CODE handler),
  flash_helper.c (LISP_MAX_SIZE and flash_helper_code_data/size),
  comm/packet.h (512-byte default payload ceiling; use 256-byte code chunks).
"""
import argparse
import binascii
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import termios
import tty

from capture import receive, verified_identity

READ_COMMANDS = frozenset((0, 130))  # Separate from capture.py's unchanged allowlist.
MAX_CODE_BYTES = 128 * 1024 - 8
CHUNK_BYTES = 256  # Pinned packet.h defaults to 512; handler requires length <= max - 10.
READ_TIMEOUT = 3.0
SOURCE_COMMIT = 'f7c2b34e1cff2234cae98be3abf0cd50e249558f'
KART3_UUID = '37004e000951343037353739'


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def expected_uuid(value):
    value = value.lower()
    if not re.fullmatch(r'[0-9a-f]{24}', value) or value == '0' * 24:
        raise ValueError('Expected UUID must be 24 hexadecimal digits and must not be all zero')
    return value


def query_frame(command, length=0, offset=0):
    """Construct only an identity read or a bounded signed-int32 code read."""
    if type(command) is not int or command not in READ_COMMANDS:
        raise ValueError('Only identity (0) and stored Lisp code read (130) are allowed')
    if type(length) is not int or type(offset) is not int:
        raise ValueError('Length and offset must be integers')
    if command == 0:
        if length or offset:
            raise ValueError('Identity read has no arguments')
        payload = b'\x00'
    else:
        if (not 0 <= length <= CHUNK_BYTES or not 0 <= offset <= MAX_CODE_BYTES or
                offset + length > MAX_CODE_BYTES or (length == 0 and offset != 0)):
            raise ValueError('Code query outside the bounded read range')
        payload = b'\x82' + struct.pack('>ii', length, offset)
    return (bytes((2, len(payload))) + payload +
            binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03')


def parse_code_reply(payload, length, offset, total=None):
    """Require an exact-size response for the current request; no partial acceptance."""
    query_frame(130, length, offset)
    if len(payload) < 9 or payload[0] != 130:
        raise ValueError('Invalid Lisp read response header')
    received_total, received_offset = struct.unpack('>ii', payload[1:9])
    if not 0 <= received_total <= MAX_CODE_BYTES:
        raise ValueError('Lisp total size exceeds the pinned flash-sector limit')
    if received_offset < 0 or received_offset != offset:
        raise ValueError('Lisp response offset does not match the request')
    if total is not None and received_total != total:
        raise ValueError('Lisp total size changed during capture')
    if len(payload) != 9 + length:
        raise ValueError('Truncated or extra Lisp response data')
    if offset + length > received_total:
        raise ValueError('Lisp response exceeds its reported total')
    return received_total, payload[9:]


def require_identity(payload, target):
    result = verified_identity(payload)
    if result['firmware'] != '6.02':
        raise ValueError('Only pinned firmware 6.02 is supported')
    if result['uuid'] != target:
        raise ValueError('Controller UUID does not match --expected-uuid')
    return result


class SerialConnection:
    def __init__(self, port):
        self.port, self.fd, self.old = port, None, None

    def __enter__(self):
        try:
            self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            self.old = termios.tcgetattr(self.fd)
            tty.setraw(self.fd, termios.TCSANOW)
            cfg = termios.tcgetattr(self.fd)
            cfg[2] = (cfg[2] | termios.CLOCAL | termios.CREAD) & ~termios.HUPCL
            cfg[4] = cfg[5] = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, cfg)
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.fd is None:
            return
        try:
            if self.old is not None:
                # Restore framing without re-enabling hangup-on-close.
                self.old[2] &= ~termios.HUPCL
                termios.tcsetattr(self.fd, termios.TCSANOW, self.old)
        finally:
            os.close(self.fd)
            self.fd = None

    def __exit__(self, *unused):
        self.close()

    def query(self, command, length=0, offset=0):
        frame = query_frame(command, length, offset)
        # One syscall only. Never resend or append after a partial/uncertain send.
        if os.write(self.fd, frame) != len(frame):
            raise IOError('Partial serial read-query send; stopped without retry')
        return receive(self.fd, command, timeout=READ_TIMEOUT)


def backup(port, output, target_uuid, *, connection_factory=None):
    """Capture into a NEW directory. Retain raw replies and partial evidence on failure."""
    target_uuid = expected_uuid(target_uuid)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)  # Before any port is opened.
    (output / 'replies').mkdir()
    manifest = {
        'started_at_utc': utc_now(), 'port': port, 'transport': 'usb_serial',
        'expected_uuid': target_uuid, 'protocol_source_commit': SOURCE_COMMIT,
        'allowed_commands': sorted(READ_COMMANDS), 'chunk_bytes': CHUNK_BYTES,
        'scope': 'stored_lisp_code_blob_excluding_8_byte_size_crc_flags_header',
        'raw_flash_dump': False, 'autostart': 'not_read_unknown',
        'running_state': 'not_read_unknown', 'header_crc_independently_verified': False,
        'snapshot_atomic': False,
        'concurrent_edit_limit': 'Same-size concurrent code changes cannot be excluded.',
        'capture_complete': False, 'status': 'incomplete', 'validated_code_bytes': 0,
        'queries': [],
    }
    partial = output / 'lisp_code.partial.bin'

    def journal():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

    def read(connection, command, length=0, offset=0):
        entry = {'command': command, 'requested_at_utc': utc_now(),
                 'request_frame_hex': query_frame(command, length, offset).hex(),
                 'reply_received': False}
        if command == 130:
            entry.update({'length': length, 'offset': offset})
        manifest['queries'].append(entry)
        journal()
        payload = connection.query(command, length, offset)
        name = f'replies/{len(manifest["queries"]):04d}.bin'
        (output / name).write_bytes(payload)
        entry.update({'reply_received': True, 'transport_crc_verified': True,
                      'received_at_utc': utc_now(), 'file': name,
                      'payload_bytes': len(payload), 'sha256': sha256(payload)})
        journal()
        return payload

    try:
        journal()
        factory = connection_factory or SerialConnection
        with factory(port) as connection:
            firmware = read(connection, 0)
            (output / 'identity.bin').write_bytes(firmware)
            identity = require_identity(firmware, target_uuid)
            (output / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
            manifest['identity'] = identity
            total, _ = parse_code_reply(read(connection, 130), 0, 0)
            manifest['reported_code_bytes'] = total
            with partial.open('xb') as stream:
                for offset in range(0, total, CHUNK_BYTES):
                    length = min(CHUNK_BYTES, total - offset)
                    _, data = parse_code_reply(read(connection, 130, length, offset),
                                               length, offset, total)
                    stream.write(data)
                    stream.flush()
                    manifest['validated_code_bytes'] += len(data)
                    journal()
            # Catch reported-size/identity changes; cannot prove atomicity of same-size edits.
            if total:
                parse_code_reply(read(connection, 130), 0, 0, total)
            firmware_after = read(connection, 0)
            (output / 'identity_after.bin').write_bytes(firmware_after)
            identity_after = require_identity(firmware_after, target_uuid)
            if identity_after['hardware'] != identity['hardware']:
                raise ValueError('Controller hardware identity changed during capture')
            (output / 'identity_after.json').write_text(json.dumps(identity_after, indent=2) + '\n')
        code = partial.read_bytes()
        if len(code) != total:
            raise ValueError('Local blob length does not match reported code size')
        partial.rename(output / 'lisp_code.bin')
        manifest.update({'status': 'code_blob_captured' if total else 'no_valid_blob',
                         'capture_complete': True, 'code_file': 'lisp_code.bin',
                         'code_sha256': sha256(code), 'identity_rechecked': True})
        if not total:
            manifest['empty_result_meaning'] = (
                'Firmware exposed no valid nonempty code blob; this is not proof of blank '
                'flash and does not establish autostart flags or execution state.')
    except BaseException as error:
        manifest['status'] = 'failed'
        manifest['error'] = f'{type(error).__name__}: {error}'
        if partial.exists():
            manifest['partial_file'] = partial.name
            manifest['partial_sha256'] = sha256(partial.read_bytes())
        raise
    finally:
        manifest['finished_at_utc'] = utc_now()
        journal()
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', required=True, help='Explicit serial device; close all other clients')
    parser.add_argument('--out', required=True, type=Path, help='New output directory; never overwrite')
    parser.add_argument('--expected-uuid', required=True,
                        help=f'Required 24-digit controller UUID (kart 3: {KART3_UUID})')
    args = parser.parse_args(argv)
    try:
        target = expected_uuid(args.expected_uuid)
    except ValueError as error:
        parser.error(str(error))
    result = backup(args.port, args.out, target)
    print(f'{result["status"]}: {result["validated_code_bytes"]} code bytes; '
          'autostart/running state unknown; only read commands 0 and 130 sent.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
