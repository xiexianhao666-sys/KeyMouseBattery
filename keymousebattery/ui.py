"""界面：设备概览 + 偏好设置两页，浅色侧导航。

卡片是复用的（`DeviceCard.update_view` 只改文字与进度条），刷新时不会重建控件，
避免闪烁；四态由"是否有读数 × 是否在线"决定，未知一律显示"—"，不猜数。
"""

from __future__ import annotations

import ctypes
import time
from typing import Callable, Dict, List, Optional, Sequence

from PySide6.QtCore import (
    QSize, QEasingCurve, QByteArray, QPoint, QPointF, QRectF, QPropertyAnimation,
                            Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QIcon, QPainter, QPen, QPixmap,
                           QPolygonF)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QInputDialog,
    QMenu,QAbstractButton, QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from . import config as cfgmod
from . import icons
from . import identity
from .appearance import set_title_bar_colours
from .model import Device

BG = "#f6f6f6"            # 主内容底
SIDEBAR = "#ffffff"
SURFACE = "#f6f6f6"
CARD = "#ffffff"
BORDER = "#dedede"
BORDER_SOFT = "#e2e2e2"
TEXT = "#252525"
MUTED = "#737373"
ACCENT = "#4267d5"        # 仅主操作/品牌/蓝牙标识
ACCENT_SOFT = "#ececec"
HIGHLIGHT = "#a3a3a3"     # 重排强调：中性灰描边
OFFLINE_CARD = "#fafafa"
OFFLINE_LABEL = "#ededed"
GREEN = "#2e9e5b"
AMBER = "#ce7930"
RED = "#d64545"
BATTERY_TRACK = "#e8e8e8"

_SPI_GETCLIENTAREAANIMATION = 0x1042


def animations_enabled() -> bool:
    """系统"显示动画"开关；关掉时直接显示目标值，不加额外设置项。"""
    try:
        value = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(
            _SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0)
        return bool(value.value) if ok else True
    except Exception:  # noqa: BLE001 - 拿不到就按"允许动画"处理
        return True

KIND_TITLES = {
    "keyboard": "键盘",
    "mouse": "鼠标",
}


def asset_path(name: str) -> str:
    return str(identity.resource_dir() / "assets" / name)


def app_icon() -> QIcon:
    icon = QIcon(asset_path("app.ico"))
    if icon.isNull():
        icon = QIcon(asset_path("app-256.png"))
    return icon


def colour_for(level: Optional[int], low: int, online: bool) -> str:
    if level is None or not online:
        return MUTED
    if level <= config_low_visual(low):
        return AMBER
    return GREEN


def config_low_visual(low: int) -> int:
    return cfgmod.low_visual(low)


def icon_pixmap(level: Optional[int], charging: Optional[bool], size: int = 64,
                low: int = 20, online: bool = True, mode: str = "number",
                light_taskbar: bool = True) -> QPixmap:
    """托盘/任务栏图标：数字模式画环+数字，电池模式画电池轮廓。"""
    ratio = 1.0
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    base = QColor("#1f2937" if light_taskbar else "#f8fafc")
    colour = QColor(colour_for(level, low, online))
    margin = size * 0.06
    rect = pixmap.rect().adjusted(int(margin), int(margin), -int(margin), -int(margin))
    if mode == "battery":
        body = rect.adjusted(0, int(size * 0.18), -int(size * 0.14), -int(size * 0.18))
        pen = QPen(colour if level is not None and online else QColor(MUTED), max(1.4, size * 0.075))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(body, size * 0.08, size * 0.08)
        cap = body.adjusted(body.width(), int(body.height() * 0.25), int(size * 0.09), -int(body.height() * 0.25))
        painter.setBrush(pen.color())
        painter.drawRoundedRect(cap, size * 0.03, size * 0.03)
        if level is not None and online:
            fill = body.adjusted(0, 0, -int(body.width() * (1 - min(100, max(0, level)) / 100.0)), 0)
            painter.setBrush(pen.color())
            painter.drawRoundedRect(fill.adjusted(2, 2, -2, -2), size * 0.05, size * 0.05)
    else:
        pen = QPen(colour if online else QColor(MUTED), max(1.5, size * 0.09))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect.adjusted(2, 2, -2, -2), 90 * 16, -int(360 * 16 * (1.0 if level is None else level / 100.0)))
        text = "—" if level is None else str(int(level))
        font = QFont()
        font.setPixelSize(int(size * (0.46 if len(text) < 3 else 0.36)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(TEXT if light_taskbar else "#f8fafc")))
        painter.drawText(rect, Qt.AlignCenter, text)
    painter.end()
    return pixmap


def tray_icon(device: Device, low: int, mode: str, light_taskbar: bool = True) -> QIcon:
    sample = device.sample
    return QIcon(icon_pixmap(sample.level, sample.charging, 64, low, sample.online, mode, light_taskbar))


def device_glyph(kind: str, colour: str, size: int = 14, variant: str = "A") -> QPixmap:
    """电量条上的鼠标/键盘小图形：统一用 Lucide 图标，variant 仅保留兼容参数。"""
    del variant
    return icons.bar_pixmap(kind, colour, size)


_BLUETOOTH_PATH = (
    "M17.71,7.71L12,2h-1v7.59L6.41,5 5,6.41 10.59,12 5,17.59 6.41,19 11,14.41V22h1l5.71,"
    "-5.71 -4.3,-4.29 4.3,-4.29zM13,5.83l1.88,1.88L13,9.59V5.83zM14.88,16.29L13,18.17v-3.76z"
)
_USB_PATH = (
    "M15,7v4h1v2h-3V5h2l-3-4-3,4h2v8H8v-2.07c0.7-0.37 1.2-1.1 1.2-1.93c0-1.21-0.99-2.2-2.2-2.2"
    "c-1.21,0-2.2,0.99-2.2,2.2c0,0.83 0.5,1.56 1.2,1.93V13c0,1.11 0.89,2 2,2h3v3.05c-0.71,0.37-1.2,1.1-1.2,1.95"
    "c0,1.22 0.99,2.2 2.2,2.2c1.21,0 2.2-0.98 2.2-2.2c0-0.85-0.49-1.58-1.2-1.95V15h3c1.11,0 2-0.89 2-2v-2h1V7H15z"
)
_GLYPH_CACHE: Dict[tuple, QPixmap] = {}


