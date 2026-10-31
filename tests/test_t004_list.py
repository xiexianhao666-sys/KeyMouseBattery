"""T004：动态设备列表与托盘（空态、排序、断连下移、重连置顶、托盘只留在线）。"""

from __future__ import annotations

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vigilwatt_py.model import Device, Sample  # noqa: E402
from vigilwatt_py.tray import IDLE_KEY, TrayIcons  # noqa: E402
from vigilwatt_py.ui import DeviceListPanel  # noqa: E402

APP = QApplication.instance() or QApplication([])


def device(key: str, name: str, kind: str = "keyboard", online: bool = True,
           level: int | None = 76, order: int = 0, last_connected: float | None = None,
           stale: bool = False) -> Device:
    return Device(key=key, name=name, kind=kind, connection="ble", source="windows-ble",
                  order=order, last_connected=last_connected, stale=stale,
                  sample=Sample(level=level, charging=None, online=online, sampled_at=0.0))


class ListTests(unittest.TestCase):
    def setUp(self):
        self.panel = DeviceListPanel()
        self.panel.resize(560, 500)

    def tearDown(self):
        self.panel.deleteLater()

    def test_empty_list_shows_hint(self):
        self.panel.render([], 20, time.time())
        self.assertEqual(self.panel.pages.currentIndex(), 0)
        self.assertEqual(self.panel.card_order(), [])

    def test_devices_appear_dynamically(self):
        devices = [device("ble:0%d" % i, "键盘%d" % i, order=i) for i in range(1, 6)]
        self.panel.render(devices, 20, time.time())
        self.assertEqual(self.panel.pages.currentIndex(), 1)
        self.assertEqual(len(self.panel.card_order()), 5)

    def test_online_sorted_before_offline(self):
        devices = [
            device("ble:01", "旧键盘", order=1),
            device("ble:02", "新键盘", order=3),
            device("ble:03", "鼠标", "mouse", order=2),
            device("ble:04", "离线键盘", online=False, level=None, order=9),
        ]
        self.panel.render(devices, 20, time.time())
        self.assertEqual(self.panel.card_order(), ["ble:02", "ble:03", "ble:01", "ble:04"])

    def test_disconnect_moves_card_below_online(self):
        self.panel.render([device("ble:01", "A", order=2), device("ble:02", "B", order=1)],
                          20, time.time())
        self.assertEqual(self.panel.card_order(), ["ble:01", "ble:02"])
        self.panel.render([device("ble:01", "A", online=False, level=None, order=2),
                           device("ble:02", "B", order=1)], 20, time.time())
        self.assertEqual(self.panel.card_order(), ["ble:02", "ble:01"])

    def test_reconnect_returns_to_top(self):
        self.panel.render([device("ble:01", "A", order=2), device("ble:02", "B", order=1)],
                          20, time.time())
        self.panel.render([device("ble:01", "A", online=False, level=None, order=2),
                           device("ble:02", "B", order=1)], 20, time.time())
        self.panel.render([device("ble:01", "A", order=3), device("ble:02", "B", order=1)],
                          20, time.time())
        self.assertEqual(self.panel.card_order(), ["ble:01", "ble:02"])

    def test_offline_card_hides_level(self):
        self.panel.render([device("ble:01", "A", online=False, level=None, order=1)],
                          20, time.time())
        card = self.panel._cards["ble:01"]
        self.assertEqual(card.level.text(), "未连接")
        self.assertFalse(card.bar_slot.isVisible())


class TrayTests(unittest.TestCase):
    def setUp(self):
        self.tray = TrayIcons(open_panel=lambda: None, refresh=lambda: None,
                              toggle_bar=lambda _v: None, open_settings=lambda: None,
                              quit_app=lambda: None, bar_visible=lambda: False)

    def tearDown(self):
        self.tray.stop()

    def test_only_online_devices_get_icons(self):
        self.tray.update([device("ble:01", "A"), device("ble:02", "B", online=False, level=None)],
                         20, "number")
        self.assertEqual(sorted(self.tray._icons), ["ble:01"])

    def test_all_offline_keeps_idle_icon(self):
        self.tray.update([device("ble:01", "A", online=False, level=None)], 20, "number")
        self.assertEqual(sorted(self.tray._icons), [IDLE_KEY])

    def test_idle_icon_replaced_when_device_returns(self):
        self.tray.update([], 20, "number")
        self.assertEqual(sorted(self.tray._icons), [IDLE_KEY])
        self.tray.update([device("ble:01", "A")], 20, "number")
        self.assertEqual(sorted(self.tray._icons), ["ble:01"])


if __name__ == "__main__":
    unittest.main()
