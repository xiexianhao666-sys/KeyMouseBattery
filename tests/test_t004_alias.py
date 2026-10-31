"""0.4.2：设备自定义名称（alias）的持久化与生效规则。"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from keymousebattery.model import Device, Sample
from keymousebattery.records import RecordStore


def _device(key="ble:aa", name="MCHOSE G75 5.0", kind="keyboard", online=True, level=80):
    return Device(key=key, name=name, kind=kind, connection="ble", source="gatt",
                  sample=Sample(level=level, charging=None, online=online,
                                sampled_at=time.time()))


class AliasTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = RecordStore(Path(self._tmp.name) / "devices.json")
        self.store.observe([_device()], now=time.time())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rename_applies_to_cards(self):
        self.assertTrue(self.store.rename("ble:aa", "我的键盘"))
        merged = self.store.merge([_device()])
        self.assertEqual(merged[0].name, "我的键盘")
        self.assertEqual(merged[0].alias, "我的键盘")

    def test_rename_persists_across_reload(self):
        self.store.rename("ble:aa", "办公室键盘")
        self.store.save()
        again = RecordStore(self.store.path)
        again.load()
        merged = again.merge([])
        self.assertEqual(merged[0].name, "办公室键盘")

    def test_reset_restores_discovered_name(self):
        self.store.rename("ble:aa", "临时名字")
        self.assertTrue(self.store.rename("ble:aa", ""))
        merged = self.store.merge([_device()])
        self.assertEqual(merged[0].name, "MCHOSE G75 5.0")
        self.assertEqual(merged[0].alias, "")

    def test_alias_survives_new_samples(self):
        self.store.rename("ble:aa", "常用键盘")
        self.store.observe([_device(name="MCHOSE G75 5.0 B")], now=time.time())
        merged = self.store.merge([_device()])
        self.assertEqual(merged[0].name, "常用键盘")
        # 记录内部仍保存采集到的原名，方便恢复默认
        self.assertEqual(self.store.records["ble:aa"].name, "MCHOSE G75 5.0 B")

    def test_rename_trims_and_caps(self):
        long_name = "  超长名字" + "字" * 60 + "  "
        self.store.rename("ble:aa", long_name)
        self.assertEqual(len(self.store.records["ble:aa"].alias), 40)
        self.assertFalse(self.store.records["ble:aa"].alias.startswith(" "))

    def test_rename_unknown_key_is_noop(self):
        self.assertFalse(self.store.rename("ble:missing", "x"))

    def test_alias_is_in_offline_card(self):
        self.store.rename("ble:aa", "备用键盘")
        merged = self.store.merge([])          # 设备不在线 → 用记录补一张离线卡
        self.assertEqual(merged[0].name, "备用键盘")
        self.assertFalse(merged[0].sample.online)


if __name__ == "__main__":
    unittest.main()