def bluetooth_glyph(colour: str, size: int = 14) -> QPixmap:
    """标准蓝牙符文（Material 图标路径），比手画的折线更像大家认得的那个标。"""
    key = (colour, size)
    cached = _GLYPH_CACHE.get(key)
    if cached is not None:
        return cached
    ratio = QGuiApplication.instance().devicePixelRatio() if QGuiApplication.instance() else 1.0
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           '<path fill="%s" d="%s"/></svg>' % (colour, _BLUETOOTH_PATH))
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    _GLYPH_CACHE[key] = pixmap
    return pixmap


_REFRESH_PATH = (
    "M17.65,6.35C16.2,4.9 14.21,4 12,4c-4.42,0-7.99,3.58-7.99,8s3.57,8 7.99,8"
    "c3.73,0 6.84-2.55 7.73-6h-2.08c-0.82,2.33-3.04,4-5.65,4c-3.31,0-6-2.69-6-6"
    "s2.69-6 6-6c1.66,0 3.14,0.69 4.22,1.78L13,11h7V4l-2.35,2.35z"
)


def usb_glyph(colour: str, size: int = 14) -> QPixmap:
    """USB 三叉标（Material usb 路径），与蓝牙徽标同尺寸同风格。"""
    key = ("usb:" + colour, size)
    cached = _GLYPH_CACHE.get(key)
    if cached is not None:
        return cached
    ratio = QGuiApplication.instance().devicePixelRatio() if QGuiApplication.instance() else 1.0
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           '<path fill="%s" d="%s"/></svg>' % (colour, _USB_PATH))
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    _GLYPH_CACHE[key] = pixmap
    return pixmap


def refresh_glyph(colour: str, size: int = 14) -> QIcon:
    """刷新按钮的小图标：与徽标同一条矢量路径思路，避免 Unicode 箭头在不同字体下发虚。"""
    key = ("refresh:" + colour, size)
    cached = _GLYPH_CACHE.get(key)
    if cached is None:
        ratio = QGuiApplication.instance().devicePixelRatio() if QGuiApplication.instance() else 1.0
        pixmap = QPixmap(int(size * ratio), int(size * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
               '<path fill="%s" d="%s"/></svg>' % (colour, _REFRESH_PATH))
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        cached = QIcon(pixmap)
        _GLYPH_CACHE[key] = cached
    return cached

def kind_glyph(kind: str, colour: str, size: int = 24) -> QPixmap:
    """设备类型图标：Lucide（ISC）线稿，按目标尺寸重新渲染。"""
    return icons.kind_pixmap(kind, colour, size)


def _nav_icon(painter: QPainter, rect: QRectF, kind: str, colour: str) -> None:
    """侧栏导航图标：同样是 Lucide 线稿。"""
    side = int(min(rect.width(), rect.height()))
    pixmap = icons.nav_pixmap(kind, colour, side)
    painter.drawPixmap(int(rect.left()), int(rect.top()), pixmap)


class ConnectionBadge(QWidget):
    """连接方式徽标：蓝牙用蓝底白标，接收器用灰标，替代压在设备名下面的说明文字。"""

    COLORS = {
        "ble": ("#2f5bea", "#ffffff"),
        "usb": ("#475569", "#ffffff"),
        "unknown": ("#f1f4f9", "#9aa3ad"),
    }

    def __init__(self) -> None:
        super().__init__()
        self._kind = "unknown"
        self.setFixedSize(22, 22)
        self.setToolTip("连接方式未知")

    def set_connection(self, kind: str, text: str) -> None:
        self._kind = kind if kind in self.COLORS else "unknown"
        self.setToolTip(text)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        background, foreground = self.COLORS[self._kind]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 7, 7)
        if self._kind in ("ble", "usb"):
            glyph = bluetooth_glyph(foreground, 17) if self._kind == "ble" else usb_glyph(foreground, 17)
            side = glyph.width() / max(1.0, glyph.devicePixelRatio())
            painter.drawPixmap(int((self.width() - side) / 2), int((self.height() - side) / 2), glyph)
        else:
            font = QFont(self.font())
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor(foreground)))
            painter.drawText(self.rect(), Qt.AlignCenter, "?")
        painter.end()


class ChevronCombo(QComboBox):
    """统一的下拉外观：浅灰胶囊 + 自绘箭头（原生箭头在高 DPI 下发虚）。"""

    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(30)
        self.setStyleSheet(
            "QComboBox { background: #f1f1f1; border: 1px solid #e2e2e2; border-radius: 15px;"
            " padding: 4px 28px 4px 12px; font-size: 12px; color: %s; min-width: 76px; }"
            "QComboBox:hover { background: #e8eef8; }"
            "QComboBox:focus { background: #e8eef8; }"
            "QComboBox::drop-down { border: none; width: 0px; }"
            "QComboBox::down-arrow { image: none; }"
            "QComboBox QAbstractItemView { background: #ffffff; border: 1px solid %s;"
            " padding: 4px; outline: none; selection-background-color: #eef3ff;"
            " selection-color: #252525; }" % (TEXT, BORDER)
        )

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(MUTED), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = self.width() - 14.0
        cy = self.height() / 2.0
        painter.drawLine(QPointF(cx - 3.6, cy - 1.6), QPointF(cx, cy + 2.0))
        painter.drawLine(QPointF(cx, cy + 2.0), QPointF(cx + 3.6, cy - 1.6))
        painter.end()


