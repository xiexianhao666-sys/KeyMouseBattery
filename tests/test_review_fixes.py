"""审查 review1 的 F1–F5 定向回归。

Qt 部分用 offscreen 平台跑，不依赖真实桌面：只验证菜单绑定、文本/配色分流、
注册表替身下的自启分支，以及单实例与显示事件的安全边界。
"""

from __future__ import annotations

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.support import temp_dir  # noqa: E402

from keymousebattery import app as app_mod  # noqa: E402
from keymousebattery import autostart, config  # noqa: E402
from keymousebattery.bar import DesktopBar, clamp_to_screens  # noqa: E402
from keymousebattery.model import Device, Sample  # noqa: E402


def _now() -> float:
    import time

    return time.time()


def _device(kind: str, level, online=True, stale=False) -> Device:
    return Device(key="%s:1" % kind, name="设备", kind=kind, connection="ble",
                  source="test", sample=Sample(level=level, charging=None, online=online),
                  stale=stale)


def _qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class BarTextTests(unittest.TestCase):
    """贴片文案（T004 改口径）：断开就写"未连接"，不再展示旧百分比。"""

    def _device(self, level, online=True, stale=False):
        sample = Sample(level=level, charging=None, online=online, sampled_at=time.time())
        return Device(key="ble:aa", name="键盘", kind="keyboard", connection="ble",
                      source="windows-ble", sample=sample, stale=stale)

    def test_online_value(self):
        self.assertEqual(app_mod.device_bar_text(self._device(76), 20), ("76%", False))

    def test_low_only_for_online(self):
        self.assertEqual(app_mod.device_bar_text(self._device(12), 20), ("12%", True))

    def test_offline_shows_unconnected(self):
        self.assertEqual(app_mod.device_bar_text(self._device(64, online=False), 20)[0], "未连接")

    def test_stale_shows_unconnected(self):
        self.assertEqual(app_mod.device_bar_text(self._device(64, stale=True), 20)[0], "未连接")

    def test_missing_device(self):
        self.assertEqual(app_mod.device_bar_text(None, 20)[0], "未连接")

    def test_online_without_reading(self):
        self.assertEqual(app_mod.device_bar_text(self._device(None), 20)[0], "—")

    def test_pick_for_bar_prefers_latest_online(self):
        older = Device(key="ble:01", name="旧键盘", kind="keyboard", connection="ble", source="windows-ble", order=1,
                       sample=Sample(level=40, charging=None, online=True, sampled_at=time.time()))
        newer = Device(key="ble:02", name="新键盘", kind="keyboard", connection="ble", source="windows-ble", order=5,
                       sample=Sample(level=90, charging=None, online=True, sampled_at=time.time()))
        offline = Device(key="ble:03", name="离线键盘", kind="keyboard", connection="ble", source="windows-ble", order=9,
                         sample=Sample(level=None, charging=None, online=False, sampled_at=time.time()))
        self.assertEqual(app_mod.pick_for_bar([older, newer, offline], "keyboard").key, "ble:02")


class BarVisibilityTests(unittest.TestCase):
    """F5：越界坐标必须被夹回屏幕范围（含任务栏带子）。"""

    def test_out_of_range_is_clamped(self):
        _qt_app()
        x, y = clamp_to_screens(100000, 100000, 200, 40)
        from PySide6.QtGui import QGuiApplication

        area = QGuiApplication.primaryScreen().geometry()
        self.assertGreaterEqual(x, area.left())
        self.assertLessEqual(x + 200, area.right() + 1)
        self.assertLessEqual(y + 40, area.bottom() + 1)

    def test_negative_is_clamped(self):
        _qt_app()
        x, y = clamp_to_screens(-5000, -5000, 200, 40)
        from PySide6.QtGui import QGuiApplication

        area = QGuiApplication.primaryScreen().geometry()
        self.assertGreaterEqual(x, area.left())
        self.assertGreaterEqual(y, area.top())

    def test_state_colours_include_unknown(self):
        _qt_app()
        bar = DesktopBar(lambda: None, lambda _x, _y: None)
        bar.set_state("—", "100%", keyboard_unknown=True, mouse_unknown=False)
        self.assertIn("#6b7280", bar.keyboard_label.styleSheet())
        self.assertIn("#2e9e5b", bar.mouse_label.styleSheet())
        bar.set_state("12%", "9%", keyboard_low=True, mouse_low=True)
        self.assertIn("#ce7930", bar.keyboard_label.styleSheet())
        self.assertIn("#ce7930", bar.mouse_label.styleSheet())
        bar.deleteLater()


