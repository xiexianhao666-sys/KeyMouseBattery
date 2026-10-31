"""电量动效 A 的示例入口：76% → 18% → 0% 的三段演示。

两种用法：
  python tools/motion_demo.py                # 打开一个可交互的小窗口，点"重新播放"
  python tools/motion_demo.py --gif out.gif  # 逐帧渲染并合成 GIF（无需桌面）

GIF 只是证据产物；真实效果以应用里的卡片为准。此窗口标题带"示例"字样，
不参与产品发布。
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,  # noqa: E402
                               QVBoxLayout, QWidget)

from keymousebattery import ui  # noqa: E402
from keymousebattery.model import Device, Sample  # noqa: E402

STEPS = (76, 18, 0)


def _device(level: int) -> Device:
    return Device(key="keyboard:1", name="演示键盘", kind="keyboard", connection="ble",
                  source="demo",
                  sample=Sample(level=level, charging=None, online=True,
                                sampled_at=time.time()),
                  stale=False)


def _card() -> ui.DeviceCard:
    card = ui.DeviceCard()
    card.resize(560, 120)
    return card


def _render_gif(path: str) -> int:
    app = QApplication([])
    card = _card()
    card.show()
    app.processEvents()
    frames = []
    for level in STEPS:
        card.update_view(_device(level), 20)
        card.finish_animation_target(float(level) if card._shown is None else card._shown)
        # 重新从 0 播到目标，保证每段都完整可见
        card._shown = 0.0 if level == STEPS[0] else card._shown
        card.update_view(_device(level), 20)
        for t in range(0, 651, 25):
            card._anim.setCurrentTime(t)
            app.processEvents()
            frames.append(card.grab().toImage())
        card.finish_animation()
        frames.append(card.grab().toImage())
    card.close()
    try:
        from PIL import Image
    except Exception:
        print("需要 Pillow 才能合成 GIF；已跳过硬合成")
        return 2
    images = []
    for image in frames:
        buffer = image.convertToFormat(QImage.Format.Format_RGB32)
        width, height = buffer.width(), buffer.height()
        ptr = buffer.constBits()
        data = bytes(ptr)[: width * height * 4]
        images.append(Image.frombytes("RGBA", (width, height), data, "raw", "BGRA"))
    images = [img.convert("RGB") for img in images]
    images[0].save(path, save_all=True, append_images=images[1:], duration=40, loop=0)
    print("saved", path, len(images), "frames")
    return 0


class DemoWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("电量动效示例（非产品界面）")
        self.setStyleSheet("background: %s;" % ui.BG)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        title = QLabel("电量动效 A · 76% → 18% → 0%")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: %s;" % ui.TEXT)
        layout.addWidget(title)
        self.card = _card()
        layout.addWidget(self.card)
        row = QHBoxLayout()
        self.status = QLabel("首次可见读数从 0 涨到当前值，650 ms 收尾")
        self.status.setStyleSheet("font-size: 12px; color: %s;" % ui.MUTED)
        row.addWidget(self.status, 1)
        replay = QPushButton("重新播放")
        replay.setMinimumHeight(38)
        replay.setCursor(Qt.PointingHandCursor)
        replay.clicked.connect(self.play)
        row.addWidget(replay)
        layout.addLayout(row)
        self.resize(620, 260)
        self._index = 0
        QTimer.singleShot(200, self.play)

    def play(self) -> None:
        self._index = 0
        self._step()

    def _step(self) -> None:
        if self._index >= len(STEPS):
            self.status.setText("演示结束：中途更新会从当前显示值接续，不重播")
            return
        level = STEPS[self._index]
        self.status.setText("目标 %d%%" % level)
        self.card.update_view(_device(level), 20)
        self._index += 1
        QTimer.singleShot(900, self._step)


def main(argv: list[str]) -> int:
    if "--gif" in argv:
        index = argv.index("--gif")
        path = argv[index + 1] if index + 1 < len(argv) else "motion.gif"
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        return _render_gif(path)
    app = QApplication([])
    window = DemoWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