class SegmentedChoice(QWidget):
    """两项以内的选项用分段按钮：一次点选，比下拉少一步；接口按 QComboBox 的子集实现。"""

    currentIndexChanged = Signal(int)

    def __init__(self, options: Sequence[tuple[str, object]]) -> None:
        super().__init__()
        self._values = [value for _label, value in options]
        self._index = 0
        self.setObjectName("segmented")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#segmented { background: #f1f1f1; border-radius: 15px; }"
            "QPushButton { border: none; border-radius: 12px; padding: 4px 14px;"
            " font-size: 12px; color: %s; background: transparent; }"
            "QPushButton:hover { color: %s; }"
            "QPushButton:checked { background: #ffffff; color: %s; font-weight: 600; }"
            "QPushButton:focus { outline: none; }" % (MUTED, TEXT, TEXT)
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        self._buttons: List[QPushButton] = []
        for index, (label, _value) in enumerate(options):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(24)
            button.clicked.connect(lambda _checked=False, i=index: self._choose(i))
            row.addWidget(button)
            self._buttons.append(button)

    def _choose(self, index: int) -> None:
        if index == self._index:
            self._sync()
            return
        self._index = index
        self._sync()
        self.currentIndexChanged.emit(index)

    def _sync(self) -> None:
        for position, button in enumerate(self._buttons):
            button.setChecked(position == self._index)

    def currentIndex(self) -> int:  # noqa: N802 - 与 QComboBox 对齐
        return self._index

    def currentData(self):
        return self._values[self._index]

    def findData(self, value) -> int:  # noqa: N802 - 与 QComboBox 对齐
        try:
            return self._values.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 - 与 QComboBox 对齐
        if 0 <= index < len(self._values):
            self._index = index
            self._sync()


