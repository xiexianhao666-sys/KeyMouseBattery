"""示例数据截图：四种状态各一张，图角自标"示例数据"。

只在截图工具里用假设备，产品默认模式不注入演示数据。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QPainter, QColor, QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vigilwatt_py.model import Device, Sample  # noqa: E402
from vigilwatt_py.ui import MainWindow  # noqa: E402


def device(key, name, kind, level, online=True, stale=False, charging=None, age=5.0):
    return Device(key=key, name=name, kind=kind, connection="ble", source="windows-ble",
                  sample=Sample(level=level, charging=charging, online=online,
                                sampled_at=time.time() - age), stale=stale)


def tag(window, text):
    pixmap = window.grab()
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(206, 121, 48, 230))
    x = max(8, pixmap.width() - 104)
    y = 8
    painter.drawRoundedRect(x, y, 96, 22, 6, 6)
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Microsoft YaHei UI", 8)
    painter.setFont(font)
    painter.drawText(x + 6, y + 15, text)
    painter.end()
    return pixmap


def save(window, path, text):
    window.repaint()
    QApplication.processEvents()
    tag(window, text).save(str(path))


def main(argv):
    out = Path(argv[1] if len(argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(lambda: None)
    window.resize(760, 420)
    window.show()

    normal = [device("kb", "MCHOSE G75 5.0", "keyboard", 86, charging=False),
              device("ms", "ELECOM EX-G", "mouse", 64, charging=None, age=40)]
    window.render_devices(normal, 60, 20, time.time())
    save(window, out / "state-normal.png", "示例数据")

    low = [device("kb", "MCHOSE G75 5.0", "keyboard", 12, charging=None),
           device("ms", "ELECOM EX-G", "mouse", 100, charging=None)]
    window.render_devices(low, 60, 20, time.time())
    save(window, out / "state-low.png", "示例数据")

    stale = [device("kb", "MCHOSE G75 5.0", "keyboard", 64, online=False, stale=True, age=600),
             device("ms", "ELECOM EX-G", "mouse", None, online=False, age=600)]
    window.render_devices(stale, 60, 20, time.time())
    save(window, out / "state-stale.png", "示例数据")

    window.show_page(1)
    window.settings_page.load({"interval": 60, "low": 20, "tray_icon": "number",
                               "desktop_bar": False, "autostart": False})
    save(window, out / "page-settings.png", "示例数据")
    window.show_page(0)
    window.render_devices(normal, 60, 20, time.time())
    save(window, out / "page-devices.png", "示例数据")
    print("saved", sorted(p.name for p in out.glob("*.png")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
