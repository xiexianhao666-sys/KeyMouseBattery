import json
import unittest

from vigilwatt_py import config
from tests.support import cleanup, temp_dir


class DefaultsTests(unittest.TestCase):
    def test_defaults_are_usb_first(self):
        cfg, report = config.validate({})
        self.assertEqual(cfg["interval"], 60)
        self.assertEqual(cfg["low"], 20)
        self.assertTrue(cfg["percent_in_icon"])
        self.assertTrue(cfg["mchose_enabled"])
        self.assertEqual(cfg["ble_target"], "ELECOM")
        self.assertEqual(report["fixed"], [])

    def test_out_of_range_falls_back_to_default(self):
        cfg, report = config.validate({"interval": 5, "low": 500})
        self.assertEqual(cfg["interval"], 60)
        self.assertEqual(cfg["low"], 20)
        self.assertIn("interval", report["fixed"])

    def test_unknown_keys_are_dropped(self):
        cfg, report = config.validate({"mystery": 1})
        self.assertNotIn("mystery", cfg)
        self.assertEqual(report["dropped"], ["mystery"])


class FileTests(unittest.TestCase):
    def setUp(self):
        self.folder = temp_dir("cfg")
        self.path = self.folder / "config.json"

    def tearDown(self):
        cleanup(self.folder)

    def test_missing_file_is_created_with_defaults(self):
        cfg, report = config.load_or_create(self.path)
        self.assertTrue(report["created"])
        self.assertTrue(self.path.exists())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["interval"], 60)

    def test_save_and_reload_roundtrip(self):
        cfg, _ = config.validate({})
        cfg["interval"] = 120
        cfg["low"] = 30
        config.save(self.path, cfg)
        loaded, _ = config.load(self.path)
        self.assertEqual(loaded["interval"], 120)
        self.assertEqual(loaded["low"], 30)

    def test_corrupt_file_is_quarantined(self):
        self.path.write_text("{not json", encoding="utf-8")
        cfg, report = config.load(self.path)
        self.assertEqual(cfg["interval"], 60)
        self.assertIn("quarantined", report)
        self.assertFalse(self.path.exists())

    def test_bom_from_notepad_is_accepted(self):
        """记事本另存为 UTF-8 带 BOM 时不能当成损坏文件隔离掉。"""
        self.path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"interval": 120, "low": 30}).encode("utf-8"))
        cfg, report = config.load(self.path)
        self.assertEqual(cfg["interval"], 120)
        self.assertEqual(cfg["low"], 30)
        self.assertNotIn("quarantined", report)

    def test_zero_zero_is_rejected_for_interval(self):
        cfg, _ = config.validate({"interval": 0})
        self.assertEqual(cfg["interval"], 60)


if __name__ == "__main__":
    unittest.main()