class DeviceCard(QFrame):
    """设备卡：读数变化时做 650ms 收起动画，只影响展示，不改 Sample。"""

    ANIM_MS = 650
    rename_requested = Signal(str)
    reset_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        self._offline = False
        self._device_key = ""
        self._alias = ""
        # 右键菜单：重命名 / 恢复默认名称（0.4.2 起）
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.setStyleSheet(
                           "QFrame#card { background: %s; border: 1px solid %s; border-radius: 14px; }" % (CARD, BORDER))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 16)
        layout.setSpacing(9)
        top = QHBoxLayout()
        top.setSpacing(12)
        left = QHBoxLayout()
        left.setSpacing(9)
        self.kind_mark = QLabel()
        self.kind_mark.setFixedSize(27, 27)
        self.kind_mark.setAlignment(Qt.AlignCenter)
        self.name = QLabel("—")
        self.name.setStyleSheet("font-size: 15px; font-weight: 600; color: %s;" % TEXT)
        self.name.setWordWrap(True)
        self.badge = ConnectionBadge()
        left.addWidget(self.kind_mark, 0, Qt.AlignVCenter)
        left.addWidget(self.name, 0, Qt.AlignVCenter)
        left.addWidget(self.badge, 0, Qt.AlignVCenter)
        left.addStretch(1)
        self.level = QLabel("—")
        self.level.setStyleSheet("font-size: 34px; font-weight: 600; color: %s;" % TEXT)
        self.level.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addLayout(left, 1)
        top.addWidget(self.level)
        layout.addLayout(top)
        # 更粗的电量条：两端全圆角，自己画在 paintEvent 里，避免子控件被裁成方角
        self.bar_slot = QWidget(self)
        self.bar_slot.setFixedHeight(10)
        self.bar_slot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.bar_slot)
        bottom = QHBoxLayout()
        self.state = QLabel("—")
        self.state.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        self.updated = QLabel("")
        self.updated.setStyleSheet("font-size: 11px; color: %s;" % MUTED)
        self.updated.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self.state)
        bottom.addWidget(self.updated, 1)
        layout.addLayout(bottom)
        self._kind = "device"
        self._level: Optional[int] = None
        self._colour = GREEN
        self._fraction: Optional[float] = None     # 电量条填充比例（真实读数）
        self._shown: Optional[float] = None       # 屏幕当前显示的浮点进度
        self._target: Optional[float] = None      # 最近一次真实读数
        self._entered = False                     # 是否已播放过入场动画
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(self.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)

    # ---------- 类型图标 / 离线底色 ----------
    def _set_kind(self, kind: Optional[str], online: bool) -> None:
        self._kind = kind or "device"
        colour = TEXT if online else MUTED
        self.kind_mark.setPixmap(kind_glyph(self._kind, colour, 22))
        self.kind_mark.setToolTip({"keyboard": "键盘", "mouse": "鼠标", "headset": "耳机",
                                   "gamepad": "手柄"}.get(self._kind, "设备类型未知"))

    def _context_menu(self, pos) -> None:
        if not self._device_key:
            return
        menu = QMenu(self)
        rename = menu.addAction("重命名…")
        reset = menu.addAction("恢复默认名称")
        reset.setEnabled(bool(self._alias))
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is rename:
            self.rename_requested.emit(self._device_key)
        elif chosen is reset:
            self.reset_requested.emit(self._device_key)

    def _set_offline_look(self, offline: bool) -> None:
        self._offline = bool(offline)
        background = OFFLINE_CARD if offline else CARD
        self.setStyleSheet("QFrame#card { background: %s; border: 1px solid %s;"
                           " border-radius: 14px; }" % (background, BORDER))

    # ---------- 动画 ----------
    def _on_anim_value(self, value) -> None:
        self._shown = float(value)
        self._paint_level(self._shown)

    def _paint_level(self, value: Optional[float]) -> None:
        if value is None:
            self.level.setText("—")
            self.level.setStyleSheet("font-size: 34px; font-weight: 600; color: %s;" % MUTED)
            self._set_bar_fraction(None)
            return
        self.level.setText("%d%%" % int(round(value)))
        self._set_bar_fraction(value)

    def _set_bar_fraction(self, value: Optional[float]) -> None:
        if value is None:
            self._level = None
            self._fraction = None
        else:
            level = max(0.0, min(100.0, float(value)))
            self._level = int(round(level))
            self._fraction = level / 100.0
        self.update()

    def _bar_visible(self) -> bool:
        """离线卡不要画电量条：bar_slot 被 hide() 后 geometry 仍在，不能只看 rect。"""
        return not self._offline and not self.bar_slot.isHidden()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().paintEvent(event)
        if not self._bar_visible():
            return
        rect = QRectF(self.bar_slot.geometry())
        if rect.width() <= 0 or rect.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        radius = rect.height() / 2.0
        painter.setBrush(QColor(BATTERY_TRACK))
        painter.drawRoundedRect(rect, radius, radius)
        if self._fraction is None or self._fraction <= 0:
            painter.end()
            return
        filled = QRectF(rect.left(), rect.top(), max(rect.height(), rect.width() * self._fraction),
                        rect.height())
        cover = min(radius, filled.width() / 2.0)
        painter.setBrush(QColor(self._colour))
        painter.drawRoundedRect(filled, cover, cover)
        painter.end()

    def _animate_to(self, target: Optional[float], *, visible: bool) -> None:
        """目标为空＝未知；可见时才播，隐藏或关闭动画时直接落到目标。"""
        self._target = target
        if target is None:
            self._anim.stop()
            self._shown = None
            self._paint_level(None)
            return
        if self._anim.state() == QVariantAnimation.Running:
            self._anim.stop()
        start = self._shown
        if not visible or not animations_enabled():
            self._entered = True
            self._shown = target
            self._paint_level(target)
            return
        if start is None:
            if self._entered:
                # 之前真正显示过读数，重新有值时不从零播，直接显示
                self._shown = target
                self._paint_level(target)
                return
            start = 0.0
        if abs(target - start) < 0.5:
            self._entered = True
            self._shown = target
            self._paint_level(target)
            return
        self._entered = True
        self._anim.stop()
        self._anim.setStartValue(float(start))
        self._anim.setEndValue(float(target))
        self._anim.start()

    def finish_animation(self) -> None:
        """隐藏页面或被要求减少动画时，直接落到最新目标。"""
        self._anim.stop()
        if self._target is None:
            self._shown = None
            self._paint_level(None)
        else:
            self._shown = self._target
            self._paint_level(self._shown)

    def update_view(self, device: Optional[Device], low: int, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        if device is None:
            self.name.setText("等待设备")
            self.badge.set_connection("unknown", "连接方式未知")
            self.kind_mark.clear()
            self._set_offline_look(False)
            self.state.setText("尚未检测到设备")
            self.updated.setText("")
            self._colour = MUTED
            self._animate_to(None, visible=False)
            return
        sample = device.sample
        self._device_key = device.key
        self._alias = getattr(device, "alias", "") or ""
        self.name.setText(device.name)
        self.badge.set_connection(device.connection, device.connection_text)
        self._set_kind(device.kind, sample.online and getattr(sample, "confirmed", True))
        self._set_offline_look(False)
        if not sample.online:
            self.show_offline(device)
            return
        if not getattr(sample, "confirmed", True):
            # 失去状态证据：不显示旧电量、不判断开，只标"状态待确认"。
            self._anim.stop()
            self._target = None
            self._shown = None
            self.level.setText("—")
            self.level.setStyleSheet("font-size: 34px; font-weight: 600; color: %s;" % MUTED)
            self.level.show()
            self.bar_slot.hide()
            self.state.setText("状态待确认")
            self.state.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
            self.updated.setText(updated_text(device, now))
            return
        # 恢复在线形态（断连时曾把数字与电量条藏起来）
        self.level.show()
        self.bar_slot.show()
        level = sample.level
        # 颜色一律用真实读数，动画只是展示层，避免途经低值触发视觉误判
        self._colour = colour_for(level, low, sample.online)
        self.level.setStyleSheet("font-size: 34px; font-weight: 600; color: %s;" % self._colour)
        self.state.setText(state_text(device))
        self.state.setStyleSheet("font-size: 12px; color: %s;" % self._colour)
        self.updated.setText(updated_text(device, now))
        target = float(level) if level is not None else None
        visible = self.isVisible()
        if device.stale or not sample.online:
            # 旧读数直接展示并标旧，动画不能为它生成"从 0 涨上来"的假过程
            if target is not None:
                # 只有真的显示出读数才算"已入场"，None 占位不消耗首次动效
                self._entered = True
            self.finish_animation_target(target)
            return
        if target is not None and self._target is not None and abs(target - self._target) < 0.5:
            # 目标没变（只是又刷新了一轮）：保留现有时间轴，不重新计时
            if self._anim.state() != QVariantAnimation.Running:
                self._paint_level(self._shown)
            return
        playing = self._anim.state() == QVariantAnimation.Running
        same = target is not None and self._shown is not None and abs(target - self._shown) < 0.5
        if not playing and same:
            self._paint_level(self._shown)  # 只更新时间文案，不重播
            return
        self._animate_to(target, visible=visible)

    def finish_animation_target(self, target: Optional[float]) -> None:
        self._target = target
        self._anim.stop()
        self._shown = target
        self._paint_level(target)

    def show_offline(self, device: Device, now: Optional[float] = None) -> None:
        """断开后保留记录：隐藏百分比与电量条，只说明"未连接"和上次连接时间。"""
        self._device_key = device.key
        self._alias = getattr(device, "alias", "") or ""
        self.name.setText(device.name)
        self._set_kind(device.kind, False)
        self._set_offline_look(True)
        self._anim.stop()
        self._target = None
        self._shown = None
        self._fraction = None
        self._level = None
        self._entered = False  # 重连时重新从 0 涨上来
        self.level.setText("未连接")
        self.level.setStyleSheet("font-size: 16px; font-weight: 600; color: %s;" % MUTED)
        self.bar_slot.hide()
        self.state.setText("未连接")
        self.state.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        self.updated.setText(last_connected_text(device, now))
        self.update()

    def set_highlight(self, on: bool, colour: str = HIGHLIGHT) -> None:
        """最新连接置顶时的短暂强调：只改描边，不改变尺寸，避免影响布局动画。"""
        border = colour if on else BORDER
        background = OFFLINE_CARD if self._offline else CARD
        self.setStyleSheet("QFrame#card { background: %s; border: 1px solid %s; border-radius: 14px; }"
                           % (background, border))

    def _set_bar(self, level: Optional[int], colour: str) -> None:
        self._colour = colour
        self._set_bar_fraction(level)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().resizeEvent(event)
        self._set_bar_fraction(self._shown)


def state_text(device: Device) -> str:
    sample = device.sample
    if not getattr(sample, "confirmed", True):
        return "状态待确认"
    if not sample.online:
        return "未连接"
    if sample.level is None:
        return "电量暂不可用"
    if sample.charging is True:
        return "充电中"
    if sample.charging is False:
        return "未充电"
    return "充电状态未知"


def last_connected_text(device: Device, now: Optional[float] = None) -> str:
    stamp = device.last_connected
    if not stamp:
        return "没有连接记录"
    age = max(0.0, (now or time.time()) - stamp)
    if age < 60:
        return "上次连接：刚刚"
    if age < 3600:
        return "上次连接：%d 分钟前" % int(age // 60)
    return "上次连接：" + time.strftime("%m-%d %H:%M", time.localtime(stamp))


def updated_text(device: Device, now: float) -> str:
    sample = device.sample
    stamp = sample.sampled_at
    if not stamp:
        return "无有效读数"
    age = max(0.0, now - stamp)
    fresh = age < 90
    if fresh:
        return "刚刚更新"
    if age < 3600:
        return "%d 分钟前" % int(age // 60)
    return time.strftime("%m-%d %H:%M", time.localtime(stamp))


class DeviceListPanel(QWidget):
    rename_requested = Signal(str)
    reset_requested = Signal(str)
    """动态设备列表：记录几张卡就有几张卡，连接插入、断开下移、重连置顶。

    Qt 的 layout 与几何动画会互相争夺，所以这里不用 QVBoxLayout 排卡片，
    而是记住动画前的位置、算好最终位置，再用 QPropertyAnimation 过渡到目标，
    动画结束后布局与视觉顺序、Tab 顺序完全一致。
    """

    GAP = 14
    MOVE_MS = 620
    FOCUS_MS = 760
    NEW_OFFSET = 38
    FADE_MS = 220

    def __init__(self) -> None:
        super().__init__()
        self._cards: Dict[str, DeviceCard] = {}
        self._last: Optional[tuple] = None
        self._order: List[str] = []
        self._online: Dict[str, bool] = {}
        self._anims: Dict[str, QPropertyAnimation] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        self.pages = QStackedWidget()
        self.empty = self._build_empty()
        self.pages.addWidget(self.empty)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.canvas = QWidget()
        self.canvas.setStyleSheet("background: transparent;")
        self.scroll.setWidget(self.canvas)
        self.pages.addWidget(self.scroll)
        outer.addWidget(self.pages, 1)

    # ---------- 空状态 ----------
    def _build_empty(self) -> QWidget:
        box = QFrame()
        box.setObjectName("emptyBox")
        box.setStyleSheet("QFrame#emptyBox { background: %s; border: 1px dashed #ccd8e8;"
                          " border-radius: 15px; }" % OFFLINE_CARD)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(24, 40, 24, 40)
        layout.setSpacing(10)
        layout.addStretch(1)
        title = QLabel("连接设备后，电量会显示在这里")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #303030;")
        hint = QLabel("不预留空卡片，设备连接时自动加入列表。")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch(1)
        return box

    # ---------- 渲染 ----------
    @staticmethod
    def _sort_key(device: Device) -> tuple:
        online = 1 if device.sample.online else 0
        return (-online, -int(device.order or 0), -float(device.last_connected or 0.0), device.key)

    def card_order(self) -> List[str]:
        return list(self._order)

    def render(self, devices: Sequence[Device], low: int, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        ordered = sorted(devices, key=self._sort_key)
        before = {key: card.pos().y() for key, card in self._cards.items()}
        previous = dict(self._online)
        featured: Optional[str] = None
        for device in ordered:
            was = previous.get(device.key)
            if device.sample.online and was is not True:
                featured = device.key
                break
        wanted = {device.key for device in ordered}
        for device in ordered:
            card = self._cards.get(device.key)
            if card is None:
                card = DeviceCard()
                card.setParent(self.canvas)
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                card.rename_requested.connect(self.rename_requested)
                card.reset_requested.connect(self.reset_requested)
                card.show()
                self._cards[device.key] = card
            card.update_view(device, low, now)
            self._online[device.key] = device.sample.online
        for key in list(self._cards):
            if key not in wanted:
                self._stop_anim(key)
                self._cards.pop(key).deleteLater()
                self._online.pop(key, None)
                before.pop(key, None)
        self._order = [device.key for device in ordered]
        self._last = (ordered, low, now)
        self._layout(before, featured)
        online = sum(1 for device in ordered if device.sample.online)
        self.pages.setCurrentIndex(1 if ordered else 0)
        if featured is not None:
            self.scroll.verticalScrollBar().setValue(0)

    def _layout(self, before: Dict[str, float], featured: Optional[str]) -> None:
        width = max(320, self.scroll.viewport().width() - 16)
        targets: Dict[str, int] = {}
        y = 0
        for key in self._order:
            card = self._cards[key]
            # 先解除上一轮的固定高度，否则离线卡缩短后 sizeHint 仍是被锁住的旧值，
            # 会把下一张卡算到重叠。
            card.setMinimumHeight(0)
            card.setMaximumHeight(16777215)
            card.setFixedWidth(width)
            layout = card.layout()
            if layout is not None:
                layout.activate()  # 让刚改过的文案先参与测量，否则拿到上一轮的高度
            card.setFixedHeight(max(104, card.sizeHint().height()))
            card.move(4, card.y())
            targets[key] = y
            y += card.height() + self.GAP
        self.canvas.setFixedHeight(max(0, y - self.GAP))
        animate = animations_enabled()
        for key, target in targets.items():
            card = self._cards[key]
            self._stop_anim(key)
            old = before.get(key)
            if old is None:
                card.move(4, target if not animate else target + self.NEW_OFFSET)
                if animate:
                    self._fade_in(card)
                else:
                    card.move(4, target)
                continue
            if animate and abs(old - target) >= 1:
                anim = QPropertyAnimation(card, b"pos", self)
                anim.setDuration(self.FOCUS_MS if key == featured else self.MOVE_MS)
                anim.setEasingCurve(QEasingCurve.OutQuart)
                anim.setStartValue(QPoint(4, int(old)))
                anim.setEndValue(QPoint(4, target))
                anim.start()
                self._anims[key] = anim
            else:
                card.move(4, target)
        if featured is not None:
            card = self._cards.get(featured)
            if card is not None:
                card.set_highlight(True)
                QTimer.singleShot(self.FOCUS_MS, lambda c=card: c.set_highlight(False))

    def relayout(self) -> None:
        """窗口显示后重新量一遍高度：首帧测量时字体样式可能还没生效。"""
        if self._last is None or not self._cards:
            return
        before = {key: card.pos().y() for key, card in self._cards.items()}
        self._layout(before, None)

    def _fade_in(self, card: DeviceCard) -> None:
        effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(self.FADE_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: card.setGraphicsEffect(None))
        anim.start()
        self._anims[card.objectName() or str(id(card))] = anim

    def _stop_anim(self, key: str) -> None:
        anim = self._anims.pop(key, None)
        if anim is not None:
            anim.stop()

    def finish_animations(self) -> None:
        for key in list(self._anims):
            self._stop_anim(key)
        for key in self._order:
            card = self._cards[key]
            card.setGraphicsEffect(None)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().resizeEvent(event)
        if self._order:
            self._layout({}, None)


class Switch(QAbstractButton):
    """紧凑开关：可 Tab 聚焦、空格切换；只作为表单控件，提交仍走"保存设置"。"""

    WIDTH = 40
    HEIGHT = 22

    def __init__(self) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        radius = self.HEIGHT / 2.0
        rect = QRectF(0.5, 0.5, self.WIDTH - 1.0, self.HEIGHT - 1.0)
        track = ACCENT if self.isChecked() else "#d4d4d4"
        painter.setPen(QPen(QColor(track), 1))
        painter.setBrush(QColor(track))
        painter.drawRoundedRect(rect, radius, radius)
        knob = radius - 3.0
        cx = self.WIDTH - radius if self.isChecked() else radius
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPointF(cx, self.HEIGHT / 2.0), knob, knob)
        if self.hasFocus():
            painter.setPen(QPen(QColor("#b9c7ee"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(1.0, 1.0, self.WIDTH - 2.0, self.HEIGHT - 2.0),
                                    radius, radius)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)


class SettingsPage(QWidget):
    apply_requested = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._loaded: dict = {}
        self._loading = False
        self._autostart_touched = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            "QFrame#card { background: %s; border: 1px solid %s; border-radius: 14px; }" % (CARD, BORDER))
        body = QVBoxLayout(card)
        body.setContentsMargins(24, 8, 24, 12)
        body.setSpacing(0)
        self._group(body, "显示")
        self.tray_icon = self._combo_row(body, "托盘图标", "数字更直观，电池图标更小",
                                         [("数字", "number"), ("电池图标", "battery")],
                                         segmented=True)
        self.desktop_bar = self._check_row(body, "桌面电量条", "在任务栏显示「键盘 100% | 鼠标 100%」")
        self._group(body, "提醒与刷新")
        self.low = self._combo_row(body, "低电量提醒", "关闭后不再弹出低电量通知",
                                   [("关闭", 0)] + [("%d%%" % v, v) for v in cfgmod.LOW_CHOICES if v > 0])
        self.interval = self._combo_row(body, "刷新间隔", "多久读取一次电量",
                                        [("%d 秒" % v, v) for v in cfgmod.INTERVAL_CHOICES])
        self._group(body, "启动")
        self.autostart = self._check_row(body, "开机启动", "登录 Windows 后在后台启动")
        self.autostart.toggled.connect(self._on_autostart_toggled)
        self.autostart_note = QLabel("")
        self.autostart_note.setStyleSheet("font-size: 11px; color: %s;" % MUTED)
        self.autostart_note.setWordWrap(True)
        body.addWidget(self.autostart_note)
        outer.addWidget(card)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        self.feedback = QLabel("")
        self.feedback.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        self.feedback.setMinimumHeight(20)
        self.save = QPushButton("保存设置")
        self.save.setCursor(Qt.PointingHandCursor)
        self.save.setMinimumHeight(38)
        self.save.setMinimumWidth(112)
        self.save.setStyleSheet(
            "QPushButton { background: %s; color: #ffffff; border: none; border-radius: 10px;"
            " padding: 0 20px; font-size: 13px; }"
            "QPushButton:hover { background: #375ac4; }"
            "QPushButton:pressed { background: #2f4cae; }"
            "QPushButton:disabled { background: #a9b7d8; }"
            "QPushButton:focus { outline: none; border: 2px solid #c9c9c9; }" % ACCENT)
        self.save.clicked.connect(self._emit)
        actions.addWidget(self.feedback, 1)
        actions.addWidget(self.save)
        outer.addLayout(actions)
        outer.addStretch(1)
        self._loaded: Dict[str, object] = {}

    def _group(self, parent: QVBoxLayout, title: str) -> None:
        label = QLabel(title)
        label.setStyleSheet("font-size: 12px; font-weight: 600; color: %s; padding-top: 10px;"
                            " padding-bottom: 2px;" % MUTED)
        parent.addSpacing(6)
        parent.addWidget(label)

    def _row(self, parent: QVBoxLayout, title: str, hint: str) -> QHBoxLayout:
        wrapper = QFrame()
        wrapper.setStyleSheet("border-bottom: 1px solid %s;" % BORDER)
        wrapper.setMinimumHeight(68)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(3)
        head = QLabel(title)
        head.setStyleSheet("font-size: 13px; font-weight: 600; color: %s;" % TEXT)
        sub = QLabel(hint)
        sub.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        left.addWidget(head)
        left.addWidget(sub)
        row.addLayout(left, 1)
        parent.addWidget(wrapper)
        return row

    def _combo_row(self, parent: QVBoxLayout, title: str, hint: str,
                   options: Sequence[tuple[str, object]], segmented: bool = False):
        row = self._row(parent, title, hint)
        if segmented and len(options) <= 2:
            control = SegmentedChoice(options)
        else:
            control = ChevronCombo()
            for label, value in options:
                control.addItem(label, value)
            control.setMinimumWidth(96)
        row.addWidget(control, 0, Qt.AlignVCenter)
        return control

    def _check_row(self, parent: QVBoxLayout, title: str, hint: str) -> Switch:
        row = self._row(parent, title, hint)
        box = Switch()
        row.addWidget(box, 0, Qt.AlignVCenter)
        return box

    def load(self, cfg: dict) -> None:
        self._loaded = dict(cfg)
        self._loading = True
        self._set_combo(self.interval, cfg.get("interval", cfgmod.INTERVAL_DEFAULT))
        self._set_combo(self.low, cfg.get("low", cfgmod.LOW_DEFAULT))
        self._set_combo(self.tray_icon, cfg.get("tray_icon", cfgmod.TRAY_ICON_DEFAULT))
        self.desktop_bar.setChecked(bool(cfg.get("desktop_bar")))
        self.autostart.setChecked(bool(cfg.get("autostart")))
        self._autostart_touched = False
        self._loading = False
        self.feedback.setText("")

    def _on_autostart_toggled(self, _checked: bool) -> None:
        """只有用户亲手改这一项，才允许在保存时动注册表。"""
        if not self._loading:
            self._autostart_touched = True

    def set_autostart_state(self, checked: bool, note: str, warn: bool = False) -> None:
        """按注册表实际状态勾选并解释；不改注册表，也不覆盖用户的其它设置。"""
        self._loading = True
        self.autostart.setChecked(bool(checked))
        self._loading = False
        self._autostart_touched = False
        self.set_autostart_note(note, warn)

    def _set_combo(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def payload(self) -> dict:
        return {
            "interval": self.interval.currentData(),
            "low": self.low.currentData(),
            "tray_icon": self.tray_icon.currentData(),
            "desktop_bar": self.desktop_bar.isChecked(),
            "autostart": self.autostart.isChecked(),
            # 只在用户亲手改过开机启动时才让保存去动注册表
            "autostart_changed": self._autostart_touched,
        }

    def _emit(self) -> None:
        self.apply_requested.emit(self.payload())

    def show_result(self, ok: bool, message: str) -> None:
        if ok:
            self.feedback.setStyleSheet("font-size: 12px; color: %s;" % GREEN)
            self.feedback.setText(message or "已保存")
            self._loaded = self.payload()
        else:
            self.feedback.setStyleSheet("font-size: 12px; color: %s;" % RED)
            self.feedback.setText(message or "保存失败")
            self.load(self._loaded)

    def set_autostart_note(self, text: str, warn: bool = False) -> None:
        """显示注册表的实际状态；与配置不一致时如实说明，不改写启动项。"""
        self.autostart_note.setText(text)
        colour = AMBER if warn else MUTED
        self.autostart_note.setStyleSheet("font-size: 11px; color: %s;" % colour)


class NavButton(QPushButton):
    """侧栏导航（C 组）：圆角底座 + 矢量图标，选中行灰底白底座。"""

    BASE = 30.0
    ICON = 22.0
    GAP = 11.0

    def __init__(self, label: str, kind: str) -> None:
        super().__init__(label)
        self._kind = kind
        self._hover = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        # 自绘选中态，不要让 Qt 再画虚线焦点框（截图里会像一圈毛边）
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet("background: transparent; border: none; padding: 0;")

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        checked = self.isChecked()
        width, height = float(self.width()), float(self.height())
        row = QRectF(0.5, 0.5, width - 1.0, height - 1.0)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ebebeb"))
            painter.drawRoundedRect(row, 9.0, 9.0)
        elif self._hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#f2f2f2"))
            painter.drawRoundedRect(row, 9.0, 9.0)
        left = 10.0
        base = QRectF(left, (height - self.BASE) / 2.0, self.BASE, self.BASE)
        painter.setPen(QPen(QColor("#dedede"), 1.0) if checked else Qt.NoPen)
        painter.setBrush(QColor("#ffffff") if checked else QColor("#eeeeee"))
        painter.drawRoundedRect(base, 6.0, 6.0)
        icon_rect = QRectF(base.left() + (self.BASE - self.ICON) / 2.0,
                           base.top() + (self.BASE - self.ICON) / 2.0,
                           self.ICON, self.ICON)
        colour = "#303030" if checked else "#6f6f6f"
        _nav_icon(painter, icon_rect, self._kind, colour)
        font = QFont(self.font())
        font.setPixelSize(13)
        font.setWeight(QFont.DemiBold if checked else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#303030" if checked else "#5f5f5f"))
        text_rect = QRectF(base.right() + self.GAP, 0.0, width - base.right() - self.GAP - 6.0, height)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#9c9c9c"), 1.0, Qt.DashLine))
            painter.drawRoundedRect(row.adjusted(1.5, 1.5, -1.5, -1.5), 8.0, 8.0)
        painter.end()


class MainWindow(QWidget):
    def __init__(self, on_refresh: Callable[[], None]) -> None:
        super().__init__()
        self.on_refresh = on_refresh
        self.on_close: Optional[Callable[[], bool]] = None
        self.settings_page = SettingsPage()
        self._allow_close = False
        self.device_list: Optional[DeviceListPanel] = None
        self.setWindowTitle(identity.APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(880, 620)
        self.setMinimumSize(760, 520)
        self.setStyleSheet("QWidget { font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif; }"
                           "QWidget#root { background: %s; }" % BG)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        root.addWidget(self._main(), 1)

    def _sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setMinimumWidth(190)
        side.setMaximumWidth(205)
        side.setStyleSheet("QFrame#sidebar { background: %s; border-right: 1px solid %s; }"
                           % (SIDEBAR, BORDER_SOFT))
        layout = QVBoxLayout(side)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(4)
        self.nav_devices = NavButton("设备", "devices")
        self.nav_settings = NavButton("设置", "settings")
        for button in (self.nav_devices, self.nav_settings):
            layout.addWidget(button)
        self.nav_devices.setChecked(True)
        self.nav_devices.clicked.connect(lambda: self.show_page(0))
        self.nav_settings.clicked.connect(lambda: self.show_page(1))
        layout.addStretch(1)
        self.quit_button = QPushButton("退出")
        self.quit_button.setCursor(Qt.PointingHandCursor)
        self.quit_button.setMinimumHeight(36)
        # 退出是"离开"动作，给它独立的浅色块，和导航区分开
        self.quit_button.setObjectName("quitButton")
        self.quit_button.setStyleSheet(
            "QPushButton#quitButton { text-align: center; background: #f4f4f4; border: 1px solid %s;"
            " border-radius: 10px; padding: 8px 12px; font-size: 13px; color: %s; }"
            "QPushButton#quitButton:hover { background: #ededed; color: %s; }"
            "QPushButton#quitButton:pressed { background: #e4e4e4; }"
            "QPushButton#quitButton:focus { outline: none; border: 1px solid #c9c9c9; }"
            % (BORDER_SOFT, MUTED, TEXT))
        layout.addWidget(self.quit_button)
        version = QLabel(identity.APP_VERSION)
        version.setStyleSheet("font-size: 10px; color: %s; padding-left: 6px;" % MUTED)
        layout.addWidget(version)
        return side

    def _main(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("root")
        panel.setStyleSheet("QWidget#root { background: %s; }" % BG)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(16)
        head = QVBoxLayout()
        head.setSpacing(4)
        self.title = QLabel("设备概览")
        self.title.setStyleSheet("font-size: 23px; font-weight: 700; color: %s;" % TEXT)
        self.subtitle = QLabel("正在读取…")
        self._devices_subtitle = "正在读取…"
        self._title_bar_done = False
        self.subtitle.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        head.addWidget(self.title)
        head.addWidget(self.subtitle)
        layout.addLayout(head)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._devices_page())
        self.stack.addWidget(self._settings_host())
        layout.addWidget(self.stack, 1)
        footer = QHBoxLayout()
        self.footer = QLabel("每 60 秒自动刷新")
        self.footer.setStyleSheet("font-size: 12px; color: %s;" % MUTED)
        self.refresh_button = QPushButton(" 立即刷新")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setMinimumHeight(38)
        self.refresh_button.setMinimumWidth(104)
        self.refresh_button.setIcon(refresh_glyph("#3F4A5C", 15))
        self.refresh_button.setIconSize(QSize(15, 15))
        self.refresh_button.setStyleSheet(
            "QPushButton { border: 1px solid %s; border-radius: 10px; padding: 0 18px;"
            " font-size: 13px; color: %s; background: %s; }"
            "QPushButton:hover { background: #f3f3f3; border-color: #d0d0d0; }"
            "QPushButton:pressed { background: #ececec; }"
            "QPushButton:disabled { color: %s; background: %s; border-color: %s; }"
            "QPushButton:focus { outline: none; border: 2px solid #c9c9c9; }"
            % (BORDER, TEXT, CARD, MUTED, SURFACE, BORDER))
        self.refresh_button.clicked.connect(self.on_refresh)
        footer.addWidget(self.footer, 1)
        footer.addWidget(self.refresh_button)
        layout.addLayout(footer)
        return panel

    def begin_refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        self.refresh_button.setIcon(refresh_glyph("#9AA3AD", 15))
        self.refresh_button.setText(" 刷新中…")

    def end_refresh(self, ok: bool = True, message: str = "") -> None:
        self.refresh_button.setEnabled(True)
        self.refresh_button.setIcon(refresh_glyph("#3F4A5C", 15))
        self.refresh_button.setText(" 立即刷新")
        if message:
            self.footer.setText(message)
        elif not ok:
            self.footer.setText("刷新未完成，稍后自动重试")

    def _devices_page(self) -> QWidget:
        self.device_list = DeviceListPanel()
        return self.device_list

    def showEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().showEvent(event)
        # 首帧渲染时字体/样式可能还没生效，卡片会被量矮；显示后补量两次。
        QTimer.singleShot(0, self.device_list.relayout)
        QTimer.singleShot(120, self.device_list.relayout)
        # Windows 11 默认让标题栏跟随系统强调色，会把灰白界面顶成一条色带
        if not self._title_bar_done:
            self._title_bar_done = True
            QTimer.singleShot(0, self._harmonize_title_bar)

    def _harmonize_title_bar(self) -> None:
        try:
            hwnd = int(self.winId())
        except (TypeError, ValueError):
            return
        set_title_bar_colours(hwnd, caption=BG, text=TEXT, border=BORDER)

    def _settings_host(self) -> QWidget:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.settings_page)
        return holder

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.nav_devices.setChecked(index == 0)
        self.nav_settings.setChecked(index == 1)
        self.title.setText("设备概览" if index == 0 else "偏好设置")
        if index == 1:
            self.subtitle.setText("保存后立即生效")
        else:
            self.subtitle.setText(self._devices_subtitle)
        self.settings_page.feedback.setText("")
        if index != 0:
            # 离开设备页：把进行中的动画直接落到最新目标，回来不重播
            if self.device_list is not None:
                self.device_list.finish_animations()

    def render_devices(self, devices: Sequence[Device], interval: int, low: int,
                       now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self.device_list.render(devices, low, now)
        online = sum(1 for device in devices if device.sample.online)
        if devices:
            self._devices_subtitle = "%d 台已记录 · %d 台已连接 · %d 台未连接" % (
                len(devices), online, len(devices) - online)
        else:
            self._devices_subtitle = "还没有设备记录"
        if self.stack.currentIndex() == 0:
            self.subtitle.setText(self._devices_subtitle)
        self.footer.setText("每 %d 秒自动刷新" % interval)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        if self._allow_close or self.on_close is None:
            self._allow_close = True
            super().closeEvent(event)
            return
        if self.on_close():
            event.ignore()
        else:
            super().closeEvent(event)

    def allow_close(self) -> None:
        self._allow_close = True
