"""R1～R4 回归：公平调度、覆盖语义、USB 独立、身份稳定。"""

from __future__ import annotations

import time
import unittest

from vigilwatt_py import ble_watcher
from vigilwatt_py.ble_watcher import BleReading, BleSensor, ScanResult, rotation_indices
from vigilwatt_py.poller import DONGLE_KEY, Collector
from vigilwatt_py.model import Device, Sample


class FakeBle:
    """替身：按脚本返回成功或失败，不碰真实蓝牙。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def read(self):
        value = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return value


class R1Tests(unittest.TestCase):
    def test_failure_writes_back_offline_snapshot(self) -> None:
        sensor = BleSensor("mouse", name_hint="ELECOM", default_name="蓝牙鼠标")
        sensor.last = Sample(level=100, charging=None, online=True, sampled_at=1000.0)
        failure = Sample(level=100, charging=None, online=False, error="读取失败", sampled_at=1000.0)
        sensor.probe = lambda: type("P", (), {"sample": failure, "error": "读取失败",
                                              "name": "ELECOM EX-G"})()
        sensor.read()
        device = sensor.device()
        self.assertFalse(device.sample.online)
        self.assertEqual(device.sample.level, 100)
        self.assertEqual(device.sample.sampled_at, 1000.0)


class RotationTests(unittest.TestCase):
    """R1：不是"只读前 8 台"，而是游标轮转，10 台多轮都能被调度。"""

    def test_cursor_rotation_eventually_covers_all_ten(self) -> None:
        seen = set()
        cursor = 0
        rounds = 0
        while len(seen) < 10 and rounds < 10:
            indices, cursor, remaining = rotation_indices(10, cursor, 8)
            seen.update(indices)
            rounds += 1
            if not remaining:
                break
        self.assertEqual(seen, set(range(10)))
        self.assertLessEqual(rounds, 3)

    def test_limit_not_below_one(self) -> None:
        indices, cursor, remaining = rotation_indices(3, 0, 0)
        self.assertEqual(len(indices), 1)
        self.assertTrue(remaining)


class CoverageTests(unittest.TestCase):
    """R2：失败/部分覆盖不得按"空列表"累计缺失，也不得新增历史。"""

    def setUp(self):
        self.collector = Collector(interval=60, low=20, bluetooth=True, mchose_enabled=False)

    def tearDown(self):
        self.collector.stop()

    def _reading(self, key, name="键盘", kind="keyboard", level=76):
        return BleReading(key=key, name=name, kind=kind, address="AA:BB", level=level,
                          online=True, error="", sampled_at=time.time())

    def _ok(self, *readings):
        return ScanResult(readings=list(readings), attempted={r.key for r in readings},
                          candidates=len(readings), complete=True)

    def test_scan_publishes_every_device(self):
        self.collector._apply_scan(self._ok(self._reading("ble:01"),
                                            self._reading("ble:02", "鼠标", "mouse")))
        keys = [d.key for d in self.collector.devices()]
        self.assertEqual(sorted(keys), ["ble:01", "ble:02"])

    def test_missing_once_keeps_online(self):
        self.collector._apply_scan(self._ok(self._reading("ble:01")))
        self.collector._apply_scan(self._ok())
        devices = self.collector.devices()
        self.assertTrue(devices[0].sample.online)

    def test_missing_twice_marks_offline(self):
        self.collector._apply_scan(self._ok(self._reading("ble:01")))
        self.collector._apply_scan(self._ok())
        self.collector._apply_scan(self._ok())
        devices = self.collector.devices()
        self.assertFalse(devices[0].sample.online)
        self.assertIsNone(devices[0].sample.level)

    def test_reappearing_device_recovers(self):
        self.collector._apply_scan(self._ok(self._reading("ble:01")))
        self.collector._apply_scan(self._ok())
        self.collector._apply_scan(self._ok())
        self.collector._apply_scan(self._ok(self._reading("ble:01")))
        self.assertTrue(self.collector.devices()[0].sample.online)

    def test_partial_coverage_marks_unconfirmed_not_offline(self):
        self.collector._apply_scan(self._ok(self._reading("ble:01")))
        partial = ScanResult(readings=[], attempted=set(), candidates=3,
                             complete=False, error="预算耗尽")
        self.collector._apply_scan(partial)
        self.collector._apply_scan(partial)
        device = self.collector.devices()[0]
        self.assertTrue(device.sample.online)
        self.assertFalse(device.sample.confirmed)

    def test_scan_error_marks_unconfirmed_not_offline(self):
        self.collector._apply_scan(self._ok(self._reading("ble:01")))
        failed = ScanResult(complete=False, error="枚举失败：超时")
        self.collector._apply_scan(failed)
        self.collector._apply_scan(failed)
        device = self.collector.devices()[0]
        self.assertTrue(device.sample.online)
        self.assertFalse(device.sample.confirmed)

    def test_dongle_key_present_when_keyboard_missing(self):
        self.collector._apply_scan(self._ok())
        keys = {d.key for d in self.collector.devices()}
        self.assertTrue(set(keys) <= {DONGLE_KEY})


class DongleIndependenceTests(unittest.TestCase):
    """R3：蓝牙鼠标在线时，USB 键盘仍要被查询。"""

    def test_dongle_polled_even_when_ble_online(self) -> None:
        from vigilwatt_py import poller as poller_module

        class FakeSensor:
            def __init__(self):
                self.reads = 0

            def read(self):
                self.reads += 1
                return Sample(level=88, charging=None, online=True, sampled_at=time.time())

            def device(self):
                return Device(key=DONGLE_KEY, name="2.4G 键盘", kind="keyboard",
                              connection="usb", source="compx-receiver",
                              sample=Sample(level=88, charging=None, online=True,
                                            sampled_at=time.time()))

        collector = Collector(interval=60, low=20, bluetooth=True, mchose_enabled=False)
        sensor = FakeSensor()
        collector._dongle = sensor
        collector._snapshots["ble:mouse"] = Device(
            key="ble:mouse", name="蓝牙鼠标", kind="mouse", connection="ble", source="windows-ble",
            sample=Sample(level=64, charging=None, online=True, sampled_at=time.time()))
        collector._poll_dongle_once()
        self.assertEqual(sensor.reads, 1)
        self.assertIn(DONGLE_KEY, {d.key for d in collector.devices()})
        self.assertTrue(poller_module.Collector)


class IdentityTests(unittest.TestCase):
    """R4：优先地址；回退用完整系统 ID 哈希，不按名字合并。"""

    def test_address_wins(self) -> None:
        key = ble_watcher._identity("AA:BB:CC:DD:EE:FF", "id-1", "键盘")
        self.assertEqual(key, "aabbccddeeff")

    def test_same_suffix_ids_differ(self) -> None:
        first = ble_watcher._identity(None, "path/device/000000000001", "键盘")
        second = ble_watcher._identity(None, "path/device/000000000002", "键盘")
        self.assertNotEqual(first, second)

    def test_same_name_different_id_differ(self) -> None:
        first = ble_watcher._identity(None, "device-1", "同名键盘")
        second = ble_watcher._identity(None, "device-2", "同名键盘")
        self.assertNotEqual(first, second)

    def test_fallback_is_full_hash_not_truncated_id(self) -> None:
        key = ble_watcher._identity(None, "device-abcdef", "键盘")
        self.assertTrue(key.startswith("id-"))
        self.assertEqual(len(key), 3 + 64)


if __name__ == "__main__":
    unittest.main()
