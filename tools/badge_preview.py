"""连接徽标样张：矢量渲染，放大后依然清晰；同时给出 1:1 的实际大小。"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keymousebattery.ui import (  # noqa: E402
    BORDER,
    MUTED,
    TEXT,
    _BLUETOOTH_PATH,
    _USB_PATH,
    ConnectionBadge,
)

CHIP = 22
GLYPH = 17


def svg_path(path: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path fill="#ffffff" d="%s"/></svg>' % path)


def draw_badge(painter: QPainter, kind: str, x: float, y: float, scale: float) -> None:
    background, _fg = ConnectionBadge.COLORS[kind]
    size = CHIP * scale
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(background))
    painter.drawRoundedRect(QRectF(x, y, size, size), 7 * scale, 7 * scale)
    if kind == "ble":
        path = _BLUETOOTH_PATH
    elif kind == "usb":
        path = _USB_PATH
    else:
        painter.setPen(QColor("#8a94a3"))
        font = QFont("Microsoft YaHei UI")
        font.setPixelSize(max(8, int(13 * scale)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(x, y, size, size), Qt.AlignCenter, "?")
        return
    renderer = QSvgRenderer(QByteArray(svg_path(path).encode("utf-8")))
    inset = (CHIP - GLYPH) / 2.0 * scale
    renderer.render(painter, QRectF(x + inset, y + inset, GLYPH * scale, GLYPH * scale))


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "badges.png"
    app = QApplication([])  # noqa: F841 - 需要 QGuiApplication 实例才能渲染 SVG
    cases = (("ble", "蓝牙"), ("usb", "USB 接收器"), ("unknown", "连接方式未知"))
    cell = 170
    width, height = cell * len(cases) + 40, 420
    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#f5f7fb"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QColor(TEXT))
    painter.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
    painter.drawText(QRectF(20, 8, width - 40, 22), Qt.AlignLeft, "连接方式徽标（矢量放大 6 倍）")
    for index, (kind, label) in enumerate(cases):
        scale = 6.0
        size = CHIP * scale
        draw_badge(painter, kind, 20 + index * cell + (cell - size) / 2, 44, scale)
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Microsoft YaHei UI", 10))
        painter.drawText(QRectF(20 + index * cell, 44 + size + 12, cell, 22), Qt.AlignHCenter, label)
    painter.setPen(QColor(TEXT))
    painter.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
    painter.drawText(QRectF(20, 250, width - 40, 22), Qt.AlignLeft, "实际大小（1:1）")
    for index, (kind, label) in enumerate(cases):
        draw_badge(painter, kind, 20 + index * cell + (cell - CHIP) / 2, 282, 1.0)
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(QRectF(20 + index * cell, 282 + CHIP + 10, cell, 20), Qt.AlignHCenter, label)
    painter.setPen(QColor(BORDER))
    painter.drawLine(20, 372, width - 20, 372)
    painter.setPen(QColor(MUTED))
    painter.setFont(QFont("Microsoft YaHei UI", 9))
    painter.drawText(QRectF(20, 378, width - 40, 30), Qt.AlignLeft,
                     "徽标 22×22，图形 17×17，均由矢量路径按目标尺寸重新渲染。")
    painter.end()
    canvas.save(out)
    print("saved", out, width, "x", height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
