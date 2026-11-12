"""Simulated-board tests for tools/m5/pair_course_fallback.py. No serial port or pyserial is used.

The fake boards model what was captured on kart 3 on 2026-11-12: a board that reboots when its
port is opened drops console input while booting, a rebooted Core2 reports kart 0 until it
re-links to its own Heltec, and its radio channel hunts before settling.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools/m5/pair_course_fallback.py'
ORIGINAL = ROOT / 'tools/m5/pair_course.py'
HOST_MAC, CORE_MAC, KEY = '02:11:22:33:44:55', '02:66:77:88:99:aa', 'ab' * 32


def load_tool(clock):
    spec = importlib.util.spec_from_file_location('pair_course_fallback', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.now = clock.now
    return module


class Clock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t


class Board:
    """role 'host' or 'core2'. Times are seconds after the port was opened."""

    def __init__(self, clock, role, mac, kart, *, boot=0.0, link_at=0.0, channels=((0.0, 6),), configured=(),
                 publisher=None, pair='ok', pair_delay=0.05, late_status=0.0, share=True):
        self.clock, self.role, self.mac, self.kart = clock, role, mac, kart
        self.t0, self.boot, self.link_at, self.channels = clock.t, boot, link_at, channels
        self.configured, self.pair, self.pair_delay = list(configured), pair, pair_delay
        self.publisher = (role == 'host') if publisher is None else publisher
        self.late_status, self.share = late_status, share
        self.out, self.commands, self.pairs = [], [], []
        self.raw(b'not json at all\r\n')
        self.emit({'t': 'self', 'kart': kart, 'vesc_link': False})
        if boot:
            self.raw(b'ESP-ROM:esp32s3-20210327\r\n' if role == 'host' else b'ets Jul 29 2019 12:21:46\r\n')
            self.raw(b'rst:0x15 (USB_UART_CHIP_RESET),boot:0x29 (SPI_FAST_FLASH_BOOT)\r\n' if role == 'host'
                     else b'rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\r\n')

    def age(self):
        return self.clock.t - self.t0

    def raw(self, data, delay=0.0):
        self.out.append((self.clock.t + delay, data))

    def emit(self, obj, delay=0.0):
        self.raw((json.dumps(obj) + '\n').encode(), delay)

    def channel(self):
        current = 0
        for start, value in self.channels:
            if self.age() >= start:
                current = value
        return current

    def command(self, text):
        self.commands.append((self.age(), text))
        if self.age() < self.boot:
            return                                         # still booting: input is lost
        if text == 'share status':
            if not self.share:
                return self.emit({'t': 'log', 'msg': 'unknown command'})
            status = {'t': 'share', 'action': 'status', 'ready': False, 'publisher': self.publisher, 'bytes': 0,
                      'host': 0, 'progress': 0, 'configured': sorted(self.configured)}
            self.emit({'t': 'share_radio', 'mac': self.mac, 'channel': self.channel()})
            self.emit(status)
            if self.late_status:
                self.emit(status, self.late_status)        # a repeated request answered late
        elif text == 'status':
            if self.role == 'host':
                self.emit({'t': 'status', 'kart': self.kart, 'fw': 'kart-0.3.3'})
            else:
                linked = self.age() >= self.link_at
                self.emit({'t': 'm5_status', 'kart': self.kart if linked else 0, 'live': linked})
        elif text.startswith('share pair '):
            self.pairs.append((self.age(), text))
            if self.pair != 'silent':
                self.emit({'t': 'share', 'action': 'pair', 'ok': self.pair == 'ok', 'restart_required': True}, self.pair_delay)


class Port:
    timeout = 0.2

    def __init__(self, board):
        self.board = board

    def reset_input_buffer(self):
        self.board.out = [item for item in self.board.out if item[0] > self.board.clock.t]

    def write(self, data):
        for line in data.decode().split('\n'):
            if line:
                self.board.command(line)

    def flush(self):
        pass

    def readline(self):
        due = sorted((item for item in self.board.out if item[0] <= self.board.clock.t), key=lambda item: item[0])
        if due:
            self.board.out.remove(due[0])
            return due[0][1]
        self.board.clock.t += self.timeout
        return b''


def args(**changes):
    values = dict(host_id=2, kart_id=3, host_mac=HOST_MAC, core2_mac=CORE_MAC, settle_timeout=45.0)
    values.update(changes)
    return argparse.Namespace(**values)


class FallbackPairingTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.tool = load_tool(self.clock)
        self.plan = {'host_id': 2, 'kart_id': 3, 'host_mac': HOST_MAC, 'core2_mac': CORE_MAC, 'key': KEY}

    def boards(self, core=None, host=None):
        self.core = Board(self.clock, 'core2', CORE_MAC, 3, **(core or {}))
        self.host = Board(self.clock, 'host', HOST_MAC, 2, **(host or {}))
        return Port(self.core), Port(self.host)

    def run_provision(self, core=None, host=None, existing_plan=False, **changes):
        core_port, host_port = self.boards(core, host)
        return self.tool.provision(core_port, host_port, args(**changes), self.plan, existing_plan)

    def assert_nothing_written(self):
        self.assertEqual(self.core.pairs, [])
        self.assertEqual(self.host.pairs, [])

    def test_settled_boards_are_paired_with_one_write_each(self):
        start = self.clock.t
        result = self.run_provision()
        self.assertEqual([text for _, text in self.core.pairs], [f'share pair 2 {HOST_MAC} {KEY}'])
        self.assertEqual([text for _, text in self.host.pairs], [f'share pair 3 {CORE_MAC} {KEY}'])
        self.assertLess(self.core.pairs[0][0], self.host.pairs[0][0])          # Core2 first, as in the original
        self.assertEqual(result['rebooted_on_connect'], {'core2': False, 'host': False})
        self.assertEqual((result['paired_host'], result['player'], result['channel']), (2, 3, 6))
        self.assertTrue(result['restart_required'] and result['vehicle_pairing_unchanged'])
        self.assertNotIn(KEY, json.dumps(result))
        self.assertLess(self.clock.t - start, 15)

    def test_boards_that_reboot_on_connect_are_waited_for_then_paired(self):
        # Core2: input lost for 5 s, kart 0 until it re-links at 9 s, channel 1 before settling on 6.
        result = self.run_provision(core=dict(boot=5.0, link_at=9.0, channels=((0.0, 0), (5.0, 1), (8.0, 6))),
                                    host=dict(boot=4.5))
        self.assertEqual(result['rebooted_on_connect'], {'core2': True, 'host': True})
        self.assertEqual(len(self.core.pairs), 1)
        self.assertEqual(len(self.host.pairs), 1)
        self.assertGreaterEqual(self.core.pairs[0][0], 9.0 + self.tool.STABLE_GAP_S)
        lost = [text for age, text in self.core.commands if age < 4.9] + [text for age, text in self.host.commands if age < 4.4]
        self.assertTrue(lost)                                                   # requests really were dropped
        self.assertTrue(all(text in ('share status', 'status') for text in lost))   # and only read-only ones

    def test_core2_that_never_confirms_its_kart_is_refused_without_writing(self):
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(core=dict(boot=3.0, link_at=1e9), settle_timeout=12.0)
        self.assertIn('kart ID', str(caught.exception))
        self.assertIn('no pairing written', str(caught.exception))
        self.assert_nothing_written()

    def test_channels_that_never_align_are_refused_without_writing(self):
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(core=dict(channels=((0.0, 2),)), settle_timeout=8.0)
        self.assertIn('channels differ (Core2 2, host 6)', str(caught.exception))
        self.assert_nothing_written()

    def test_a_channel_that_changes_between_readings_restarts_the_wait(self):
        # Both radios agree on 1 for long enough to be nearly accepted, then both move to 6 at 5 s
        # (readings fall at about 3.0, 3.8, 4.6 and 5.4 s). The wait must start again for channel 6.
        moving = ((0.0, 1), (5.0, 6))
        result = self.run_provision(core=dict(channels=moving), host=dict(channels=moving))
        self.assertEqual(result['channel'], 6)
        self.assertGreaterEqual(self.core.pairs[0][0], 5.0 + self.tool.STABLE_GAP_S)

    def test_wrong_board_is_refused_at_once(self):
        start = self.clock.t
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(host=dict(boot=0.0), core=dict(boot=0.0), host_mac='02:00:00:00:00:01')
        self.assertIn('MAC', str(caught.exception))
        self.assertLess(self.clock.t - start, 5)
        self.assert_nothing_written()

    def test_wrong_firmware_role_is_refused(self):
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(host=dict(publisher=False))
        self.assertIn('role', str(caught.exception))
        self.assert_nothing_written()

    def test_host_kart_id_mismatch_is_refused(self):
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(host_id=1)
        self.assertIn('Host kart ID mismatch', str(caught.exception))
        self.assert_nothing_written()

    def test_core2_linked_to_another_kart_is_refused_at_once(self):
        start = self.clock.t
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(kart_id=4)
        self.assertIn('linked to kart 3, not kart 4', str(caught.exception))
        self.assertLess(self.clock.t - start, 5)
        self.assert_nothing_written()

    def test_existing_pairing_needs_its_original_plan(self):
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(core=dict(configured=[2]))
        self.assertIn('original private plan', str(caught.exception))
        self.assert_nothing_written()
        self.run_provision(core=dict(configured=[2]), existing_plan=True)       # same plan: re-applying is allowed
        self.assertEqual(len(self.core.pairs), 1)

    def test_late_status_line_is_not_mistaken_for_the_pair_result(self):
        # A status answer still in flight arrives before the slower pair reply.
        result = self.run_provision(core=dict(late_status=0.3, pair_delay=0.9))
        self.assertEqual(result['player'], 3)
        self.assertEqual(len(self.core.pairs), 1)
        self.assertEqual(len(self.host.pairs), 1)

    def test_refusal_on_second_board_reports_what_was_written(self):
        with self.assertRaises(RuntimeError) as caught:
            self.run_provision(host=dict(pair='refuse'))
        self.assertNotIsInstance(caught.exception, self.tool.Refused)
        self.assertIn('Pairing incomplete at host (refused by the board); written so far: core2', str(caught.exception))
        self.assertEqual((len(self.core.pairs), len(self.host.pairs)), (1, 1))

    def test_unanswered_write_is_reported_unknown_and_never_repeated(self):
        with self.assertRaises(RuntimeError) as caught:
            self.run_provision(core=dict(pair='silent'))
        self.assertIn('Pairing incomplete at core2 (no reply, outcome unknown); written so far: none', str(caught.exception))
        self.assertEqual(len(self.core.pairs), 1)
        self.assertEqual(self.host.pairs, [])

    def test_firmware_without_the_course_service_is_refused(self):
        with self.assertRaises(self.tool.Refused) as caught:
            self.run_provision(host=dict(share=False), settle_timeout=10.0)
        self.assertIn('did not answer', str(caught.exception))
        self.assert_nothing_written()

    def test_verify_is_read_only(self):
        core_port, host_port = self.boards(core=dict(configured=[2]), host=dict(configured=[3]))
        result = self.tool.verify(core_port, host_port, args())
        self.assertTrue(result['verified'] and result['nothing_written'])
        self.assert_nothing_written()
        core_port, host_port = self.boards(core=dict(configured=[2]))
        self.assertFalse(self.tool.verify(core_port, host_port, args())['verified'])
        self.assert_nothing_written()

    def test_port_open_mode(self):
        self.assertEqual(self.tool.open_mode('auto', 'darwin'), 'plain')
        self.assertEqual(self.tool.open_mode('auto', 'linux'), 'cleared')
        self.assertEqual(self.tool.open_mode('cleared', 'darwin'), 'cleared')

    def test_plan_files_are_interchangeable_with_the_original(self):
        common = ['--host-id', '2', '--kart-id', '3', '--host-mac', HOST_MAC, '--core2-mac', CORE_MAC]
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'from-original.json', Path(tmp) / 'from-fallback.json'
            for tool, plan in ((ORIGINAL, first), (TOOL, second)):
                made = subprocess.run([sys.executable, '-I', str(tool), *common, '--plan', str(plan)],
                                      capture_output=True, text=True, check=True)
                self.assertTrue(json.loads(made.stdout)['no_device_opened'])
                self.assertEqual(plan.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(json.loads(plan.read_text())['key'], made.stdout)
            self.assertEqual(set(json.loads(first.read_text())), set(json.loads(second.read_text())))
            for tool, plan in ((TOOL, first), (ORIGINAL, second)):             # each accepts the other's plan
                subprocess.run([sys.executable, '-I', str(tool), *common, '--plan', str(plan)],
                               capture_output=True, text=True, check=True)
            refused = subprocess.run([sys.executable, '-I', str(TOOL), '--host-id', '2', '--kart-id', '4', '--host-mac', HOST_MAC,
                                      '--core2-mac', CORE_MAC, '--plan', str(first)], capture_output=True, text=True)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('identity mismatch', refused.stderr)


class OriginalToolBehaviourTests(unittest.TestCase):
    """Records, against the same simulated boards, why the fallback exists."""

    def test_original_request_is_lost_while_a_board_boots(self):
        spec = importlib.util.spec_from_file_location('pair_course', ORIGINAL)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        clock = Clock()
        saved = original.time.monotonic
        original.time.monotonic = clock.now
        try:
            booting = Board(clock, 'core2', CORE_MAC, 3, boot=3.0)
            with self.assertRaises(RuntimeError) as caught:
                original.exchange(Port(booting), 'share status', ('share_radio', 'share'))
            self.assertIn('not received', str(caught.exception))
            self.assertEqual([text for _, text in booting.commands], ['share status'])   # asked once, never again
        finally:
            original.time.monotonic = saved


if __name__ == '__main__':
    unittest.main()
