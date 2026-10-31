"""T004：设备记录层（稳定 ID、连接时间、排序、损坏恢复）。"""

from __future__ import annotations

import json
import os
import tempfile
import pathlib
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.support import temp_dir  # noqa: E402
from keymousebattery.model import Device, Sample  # noqa: E402
from keymousebattery.records import RecordStore, kind_label  # noqa: E402


def device(key: str, name: str, kind: str = "keyboard", online: bool = True,
           level: int | None = 76, order: int = 0, last_connected: float | None = None,
           stale: bool = False) -> Device:
    return Device(key=key, name=name, kind=kind, connection="ble", source="windows-ble",
                  order=order, last_connected=last_connected, stale=stale,
                  sample=Sample(level=level, charging=None, online=online, sampled_at=0.0))


class RecordStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = temp_dir("records")
        self.path = self.folder / "devices.json"
        self.store = RecordStore(self.path)
        self.store.load()

    def tearDown(self):
        self.store = None

    def test_empty_store_has_no_records(self):
        self.assertEqual(self.store.merge([]), [])

    def test_observe_new_device_creates_record(self):
        changed = self.store.observe([device("ble:01", "键盘")], now=100.0)
        self.assertTrue(changed)
        merged = self.store.merge([])
        self.assertEqual(len(merged), 1)
        self.assertFalse(merged[0].sample.online)

    def test_reconnecting_bumps_order(self):
        self.store.observe([device("ble:01", "键盘")], now=100.0)
        self.store.observe([device("ble:01", "键盘", online=False, level=None)], now=110.0)
        self.store.observe([device("ble:01", "键盘")], now=120.0)
        merged = self.store.merge([device("ble:01", "键盘")])
        self.assertTrue(merged[0].sample.online)
        self.assertEqual(merged[0].last_connected, 120.0)

    def test_repeated_online_notice_keeps_connection_time(self):
        self.store.observe([device("ble:01", "键盘")], now=100.0)
        changed = self.store.observe([device("ble:01", "键盘")], now=130.0)
        self.assertFalse(changed)
        merged = self.store.merge([device("ble:01", "键盘")])
        self.assertEqual(merged[0].last_connected, 100.0)

    def test_offline_keeps_record_without_level(self):
        self.store.observe([device("ble:01", "键盘", level=64)], now=100.0)
        self.store.observe([device("ble:01", "键盘", online=False, level=None)], now=140.0)
        merged = self.store.merge([])
        self.assertEqual(merged[0].name, "键盘")
        self.assertFalse(merged[0].sample.online)
        self.assertIsNone(merged[0].sample.level)

    def test_save_and_reload(self):
        self.store.observe([device("ble:01", "键盘")], now=100.0)
        self.store.save()
        again = RecordStore(self.path)
        again.load()
        merged = again.merge([])
        self.assertEqual([d.key for d in merged], ["ble:01"])

    def test_corrupted_file_is_quarantined(self):
        self.path.write_text("{not json", encoding="utf-8")
        store = RecordStore(self.path)
        store.load()
        self.assertEqual(store.merge([]), [])
        self.assertFalse(self.path.exists())
        self.assertTrue(any(p.name.startswith("devices.json.bad-") for p in self.folder.iterdir()))

    def test_sort_online_first_then_recent(self):
        self.store.observe([device("ble:01", "旧键盘")], now=100.0)
        self.store.observe([device("ble:02", "新键盘")], now=110.0)
        self.store.observe([device("ble:03", "鼠标", "mouse")], now=120.0)
        live = [device("ble:01", "旧键盘"), device("ble:02", "新键盘")]
        merged = self.store.merge(live)
        self.assertEqual([d.key for d in merged], ["ble:02", "ble:01", "ble:03"])
        self.assertFalse(merged[-1].sample.online)

    def test_kind_label(self):
        self.assertEqual(kind_label("keyboard"), "键盘")
        self.assertEqual(kind_label("unknown-kind"), "设备")


if __name__ == "__main__":
    unittest.main()

class ConfirmedHistoryTests(unittest.TestCase):
    """v2：只有"已确认的在线证据"才新增历史；待确认不改排序、不生成事件。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = RecordStore(pathlib.Path(self.tmp.name) / "devices.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _device(self, key, online=True, confirmed=True, level=80):
        return Device(key=key, name="设备 " + key, kind="keyboard", connection="ble",
                      source="windows-ble",
                      sample=Sample(level=level if online else None, charging=None,
                                    online=online, confirmed=confirmed))

    def test_unknown_offline_device_not_recorded(self):
        self.store.observe([self._device("ble:unknown", online=False)])
        self.assertEqual(self.store.records, {})

    def test_unconfirmed_device_not_recorded(self):
        self.store.observe([self._device("ble:x", online=True, confirmed=False)])
        self.assertEqual(self.store.records, {})

    def test_confirmed_online_records(self):
        self.store.observe([self._device("ble:y")])
        self.assertIn("ble:y", self.store.records)

    def test_unconfirmed_keeps_order_and_connection_time(self):
        self.store.observe([self._device("ble:y")])
        before = self.store.records["ble:y"]
        order, connected = before.order, before.last_connected
        self.store.observe([self._device("ble:y", online=True, confirmed=False)])
        after = self.store.records["ble:y"]
        self.assertEqual(after.order, order)
        self.assertEqual(after.last_connected, connected)

    def test_reconnect_bumps_order(self):
        self.store.observe([self._device("ble:y")])
        first = self.store.records["ble:y"].order
        self.store.observe([self._device("ble:y", online=False)])
        self.store.observe([self._device("ble:y")])
        self.assertGreater(self.store.records["ble:y"].order, first)