class TrayMenuTests(unittest.TestCase):
    """F1：每个图标都要真的绑定右键菜单，且电量条勾选同步。"""

    def test_each_icon_has_bound_context_menu(self):
        _qt_app()
        from keymousebattery.tray import TrayIcons

        calls = []
        tray = TrayIcons(lambda: calls.append("open"), lambda: calls.append("refresh"),
                         lambda visible: calls.append(("bar", visible)),
                         lambda: calls.append("settings"), lambda: calls.append("quit"),
                         bar_visible=lambda: False)
        tray.update([_device("keyboard", 100), _device("mouse", 64)], 20, "number",
                    light_taskbar=True)
        for key in ("keyboard:1", "mouse:1"):
            menu = tray.context_menu(key)
            self.assertIsNotNone(menu, "context menu must be bound for %s" % key)
            self.assertEqual(menu.actions()[0].text(), "打开面板")
            texts = [action.text() for action in menu.actions()]
            self.assertIn("显示桌面电量条", texts)
            self.assertIn("设置", texts)
            self.assertIn("退出", texts)
        trays = [tray._icons[key] for key in ("keyboard:1", "mouse:1")]
        for icon in trays:
            self.assertIsNotNone(icon.contextMenu())
        # 勾选状态跟随 bar_visible
        tray._bar_visible = lambda: True
        tray.update([_device("keyboard", 100), _device("mouse", 64)], 20, "number",
                    light_taskbar=True)
        for key in ("keyboard:1", "mouse:1"):
            action = tray._bar_actions[key]
            self.assertTrue(action.isChecked())
            action.trigger()  # QAction 的可勾选项只有 trigger 才会发信号
            self.assertIn(("bar", False), calls)
        tray.stop()

    def test_menu_action_invokes_open_panel(self):
        _qt_app()
        from keymousebattery.tray import TrayIcons

        calls = []
        tray = TrayIcons(lambda: calls.append("open"), lambda: None, lambda _v: None,
                         lambda: None, lambda: None, bar_visible=lambda: False)
        tray.update([_device("keyboard", 100)], 20, "number", light_taskbar=True)
        menu = tray.context_menu("keyboard:1")
        menu.actions()[0].trigger()
        self.assertIn("open", calls)
        tray.stop()


class _Toggle:
    def __init__(self) -> None:
        self.checked = False

    def setChecked(self, value: bool) -> None:  # noqa: N802 - Qt 命名
        self.checked = bool(value)


class _Settings:
    def __init__(self) -> None:
        self.calls = []
        self.loaded = {}
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
        self.settings_page = _Settings()


class _Collector:
    def __init__(self) -> None:
        self.interval = None
        self.low = None

    def devices(self):
        return []

    def set_interval(self, value) -> None:
        self.interval = int(value)

    def set_low(self, value) -> None:
        self.low = int(value)


class _Tray:
    def update(self, *args, **kwargs) -> None:
        pass

    def message(self, *args, **kwargs) -> bool:
        return True


class _FakeRegistry(autostart.Registry):
    def __init__(self, fail_set: bool = False) -> None:
        self.values = {}
        self.fail_set = fail_set

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value):
        if self.fail_set:
            raise OSError(5, "拒绝访问。")
        self.values[name] = value

    def delete(self, name):
        return self.values.pop(name, None) is not None


