"""review1 收尾：F3 的自启状态显示与保存一致。

四组注册表替身场景（不碰真注册表、不启动真界面）：
1. 配置开着、注册表没有 → 不勾选，且不自动重建；
2. 配置关着、注册表已登记当前程序 → 勾选；
3. 读取被拒绝 → 保留用户原选择、提示无法读取，不改注册表；
4. 只改刷新间隔 → 不动注册表里指向旧副本的项；用户明确改自启才登记。
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.support import temp_dir  # noqa: E402

from keymousebattery import app as app_mod  # noqa: E402
from keymousebattery import autostart, config  # noqa: E402

OLD_COMMAND = '"C:\\old\\KeyMouseBattery.exe" --background'


class _Registry(autostart.Registry):
    def __init__(self, values=None, refuse_read=False, refuse_write=False,
                 refuse_read_after_change=False) -> None:
        self.values = dict(values or {})
        self.refuse_read = refuse_read
        self.refuse_write = refuse_write
        self.refuse_read_after_change = refuse_read_after_change
        self.changed = False
        self.writes = 0
        self.deletes = 0

    def get(self, name):
        if self.refuse_read or (self.refuse_read_after_change and self.changed):
            raise OSError(5, "拒绝访问。")
        return self.values.get(name)

    def set(self, name, value) -> None:
        if self.refuse_write:
            raise OSError(5, "拒绝访问。")
        self.writes += 1
        self.values[name] = value
        self.changed = True

    def delete(self, name) -> bool:
        self.deletes += 1
        self.changed = True
        return self.values.pop(name, None) is not None


class _Toggle:
    def __init__(self) -> None:
        self._checked = False

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value) -> None:
        self._checked = bool(value)


class _Page:
    def __init__(self) -> None:
        self.loaded = {}
        self.calls = []
        self.note = ""
        self.note_warn = False
        self.autostart_state = None
        self.desktop_bar = _Toggle()
        self.autostart = _Toggle()

    def load(self, cfg) -> None:
        self.loaded = dict(cfg)
        self.autostart_state = bool(cfg.get("autostart"))

    def show_result(self, ok, message) -> None:
        self.calls.append((bool(ok), message))

    def set_autostart_state(self, checked, note, warn=False) -> None:
        self.autostart_state = bool(checked)
        self.note = note
        self.note_warn = bool(warn)


class _Window:
    def __init__(self) -> None:
        self.settings_page = _Page()


class _Collector:
    def devices(self):
        return []

    def set_interval(self, value) -> None:
        pass

    def set_low(self, value) -> None:
        pass


class _Tray:
    def update(self, *args, **kwargs) -> None:
        pass


class _F3Base(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = temp_dir("f3-")
        self.config_path = Path(self.folder) / "config.json"
        self.app = app_mod.App()
        self.app.cfg, _report = config.load_or_create(self.config_path)
        self.app.config_path = self.config_path
        self.app.window = _Window()
        self.app.collector = _Collector()
        self.app.tray = _Tray()
        self.app.bar = None
        self._frozen = autostart.identity.is_frozen
        autostart.identity.is_frozen = lambda: True

    def tearDown(self) -> None:
        autostart.identity.is_frozen = self._frozen
        autostart.set_backend(autostart.WinRegistry())
        shutil.rmtree(self.folder, ignore_errors=True)

    def payload(self, **kwargs):
        base = {"interval": self.app.cfg["interval"], "low": self.app.cfg["low"],
                "tray_icon": self.app.cfg["tray_icon"], "desktop_bar": False,
                "autostart": bool(self.app.cfg.get("autostart")),
                "autostart_changed": False}
        base.update(kwargs)
        return base


class ReconcileTests(_F3Base):
    """启动时只读注册表：勾选跟实际走，配置不被悄悄改写。"""

    def test_config_on_but_missing_clears_checkbox_without_registering(self):
        registry = _Registry()
        autostart.set_backend(registry)
        self.app.cfg["autostart"] = True
        self.app._reconcile_autostart()
        page = self.app.window.settings_page
        self.assertFalse(page.autostart_state)
        self.assertIn("未登记", page.note)
        self.assertEqual(registry.writes, 0)
        self.assertTrue(self.app.cfg["autostart"], "读取阶段不得覆盖用户原设置")

    def test_registered_checks_even_when_config_says_off(self):
        registry = _Registry({autostart.VALUE_NAME: autostart.target_command()})
        autostart.set_backend(registry)
        self.app.cfg["autostart"] = False
        self.app._reconcile_autostart()
        page = self.app.window.settings_page
        self.assertTrue(page.autostart_state)
        self.assertIn("已登记", page.note)
        self.assertEqual(registry.writes, 0)

    def test_other_path_is_flagged_and_left_alone(self):
        registry = _Registry({autostart.VALUE_NAME: OLD_COMMAND})
        autostart.set_backend(registry)
        self.app._reconcile_autostart()
        page = self.app.window.settings_page
        self.assertFalse(page.autostart_state)
        self.assertTrue(page.note_warn)
        self.assertIn("其它位置", page.note)
        self.assertEqual(registry.values[autostart.VALUE_NAME], OLD_COMMAND)

    def test_read_refusal_keeps_user_choice(self):
        autostart.set_backend(_Registry({}, refuse_read=True))
        self.app.cfg["autostart"] = True
        self.app._reconcile_autostart()
        page = self.app.window.settings_page
        self.assertTrue(page.autostart_state, "读不到时不能替用户判定为关闭")
        self.assertIn("无法读取", page.note)
        self.assertTrue(page.note_warn)


class SaveTests(_F3Base):
    """保存：只有明确改过自启才动注册表。"""

    def test_interval_change_keeps_old_startup_entry(self):
        registry = _Registry({autostart.VALUE_NAME: OLD_COMMAND})
        autostart.set_backend(registry)
        self.app.apply_settings(self.payload(interval=120))
        self.assertEqual(registry.writes, 0)
        self.assertEqual(registry.deletes, 0)
        self.assertEqual(registry.values[autostart.VALUE_NAME], OLD_COMMAND)
        self.assertFalse(self.app.cfg["autostart"])
        ok, message = self.app.window.settings_page.calls[-1]
        self.assertTrue(ok, message)

    def test_explicit_toggle_registers_current_path(self):
        registry = _Registry()
        autostart.set_backend(registry)
        self.app.apply_settings(self.payload(autostart=True, autostart_changed=True))
        self.assertEqual(registry.writes, 1)
        self.assertEqual(registry.values[autostart.VALUE_NAME], autostart.target_command())
        self.assertTrue(self.app.cfg["autostart"])

    def test_explicit_toggle_off_removes_only_our_value(self):
        registry = _Registry({autostart.VALUE_NAME: autostart.target_command(),
                              "AnotherApp": "x.exe"})
        autostart.set_backend(registry)
        self.app.apply_settings(self.payload(autostart=False, autostart_changed=True))
        self.assertNotIn(autostart.VALUE_NAME, registry.values)
        self.assertIn("AnotherApp", registry.values)
        self.assertFalse(self.app.cfg["autostart"])

    def test_write_refusal_reports_failure_and_keeps_interval(self):
        autostart.set_backend(_Registry({}, refuse_write=True))
        self.app.apply_settings(self.payload(interval=120, autostart=True,
                                             autostart_changed=True))
        page = self.app.window.settings_page
        ok, message = page.calls[-1]
        self.assertFalse(ok)
        self.assertIn("其它设置已保存", message)
        self.assertEqual(self.app.cfg["interval"], 120)
        self.assertFalse(self.app.cfg["autostart"])


class UnreadableSaveTests(_F3Base):
    """review2 剩余分支：读不到时不能假装关闭或开启。"""

    def test_disable_with_unreadable_registry_fails_without_touching(self):
        registry = _Registry({autostart.VALUE_NAME: autostart.target_command()},
                             refuse_read=True)
        autostart.set_backend(registry)
        self.app.cfg["autostart"] = True
        self.app.apply_settings(self.payload(autostart=False, autostart_changed=True))
        page = self.app.window.settings_page
        ok, message = page.calls[-1]
        self.assertFalse(ok, "读不到注册表时不能报告已关闭")
        self.assertIn("其它设置已保存", message)
        self.assertEqual(registry.writes, 0)
        self.assertEqual(registry.deletes, 0)
        self.assertEqual(registry.values[autostart.VALUE_NAME], autostart.target_command())
        self.assertTrue(self.app.cfg["autostart"], "保留之前已知状态，不写成关闭")
        self.assertTrue(page.autostart_state, "复选框不能改成关闭")
        self.assertTrue(page.note_warn)

    def test_read_after_delete_failure_cannot_confirm_shutdown(self):
        registry = _Registry({autostart.VALUE_NAME: autostart.target_command()},
                             refuse_read_after_change=True)
        autostart.set_backend(registry)
        done, message, _changed = autostart.ensure_registered(False)
        self.assertFalse(done)
        self.assertIn("无法回读", message)

    def test_read_after_write_failure_cannot_confirm_enable(self):
        registry = _Registry({}, refuse_read_after_change=True)
        autostart.set_backend(registry)
        autostart.identity.is_frozen = lambda: True
        done, message = autostart.enable()
        self.assertFalse(done)
        self.assertIn("无法回读", message)


if __name__ == "__main__":
    unittest.main()
