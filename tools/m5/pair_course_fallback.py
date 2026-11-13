#!/usr/bin/env python3
"""PROVISIONAL fallback for pair_course.py. Use it only if pair_course.py refuses at the bench.

Same job, same arguments and the same private plan file: provision separate course-only ESP-NOW
trust between a host Heltec and a player Core2. It never changes the kart-control pairing or a VESC.

Why it exists (observed on kart 3, 2026-11-12, macOS): opening a board's USB port with DTR/RTS
cleared reboots the board. pair_course.py opens that way, then asks each board once, immediately.
A Core2 that has just rebooted reports kart 0 and a hunting radio channel for several seconds, so
the original is expected to stop with a misleading message. This version differs in four ways:

  1. On macOS it opens the ports without touching DTR/RTS, which did not reboot either board.
  2. It listens for a boot banner and reports whether a board rebooted anyway.
  3. Read-only status requests are repeated until the boards answer and have settled: the Core2
     confirms its kart ID, both radios report the same channel, and that holds for two readings.
  4. Each pairing write is still sent exactly once, and only a reply marked as a pair result
     counts. A missing reply is reported as unknown, never retried.

--verify is read-only: after restarting both boards it confirms each lists the other as a peer.
Neither tool has been run against hardware in --apply mode; simulated-board tests only.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

now = time.monotonic                      # tests substitute a simulated clock

BOOT_BANNER = re.compile(r'rst:0x[0-9a-fA-F]+|ESP-ROM:')
PORT_TIMEOUT = 0.2
LISTEN_S = 1.5                            # after opening: watch for a boot banner
RESEND_S = 1.0                            # read-only requests only
READ_TIMEOUT_S = 6.0
WRITE_TIMEOUT_S = 6.0
STABLE_GAP_S = 2.0                        # two good readings at least this far apart


class Refused(RuntimeError):
    """A check failed before anything was written."""


def mac(value):
    value = value.lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', value) or int(value[:2], 16) & 1 or value == '00:00:00:00:00:00':
        raise argparse.ArgumentTypeError('expected unicast Wi-Fi station MAC')
    return value


def open_mode(requested, platform=None):
    if requested != 'auto':
        return requested
    return 'plain' if (platform or sys.platform) == 'darwin' else 'cleared'


def connect(name, mode):
    import serial
    if open_mode(mode) == 'plain':        # driver default line state; no reset seen on macOS
        return serial.Serial(name, 115200, timeout=PORT_TIMEOUT)
    p = serial.Serial(); p.port = name; p.baudrate = 115200; p.timeout = PORT_TIMEOUT
    p.dtr = False; p.rts = False; p.open()
    return p


def listen(port, seconds):
    """Drain console output for a while; True if a boot banner went past."""
    seen = False
    deadline = now() + seconds
    while now() < deadline:
        line = port.readline()
        if line and BOOT_BANNER.search(line.decode('utf-8', 'replace')):
            seen = True
    return seen


def read_json(port):
    line = port.readline()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (ValueError, UnicodeError):
        return None
    return obj if isinstance(obj, dict) else None


def query(port, command, kinds):
    """Read-only request. Repeated every second because a booting board drops its input."""
    port.reset_input_buffer()
    out = {}
    deadline = now() + READ_TIMEOUT_S
    resend = now()
    while now() < deadline:
        if now() >= resend:
            port.write((command + '\n').encode()); port.flush()
            resend = now() + RESEND_S
        obj = read_json(port)
        if obj and obj.get('t') in kinds and (obj['t'] != 'share' or obj.get('action') == 'status'):
            out[obj['t']] = obj
        if all(k in out for k in kinds):
            return out
    return None


def write_pair(port, peer_id, peer_mac, key):
    """One write, never repeated. True/False from the board, None if no pair reply arrived."""
    port.reset_input_buffer()
    port.write(f'share pair {peer_id} {peer_mac} {key}\n'.encode()); port.flush()
    deadline = now() + WRITE_TIMEOUT_S
    while now() < deadline:
        obj = read_json(port)
        if obj and obj.get('t') == 'share' and obj.get('action') == 'pair':
            return obj.get('ok') is True
    return None


def snapshot(core, host):
    c = query(core, 'share status', ('share_radio', 'share'))
    h = query(host, 'share status', ('share_radio', 'share'))
    hs = query(host, 'status', ('status',))
    cs = query(core, 'status', ('m5_status',))
    if not (c and h and hs and cs):
        return None
    return {
        'core_mac': c['share_radio'].get('mac'), 'core_channel': c['share_radio'].get('channel'),
        'core_publisher': c['share'].get('publisher'), 'core_configured': c['share'].get('configured') or [],
        'host_mac': h['share_radio'].get('mac'), 'host_channel': h['share_radio'].get('channel'),
        'host_publisher': h['share'].get('publisher'), 'host_configured': h['share'].get('configured') or [],
        'host_kart': hs['status'].get('kart'), 'core_kart': cs['m5_status'].get('kart'),
    }


def hard_fault(s, a):
    """Things that waiting cannot fix."""
    if s['core_mac'] != a.core2_mac or s['host_mac'] != a.host_mac:
        return 'Wrong board on a port (Wi-Fi MAC does not match the plan)'
    if s['core_publisher'] is not False or s['host_publisher'] is not True:
        return 'Wrong firmware role (host must be a publisher build, Core2 must not be)'
    if s['host_kart'] != a.host_id:
        return 'Host kart ID mismatch'
    if s['core_kart'] not in (0, None, a.kart_id):
        return f"Core2 is linked to kart {s['core_kart']}, not kart {a.kart_id}"
    return None


def still_waiting(s, a):
    """Things that are normal for a few seconds after a board reboots."""
    if s['core_kart'] != a.kart_id:
        return 'Core2 has not confirmed its kart ID (is its own Heltec powered and linked?)'
    if not s['core_channel'] or not s['host_channel']:
        return 'a radio channel is not reported yet'
    if s['core_channel'] != s['host_channel']:
        return f"Wi-Fi channels differ (Core2 {s['core_channel']}, host {s['host_channel']}); align the maintenance networks"
    return None


def settle(core, host, a, timeout):
    """Return a reading once every check has passed twice, STABLE_GAP_S apart, on one channel."""
    deadline = now() + timeout
    first_good = None
    why = 'no reading yet'
    while True:
        s = snapshot(core, host)
        if s is None:
            why = 'a board did not answer the course-firmware status request'
            first_good = None
        else:
            fault = hard_fault(s, a)
            if fault:
                raise Refused(fault + '; no pairing written')
            why = still_waiting(s, a)
            if why:
                first_good = None
            elif first_good and first_good[1] == s['core_channel'] and now() - first_good[0] >= STABLE_GAP_S:
                return s
            elif not first_good or first_good[1] != s['core_channel']:
                first_good = (now(), s['core_channel'])
        if now() >= deadline:
            raise Refused(f'Boards did not settle within {timeout:.0f} s: {why or "readings not yet stable"}; no pairing written')
        listen(core, 0.25); listen(host, 0.25)


def load_or_create_plan(a):
    """Identical file format and rules to pair_course.py, so either tool can use the other's plan."""
    expected = {'host_id': a.host_id, 'kart_id': a.kart_id, 'host_mac': a.host_mac, 'core2_mac': a.core2_mac}
    existing = a.plan.exists()
    if existing:
        if a.plan.stat().st_mode & 0o077:
            raise Refused('Private plan must have permissions 0600')
        plan = json.loads(a.plan.read_text())
        if any(plan.get(k) != v for k, v in expected.items()) or not re.fullmatch('[0-9a-f]{64}', plan.get('key', '')):
            raise Refused('Existing plan identity mismatch')
    else:
        plan = dict(expected, key=secrets.token_hex(32))
        a.plan.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(a.plan, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(plan, f, indent=2); f.write('\n')
    return plan, existing


def provision(core, host, a, plan, existing_plan):
    rebooted = {'core2': listen(core, LISTEN_S), 'host': listen(host, LISTEN_S)}
    s = settle(core, host, a, a.settle_timeout)
    if not existing_plan and (a.host_id in s['core_configured'] or a.kart_id in s['host_configured']):
        raise Refused('Course pairing exists; use its original private plan to preserve the key; no pairing written')
    written = []
    for name, port, peer_id, peer_mac in (('core2', core, a.host_id, a.host_mac), ('host', host, a.kart_id, a.core2_mac)):
        ok = write_pair(port, peer_id, peer_mac, plan['key'])
        if ok is not True:
            outcome = 'refused by the board' if ok is False else 'no reply, outcome unknown'
            raise RuntimeError(f"Pairing incomplete at {name} ({outcome}); written so far: {', '.join(written) or 'none'}; "
                               'private plan retained; inspect both boards before retrying')
        written.append(name)
    return {'paired_host': a.host_id, 'player': a.kart_id, 'restart_required': True, 'vehicle_pairing_unchanged': True,
            'channel': s['core_channel'], 'rebooted_on_connect': rebooted, 'tool': 'pair_course_fallback'}


def verify(core, host, a):
    """Read-only check for after the operator has restarted both boards."""
    rebooted = {'core2': listen(core, LISTEN_S), 'host': listen(host, LISTEN_S)}
    s = settle(core, host, a, a.settle_timeout)
    ok = a.host_id in s['core_configured'] and a.kart_id in s['host_configured']
    return {'verified': ok, 'core2_peers': s['core_configured'], 'host_peers': s['host_configured'],
            'channel': s['core_channel'], 'rebooted_on_connect': rebooted, 'nothing_written': True}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--host-id', required=True, type=int, choices=range(1, 9))
    p.add_argument('--kart-id', required=True, type=int, choices=range(1, 9))
    p.add_argument('--host-mac', required=True, type=mac)
    p.add_argument('--core2-mac', required=True, type=mac)
    p.add_argument('--plan', type=Path, help='private JSON file outside tracked files (e.g. firmware/build/bench-private/course-2-3.json)')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--verify', action='store_true', help='read-only: confirm both boards list each other after a restart')
    p.add_argument('--host-port'); p.add_argument('--core2-port')
    p.add_argument('--settle-timeout', type=float, default=45.0, help='seconds to wait for rebooted boards to settle')
    p.add_argument('--port-open', choices=('auto', 'plain', 'cleared'), default='auto',
                   help='plain leaves DTR/RTS alone (macOS default here); cleared is what pair_course.py does')
    a = p.parse_args(argv)
    if a.host_id == a.kart_id or a.host_mac == a.core2_mac:
        p.error('host and player must be distinct')
    if a.apply and a.verify:
        p.error('choose --apply or --verify')
    if (a.apply or a.verify) and (not a.host_port or not a.core2_port or a.host_port == a.core2_port):
        p.error('--apply and --verify require distinct explicit host/core2 USB ports')
    if not a.verify and not a.plan:
        p.error('--plan is required')
    try:
        if a.verify:
            with connect(a.core2_port, a.port_open) as core, connect(a.host_port, a.port_open) as host:
                result = verify(core, host, a)
            print(json.dumps(result))
            return 0 if result['verified'] else 1
        plan, existing = load_or_create_plan(a)
        if not a.apply:
            print(json.dumps({'plan': str(a.plan.resolve()), 'no_device_opened': True,
                              'next': 'rerun with --apply and explicit ports while stationary'}))
            return 0
        with connect(a.core2_port, a.port_open) as core, connect(a.host_port, a.port_open) as host:
            result = provision(core, host, a, plan, existing)
        print(json.dumps(dict(result, plan=str(a.plan.resolve()))))
        return 0
    except (Refused, RuntimeError) as error:
        print(json.dumps({'error': str(error), 'nothing_written': isinstance(error, Refused)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