class ApplySettingsTests(unittest.TestCase):
    """F3：以注册表实际状态为准；自启失败也要把其它设置落地。"""

    def setUp(self) -> None:
        self.folder = temp_dir("apply-")
        self.path = os.path.join(self.folder, "config.json")
        self.app = app_mod.App()
        self.app.cfg, _report = config.load_or_create(__import__("pathlib").Path(self.path))
        self.app.config_path = __import__("pathlib").Path(self.path)
        self.app.window = _Window()
        self.app.collector = _Collector()
        self.app.tray = _Tray()
        self.app.bar = None

    def tearDown(self) -> None:
        autostart.set_backend(autostart.WinRegistry())
        import shutil

        shutil.rmtree(self.folder, ignore_errors=True)

    def _payload(self, **kwargs):
        base = {"interval": self.app.cfg["interval"], "low": self.app.cfg["low"], "autostart_changed": False,
                "tray_icon": self.app.cfg["tray_icon"],
                "desktop_bar": False, "autostart": False}
        base.update(kwargs)
        return base

    def test_rewrites_existing_value_when_program_moved(self):
        registry = _FakeRegistry()
        registry.values[autostart.VALUE_NAME] = '"C:\\old\\KeyMouseBattery.exe" --background'
        autostart.set_backend(registry)
        original_frozen = autostart.identity.is_frozen
        autostart.identity.is_frozen = lambda: True
        try:
            self.app.apply_settings(self._payload(autostart=True, autostart_changed=True))
        finally:
            autostart.identity.is_frozen = original_frozen
        ok, message = self.app.window.settings_page.calls[-1]
        self.assertTrue(ok, message)
        self.assertTrue(self.app.cfg["autostart"])
        self.assertIn(autostart.VALUE_NAME, registry.values)
        self.assertNotIn("old", registry.values[autostart.VALUE_NAME])

    def test_failure_keeps_other_settings_and_reports(self):
        registry = _FakeRegistry(fail_set=True)
        autostart.set_backend(registry)
        original_frozen = autostart.identity.is_frozen
        autostart.identity.is_frozen = lambda: True
        try:
            self.app.apply_settings(self._payload(autostart=True, interval=120, autostart_changed=True))
        finally:
            autostart.identity.is_frozen = original_frozen
        ok, message = self.app.window.settings_page.calls[-1]
        self.assertFalse(ok)
        self.assertIn("其它设置已保存并生效", message)
        self.assertEqual(self.app.collector.interval, 120)
        self.assertEqual(self.app.cfg["interval"], 120)
        self.assertFalse(self.app.cfg["autostart"])
        saved, _report = config.load(__import__("pathlib").Path(self.path))
        self.assertEqual(saved["interval"], 120)
        self.assertFalse(saved["autostart"])

    def test_disabling_removes_only_our_value(self):
        registry = _FakeRegistry()
        registry.values[autostart.VALUE_NAME] = '"C:\\x\\KeyMouseBattery.exe" --background'
        registry.values["OtherApp"] = "other.exe"
        autostart.set_backend(registry)
        self.app.cfg["autostart"] = True
        self.app.apply_settings(self._payload(autostart=False, autostart_changed=True))
        ok, message = self.app.window.settings_page.calls[-1]
        self.assertTrue(ok, message)
        self.assertNotIn(autostart.VALUE_NAME, registry.values)
        self.assertIn("OtherApp", registry.values)


class SingleInstanceTests(unittest.TestCase):
    """F4：互斥量可重复申请、退出后可再申请；没有事件时不假装成功。"""

    def test_acquire_release_cycle(self):
        original_name = app_mod.identity.MUTEX_NAME
        app_mod.identity.MUTEX_NAME = "Local\\KeyMouseBattery_test_single_instance"
        try:
            self.assertTrue(app_mod.acquire_single_instance())
            self.assertFalse(app_mod.acquire_single_instance())
            app_mod.release_single_instance()
            self.assertTrue(app_mod.acquire_single_instance())
        finally:
            app_mod.release_single_instance()
            app_mod.identity.MUTEX_NAME = original_name

    def test_signal_without_existing_event_is_false(self):
        original = app_mod.identity.SHOW_EVENT_NAME
        app_mod.identity.SHOW_EVENT_NAME = "Local\\KeyMouseBattery_test_show_%d" % os.getpid()
        try:
            self.assertFalse(app_mod.signal_show_event())
        finally:
            app_mod.identity.SHOW_EVENT_NAME = original


if __name__ == "__main__":
    unittest.main()
