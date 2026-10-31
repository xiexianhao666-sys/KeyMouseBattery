"""低电量提醒：只在在线有效读数跨阈值时提醒，按设备去重并在回升后重新武装。"""

from __future__ import annotations

import unittest

from keymousebattery import alerts
from keymousebattery.model import Device, Sample

NOW = 1_000_000.0


def device(key: str, level, online: bool = True, stale: bool = False, kind: str = "mouse") -> Device:
    return Device(key=key, name=key, kind=kind, connection="ble", source="windows-ble",
                  sample=Sample(level=level, charging=None, online=online, sampled_at=NOW),
                  stale=stale)


class AlertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.alerts = alerts.Alerts()

    def test_threshold_crossing_alerts_once(self) -> None:
        first = self.alerts.check([device("mouse", 15)], 20, NOW)
        second = self.alerts.check([device("mouse", 14)], 20, NOW + 60)
        self.assertEqual([a.key for a in first], ["mouse"])
        self.assertEqual(second, [])

    def test_rearms_after_margin(self) -> None:
        self.alerts.check([device("mouse", 15)], 20, NOW)
        self.assertEqual(self.alerts.check([device("mouse", 25)], 20, NOW + 60), [])
        again = self.alerts.check([device("mouse", 19)], 20, NOW + 120)
        self.assertEqual([a.key for a in again], ["mouse"])

    def test_offline_and_stale_do_not_alert(self) -> None:
        self.assertEqual(self.alerts.check([device("mouse", 5, online=False)], 20, NOW), [])
        self.assertEqual(self.alerts.check([device("mouse", 5, stale=True)], 20, NOW), [])

    def test_unknown_level_does_not_alert(self) -> None:
        self.assertEqual(self.alerts.check([device("mouse", None)], 20, NOW), [])

    def test_threshold_zero_is_silent(self) -> None:
        self.assertEqual(self.alerts.check([device("mouse", 3)], 0, NOW), [])

    def test_startup_already_low_alerts_once(self) -> None:
        first = self.alerts.check([device("keyboard", 8), device("mouse", 9)], 20, NOW)
        self.assertEqual(sorted(a.key for a in first), ["keyboard", "mouse"])
        self.assertEqual(self.alerts.check([device("keyboard", 8), device("mouse", 9)], 20, NOW + 5), [])

    def test_device_disappearing_then_returning(self) -> None:
        self.alerts.check([device("mouse", 10)], 20, NOW)
        self.alerts.check([], 20, NOW + 30)
        self.assertEqual([a.key for a in self.alerts.check([device("mouse", 10)], 20, NOW + 60)], ["mouse"])

    def test_message_text_mentions_threshold(self) -> None:
        messages = self.alerts.check([device("mouse", 12)], 20, NOW)
        self.assertIn("12%", messages[0].text)
        self.assertIn("mouse", messages[0].text)


if __name__ == "__main__":
    unittest.main()
