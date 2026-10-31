"""示例：用真实 Qt 控件演示动态设备列表（5 台设备、插入 / 断开下移 / 重连置顶）。

这里的设备是构造出来的示例数据，界面上会打"示例数据"角标；真实运行时的数据
来自 `devices.json` 记录与蓝牙扫描/接收器读取。

用法：
  python tools/list_demo.py --png out.png            # 静态截图
  python tools/list_demo.py --gif out.gif            # 动画（插入 → 断开 → 重连）
  python tools/list_demo.py --live                   # 可交互窗口（真实控件）
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keymousebattery.model import Device, Sample  # noqa: E402
from keymousebattery.ui import MainWindow  # noqa: E402


def make_device(key: str, name: str, kind: str, level: int | None, online: bool,
                order: int, last_connected: float, stale: bool = False) -> Device:
    return Device(key=key, name=name, kind=kind, connection="ble", source="windows-ble",
                  order=order, last_connected=last_connected, stale=stale,
                  sample=Sample(level=level, charging=None, online=online,
                                sampled_at=time.time()))


def initial() -> list[Device]:
    now = time.time()
    return [
        make_device("ble:01", "MCHOSE G75 5.0", "keyboard", 100, True, 3, now - 10),
        make_device("ble:02", "ELECOM EX-G", "mouse", 86, True, 2, now - 60),
        make_device("ble:03", "备用键盘", "keyboard", 42, True, 1, now - 120),
        make_device("ble:04", "Xbox 手柄", "gamepad", 64, True, 4, now - 300),
        make_device("ble:05", "旧鼠标", "mouse", None, False, 0, now - 7200),
    ]


def pair() -> list[Device]:
    """一张在线 + 一张离线，用来核对离线卡没有残留电量条。"""
    now = time.time()
    return [
        make_device("ble:11", "ELECOM EX-G", "mouse", 100, True, 2, now),
        make_device("ble:12", "MCHOSE G75 5.0", "keyboard", None, False, 0, now - 120),
    ]


def tag(pixmap, text: str = "示例数据"):
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    font = QFont("Microsoft YaHei UI", 9)
    painter.setFont(font)
    width = painter.fontMetrics().horizontalAdvance(text) + 16
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(206, 121, 48, 235))
    painter.drawRoundedRect(pixmap.width() - width - 12, 12, width, 24, 8, 8)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(pixmap.width() - width - 4, 12 + 17, text)
    painter.end()


def build_window() -> MainWindow:
    window = MainWindow(lambda: None)
    window.resize(880, 620)
    window.show()
    QApplication.processEvents()
    return window


def shot(window: MainWindow, path: str, label: str = "示例数据") -> None:
    pix = window.grab()
    tag(pix, label)
    pix.save(path)
    print("saved", path)


def run_gif(window: MainWindow, path: str) -> None:
    """插入一台 → 断开一台下移 → 重连置顶，逐帧抓真实控件画面。"""
    frames: list = []
    devices = initial()
    window.render_devices(devices, 60, 20, time.time())

    def grab() -> None:
        pix = window.grab()
        tag(pix)
        frames.append(pix.toImage().convertToFormat(QImage.Format.Format_RGB32))

    grab()
    steps: list[tuple[int, object]] = []

    def insert_device() -> None:
        now = time.time()
        devices.append(make_device("ble:06", "临时键盘", "keyboard", 73, True, 6, now))
        window.render_devices(devices, 60, 20, now)

    def disconnect_second() -> None:
        now = time.time()
        devices[1] = make_device("ble:02", "ELECOM EX-G", "mouse", None, False, 2, now - 60)
        window.render_devices(devices, 60, 20, now)

    def reconnect_second() -> None:
        now = time.time()
        devices[1] = make_device("ble:02", "ELECOM EX-G", "mouse", 86, True, 7, now)
        window.render_devices(devices, 60, 20, now)

    timeline: list[tuple[int, object]] = []
    timeline.append((1500, grab))
    timeline.append((300, insert_device))
    timeline.extend([(50, grab)] * 18)
    timeline.append((500, disconnect_second))
    timeline.extend([(50, grab)] * 18)
    timeline.append((500, reconnect_second))
    timeline.extend([(50, grab)] * 18)
    timeline.append((700, grab))
    delay = 0
    for wait, action in timeline:
        delay += wait
        QTimer.singleShot(delay, action)

    def finish() -> None:
        from PIL import Image
        images = []
        for frame in frames:
            frame = frame.copy()
            buffer = frame.bits()
            image = Image.frombytes("RGBA", (frame.width(), frame.height()),
                                    bytes(buffer), "raw", "BGRA")
            images.append(image.convert("RGB"))
        # 丢掉"列表还没画出来"的帧（首帧在窗口完成首绘之前抓会全白）
        kept = []
        for image in images:
            region = image.crop((236, 128, 852, 552)).convert("L")
            if max(region.getdata()) - min(region.getdata()) > 12:
                kept.append(image)
        if not kept:
            kept = images
        first, rest = kept[0], kept[1:]
        first.save(path, save_all=True, append_images=rest, duration=80, loop=0)
        print("saved", path, len(kept), "frames")
        QApplication.quit()

    QTimer.singleShot(delay + 900, finish)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="动态设备列表示例")
    parser.add_argument("--png", default="")
    parser.add_argument("--gif", default="")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--page", choices=("devices", "settings"), default="devices")
    parser.add_argument("--empty", action="store_true", help="渲染空状态（无设备记录）")
    parser.add_argument("--pair", action="store_true", help="只渲染一张在线卡与一张离线卡")
    args = parser.parse_args(argv[1:])
    app = QApplication.instance() or QApplication([])
    window = build_window()
    devices = [] if args.empty else (pair() if args.pair else initial())
    window.render_devices(devices, 60, 20, time.time())
    if args.page == "settings":
        window.show_page(1)
        QApplication.processEvents()
    if args.png:
        QTimer.singleShot(900, lambda: (shot(window, args.png), QApplication.quit()))
        app.exec()
        return 0
    if args.gif:
        run_gif(window, args.gif)
        app.exec()
        return 0
    if args.live:
        window.render_devices(devices, 60, 20, time.time())
        return app.exec()
    print("用法：--png/--gif/--live")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
