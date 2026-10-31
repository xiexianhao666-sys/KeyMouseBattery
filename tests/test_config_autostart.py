"""配置迁移、越界修复、写入失败反馈与自启注册项。"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from vigilwatt_py import autostart, config
from tests.support import temp_dir, cleanup


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = temp_dir("cfg-")
        self.path = self.folder / "config.json"

    def tearDown(self) -> None:
        cleanup(self.folder)

    def test_old_percent_in_icon_becomes_tray_icon(self) -> None:
        self.path.write_text(json.dumps({"percent_in_icon": False, "interval": 60}), encoding="utf-8")
        cfg, report = config.load(self.path)
        self.assertEqual(cfg["tray_icon"], "battery")
        self.assertIn("percent_in_icon->tray_icon", report["migrated"])

    def test_unknown_keys_dropped_and_range_fixed(self) -> None:
        self.path.write_text(json.dumps({"interval": 7, "low": 90, "nonsense": 1}), encoding="utf-8")
        cfg, report = config.load(self.path)
        self.assertEqual(cfg["interval"], 60)
        self.assertEqual(cfg["low"], 20)
        self.assertNotIn("nonsense", cfg)
        self.assertIn("interval", report["fixed"])

    def test_write_failure_is_reported(self) -> None:
        cfg = dict(config.DEFAULTS)
        with mock.patch("vigilwatt_py.config.os.replace", side_effect=OSError("拒绝访问")):
            ok, message = config.write_atomic(self.path, cfg)
        self.assertFalse(ok)
        self.assertIn("拒绝访问", message)
        self.assertFalse(self.path.exists())

    def test_low_visual_keeps_colour_threshold_when_alerts_off(self) -> None:
        self.assertEqual(config.low_visual(0), config.LOW_VISUAL_FLOOR)
        self.assertEqual(config.low_visual(30), 30)

    def test_bar_pos_round_trip(self) -> None:
        cfg = dict(config.DEFAULTS)
        cfg["bar_pos"] = [120, 640]
        config.save(self.path, cfg)
        loaded, _report = config.load(self.path)
        self.assertEqual(loaded["bar_pos"], [120, 640])


class FakeRegistry(autostart.Registry):
    def __init__(self, initial=None) -> None:
        self.values = dict(initial or {})
        self.deleted = 0

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value):
        self.values[name] = value

    def delete(self, name):
        self.deleted += 1
        return self.values.pop(name, None) is not None


class AutostartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = FakeRegistry()
        autostart.set_backend(self.registry)
        self._frozen = mock.patch("vigilwatt_py.autostart.identity.is_frozen", return_value=True)
        self._frozen.start()

    def tearDown(self) -> None:
        self._frozen.stop()
        autostart.set_backend(None)

    def test_target_command_is_quoted_and_has_flag(self) -> None:
        command = autostart.target_command(r"C:\Program Files\VigilWattPy\VigilWattPy.exe")
        self.assertTrue(command.startswith('"C:\\Program Files\\VigilWattPy\\VigilWattPy.exe"'))
        self.assertTrue(command.endswith("--background"))

    def test_enable_writes_registration(self) -> None:
        ok, note = autostart.enable(exe=r"D:\apps\demo\VigilWattPy.exe")
        self.assertTrue(ok, note)
        self.assertEqual(self.registry.values[autostart.VALUE_NAME],
                         '"D:\\apps\\demo\\VigilWattPy.exe" --background')

    def test_disable_only_removes_own_value(self) -> None:
        self.registry.values["Other"] = "keep me"
        autostart.enable(exe=r"D:\apps\demo\VigilWattPy.exe")
        ok, _note = autostart.disable()
        self.assertTrue(ok)
        self.assertNotIn(autostart.VALUE_NAME, self.registry.values)
        self.assertEqual(self.registry.values["Other"], "keep me")

    def test_read_state_reports_moved_program(self) -> None:
        self.registry.values[autostart.VALUE_NAME] = '"D:\\old\\VigilWattPy.exe" --background'
        ok, raw, note = autostart.read_state(exe=r"D:\new\VigilWattPy.exe")
        self.assertFalse(ok)
        self.assertIn("其它位置", note)
        self.assertIn("old", raw)

    def test_enable_fails_when_value_vanishes(self) -> None:
        registry = FakeRegistry()
        autostart.set_backend(registry)
        with mock.patch.object(registry, "set", lambda name, value: None):
            ok, note = autostart.enable(exe=r"D:\apps\demo\VigilWattPy.exe")
        self.assertFalse(ok)
        self.assertIn("校验失败", note)

    def test_source_run_is_unsupported(self) -> None:
        with mock.patch("vigilwatt_py.autostart.identity.is_frozen", return_value=False):
            self.assertFalse(autostart.is_supported())


if __name__ == "__main__":
    unittest.main()
