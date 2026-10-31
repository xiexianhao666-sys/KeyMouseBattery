"""托盘：每台设备一个图标，数字或电池样式，菜单与 tooltip 都带设备信息。

托盘不可用时（进程完整性级别被压到 Low 时会发生）不假装成功：返回 False，
由调用方保留可见窗口，避免"关掉窗口就再也打不开"。

F1（审查 2026-10-30）：QSystemTrayIcon 的构造参数不是"设置右键菜单"，
必须显式 setContextMenu；电量条勾选要按设备各存一份并保持同步。
"""

from __future__ import annotations



import time

from typing import Callable, Dict, Optional, Sequence



from PySide6.QtGui import QAction

from PySide6.QtWidgets import QMenu, QSystemTrayIcon



from . import identity

from .model import Device

from .ui import icon_pixmap, tray_icon, updated_text

IDLE_KEY = "__idle__"





class TrayIcons:

    def __init__(self, open_panel: Callable[[], None], refresh: Callable[[], None],

                 toggle_bar: Callable[[bool], None], open_settings: Callable[[], None],

                 quit_app: Callable[[], None],

                 bar_visible: Callable[[], bool]) -> None:

        self._open_panel = open_panel

        self._refresh = refresh

        self._toggle_bar = toggle_bar

        self._open_settings = open_settings

        self._quit = quit_app

        self._bar_visible = bar_visible

        self._icons: Dict[str, QSystemTrayIcon] = {}

        self._menus: Dict[str, QMenu] = {}

        self._bar_actions: Dict[str, QAction] = {}

        self._available = QSystemTrayIcon.isSystemTrayAvailable()



    @property

    def available(self) -> bool:

        return self._available



    def _menu(self, key: str) -> QMenu:

        menu = self._menus.get(key)

        if menu is not None:

            return menu

        menu = QMenu()

        open_action = menu.addAction("打开面板")

        open_action.triggered.connect(lambda: self._open_panel())

        refresh_action = menu.addAction("立即刷新")

        refresh_action.triggered.connect(lambda: self._refresh())

        menu.addSeparator()

        bar_action = menu.addAction("显示桌面电量条")

        bar_action.setCheckable(True)

        bar_action.setChecked(self._bar_visible())

        bar_action.triggered.connect(self._on_bar_toggled)

        self._bar_actions[key] = bar_action

        menu.addSeparator()

        settings_action = menu.addAction("设置")

        settings_action.triggered.connect(lambda: self._open_settings())

        quit_action = menu.addAction("退出")

        quit_action.triggered.connect(lambda: self._quit())

        self._menus[key] = menu

        return menu



    def _on_bar_toggled(self, checked: bool) -> None:

        self._toggle_bar(bool(checked))

        self._sync_bar_actions()



    def _sync_bar_actions(self) -> None:

        visible = self._bar_visible()

        for action in self._bar_actions.values():

            if action.isChecked() != visible:

                action.setChecked(visible)



    def _ensure(self, key: str) -> QSystemTrayIcon:

        icon = self._icons.get(key)

        if icon is not None:

            return icon

        menu = self._menu(key)

        icon = QSystemTrayIcon()  # 不把 QMenu 当父对象：那不是设置右键菜单

        icon.setContextMenu(menu)

        icon.setToolTip(identity.APP_NAME)

        icon.setIcon(icon_pixmap(None, False, 64))

        icon.activated.connect(self._on_activated)

        icon.show()

        self._icons[key] = icon

        return icon



    def context_menu(self, key: str) -> Optional[QMenu]:

        """给测试与自检用：确认图标真的绑了菜单。"""

        icon = self._icons.get(key)

        return None if icon is None else icon.contextMenu()



    def _on_activated(self, reason) -> None:

        if reason == QSystemTrayIcon.Trigger:  # 左键单击

            self._open_panel()



    def tooltip_for(self, device: Device, low: int, now: Optional[float] = None) -> str:

        now = time.time() if now is None else now

        sample = device.sample

        level = "—" if sample.level is None else "%d%%" % sample.level

        if sample.level is not None and (device.stale or not sample.online):

            where = "断连 · 上次读数"

        elif sample.online:

            where = "已连接"

        else:

            where = "未连接"

        return "%s · %s %s · %s · %s" % (identity.APP_NAME, device.name, level, where,

                                         updated_text(device, now))



    def update(self, devices: Sequence[Device], low: int, mode: str,

               light_taskbar: bool = True, now: Optional[float] = None) -> None:

        now = time.time() if now is None else now

        # 断开记录的设备不能继续显示上次百分比：托盘只保留在线设备的图标。

        online = [device for device in devices if device.sample.online and not device.stale]

        if not online:

            self._show_idle()

            return

        seen = set()

        for device in online:

            key = device.key

            seen.add(key)

            icon = self._ensure(key)

            icon.setIcon(tray_icon(device, low, mode, light_taskbar))

            icon.setToolTip(self.tooltip_for(device, low, now))

        for key in list(self._icons):

            if key not in seen and key != IDLE_KEY:

                self._icons.pop(key).hide()

                self._menus.pop(key, None)

                self._bar_actions.pop(key, None)

        idle = self._icons.pop(IDLE_KEY, None)

        if idle is not None:

            idle.hide()

            self._menus.pop(IDLE_KEY, None)

            self._bar_actions.pop(IDLE_KEY, None)

        self._sync_bar_actions()



    def _show_idle(self) -> None:

        """全部离线时留一个入口图标，避免托盘里什么都不剩。"""

        for key in list(self._icons):

            if key != IDLE_KEY:

                self._icons.pop(key).hide()

                self._menus.pop(key, None)

                self._bar_actions.pop(key, None)

        icon = self._ensure(IDLE_KEY)

        icon.setIcon(icon_pixmap(None, False, 64))

        icon.setToolTip("%s · 未连接设备" % identity.APP_NAME)

        self._sync_bar_actions()



    def message(self, title: str, text: str) -> bool:

        """通知不可用时返回 False，不阻塞界面。"""

        if not self._icons:

            return False

        first = next(iter(self._icons.values()))

        try:

            first.showMessage(title, text, QSystemTrayIcon.Information, 5000)

            return True

        except Exception:  # noqa: BLE001 - 通知失败不能影响主流程

            return False



    def stop(self) -> None:

        for icon in self._icons.values():

            icon.hide()

        self._icons.clear()

        self._menus.clear()

        self._bar_actions.clear()

