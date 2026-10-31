"""侧栏导航图标候选：设备 / 设置两组，按 C 组底座渲染（30 底座 + 22 图标）。"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen

from keymousebattery import icons

DEVICE_CANDIDATES = [
    ("monitor-smartphone", "设备（多屏+手机）"),
    ("monitor", "显示器"),
    ("layout-grid", "网格"),
    ("layers", "层叠"),
    ("cpu", "芯片"),
    ("house", "首页"),
]

SETTINGS_CANDIDATES = [
    ("settings", "齿轮"),
    ("sliders-horizontal", "滑杆"),
    ("wrench", "扳手"),
]


def draw_nav(p: QPainter, x: float, y: float, name: str, label: str, checked: bool) -> None:
    base_side, icon_side, height, width = 30.0, 22.0, 40.0, 150.0
    row = QRectF(x, y, width, height)
    if checked:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ebebeb"))
        p.drawRoundedRect(row, 9.0, 9.0)
    base = QRectF(x + 10.0, y + (height - base_side) / 2.0, base_side, base_side)
    p.setPen(QPen(QColor("#dedede"), 1.0) if checked else Qt.NoPen)
    p.setBrush(QColor("#ffffff") if checked else QColor("#eeeeee"))
    p.drawRoundedRect(base, 6.0, 6.0)
    colour = "#303030" if checked else "#6f6f6f"
    glyph = icons.pixmap(name, colour, int(icon_side))
    p.drawPixmap(int(base.left() + (base_side - icon_side) / 2.0),
                 int(base.top() + (base_side - icon_side) / 2.0), glyph)
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(13)
    font.setWeight(QFont.DemiBold if checked else QFont.Normal)
    p.setFont(font)
    p.setPen(QColor("#303030" if checked else "#5f5f5f"))
    p.drawText(QRectF(base.right() + 11, y, width - 51, height),
               Qt.AlignVCenter | Qt.AlignLeft, label)


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "nav-samples.png"
    QGuiApplication.instance() or QGuiApplication([])
    width, height = 980, 640
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    head = QFont("Microsoft YaHei UI")
    head.setPixelSize(17)
    head.setBold(True)
    painter.setFont(head)
    painter.setPen(QColor("#252525"))
    painter.drawText(28, 40, "侧栏导航图标候选（Lucide，选中态 / 未选中态）")

    label = QFont("Microsoft YaHei UI")
    label.setPixelSize(11)

    y = 78
    for name, caption in DEVICE_CANDIDATES:
        painter.setFont(label)
        painter.setPen(QColor("#6b6b6b"))
        painter.drawText(QRectF(28, y + 4, 90, 18), Qt.AlignLeft, name)
        draw_nav(painter, 150, y, name, "设备", True)
        draw_nav(painter, 320, y, name, "设备", False)
        painter.setFont(label)
        painter.setPen(QColor("#8a8a8a"))
        painter.drawText(QRectF(492, y + 12, 460, 18), Qt.AlignLeft, caption)
        y += 52

    y += 24
    sub = QFont("Microsoft YaHei UI")
    sub.setPixelSize(15)
    sub.setBold(True)
    painter.setFont(sub)
    painter.setPen(QColor("#252525"))
    painter.drawText(28, y, "设置页图标候选")
    y += 34
    for name, caption in SETTINGS_CANDIDATES:
        painter.setFont(label)
        painter.setPen(QColor("#6b6b6b"))
        painter.drawText(QRectF(28, y + 4, 90, 18), Qt.AlignLeft, name)
        draw_nav(painter, 150, y, name, "设置", True)
        draw_nav(painter, 320, y, name, "设置", False)
        painter.setFont(label)
        painter.setPen(QColor("#8a8a8a"))
        painter.drawText(QRectF(492, y + 12, 460, 18), Qt.AlignLeft, caption)
        y += 52

    painter.setFont(label)
    painter.setPen(QColor("#8a8a8a"))
    painter.drawText(28, height - 20, "素材：Lucide（ISC）。底座 30px、图标 22px、线宽 1.75，与设备卡片类型图标同一套。")
    painter.end()
    image.save(out, "PNG")
    print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
