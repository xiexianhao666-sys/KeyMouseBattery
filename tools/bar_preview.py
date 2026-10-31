"""桌面电量条预览：浅色 / 深色任务栏各一条，图形与读数按当前 Lucide 图标渲染。"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vigilwatt_py.bar import DesktopBar  # noqa: E402


BANDS = (("浅色任务栏", QColor(243, 243, 243), True),
         ("深色任务栏", QColor(32, 32, 32), False))


def render_bar(app: QApplication, light: bool) -> "QImage":
    bar = DesktopBar(lambda: None, lambda _x, _y: None)
    bar.set_taskbar_light(light)
    bar.set_state("100%", "86%")
    bar.move(-4000, -4000)
    bar.show()
    app.processEvents()
    image = bar.grab().toImage()
    bar.close()
    return image


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "bar-preview.png"
    QGuiApplication.instance() or QApplication([])
    app = QApplication.instance()
    images = {light: render_bar(app, light) for _title, _bg, light in BANDS}
    scale = 2
    band_h = 34
    gap = 26
    width = 760
    height = 24 + len(BANDS) * (band_h + gap + 20) + 24
    canvas = QImage(width, height, QImage.Format_ARGB32)
    canvas.fill(QColor(255, 255, 255))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)
    y = 16
    for title, bg, light in BANDS:
        painter.setPen(QPen(QColor(90, 90, 90)))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.drawText(24, y + 12, "%s · 实际尺寸的 2 倍" % title)
        y += 18
        painter.fillRect(QRectF(20, y, width - 40, band_h), bg)
        img = images[light]
        target_h = img.height() * scale
        target_w = img.width() * scale
        painter.drawImage(QRectF(40, y + (band_h - target_h) / 2, target_w, target_h), img)
        y += band_h + gap
    painter.setPen(QPen(QColor(120, 120, 120)))
    painter.drawText(24, y + 6, "图形跟随任务栏深浅取色；读数颜色只随状态变化（正常深灰、低电量红、未知灰）。")
    painter.end()
    canvas.save(out)
    print("saved", out, canvas.width(), "x", canvas.height())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
