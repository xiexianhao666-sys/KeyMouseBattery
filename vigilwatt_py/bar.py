"""桌面电量条：贴合任务栏的紧凑窗口，样式对齐参考图（图形 + 百分比）。

形如 `🖱 100% │ ⌨ 100%`：鼠标在左、键盘在右，与上游 VigilWatt 的任务栏贴片一致；
颜色随状态走（正常蓝、低电量琥珀、未知灰），断连旧值在百分比后加「（旧）」。

不注入 Explorer、不改任务栏：只是把自己摆到任务栏那条带子上，位置可拖动并记住。
F2：两台设备分别着色；F5：屏幕增删/可用区域变化后自动夹回可见范围。
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .ui import device_glyph

BACKGROUND = "rgba(248, 250, 252, 0.96)"
BORDER = "#d5dde8"
TEXT = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#2f6bd8"
VALUE = "#2e9e5b"  # 正常读数用绿色，和任务栏参考样式一致
GLYPH = "#4b5563"  # 设备图形固定深灰，不随读数变色
GLYPH_VARIANT = "B"  # A/B/C 三套线稿造型，见 ui.device_glyph
LOW = "#ce7930"

DRAG_THRESHOLD = 4


def clamp_to_screens(x: int, y: int, w: int, h: int) -> Tuple[int, int]:
    """把窗口夹到最近的屏幕范围内（含任务栏那条带子，允许贴着任务栏摆放）。"""
    target = QGuiApplication.screenAt(QPoint(x + w // 2, y + h // 2)) or QGuiApplication.primaryScreen()
    if target is None:
        return x, y
    area = target.geometry()
    nx = min(max(x, area.left()), area.right() - w + 1)
    ny = min(max(y, area.top()), area.bottom() - h + 1)
    return nx, ny


class DesktopBar(QWidget):
    def __init__(self, on_click: Callable[[], None], on_moved: Callable[[int, int], None],
                 position: Optional[Tuple[int, int]] = None) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._on_click = on_click
        self._on_moved = on_moved
        self._press: Optional[QPoint] = None
        self._origin: Optional[QPoint] = None
        self._moved = False
        self.setObjectName("desktopBar")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 背景完全透明，样式表只管字号与字色（画底在 paintEvent 里按悬停处理）
        self.setStyleSheet(
            "QLabel { color: %s; font-size: 12px; background: transparent; }"
            "QLabel#barSep { color: #9aa3ad; }" % TEXT)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(6)
        self.mouse_glyph = QLabel()
        self.mouse_label = QLabel("鼠标 —")
        sep = QLabel("│")
        sep.setObjectName("barSep")
        self.keyboard_glyph = QLabel()
        self.keyboard_label = QLabel("键盘 —")
        row.addWidget(self.mouse_glyph)
        row.addWidget(self.mouse_label)
        row.addWidget(sep)
        row.addWidget(self.keyboard_glyph)
        row.addWidget(self.keyboard_label)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("单击打开面板，拖动可移动")
        self._colour_kb = ACCENT
        self._colour_ms = ACCENT
        self._variant = GLYPH_VARIANT
        self._light_taskbar = True
        self._app_watched = False
        self._watched_screens: set = set()
        self.set_state("—", "—")
        if position:
            self.move(*clamp_to_screens(int(position[0]), int(position[1]), self.width(), self.height()))
        self._watch_screens()

    # ---------- 屏幕变化 ----------
    def _watch_screens(self) -> None:
        """应用级信号只连接一次；每块屏幕的几何变化单独去重绑定。"""
        app = QGuiApplication.instance()
        if app is None:
            return
        if not self._app_watched:
            app.screenAdded.connect(self._on_screen_added)
            app.screenRemoved.connect(self._on_screen_gone)
            app.primaryScreenChanged.connect(self._on_primary_changed)
            self._app_watched = True
        for screen in app.screens():
            self._watch_screen(screen)

    def _on_screen_added(self, screen) -> None:
        # 新屏幕先绑定几何信号，再夹取一次位置：否则它会一直停在主屏坐标上
        self._watch_screen(screen)
        self.ensure_visible()

    def _on_screen_gone(self, _screen) -> None:
        self.ensure_visible()

    def _on_primary_changed(self, _screen) -> None:
        self.ensure_visible()

    def _watch_screen(self, screen) -> None:
        if id(screen) in self._watched_screens:
            return
        try:
            screen.availableGeometryChanged.connect(self._on_geometry_changed)
            screen.geometryChanged.connect(self._on_geometry_changed)
        except (AttributeError, TypeError):  # 老版本 Qt 没有这两个信号
            return
        self._watched_screens.add(id(screen))

    def _on_geometry_changed(self, _rect) -> None:
        self.ensure_visible()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().showEvent(event)
        self._watch_screens()
        self.ensure_visible()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        """完全透明：只把图形和读数浮在任务栏上，和参考样式一致。"""
        painter = QPainter(self)
        if self.underMouse():
            # 仅悬停时给一点极浅的底，方便看出可点击区域
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(QColor(255, 255, 255, 40))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        painter.end()

    # ---------- 文本与颜色 ----------
    def set_glyph_variant(self, variant: str) -> None:
        """切换图形造型，只给预览和挑选用。"""
        self._variant = variant
        self._paint()

    def set_taskbar_light(self, light: bool) -> None:
        """任务栏深浅决定图形颜色：深色任务栏上用浅灰，否则几乎看不见。"""
        if light == self._light_taskbar:
            return
        self._light_taskbar = light
        self._paint()

    def _paint(self) -> None:
        colour = GLYPH if self._light_taskbar else "#d8dde6"
        self.mouse_glyph.setPixmap(device_glyph("mouse", colour, variant=self._variant))
        self.keyboard_glyph.setPixmap(device_glyph("keyboard", colour, variant=self._variant))
        self.mouse_label.setStyleSheet("color: %s;" % self._colour_ms)
        self.keyboard_label.setStyleSheet("color: %s;" % self._colour_kb)
        self.adjustSize()
        # 文本变长（如"100%（旧）"）后可能顶出屏幕右缘，重新夹一次
        self.ensure_visible()

    def set_state(self, keyboard: str, mouse: str, keyboard_low: bool = False,
                  mouse_low: bool = False, keyboard_unknown: bool = False,
                  mouse_unknown: bool = False, keyboard_name: str = "键盘",
                  mouse_name: str = "鼠标") -> None:
        """参考图样式：图形 + 百分比；鼠标在左、键盘在右。"""
        self._colour_kb = LOW if keyboard_low else (MUTED if keyboard_unknown else VALUE)
        self._colour_ms = LOW if mouse_low else (MUTED if mouse_unknown else VALUE)
        self.mouse_label.setText(mouse)
        self.keyboard_label.setText(keyboard)
        self.setToolTip("单击打开面板，拖动可移动\n%s %s · %s %s"
                        % (mouse_name, mouse, keyboard_name, keyboard))
        self._paint()

    def set_texts(self, keyboard: str, mouse: str, keyboard_low: bool = False,
                  mouse_low: bool = False) -> None:
        """兼容旧调用：不带未知标记时按"有值"处理。"""
        self.set_state(keyboard, mouse, keyboard_low, mouse_low)

    # ---------- 拖动与点击 ----------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._origin = self.pos()
            self._moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press is not None and self._origin is not None:
            delta = event.globalPosition().toPoint() - self._press
            if abs(delta.x()) > DRAG_THRESHOLD or abs(delta.y()) > DRAG_THRESHOLD:
                self._moved = True
                self.move(self._origin + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._press is not None:
            if self._moved:
                x, y = clamp_to_screens(self.x(), self.y(), self.width(), self.height())
                self.move(x, y)
                self._on_moved(x, y)
            else:
                self._on_click()
        self._press = None
        self._origin = None
        super().mouseReleaseEvent(event)

    def ensure_visible(self) -> None:
        x, y = clamp_to_screens(self.x(), self.y(), self.width(), self.height())
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
