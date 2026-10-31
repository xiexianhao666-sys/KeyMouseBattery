"""装配：配置、界面、托盘、采集线程、桌面电量条与低电量提醒。

界面线程只做渲染，采集在 `Collector` 的守护线程里跑；托盘不可用时不隐藏窗口，
保证用户仍然有入口。

审查修复（review1）：
- F3 自启以注册表实际状态为准，保存时该修就修；失败原因可见，且不影响其它设置。
- F4 显示请求用主线程 QTimer 轮询事件对象，不再从原生线程碰 QWidget；
  句柄创建失败不进入等待循环，退出时释放 mutex/event；后台模式重复启动不抢前台。
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from . import alerts as alerts_mod
from .records import RecordStore
from . import autostart, config, identity, log
from .bar import DesktopBar
from .model import Device
from .poller import Collector, merge_usb_channels
from .tray import TrayIcons

LOGGER = logging.getLogger("keymousebattery.app")
TICK_MS = 1000
SHOW_POLL_MS = 500
REFRESH_FEEDBACK_SECONDS = 20.0
WAIT_OBJECT_0 = 0
EVENT_MODIFY_STATE = 0x0002
ERROR_ALREADY_EXISTS = 183

_MUTEX = None
_SHOW_EVENT = None


def _kernel32():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.OpenEventW.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.OpenEventW.restype = ctypes.c_void_p
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.SetEvent.restype = ctypes.c_bool
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel.WaitForSingleObject.restype = ctypes.c_uint
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_bool
    return kernel


def acquire_single_instance() -> bool:
    """句柄保存在模块级，退出时关闭；创建失败按"拿不到单实例"处理。

    已有实例时立即关闭自己那份句柄：否则本进程会在退出后继续"占着"互斥量，
    让之后的启动误判成重复运行。
    """
    global _MUTEX
    if _MUTEX:
        return False
    kernel = _kernel32()
    handle = kernel.CreateMutexW(None, False, identity.MUTEX_NAME)
    if not handle:
        LOGGER.error("单实例互斥量创建失败（GetLastError=%s）", ctypes.get_last_error())
        return False
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel.CloseHandle(handle)
        return False
    _MUTEX = handle
    return True


def release_single_instance() -> None:
    global _MUTEX
    if _MUTEX:
        _kernel32().CloseHandle(_MUTEX)
        _MUTEX = None


def signal_show_event() -> bool:
    kernel = _kernel32()
    handle = kernel.OpenEventW(EVENT_MODIFY_STATE, False, identity.SHOW_EVENT_NAME)
    if not handle:
        return False
    try:
        return bool(kernel.SetEvent(handle))
    finally:
        kernel.CloseHandle(handle)


class App:
    def __init__(self, shot: str = "", verbose: bool = False, background: bool = False,
                 shot_page: str = "devices") -> None:
        self.shot = shot
        self.shot_page = shot_page
        self.verbose = verbose
        self.background = background
        self.window = None
        self.tray: Optional[TrayIcons] = None
        self.bar: Optional[DesktopBar] = None
        self.collector: Optional[Collector] = None
        self.records: Optional[RecordStore] = None
        self.devices: List[Device] = []
        self.cfg: dict = {}
        self.config_path: Optional[Path] = None
        self.alerts = alerts_mod.Alerts()
        self._quit = False
        self._last_round = 0.0
        self._refresh_from = 0.0
        self._show_timer = None
        self.app = None

    # ---------- 启动 ----------
    def run(self) -> int:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        folder = identity.ensure_data_dir()
        if folder is None:
            sys.stderr.write("数据目录不可写：%s\n" % identity.data_dir())
            return 2
        identity.prepare_temp_dir(folder)
        log.setup(folder, self.verbose)
        self.config_path = identity.data_dir() / "config.json"
        self.cfg, report = config.load_or_create(self.config_path)
        LOGGER.info("%s %s starting (%s)", identity.APP_NAME, identity.APP_VERSION,
                    identity.describe_paths())
        if report.get("quarantined"):
            LOGGER.warning("配置损坏，已隔离到 %s", report["quarantined"])
        if not acquire_single_instance():
            # 后台模式的重复启动不抢前台：只有用户直接双击时才请求一次显示。
            if not self.background and signal_show_event():
                LOGGER.info("已有实例，已请求它显示面板")
            else:
                LOGGER.info("已有实例在运行")
            release_single_instance()
            return 0

        from .ui import MainWindow, app_icon

        self.app = QApplication.instance() or QApplication(sys.argv[:1])
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setWindowIcon(app_icon())
        self.window = MainWindow(self.request_refresh)
        self.window.on_close = self._on_window_close
        self.window.quit_button.clicked.connect(self.quit)
        self.window.settings_page.load(self.cfg)
        self.window.settings_page.apply_requested.connect(self.apply_settings)
        self._reconcile_autostart()

        self.records = RecordStore(identity.data_dir() / "devices.json")
        self.records.load()
        self.collector = Collector(
            interval=int(self.cfg["interval"]), low=int(self.cfg["low"]),
            bluetooth=True,
            mchose_enabled=bool(self.cfg.get("mchose_enabled", True)),
        )
        self.tray = TrayIcons(
            open_panel=self.show_panel,
            refresh=self.request_refresh,
            toggle_bar=self.set_bar_visible,
            open_settings=self.show_settings,
            quit_app=self.quit,
            bar_visible=lambda: bool(self.cfg.get("desktop_bar")),
        )
        if not self.tray.available:
            LOGGER.error("系统托盘不可用（isSystemTrayAvailable=False），保留主窗口")
        self.collector.start()
        if self.cfg.get("desktop_bar"):
            self.set_bar_visible(True, persist=False)
        self._start_show_poller()

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)
        if not self.background or not self.tray.available:
            self.window.show()
        if self.shot:
            QTimer.singleShot(2500, self._save_shot)
        return self.app.exec()

    # ---------- 显示请求（F4） ----------
    def _start_show_poller(self) -> None:
        from PySide6.QtCore import QTimer

        global _SHOW_EVENT
        kernel = _kernel32()
        handle = kernel.CreateEventW(None, False, False, identity.SHOW_EVENT_NAME)
        if not handle:
            LOGGER.error("显示事件创建失败（GetLastError=%s），重复启动将无法唤出面板",
                         ctypes.get_last_error())
            return
        _SHOW_EVENT = handle
        self._show_timer = QTimer()
        self._show_timer.timeout.connect(self._poll_show_event)
        self._show_timer.start(SHOW_POLL_MS)

    def _poll_show_event(self) -> None:
        if not _SHOW_EVENT or self._quit:
            return
        if _kernel32().WaitForSingleObject(_SHOW_EVENT, 0) == WAIT_OBJECT_0:
            LOGGER.info("收到显示请求，唤出面板")
            self.show_panel()

    def _release_show_event(self) -> None:
        global _SHOW_EVENT
        if self._show_timer is not None:
            self._show_timer.stop()
            self._show_timer = None
        if _SHOW_EVENT:
            _kernel32().CloseHandle(_SHOW_EVENT)
            _SHOW_EVENT = None

    # ---------- 事件 ----------
    def request_refresh(self) -> None:
        if self.collector is not None:
            self.collector.refresh_now()
        if self.window is not None:
            # 必须记下“从什么时候开始等”，否则刷新按钮会一直停在“刷新中…”。
            self._refresh_from = time.time()
            self.window.begin_refresh()

    def show_panel(self) -> None:
        if self.window is None:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def show_settings(self) -> None:
        self.show_panel()
        self.window.show_page(1)

    def _on_window_close(self) -> bool:
        """返回 True 表示"已隐藏到托盘"，False 表示真的关掉。"""
        if self.tray is not None and self.tray.available:
            self.window.hide()
            LOGGER.info("主窗口已隐藏到托盘")
            return True
        self.quit()
        return False

    # ---------- 刷新 ----------
    def tick(self) -> None:
        if self._quit or self.collector is None or self.window is None:
            return
        live = self.collector.devices()
        devices = live
        if self.records is not None:
            changed = self.records.observe(live)
            devices = merge_usb_channels(self.records.merge(live))
            if changed:
                # 只在连接状态或设备集合变化时落盘，普通采样不碰磁盘。
                self.records.save()
        self.devices = devices
        low = int(self.cfg.get("low", 20))
        visual_low = config.low_visual(low)
        self.window.render_devices(devices, int(self.cfg["interval"]), low, time.time())
        light_taskbar = self._taskbar_is_light()
        if self.tray is not None:
            self.tray.update(devices, visual_low, str(self.cfg.get("tray_icon", "number")),
                             light_taskbar=light_taskbar)
        if self.bar is not None:
            self.bar.set_taskbar_light(light_taskbar)
            keyboard = pick_for_bar(devices, "keyboard")
            mouse = pick_for_bar(devices, "mouse")
            kb_text, kb_low = device_bar_text(keyboard, low)
            ms_text, ms_low = device_bar_text(mouse, low)
            self.bar.set_state(
                kb_text, ms_text,
                keyboard_low=kb_low, mouse_low=ms_low,
                keyboard_unknown=(keyboard is None or keyboard.sample.level is None),
                mouse_unknown=(mouse is None or mouse.sample.level is None),
                keyboard_name=(keyboard.name if keyboard is not None else "键盘"),
                mouse_name=(mouse.name if mouse is not None else "鼠标"),
            )
        if self.collector.first_round_done() and time.time() - self._last_round > 0.5:
            self._last_round = time.time()
            self._check_alerts(devices, low)
        self._settle_refresh()

    def _settle_refresh(self) -> None:
        """手动刷新后，等某条通道的新一轮结果回来再恢复按钮，不让它一直转。"""
        if not self._refresh_from:
            return
        attempts = self.collector.attempts() if self.collector is not None else {}
        if max(attempts.values(), default=0.0) > self._refresh_from:
            self._refresh_from = 0.0
            self.window.end_refresh(True)
        elif time.time() - self._refresh_from > REFRESH_FEEDBACK_SECONDS:
            self._refresh_from = 0.0
            self.window.end_refresh(False)

    def _check_alerts(self, devices, low: int) -> None:
        messages = self.alerts.check(devices, low)
        for message in messages:
            LOGGER.warning("提醒：%s %s", message.title, message.text)
            if self.tray is not None:
                self.tray.message(message.title, message.text)

    @staticmethod
    def _taskbar_is_light() -> bool:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            return bool(value)
        except OSError:
            return True

    # ---------- 设置 ----------
    def apply_settings(self, payload: dict) -> None:
        previous = dict(self.cfg)
        candidate = dict(self.cfg)
        candidate.update(payload)
        merged, report = config.validate(candidate)
        # 只有用户亲手改过"开机启动"这一项，才允许动注册表；只改间隔等不碰现有启动项。
        touched = bool(payload.get("autostart_changed"))
        desired_autostart = bool(merged.get("autostart")) if touched else bool(previous.get("autostart"))
        # F3：先把与自启无关的设置落到磁盘与运行时，再单独处理自启，避免"提早 return"。
        ok, message = (config.write_atomic(self.config_path, merged)
                       if self.config_path else (False, "无配置路径"))
        if not ok:
            self.window.settings_page.show_result(False, "配置写入失败：%s" % message)
            self.cfg = previous
            return
        self.cfg = merged
        if self.collector is not None:
            self.collector.set_interval(int(merged["interval"]))
            self.collector.set_low(int(merged["low"]))
        if bool(merged.get("desktop_bar")) != (self.bar is not None):
            self.set_bar_visible(bool(merged.get("desktop_bar")), persist=False)
        if self.tray is not None:
            self.tray.update(self.collector.devices() if self.collector else [],
                             config.low_visual(int(merged["low"])),
                             str(merged.get("tray_icon", "number")))

        if not touched:
            # 未改自启：保留注册表现状，把配置回填成实际状态，界面按实际勾选。
            state = autostart.inspect()
            if state.readable:
                self.cfg["autostart"] = bool(state.registered)
                if self.config_path is not None:
                    config.write_atomic(self.config_path, self.cfg)
            self.window.settings_page.set_autostart_state(
                bool(self.cfg.get("autostart")), state.note, warn=state.state in ("other", "error"))
            extra = "，部分取值已回退" if report.get("fixed") else ""
            self.window.settings_page.show_result(True, "已保存并立即生效" + extra)
            return

        done, note, _changed = autostart.ensure_registered(desired_autostart)
        state = autostart.inspect()
        if not state.readable:
            # 读不到就不敢说成功：保留已保存的其它设置，自启维持之前已知状态并标"未知"。
            self.cfg["autostart"] = bool(previous.get("autostart"))
            if self.config_path is not None:
                config.write_atomic(self.config_path, self.cfg)
            self.window.settings_page.set_autostart_state(
                bool(self.cfg.get("autostart")), state.note, warn=True)
            self.window.settings_page.show_result(
                False, "%s（%s；其它设置已保存并生效）"
                % (note or "无法确认自启状态", state.note))
            return
        actual = bool(state.registered)
        if not done or actual != desired_autostart:
            # 注册失败或注册表仍与期望不符：配置存实际状态，开关回到现实状态并说明原因。
            self.cfg["autostart"] = actual
            if self.config_path is not None:
                config.write_atomic(self.config_path, self.cfg)
            self.window.settings_page.set_autostart_state(actual, state.note, warn=True)
            self.window.settings_page.show_result(
                False, "%s（其它设置已保存并生效）" % (note or state.note or "自启未生效"))
            return
        self.cfg["autostart"] = actual
        if self.config_path is not None:
            config.write_atomic(self.config_path, self.cfg)
        extra = "，部分取值已回退" if report.get("fixed") else ""
        idle = "（配置无变化）" if self.cfg == previous else ""
        self.window.settings_page.load(self.cfg)
        self.window.settings_page.set_autostart_state(
            bool(self.cfg.get("autostart")), state.note, warn=state.state == "other")
        self.window.settings_page.show_result(True, "已保存并立即生效" + idle + extra)

    def set_bar_visible(self, visible: bool, persist: bool = True) -> None:
        if visible and self.bar is None:
            self.bar = DesktopBar(self.show_panel, self._on_bar_moved)
            saved = self.cfg.get("bar_pos")
            if saved:
                self.bar.move(int(saved[0]), int(saved[1]))
            else:
                self.bar.move(*self._default_bar_position(self.bar.width(), self.bar.height()))
            self.bar.show()
            LOGGER.info("desktop bar shown at %s,%s %sx%s (screen %s)", self.bar.x(), self.bar.y(), self.bar.width(), self.bar.height(), self.bar.screen().geometry())
        elif not visible and self.bar is not None:
            self.bar.close()
            self.bar.deleteLater()
            self.bar = None
        self.cfg["desktop_bar"] = bool(visible)
        if persist and self.config_path is not None:
            ok, _message = config.write_atomic(self.config_path, self.cfg)
            if not ok:
                LOGGER.warning("电量条状态写入配置失败")
        if self.window is not None:
            self.window.settings_page.desktop_bar.setChecked(bool(visible))
        if self.tray is not None:
            self.tray.update(self.collector.devices() if self.collector else [],
                             config.low_visual(int(self.cfg.get("low", 20))),
                             str(self.cfg.get("tray_icon", "number")))

    def _default_bar_position(self, width: int = 190, height: int = 30) -> Tuple[int, int]:
        """贴着任务栏：落在通知区左侧，任务栏在下方时垂直居中于那条带子。"""
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return 100, 100
        full = screen.geometry()
        avail = screen.availableGeometry()
        band = full.bottom() - avail.bottom()
        if band >= height // 2:
            y = avail.bottom() + 1 + max(0, (band - height) // 2)
        else:
            y = avail.bottom() - height - 8
        tray_left = self._tray_left()
        if tray_left is not None:
            # GetWindowRect 给的是物理像素，Qt 用的是与缩放无关的逻辑坐标
            ratio = float(screen.devicePixelRatio() or 1.0)
            x = int(tray_left / ratio) - width - 44
        else:
            x = avail.right() - width - 210
        return max(avail.left(), x), y

    @staticmethod
    def _tray_left() -> Optional[int]:
        """通知区的左边界；拿不到就返回 None，由调用方退回估算位置。"""
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
            user32.FindWindowW.restype = ctypes.c_void_p
            user32.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                             ctypes.c_wchar_p, ctypes.c_wchar_p]
            user32.FindWindowExW.restype = ctypes.c_void_p

            class _Rect(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Rect)]
            tray = user32.FindWindowW("Shell_TrayWnd", None)
            if not tray:
                return None
            notify = user32.FindWindowExW(tray, None, "TrayNotifyWnd", None)
            if not notify:
                return None
            rect = _Rect()
            if not user32.GetWindowRect(notify, ctypes.byref(rect)):
                return None
            return int(rect.left)
        except (OSError, AttributeError):
            return None

    def _on_bar_moved(self, x: int, y: int) -> None:
        self.cfg["bar_pos"] = [int(x), int(y)]
        if self.config_path is not None:
            ok, _message = config.write_atomic(self.config_path, self.cfg)
            if not ok:
                LOGGER.warning("电量条位置写入配置失败")

    def _reconcile_autostart(self) -> None:
        """启动只读注册表并显示实际状态，绝不自动增删启动项。

        旧副本开过自启、新解压目录里配置还是默认关闭时，普通启动不该删掉那条
        仍然有效的启动项；反过来配置写着开启、启动项被删掉时，也不该在后台悄悄重建。
        只有用户在设置页勾选并保存时才写注册表。
        """
        page = self.window.settings_page if self.window is not None else None
        if page is None:
            return
        state = autostart.inspect()
        if state.state == "dev":
            if self.cfg.get("autostart"):
                LOGGER.warning("源码运行不支持开机自启，界面保持关闭（不改注册表）")
            page.set_autostart_state(False, state.note)
            return
        if state.state == "error":
            # 读不到就不动开关、也不改配置：保留用户原来的选择，只提示无法读取。
            page.set_autostart_state(bool(self.cfg.get("autostart")), state.note, warn=True)
            return
        # 勾选状态一律以注册表实际值为准（registered / missing / other）。
        page.set_autostart_state(bool(state.registered), state.note,
                                 warn=state.state == "other")
        if bool(self.cfg.get("autostart")) != bool(state.registered):
            LOGGER.info("开机启动实际状态与配置不一致：配置=%s 注册表=%s（不改注册表）",
                        bool(self.cfg.get("autostart")), state.note)

    # ---------- 截图与退出 ----------
    def _save_shot(self, waited: int = 0) -> None:
        if self.window is None or not self.shot:
            return
        if waited == 0:
            # 排查"截图命令偶发不落盘"：确认定时器到底有没有进到主线程
            LOGGER.info("shot start page=%s devices=%d", self.shot_page, len(self.devices or []))
        if self.shot_page == "settings":
            self.window.show_page(1)
        self.window.show()
        if self.shot_page == "devices" and not self.devices and waited < 24000:
            # 首次蓝牙扫描可能要十几秒，没结果时先别截空列表
            QTimer.singleShot(1500, lambda: self._save_shot(waited + 1500))
            return
        try:
            self.window.repaint()
            path = Path(self.shot)
            path.parent.mkdir(parents=True, exist_ok=True)
            ok = self.window.grab().save(str(path))
            LOGGER.info("shot saved %s ok=%s waited=%dms", path, ok, waited)
        except Exception:  # noqa: BLE001 - 截图失败也要退出，否则进程会一直挂着
            LOGGER.exception("截图失败")
        finally:
            self.quit()

    def quit(self) -> None:
        if self._quit:
            return
        self._quit = True
        LOGGER.info("退出中")
        self._release_show_event()
        if self.tray is not None:
            self.tray.stop()
        if self.collector is not None:
            self.collector.stop()
        if self.bar is not None:
            self.bar.close()
            self.bar = None
        if self.window is not None:
            self.window.allow_close()
            self.window.close()
        release_single_instance()
        if getattr(self.app, "quit", None) is not None:
            self.app.quit()
        LOGGER.info("已退出")


def device_bar_text(device: Optional[Device], low: int) -> Tuple[str, bool]:
    """贴片文案：只显示在线且拿得到读数的设备；断开就写"未连接"，不给旧百分比。"""
    if device is None:
        return "未连接", False
    sample = device.sample
    if not sample.online or device.stale:
        return "未连接", False
    if sample.level is None:
        return "—", False
    return "%d%%" % sample.level, low > 0 and sample.level <= low


def pick_for_bar(devices: Sequence[Device], kind: str) -> Optional[Device]:
    """同一类有多台时，贴片只取"在线且最新连接"的那台，tooltip 里已经写了名字。"""
    candidates = [d for d in devices if d.kind == kind and d.sample.online and not d.stale]
    if not candidates:
        return None
    return max(candidates, key=lambda d: (int(d.order or 0), float(d.last_connected or 0.0)))
