"""USB 接收器与蓝牙通道的同一键盘去重。"""

from __future__ import annotations

import unittest

from keymousebattery.model import Device, Sample
from keymousebattery.poller import merge_usb_channels, model_tokens


def device(key: str, name: str, kind: str, connection: str, online: bool,
           level: int | None = None) -> Device:
    return Device(key=key, name=name, kind=kind, connection=connection,
                  source=connection, sample=Sample(level=level, online=online))


class TokenTests(unittest.TestCase):
    def test_g75_found(self) -> None:
        self.assertIn("G75", model_tokens("迈从 G75 Pro"))
        self.assertIn("G75", model_tokens("MCHOSE G75 5.0"))

    def test_short_or_digitless_ignored(self) -> None:
        self.assertEqual(set(), model_tokens("Mouse"))
        self.assertEqual(set(), model_tokens("EX-G"))
        self.assertEqual(set(), model_tokens(""))


class MergeTests(unittest.TestCase):
    def test_usb_keyboard_hidden_when_ble_keyboard_online(self) -> None:
        devices = [
            device("ble:k", "MCHOSE G75 5.0", "keyboard", "ble", True, 100),
            device("usb:compx-receiver", "迈从 G75 Pro", "keyboard", "usb", True, 100),
        ]
        kept = merge_usb_channels(devices)
        self.assertEqual(["ble:k"], [item.key for item in kept])

    def test_usb_keyboard_hidden_even_when_name_differs(self) -> None:
        devices = [
            device("ble:k", "MCHOSE G75 5.0", "keyboard", "ble", True, 100),
            device("usb:compx-receiver", "迈从 键盘", "keyboard", "usb", True, 80),
        ]
        self.assertEqual(1, len(merge_usb_channels(devices)))

    def test_usb_keyboard_hidden_when_ble_record_offline(self) -> None:
        devices = [
            device("ble:k", "MCHOSE G75 5.0", "keyboard", "ble", False, None),
            device("usb:compx-receiver", "迈从 G75 Pro", "keyboard", "usb", True, 100),
        ]
        self.assertEqual(1, len(merge_usb_channels(devices)))

    def test_usb_keyboard_kept_when_no_ble_keyboard_at_all(self) -> None:
        devices = [
            device("usb:compx-receiver", "迈从 G75 Pro", "keyboard", "usb", True, 100),
            device("ble:m", "ELECOM EX-G", "mouse", "ble", True, 100),
        ]
        self.assertEqual(2, len(merge_usb_channels(devices)))

    def test_usb_mouse_hidden_when_ble_mouse_online(self) -> None:
        devices = [
            device("ble:m", "ELECOM EX-G", "mouse", "ble", True, 100),
            device("usb:m", "ELECOM EX-G", "mouse", "usb", True, 100),
        ]
        self.assertEqual(1, len(merge_usb_channels(devices)))

    def test_usb_mouse_hidden_when_ble_mouse_record_exists(self) -> None:
        devices = [
            device("ble:m", "ELECOM EX-G", "mouse", "ble", False, None),
            device("usb:m", "ELECOM EX-G", "mouse", "usb", True, 100),
        ]
        self.assertEqual(1, len(merge_usb_channels(devices)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
