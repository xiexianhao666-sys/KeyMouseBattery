"""Lucide 图标（ISC 授权）的着色渲染包装。

素材存放于 `assets/icons/lucide/*.svg`，原样保留上游 SVG，只在渲染前把
`currentColor` 与 `stroke-width` 替换成应用需要的颜色与线宽。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import identity

# 设备类型 → Lucide 文件名
KIND_ICONS = {
    "keyboard": "keyboard",
    "mouse": "mouse",
    "gamepad": "gamepad-2",
    "headset": "headphones",
    "device": "circle-question-mark",
    "unknown": "circle-question-mark",
}

NAV_ICONS = {
    "devices": "monitor-smartphone",
    "settings": "settings",
}

BAR_ICONS = {"keyboard": "keyboard", "mouse": "mouse"}


def _icon_dir() -> Path:
    return identity.resource_dir() / "assets" / "icons" / "lucide"


@lru_cache(maxsize=64)
def _source(name: str) -> str | None:
    path = _icon_dir() / f"{name}.svg"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


@lru_cache(maxsize=256)
def _svg_bytes(name: str, colour: str, stroke: float) -> bytes | None:
    text = _source(name)
    if text is None:
        return None
    text = text.replace("currentColor", colour)
    text = text.replace('stroke-width="2"', 'stroke-width="%s"' % stroke)
    return text.encode("utf-8")


def _ratio() -> float:
    instance = QGuiApplication.instance()
    return instance.devicePixelRatio() if instance is not None else 1.0


_CACHE: dict[tuple, QPixmap] = {}


def pixmap(name: str, colour: str, size: int, stroke: float = 1.75) -> QPixmap:
    """按目标尺寸渲染一张着色位图；找不到素材时返回空位图。"""
    ratio = _ratio()
    cache_key = (name, colour, size, stroke, round(ratio, 2))
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached
    data = _svg_bytes(name, colour, stroke)
    pixmap_ = QPixmap(int(size * ratio), int(size * ratio))
    pixmap_.setDevicePixelRatio(ratio)
    pixmap_.fill(Qt.transparent)
    if data is not None:
        renderer = QSvgRenderer(QByteArray(data))
        if renderer.isValid():
            painter = QPainter(pixmap_)
            painter.setRenderHint(QPainter.Antialiasing, True)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
    _CACHE[cache_key] = pixmap_
    return pixmap_


def icon(name: str, colour: str, size: int, stroke: float = 1.75) -> QIcon:
    return QIcon(pixmap(name, colour, size, stroke))


def kind_pixmap(kind: str, colour: str, size: int = 24, stroke: float = 1.75) -> QPixmap:
    return pixmap(KIND_ICONS.get(kind, KIND_ICONS["device"]), colour, size, stroke)


def nav_pixmap(kind: str, colour: str, size: int = 22, stroke: float = 1.75) -> QPixmap:
    return pixmap(NAV_ICONS.get(kind, NAV_ICONS["devices"]), colour, size, stroke)


def bar_pixmap(kind: str, colour: str, size: int = 14, stroke: float = 1.9) -> QPixmap:
    return pixmap(BAR_ICONS.get(kind, BAR_ICONS["keyboard"]), colour, size, stroke)
