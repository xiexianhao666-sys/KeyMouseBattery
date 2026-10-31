"""手动刷新状态机与接收器“在但读不到”的回归用例。

两个用户现场问题：
1. 点“立即刷新”后按钮一直停在“刷新中…”。
2. 插上 2.4G 接收器后刷新，列表里没有这张卡。
"""

from __future__ import annotations

import time
import unittest

from keymousebattery import app as app_module
from keymousebattery.mchose_plugin import KeyboardSensor
from keymousebattery.model import Device, Sample
from keymousebattery.poller import DONGLE_KEY, Collector, merge_usb_channels


class FakeCollector:
    def __init__(self, attempts=None):
        self.refreshed = 0
        self._attempts = attempts or {}

    def refresh_now(self):
        self.refreshed += 1

    def attempts(self):
        return dict(self._attempts)


class FakeWindow:
    def __init__(self):
        self.begin = 0
        self.ends = []

    def begin_refresh(self):
        self.begin += 1

    def end_refresh(self, ok=True, message=""):
        self.ends.append((ok, message))


def make_app(collector, window):
    app = app_module.App.__new__(app_module.App)
    app.collector = collector
    app.window = window
    app._refresh_from = 0.0
    return app


class RefreshStateTests(unittest.TestCase):
    def test_request_refresh_records_start_time(self) -> None:
        app = make_app(FakeCollector(), FakeWindow())
        app.request_refresh()
        self.assertEqual(app.collector.refreshed, 1)
        self.assertGreater(app._refresh_from, 0.0)
        self.assertEqual(app.window.begin, 1)

    def test_new_attempt_ends_refresh(self) -> None:
        collector = FakeCollector()
        window = FakeWindow()
        app = make_app(collector, window)
        app.request_refresh()
        started = app._refresh_from
        collector._attempts = {DONGLE_KEY: started + 1.0}
        app._settle_refresh()
        self.assertEqual(window.ends, [(True, "")])
        self.assertEqual(app._refresh_from, 0.0)

    def test_stale_attempt_keeps_waiting(self) -> None:
        collector = FakeCollector()
        window = FakeWindow()
        app = make_app(collector, window)
        app.request_refresh()
        collector._attempts = {DONGLE_KEY: app._refresh_from - 5.0}
        app._settle_refresh()
        self.assertEqual(window.ends, [])

    def test_timeout_restores_button(self) -> None:
        app = make_app(FakeCollector(), FakeWindow())
        app.request_refresh()
        app._refresh_from = time.time() - app_module.REFRESH_FEEDBACK_SECONDS - 1.0
        app._settle_refresh()
        self.assertEqual(app.window.ends, [(False, "")])

    def test_settle_without_refresh_does_nothing(self) -> None:
        app = make_app(FakeCollector(), FakeWindow())
        app._settle_refresh()
        self.assertEqual(app.window.ends, [])


class FakeDongle:
    def __init__(self, sample: Sample, name: str = "迈从 G75 Pro"):
        self.sample = sample
        self.name = name

    def read(self):
        return self.sample

    def device(self):
        return Device(key=DONGLE_KEY, name=self.name, kind="keyboard",
                      connection="usb", source="mchose-v1", sample=self.sample)


def collector_with(dongle):
    collector = Collector(mchose_enabled=False)
    collector._dongle = dongle
    return collector


class DongleVisibilityTests(unittest.TestCase):
    def test_unreadable_receiver_still_publishes_a_card(self) -> None:
        sample = Sample(level=None, charging=None, online=True,
                        error="接收器已连接，读不到电量")
        collector = collector_with(FakeDongle(sample))
        collector._poll_dongle_once()
        devices = {item.key: item for item in collector.devices()}
        self.assertIn(DONGLE_KEY, devices)
        self.assertTrue(devices[DONGLE_KEY].sample.online)
        self.assertIsNone(devices[DONGLE_KEY].sample.level)
        self.assertEqual(devices[DONGLE_KEY].connection, "usb")

    def test_unplugged_receiver_goes_offline(self) -> None:
        sample = Sample(level=None, charging=None, online=False, error="未找到目标接口（FF02:0002）")
        collector = collector_with(FakeDongle(sample))
        collector._poll_dongle_once()
        device = collector.devices()[0]
        self.assertFalse(device.sample.online)

    def test_card_survives_merge_when_no_ble_keyboard(self) -> None:
        sample = Sample(level=None, charging=None, online=True, error="查询无应答")
        collector = collector_with(FakeDongle(sample))
        collector._poll_dongle_once()
        mouse = Device(key="ble:mouse", name="ELECOM EX-G", kind="mouse",
                       connection="ble", source="windows-ble",
                       sample=Sample(level=86, online=True))
        kept = merge_usb_channels(list(collector.devices()) + [mouse])
        self.assertEqual({item.key for item in kept}, {DONGLE_KEY, "ble:mouse"})


class SensorDetectedTests(unittest.TestCase):
    def _sensor(self, found: bool, error: str) -> KeyboardSensor:
        sensor = KeyboardSensor()
        sensor.probe = lambda: type("P", (), {
            "found": found, "sample": Sample(), "error": error,
        })()
        return sensor

    def test_detected_but_unreadable_is_online_without_level(self) -> None:
        sensor = self._sensor(True, "查询无应答")
        sample = sensor.read()
        self.assertTrue(sample.online)
        self.assertIsNone(sample.level)
        self.assertIn("查询无应答", sample.error)

    def test_device_view_matches_last_read(self) -> None:
        # 现场问题：read() 的结果没有回写 self.last，UI 拿到的是空样本 → 卡片消失。
        sensor = self._sensor(True, "接收器已连接，读不到电量")
        sensor.read()
        device = sensor.device()
        self.assertTrue(device.sample.online)
        self.assertIsNone(device.sample.level)
        self.assertIn("接收器已连接", device.sample.error)

    def test_absent_receiver_device_view_is_offline(self) -> None:
        sensor = self._sensor(False, "未找到目标接口（FF02:0002）")
        sensor.read()
        device = sensor.device()
        self.assertFalse(device.sample.online)
        self.assertIn("未找到目标接口", device.sample.error)

    def test_backoff_keeps_card_when_detected(self) -> None:
        sensor = self._sensor(True, "查询无应答")
        sensor.read()
        sensor.backoff_until = time.monotonic() + 30.0
        sample = sensor.read()
        self.assertTrue(sample.online)
        self.assertIn("退避中", sample.error)


if __name__ == "__main__":
    unittest.main()
