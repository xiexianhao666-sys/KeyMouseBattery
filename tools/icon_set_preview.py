"""对比现成图标集（Lucide / Tabler / Bootstrap / Phosphor / Material Symbols）。

读取 `assets/icons/<set>/*.svg`，按目标尺寸重新渲染为位图并拼成对照表。
所有素材均为 MIT / ISC / Apache-2.0 授权，来源见 CREDITS.md。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ICONS = ROOT.parent / "assets" / "icons"

CELL_W, CELL_H, COL_GAP = 128, 176, 10
LEFT, TOP = 236, 92
INK = "#3a3a3a"
PAPER = "#ffffff"
PANEL = "#f7f7f7"
LABEL = "#6b6b6b"
HEAD = "#252525"

KINDS = [("键盘", "keyboard"), ("鼠标", "mouse"), ("手柄", "gamepad"),
         ("耳机", "headset"), ("未知", "unknown")]

SETS = [
    ("Lucide · ISC", "lucide", "stroke"),
    ("Lucide 1.5px · ISC", "lucide", "stroke-thin"),
    ("Tabler · MIT", "tabler", "stroke"),
    ("Tabler 1.5px · MIT", "tabler", "stroke-thin"),
    ("Bootstrap · MIT", "bootstrap", "fill"),
    ("Phosphor Regular · MIT", "phosphor-regular", "fill"),
    ("Phosphor Fill · MIT", "phosphor-fill", "fill"),
    ("Material Rounded · Apache-2.0", "material-rounded", "fill"),
]


def load_svg(path: Path, style: str) -> QByteArray | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("currentColor", INK)
    if style == "stroke-thin":
        text = text.replace('stroke-width="2"', 'stroke-width="1.5"')
    elif style == "stroke-175":
        text = text.replace('stroke-width="2"', 'stroke-width="1.75"')
    return QByteArray(text.encode("utf-8"))


def render(renderer: QSvgRenderer, size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return image


CONTEXT_SETS = [
    ("Lucide 1.5px", "lucide", "stroke-thin"),
    ("Lucide 1.75px", "lucide", "stroke-175"),
    ("Tabler 1.5px", "tabler", "stroke-thin"),
    ("Tabler 1.75px", "tabler", "stroke-175"),
    ("Bootstrap", "bootstrap", "fill"),
    ("Phosphor Regular", "phosphor-regular", "fill"),
    ("Material Rounded", "material-rounded", "fill"),
]

CONTEXT_DEVICES = [("MCHOSE G75 5.0", "keyboard"), ("ELECOM EX-G", "mouse"),
                   ("Xbox 手柄", "gamepad"), ("未知设备", "unknown")]


def render_context(out: Path) -> int:
    width, row_h = 980, 108
    height = 92 + row_h * len(CONTEXT_SETS) + 40
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(PAPER))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    head = QFont("Microsoft YaHei UI")
    head.setPixelSize(17)
    head.setBold(True)
    label = QFont("Microsoft YaHei UI")
    label.setPixelSize(12)
    name_font = QFont("Microsoft YaHei UI")
    name_font.setPixelSize(15)
    name_font.setBold(True)

    painter.setFont(head)
    painter.setPen(QColor(HEAD))
    painter.drawText(28, 40, "候选图标集在卡片里的实际效果（24px，灰白界面）")

    y = 68
    for title, folder, style in CONTEXT_SETS:
        painter.setFont(label)
        painter.setPen(QColor(HEAD))
        painter.drawText(QRectF(28, y + 30, 150, 20), Qt.AlignLeft, title)
        painter.setPen(QPen(QColor("#dedede"), 1))
        painter.setBrush(QColor(PAPER))
        card = QRectF(186, y, 770, 74)
        painter.drawRoundedRect(card, 14, 14)
        for index, (text, key) in enumerate(CONTEXT_DEVICES):
            x = card.left() + 22 + index * 190
            data = load_svg(ICONS / folder / f"{key}.svg", style)
            if data is None:
                continue
            painter.drawImage(QRectF(x, card.top() + 26, 24, 24), render(QSvgRenderer(data), 24))
            painter.setFont(name_font)
            painter.setPen(QColor(HEAD))
            painter.drawText(QRectF(x + 33, card.top() + 24, 155, 28),
                             Qt.AlignLeft | Qt.AlignVCenter, text)
        y += row_h

    painter.setFont(label)
    painter.setPen(QColor(LABEL))
    painter.drawText(28, height - 18, "授权：Lucide ISC / Tabler MIT / Bootstrap MIT / Phosphor MIT / Material Apache-2.0")
    painter.end()
    image.save(str(out), "PNG")
    print("saved", out)
    return 0


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else Path("icon-sets.png")
    QGuiApplication.instance() or QGuiApplication([])
    if len(argv) > 2 and argv[2] == "context":
        return render_context(out)

    width = LEFT + len(KINDS) * (CELL_W + COL_GAP) + 24
    height = TOP + len(SETS) * (CELL_H + 26) + 40
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(PAPER))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    head = QFont("Microsoft YaHei UI")
    head.setPixelSize(17)
    head.setBold(True)
    label = QFont("Microsoft YaHei UI")
    label.setPixelSize(12)
    small = QFont("Microsoft YaHei UI")
    small.setPixelSize(10)

    painter.setFont(head)
    painter.setPen(QColor(HEAD))
    painter.drawText(28, 40, "现成图标集对照：每格 24px 实际尺寸 + 4 倍放大（灰白界面配色）")

    painter.setFont(label)
    painter.setPen(QColor(LABEL))
    for index, (title, _key) in enumerate(KINDS):
        x = LEFT + index * (CELL_W + COL_GAP)
        painter.drawText(QRectF(x, 58, CELL_W, 18), Qt.AlignHCenter, title)

    y = TOP
    missing: list[str] = []
    for name, folder, style in SETS:
        painter.setFont(label)
        painter.setPen(QColor(HEAD))
        painter.drawText(QRectF(28, y + 60, 190, 20), Qt.AlignLeft, name)
        for index, (_title, key) in enumerate(KINDS):
            x = LEFT + index * (CELL_W + COL_GAP)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(PANEL))
            painter.drawRoundedRect(QRectF(x, y, CELL_W, CELL_H - 8), 10, 10)
            data = load_svg(ICONS / folder / f"{key}.svg", style)
            if data is None:
                missing.append(f"{folder}/{key}")
                painter.setFont(small)
                painter.setPen(QColor("#b04a4a"))
                painter.drawText(QRectF(x, y + 70, CELL_W, 18), Qt.AlignHCenter, "缺失")
                continue
            svg = QSvgRenderer(data)
            big = render(svg, 96)
            small_img = render(svg, 24)
            painter.drawImage(QRectF(x + 16, y + 22, 96, 96), big)
            painter.drawImage(QRectF(x + 52, y + 128, 24, 24), small_img)
            painter.setFont(small)
            painter.setPen(QColor(LABEL))
            painter.drawText(QRectF(x, y + 154, CELL_W, 14), Qt.AlignHCenter, "24px")
        y += CELL_H + 26

    painter.setFont(small)
    painter.setPen(QColor(LABEL))
    painter.drawText(28, height - 18,
                     "素材来源：lucide (ISC)、tabler icons (MIT)、bootstrap-icons (MIT)、"
                     "phosphor-icons (MIT)、Material Symbols Rounded (Apache-2.0)")
    painter.end()
    image.save(str(out), "PNG")
    print("saved", out)
    if missing:
        print("missing:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
