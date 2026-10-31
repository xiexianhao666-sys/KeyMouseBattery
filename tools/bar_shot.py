"""把桌面电量条单独渲染出来，贴在深色底上，方便看清圆角与配色。

只用于取证：真实运行时它浮在壁纸或窗口之上，背景对比才明显。
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vigilwatt_py.bar import DesktopBar  # noqa: E402


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "bar.png"
    app = QApplication([])
    bar = DesktopBar(lambda: None, lambda _x, _y: None)
    bar.set_texts("12%", "100%", True, False)
    bar.show()
    app.processEvents()
    pix = bar.grab()
    canvas = QImage(pix.width() + 40, pix.height() + 40, QImage.Format_ARGB32)
    canvas.fill(QColor(28, 28, 32))
    painter = QPainter(canvas)
    painter.drawImage(20, 20, pix.toImage())
    painter.end()
    canvas.save(out)
    bar.close()
    print("saved", out, canvas.width(), "x", canvas.height())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
