import sys
import types
import unittest

from vigilwatt_py import mchose_plugin, protocol_mchose as proto


def build(payload: bytes) -> bytes:
    body = bytearray(20)
    body[: len(payload)] = payload
    body[19] = sum(body[:19]) & 0xFF
    return bytes(body)


ACK_G75 = build(bytes([0x13, 0x05, 0x01, 0x00, 0x0A, 0x03, 0x00, 0x00, 0x00, 0x01, 0x15, 0x01]))
ACK_OTHER = build(bytes([0x13, 0x05, 0x01, 0x00, 0x0A, 0x03, 0x00, 0x00, 0x00, 0x02, 0x1C, 0x01]))
BATTERY_36 = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x24, 0x01]))
BATTERY_ZERO = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x00, 0x01]))

ENTRY = {"vendor_id": 0x3554, "product_id": 0xFA09, "usage_page": 0xFF02,
         "usage": 0x0002, "path": b"fake-path", "product_string": "2.4G Receiver"}
OTHER_ENTRY = {"vendor_id": 0x3554, "product_id": 0xFA09, "usage_page": 0xFF04,
               "usage": 0x0002, "path": b"other", "product_string": "2.4G Receiver"}


class FakeDevice:
    def __init__(self, replies):
        self.replies = list(replies)
        self.writes = []
        self.closed = False

    def open_path(self, path):
        self.path = path

    def set_nonblocking(self, value):
        self.nonblocking = value

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def read(self, size, timeout_ms):
        if not self.replies:
            return []
        return list(self.replies.pop(0))

    def close(self):
        self.closed = True


class FakeHid(types.ModuleType):
    def __init__(self, entries, device):
        super().__init__("hid")
        self.entries = entries
        self.device_obj = device
        self.enumerate_calls = 0

    def enumerate(self, vid=0, pid=0):
        self.enumerate_calls += 1
        return list(self.entries)

    def device(self):
        return self.device_obj


class PluginTests(unittest.TestCase):
    def install(self, entries, replies):
        device = FakeDevice(replies)
        module = FakeHid(entries, device)
        self._previous = sys.modules.get("hid")
        sys.modules["hid"] = module
        return device, module

    def tearDown(self):
        if self._previous is None:
            sys.modules.pop("hid", None)
        else:
            sys.modules["hid"] = self._previous

    def test_probe_reads_g75_pro(self):
        device, _ = self.install([ENTRY, OTHER_ENTRY], [ACK_G75, BATTERY_36])
        probe = mchose_plugin.KeyboardSensor().probe()
        self.assertTrue(probe.found)
        self.assertEqual(probe.model, "G75 Pro")
        self.assertEqual(probe.sample.level, 36)
        self.assertFalse(probe.sample.charging)
        self.assertEqual(device.writes[0], proto.session_frame())
        self.assertEqual(device.writes[1], proto.battery_frame())
        self.assertTrue(device.closed)

    def test_shared_fingerprint_with_other_model_is_not_claimed(self):
        self.install([ENTRY], [ACK_OTHER])
        probe = mchose_plugin.KeyboardSensor().probe()
        self.assertTrue(probe.found)
        self.assertEqual(probe.model, "G87")
        self.assertIsNone(probe.sample.level)
        self.assertIn("不在本阶段支持范围", probe.error)

    def test_missing_interface_is_reported(self):
        self.install([OTHER_ENTRY], [])
        probe = mchose_plugin.KeyboardSensor().probe()
        self.assertFalse(probe.found)
        self.assertIn("FF02", probe.error)

    def test_zero_percent_is_filtered_but_raw_kept(self):
        self.install([ENTRY], [ACK_G75, BATTERY_ZERO])
        probe = mchose_plugin.KeyboardSensor().probe()
        self.assertIsNone(probe.sample.level)
        self.assertEqual(probe.sample.raw_level, 0)
        self.assertIn("原始 0%", probe.sample.error)

    def test_disabled_sensor_does_not_touch_hid(self):
        device, module = self.install([ENTRY], [])
        probe = mchose_plugin.KeyboardSensor(enabled=False).probe()
        self.assertEqual(probe.error, "插件已关闭")
        self.assertEqual(module.enumerate_calls, 0)

    def test_repeated_failures_enter_backoff(self):
        self.install([], [])
        sensor = mchose_plugin.KeyboardSensor()
        for _ in range(3):
            sensor.read()
        self.assertGreater(sensor.backoff_until, 0.0)
        self.assertEqual(sensor.backoff_index, 1)

    def test_stale_sample_keeps_last_level(self):
        self.install([ENTRY], [ACK_G75, BATTERY_36])
        sensor = mchose_plugin.KeyboardSensor()
        self.assertEqual(sensor.read().level, 36)
        self.install([], [])
        stale = sensor.read()
        self.assertEqual(stale.level, 36)
        self.assertFalse(stale.online)


if __name__ == "__main__":
    unittest.main()
