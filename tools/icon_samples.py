"""图标样本：设备类型图标的三种风格，供挑选。

只画图，不启动窗口；输出一张对照表（实际 24px + 放大 6 倍）与一行卡片上下文。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen

WIDTH, HEIGHT = 960, 980
INK = "#3a3a3a"
PAPER = "#ffffff"
LABEL = "#5f5f5f"
HEAD = "#252525"


def _line(p: QPainter, colour: str, width: float) -> None:
    p.setPen(QPen(QColor(colour), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))


def _fill(p: QPainter, colour: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(colour))


def _question(p: QPainter, r: QRectF, colour: str) -> None:
    """在给定区域内居中画一个问号。"""
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(max(8, int(r.height() * 0.52)))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(colour))
    p.setBrush(Qt.NoBrush)
    p.drawText(QRectF(r.left(), r.top() + r.height() * 0.06, r.width(), r.height() * 0.90),
               Qt.AlignCenter, "?")


# ---------------- A：细线轮廓 ----------------
def keyboard_a(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.075)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.06, r.top() + r.height() * 0.30,
                             r.width() * 0.88, r.height() * 0.40), 3.0, 3.0)
    for row in (0.42, 0.54):
        for i in range(4):
            x = r.left() + r.width() * 0.16 + i * r.width() * 0.19
            p.drawLine(QPointF(x, r.top() + r.height() * row),
                       QPointF(x + r.width() * 0.10, r.top() + r.height() * row))
    p.drawLine(QPointF(r.left() + r.width() * 0.30, r.top() + r.height() * 0.63),
               QPointF(r.left() + r.width() * 0.70, r.top() + r.height() * 0.63))


def mouse_a(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.075)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.26, r.top() + r.height() * 0.06,
                             r.width() * 0.48, r.height() * 0.88),
                      r.width() * 0.24, r.width() * 0.24)
    p.drawLine(QPointF(r.left() + r.width() * 0.50, r.top() + r.height() * 0.20),
               QPointF(r.left() + r.width() * 0.50, r.top() + r.height() * 0.36))


def gamepad_a(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.075)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.06, r.top() + r.height() * 0.34,
                             r.width() * 0.88, r.height() * 0.34), 8.0, 8.0)
    p.drawLine(QPointF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.42),
               QPointF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.60))
    p.drawLine(QPointF(r.left() + r.width() * 0.19, r.top() + r.height() * 0.51),
               QPointF(r.left() + r.width() * 0.37, r.top() + r.height() * 0.51))
    p.drawEllipse(QPointF(r.left() + r.width() * 0.70, r.top() + r.height() * 0.45), 2.2, 2.2)
    p.drawEllipse(QPointF(r.left() + r.width() * 0.79, r.top() + r.height() * 0.57), 2.2, 2.2)


def headset_a(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.075)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(r.left() + r.width() * 0.16, r.top() + r.height() * 0.10,
                     r.width() * 0.68, r.height() * 0.68), 0, 180 * 16)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.14, r.top() + r.height() * 0.46,
                             r.width() * 0.16, r.height() * 0.34), 3.0, 3.0)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.70, r.top() + r.height() * 0.46,
                             r.width() * 0.16, r.height() * 0.34), 3.0, 3.0)


def unknown_a(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.08)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.14,
                             r.width() * 0.44, r.height() * 0.72), 4.0, 4.0)
    _question(p, r, c)


# ---------------- B：轮廓 + 实心细节 ----------------
def keyboard_b(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.085)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.05, r.top() + r.height() * 0.28,
                             r.width() * 0.90, r.height() * 0.44), 3.5, 3.5)
    _fill(p, c)
    for row in (0, 1):
        for col in range(4):
            x = r.left() + r.width() * (0.17 + col * 0.185)
            y = r.top() + r.height() * (0.40 + row * 0.13)
            p.drawRoundedRect(QRectF(x, y, r.width() * 0.075, r.height() * 0.06), 1.0, 1.0)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.32, r.top() + r.height() * 0.62,
                             r.width() * 0.36, r.height() * 0.06), 1.2, 1.2)


def mouse_b(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.085)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.25, r.top() + r.height() * 0.06,
                             r.width() * 0.50, r.height() * 0.88),
                      r.width() * 0.25, r.width() * 0.25)
    _fill(p, c)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.465, r.top() + r.height() * 0.18,
                             r.width() * 0.07, r.height() * 0.18), 1.0, 1.0)


def gamepad_b(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.085)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.05, r.top() + r.height() * 0.30,
                             r.width() * 0.90, r.height() * 0.40), 9.0, 9.0)
    p.drawLine(QPointF(r.left() + r.width() * 0.29, r.top() + r.height() * 0.40),
               QPointF(r.left() + r.width() * 0.29, r.top() + r.height() * 0.60))
    p.drawLine(QPointF(r.left() + r.width() * 0.20, r.top() + r.height() * 0.50),
               QPointF(r.left() + r.width() * 0.38, r.top() + r.height() * 0.50))
    _fill(p, c)
    p.drawEllipse(QPointF(r.left() + r.width() * 0.70, r.top() + r.height() * 0.44), 2.6, 2.6)
    p.drawEllipse(QPointF(r.left() + r.width() * 0.80, r.top() + r.height() * 0.56), 2.6, 2.6)


def headset_b(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.085)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(r.left() + r.width() * 0.16, r.top() + r.height() * 0.10,
                     r.width() * 0.68, r.height() * 0.68), 0, 180 * 16)
    _fill(p, c)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.13, r.top() + r.height() * 0.45,
                             r.width() * 0.19, r.height() * 0.36), 4.0, 4.0)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.68, r.top() + r.height() * 0.45,
                             r.width() * 0.19, r.height() * 0.36), 4.0, 4.0)


def unknown_b(p: QPainter, r: QRectF, c: str) -> None:
    _line(p, c, r.width() * 0.09)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.14,
                             r.width() * 0.44, r.height() * 0.72), 4.0, 4.0)
    _question(p, r, c)


# ---------------- C：实心面性 ----------------
def keyboard_c(p: QPainter, r: QRectF, c: str) -> None:
    body = QRectF(r.left() + r.width() * 0.04, r.top() + r.height() * 0.28,
                  r.width() * 0.92, r.height() * 0.44)
    _fill(p, c)
    p.drawRoundedRect(body, 3.0, 3.0)
    _fill(p, PAPER)
    for row in (0, 1):
        for col in range(4):
            x = body.left() + body.width() * (0.10 + col * 0.21)
            y = body.top() + body.height() * (0.20 + row * 0.26)
            p.drawRoundedRect(QRectF(x, y, body.width() * 0.11, body.height() * 0.16), 0.8, 0.8)
    p.drawRoundedRect(QRectF(body.left() + body.width() * 0.30, body.top() + body.height() * 0.70,
                             body.width() * 0.40, body.height() * 0.14), 0.9, 0.9)


def mouse_c(p: QPainter, r: QRectF, c: str) -> None:
    body = QRectF(r.left() + r.width() * 0.27, r.top() + r.height() * 0.05,
                  r.width() * 0.46, r.height() * 0.90)
    _fill(p, c)
    p.drawRoundedRect(body, r.width() * 0.23, r.width() * 0.23)
    _fill(p, PAPER)
    p.drawRoundedRect(QRectF(body.center().x() - r.width() * 0.035,
                             body.top() + body.height() * 0.16,
                             r.width() * 0.07, body.height() * 0.20), 1.2, 1.2)


def gamepad_c(p: QPainter, r: QRectF, c: str) -> None:
    body = QRectF(r.left() + r.width() * 0.04, r.top() + r.height() * 0.30,
                  r.width() * 0.92, r.height() * 0.40)
    _fill(p, c)
    p.drawRoundedRect(body, body.height() * 0.45, body.height() * 0.45)
    _fill(p, PAPER)
    cx = body.left() + body.width() * 0.27
    cy = body.top() + body.height() * 0.50
    p.drawRoundedRect(QRectF(cx - r.width() * 0.026, cy - r.height() * 0.15,
                             r.width() * 0.052, r.height() * 0.30), 0.8, 0.8)
    p.drawRoundedRect(QRectF(cx - r.width() * 0.095, cy - r.height() * 0.045,
                             r.width() * 0.19, r.height() * 0.09), 0.8, 0.8)
    p.drawEllipse(QPointF(body.left() + body.width() * 0.72, body.top() + body.height() * 0.36),
                  r.width() * 0.045, r.width() * 0.045)
    p.drawEllipse(QPointF(body.left() + body.width() * 0.82, body.top() + body.height() * 0.62),
                  r.width() * 0.045, r.width() * 0.045)


def headset_c(p: QPainter, r: QRectF, c: str) -> None:
    p.setPen(QPen(QColor(c), r.width() * 0.14, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(r.left() + r.width() * 0.14, r.top() + r.height() * 0.10,
                     r.width() * 0.72, r.height() * 0.72), 0, 180 * 16)
    _fill(p, c)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.12, r.top() + r.height() * 0.44,
                             r.width() * 0.18, r.height() * 0.36), 4.0, 4.0)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.70, r.top() + r.height() * 0.44,
                             r.width() * 0.18, r.height() * 0.36), 4.0, 4.0)


def unknown_c(p: QPainter, r: QRectF, c: str) -> None:
    _fill(p, c)
    p.drawRoundedRect(QRectF(r.left() + r.width() * 0.26, r.top() + r.height() * 0.12,
                             r.width() * 0.48, r.height() * 0.76), 5.0, 5.0)
    _question(p, r, PAPER)


VARIANTS = [
    ("A  细线轮廓（现版）", {"keyboard": keyboard_a, "mouse": mouse_a,
                          "gamepad": gamepad_a, "headset": headset_a, "device": unknown_a}),
    ("B  轮廓 + 实心细节", {"keyboard": keyboard_b, "mouse": mouse_b,
                        "gamepad": gamepad_b, "headset": headset_b, "device": unknown_b}),
    ("C  实心面性", {"keyboard": keyboard_c, "mouse": mouse_c,
                  "gamepad": gamepad_c, "headset": headset_c, "device": unknown_c}),
]

COLUMNS = [("键盘", "keyboard"), ("鼠标", "mouse"), ("手柄", "gamepad"),
           ("耳机", "headset"), ("未知", "device")]


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "icon-samples.png"
    QGuiApplication.instance() or QGuiApplication([])
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(QColor(PAPER))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    head_font = QFont("Microsoft YaHei UI")
    head_font.setPixelSize(17)
    head_font.setBold(True)
    painter.setFont(head_font)
    painter.setPen(QColor(HEAD))
    painter.drawText(28, 40, "设备类型图标样本：A 细线 / B 轮廓+实心细节 / C 实心")

    label_font = QFont("Microsoft YaHei UI")
    label_font.setPixelSize(12)
    painter.setFont(label_font)
    painter.setPen(QColor(LABEL))
    for index, (title, _key) in enumerate(COLUMNS):
        painter.drawText(QRectF(250 + index * 140, 62, 126, 18), Qt.AlignHCenter, title)

    y = 96
    for name, painters in VARIANTS:
        painter.setFont(head_font)
        painter.setPen(QColor(HEAD))
        painter.drawText(28, y + 60, name)
        painter.setFont(label_font)
        painter.setPen(QColor(LABEL))
        for index, (_title, key) in enumerate(COLUMNS):
            x = 250 + index * 140
            panel = QRectF(x, y, 126, 168)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#f7f7f7"))
            painter.drawRoundedRect(panel, 10, 10)
            painter.setPen(Qt.NoPen)
            painters[key](painter, QRectF(x + 51, y + 14, 24, 24), INK)
            painters[key](painter, QRectF(x + 15, y + 46, 96, 96), INK)
            painter.setFont(label_font)
            painter.setPen(QColor(LABEL))
            painter.drawText(QRectF(x, y + 144, 126, 18), Qt.AlignHCenter, "24px 实际 / 放大 6×")
        y += 236

    painter.setFont(head_font)
    painter.setPen(QColor(HEAD))
    painter.drawText(28, y + 30, "卡片实际效果（B 组，24px）")
    row_y = y + 52
    card = QRectF(28, row_y, 660, 74)
    painter.setPen(QPen(QColor("#dedede"), 1))
    painter.setBrush(QColor(PAPER))
    painter.drawRoundedRect(card, 14, 14)
    name_font = QFont("Microsoft YaHei UI")
    name_font.setPixelSize(15)
    name_font.setBold(True)
    for offset, (text, key) in enumerate((("MCHOSE G75 5.0", "keyboard"),
                                          ("ELECOM EX-G", "mouse"),
                                          ("Xbox 手柄", "gamepad"))):
        bx = card.left() + 22 + offset * 215
        VARIANTS[1][1][key](painter, QRectF(bx, card.top() + 25, 24, 24), INK)
        painter.setFont(name_font)
        painter.setPen(QColor(HEAD))
        painter.drawText(QRectF(bx + 33, card.top() + 23, 175, 28),
                         Qt.AlignLeft | Qt.AlignVCenter, text)

    painter.setFont(label_font)
    painter.setPen(QColor(LABEL))
    painter.drawText(28, y + 160, "说明：图标画在透明底上，这里铺白底便于比较；选定后用同一套线条画法替换卡片名称前的类型图标。")
    painter.end()
    image.save(out, "PNG")
    print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
