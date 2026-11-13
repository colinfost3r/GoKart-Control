#!/usr/bin/env python3
"""Fixed 35-second input/telemetry trace for kart 3. No motor/config/flash writes.

Operator must first confirm wheels lifted, pedals released, cutoff accessible,
Lisp ownership reviewed, and other USB/BLE clients quiet. A driver may operate the
wired controls during the trace. This tool only observes them. One fixed monitor
expression is sent; no expression argument, resend, reset or stop command exists.
"""
import argparse
import binascii
import datetime
import json
import os
from pathlib import Path
import re
import select
import time

import rx_probe as probe
from capture import query_frame, PacketParser
from decode import decode_telemetry

DURATION = 35.0
POLL_PERIOD = 0.1
REPLY_TIMEOUT = 1.0
MAX_BYTES = 256 * 1024


def frame_for(action):
    if action == 'identity': return query_frame(0)
    if action == 'values': return query_frame(4)
    if action == 'monitor': return probe.fixed_frame('monitor')
    raise ValueError('Only fixed identity, GET_VALUES and reviewed monitor are allowed')


def completion_seen(text):
    for line in text.splitlines():
        match = re.fullmatch(r'\(done ([0-9]+) ([0-9]+)\)', line.strip())
        if match and 0 <= int(match[1]) <= int(match[2]) and int(match[2]) > 0:
            return True
    return False


class Link:
    def __init__(self, fd, journal):
        self.fd, self.journal = fd, journal
        self.parser = PacketParser()  # Shared across every query and capture phase.
        self.bytes_seen = 0
        self.started = time.monotonic()
        self.last_values_print = -1.0

    def write_record(self, record):
        self.journal.write(json.dumps(record) + '\n')
        self.journal.flush()

    def send(self, action):
        frame = frame_for(action)
        self.write_record({'elapsed_s': time.monotonic()-self.started,
                           'direction': 'tx_attempt', 'action': action, 'frame_hex': frame.hex()})
        if os.write(self.fd, frame) != len(frame):
            raise IOError('Partial/uncertain send; aborting without retry or append')

    def receive(self, wait):
        ready, _, _ = select.select([self.fd], [], [], max(0.0, min(wait, 0.05)))
        if not ready: return []
        try: raw = os.read(self.fd, 4096)
        except BlockingIOError: return []
        if not raw: raise IOError('Serial port closed during trace')
        self.bytes_seen += len(raw)
        if self.bytes_seen > MAX_BYTES: raise IOError('Trace byte budget exceeded')
        packets = self.parser.feed(raw)
        for payload in packets:
            elapsed = time.monotonic()-self.started
            record = {'elapsed_s': elapsed, 'direction': 'rx', 'command': payload[0],
                      'payload_hex': payload.hex(), 'crc_verified': True}
            if payload[0] in (135, 138):
                record['text'] = payload[1:].rstrip(b'\0').decode('utf-8', errors='replace')
                print(record['text'], flush=True)
            elif payload[0] == 4:
                try: record['values'] = decode_telemetry(payload)
                except ValueError as error: record['decode_error'] = str(error)
                if 'values' in record and elapsed-self.last_values_print >= 1.0:
                    print('VALUES '+json.dumps({key: record['values'][key] for key in
                        ('motor_current_a', 'iq_a', 'duty', 'erpm', 'input_voltage_v', 'fault_code')}), flush=True)
                    self.last_values_print = elapsed
            self.write_record(record)
        return packets


def identity_query(link, clock=time.monotonic):
    link.send('identity')
    deadline = clock() + 3.0
    while clock() < deadline:
        for payload in link.receive(min(0.05, deadline-clock())):
            if payload[0] == 0:
                return probe.require_identity(payload, probe.UUID)
    raise TimeoutError('No identity response; no automatic resend')


def capture_loop(link, *, clock=time.monotonic, duration=DURATION):
    started = clock()
    deadline = started + duration
    next_poll = started
    pending_since = None
    values_count = 0
    monitor_text = []
    link.send('monitor')  # Exactly once; the only REPL expression this helper permits.
    while clock() < deadline:
        now = clock()
        if pending_since is not None and now-pending_since >= REPLY_TIMEOUT:
            raise TimeoutError('GET_VALUES timeout; no query or monitor resend')
        # Reserve a full reply timeout before the final capture deadline.
        if pending_since is None and now >= next_poll and deadline-now > REPLY_TIMEOUT + 0.05:
            link.send('values')
            pending_since = clock()
            next_poll = pending_since + POLL_PERIOD
        packets = link.receive(min(0.05, max(0.0, deadline-clock())))
        for payload in packets:
            if payload[0] == 4:
                if pending_since is None:
                    raise RuntimeError('Unexpected telemetry reply with no outstanding query; exclusive transport required')
                decode_telemetry(payload)  # Refuse malformed telemetry, retaining raw journal evidence.
                pending_since = None
                values_count += 1
            elif payload[0] in (135, 138):
                monitor_text.append(payload[1:].rstrip(b'\0').decode('utf-8', errors='replace'))
    if pending_since is not None:
        raise TimeoutError('Trace deadline with outstanding telemetry; no automatic resend')
    done = completion_seen('\n'.join(monitor_text))
    if not done: raise RuntimeError('Monitor completion not observed; do not automatically resend')
    if not values_count: raise RuntimeError('No validated GET_VALUES replies')
    return {'elapsed_s': clock()-started, 'telemetry_replies': values_count,
            'monitor_done_seen': done, 'monitor_text': monitor_text}


def run(port, output):
    # Verify the exact committed monitor hash before opening any hardware.
    frame_for('monitor')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'port': port, 'uuid_pin': probe.UUID, 'firmware_pin': '6.02',
                'allowed_command_ids': [0, 4, 138], 'monitor_sha256': probe.MONITOR_SHA256,
                'capture_seconds': DURATION, 'requested_telemetry_hz': 10,
                'max_outstanding_values_queries': 1, 'complete': False}
    try:
        with probe.SerialConnection(port) as connection, (output/'packets.jsonl').open('x') as journal:
            link = Link(connection.fd, journal)
            manifest['identity_before'] = identity_query(link)
            manifest['trace'] = capture_loop(link)
            manifest['identity_after'] = identity_query(link)
            manifest['bytes_received'] = link.bytes_seen
            manifest['complete'] = True
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.port, args.out)
    print(json.dumps({'complete': result['complete'], 'telemetry_replies': result['trace']['telemetry_replies']}, indent=2))


if __name__ == '__main__': main()
