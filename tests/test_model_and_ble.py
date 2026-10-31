import unittest

from vigilwatt_py import ble_watcher as ble
from vigilwatt_py.model import Device, Sample


class PropsMap:
    def __init__(self, data):
        self._data = data

    def lookup(self, key):
        if key not in self._data:
            raise KeyError(key)
        return self._data[key]


class FakeInfo:
    def __init__(self, props, ident="id-1"):
        self.properties = PropsMap(props)
        self.id = ident


class HelperTests(unittest.TestCase):
    def test_prop_returns_none_when_missing(self):
        self.assertIsNone(ble._prop(PropsMap({}), ble.NAME_PROP))

    def test_prop_reads_value(self):
        self.assertEqual(ble._prop(PropsMap({ble.NAME_PROP: "ELECOM"}), ble.NAME_PROP), "ELECOM")

    def test_as_int_ignores_bool(self):
        self.assertIsNone(ble._as_int(True))
        self.assertEqual(ble._as_int("42"), 42)
        self.assertIsNone(ble._as_int("abc"))

    def test_normalize_strips_braces(self):
        self.assertEqual(ble._normalize("{00002a19-0000-1000-8000-00805F9B34FB}"),
                         "00002a19-0000-1000-8000-00805f9b34fb")

    def test_address_is_masked(self):
        self.assertEqual(ble.BleSensor._mask("AA:BB:CC:DD:EE:FF"), "**:**:**:DD:EE:FF")
        self.assertEqual(ble.BleSensor._mask(None), "**")
        self.assertEqual(ble.BleSensor._mask(0xAABBCCDDEEFF), "**:**:**:DD:EE:FF")

    def test_battery_service_uuids(self):
        self.assertEqual(ble._normalize(ble.BATTERY_SERVICE),
                         "0000180f-0000-1000-8000-00805f9b34fb")
        self.assertEqual(ble._normalize(ble.BATTERY_LEVEL_CHAR),
                         "00002a19-0000-1000-8000-00805f9b34fb")


class PickTests(unittest.TestCase):
    def make(self, name, connected=True, ident="id"):
        props = {ble.NAME_PROP: name, ble.CONNECTED_PROP: connected}
        return FakeInfo(props, ident)

    def test_name_hint_matches_case_insensitively(self):
        sensor = ble.BleSensor("mouse", "ELECOM", "蓝牙鼠标")
        picked = sensor._pick([self.make("Mouse"), self.make("ELECOM EX-G")])
        self.assertIsNotNone(picked)
        self.assertEqual(ble._prop(picked.properties, ble.NAME_PROP), "ELECOM EX-G")

    def test_no_match_returns_none(self):
        sensor = ble.BleSensor("mouse", "ELECOM", "蓝牙鼠标")
        self.assertIsNone(sensor._pick([self.make("Keyboard")]))

    def test_empty_list_returns_none(self):
        sensor = ble.BleSensor("mouse", "ELECOM", "蓝牙鼠标")
        self.assertIsNone(sensor._pick([]))

    def test_key_uses_kind(self):
        self.assertEqual(ble.BleSensor("keyboard", "MCHOSE", "蓝牙键盘").key, "ble:keyboard")


class ModelTests(unittest.TestCase):
    def test_missing_level_is_dash_not_zero(self):
        device = Device(key="k", name="n", kind="mouse", connection="ble", source="s",
                        sample=Sample(level=None, charging=None, online=False))
        self.assertEqual(device.level_text, "—")
        self.assertEqual(device.charging_text, "充电状态未知")
        self.assertEqual(device.connection_text, "蓝牙")

    def test_stale_sample_keeps_last_reading_label(self):
        device = Device(key="k", name="n", kind="keyboard", connection="usb", source="s",
                        sample=Sample(level=80, charging=False, online=False), stale=True)
        self.assertEqual(device.state_text, "上次读数")
        self.assertEqual(device.level_text, "80%")

    def test_updated_text_uses_age(self):
        device = Device(key="k", name="n", kind="mouse", connection="ble", source="s",
                        sample=Sample(level=50, online=True, sampled_at=1000.0))
        self.assertEqual(device.updated_text(now=1030.0), "刚刚更新")
        self.assertEqual(device.updated_text(now=1000.0 + 300), "5 分钟前")


if __name__ == "__main__":
    unittest.main()
