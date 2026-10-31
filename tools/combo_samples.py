"""下拉选择控件的几套外形小样，只用于选型，不进产品。

每套样式给两行：关闭态（在设置行里的样子）和展开态（弹出菜单的样子）。
渲染成一张 PNG 方便对比。
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,  # noqa: E402
                               QLabel, QPushButton, QVBoxLayout, QWidget)

from keymousebattery import ui  # noqa: E402

POPUP_QSS = (
    "QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #e1e7f0;"
    " padding: 4px; outline: none; selection-background-color: #eef3ff;"
    " selection-color: #2f5fbf; }"
    "QComboBox QAbstractItemView::item { min-height: 28px; padding: 0 10px;"
    " border-radius: 6px; color: %s; }" % ui.TEXT
)

VARIANTS = {
    "A": {
        "title": "A 现状：细边框白底 + 原生箭头",
        "qss": (
            "QComboBox { background: #ffffff; border: 1px solid %s; border-radius: 8px;"
            " padding: 3px 28px 3px 10px; font-size: 13px; color: %s; }"
            "QComboBox:hover { border-color: #cfd9e8; }"
            "QComboBox:focus { border: 1px solid #b9c7ee; }"
            % (ui.BORDER, ui.TEXT)
        ),
        "chevron": ui.MUTED,
        "native": True,
    },
    "B": {
        "title": "B 胶囊浅底：无边框、灰底、圆角 15",
        "qss": (
            "QComboBox { background: #f1f4f9; border: none; border-radius: 15px;"
            " padding: 3px 28px 3px 12px; font-size: 13px; color: %s; }"
            "QComboBox:hover { background: #e8eef8; }"
            "QComboBox:focus { background: #e8eef8; }" "QComboBox::drop-down { border: none; width: 0px; }" "QComboBox::down-arrow { image: none; }" % ui.TEXT
        ),
        "chevron": ui.MUTED,
    },
    "C": {
        "title": "C 描边 + 蓝色数值（强调“当前值”）",
        "qss": (
            "QComboBox { background: #ffffff; border: 1px solid #c9d6ea; border-radius: 9px;"
            " padding: 3px 28px 3px 10px; font-size: 13px; color: #2f5fbf; font-weight: 600; }"
            "QComboBox:hover { border-color: %s; background: #f7faff; }"
            "QComboBox:focus { border: 2px solid #b9c7ee; padding: 2px 27px 2px 9px; }" "QComboBox::drop-down { border: none; width: 0px; }" "QComboBox::down-arrow { image: none; }" % ui.ACCENT
        ),
        "chevron": ui.ACCENT,
    },
    "D": {
        "title": "D 极简：只有下划线，悬停/聚焦变蓝",
        "qss": (
            "QComboBox { background: transparent; border: none; border-bottom: 1px solid #d7deea;"
            " border-radius: 0; padding: 3px 26px 3px 2px; font-size: 13px; color: %s; }"
            "QComboBox:hover { border-bottom: 2px solid %s; padding-bottom: 2px; }"
            "QComboBox:focus { border-bottom: 2px solid %s; padding-bottom: 2px; }" "QComboBox::drop-down { border: none; width: 0px; }" "QComboBox::down-arrow { image: none; }"
            % (ui.TEXT, ui.ACCENT, ui.ACCENT)
        ),
        "chevron": ui.MUTED,
    },
}


class ChevronCombo(QComboBox):
    """自绘右侧箭头，避免不同 Windows 版本的原生箭头外观差异。"""

    def __init__(self, colour: str) -> None:
        super().__init__()
        self._chevron = QColor(colour)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(self._chevron, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = self.width() - 14.0
        cy = self.height() / 2.0
        painter.drawLine(QPointF(cx - 4.0, cy - 1.8), QPointF(cx, cy + 2.2))
        painter.drawLine(QPointF(cx, cy + 2.2), QPointF(cx + 4.0, cy - 1.8))
        painter.end()


def _segmented(labels, active: int) -> QWidget:
    holder = QFrame()
    holder.setStyleSheet(
        "QFrame { background: #f1f4f9; border-radius: 15px; }"
        "QPushButton { border: none; border-radius: 12px; padding: 4px 14px;"
        " font-size: 12px; color: %s; background: transparent; }"
        "QPushButton:checked { background: #ffffff; color: %s; font-weight: 600; }"
        % (ui.MUTED, ui.TEXT)
    )
    row = QHBoxLayout(holder)
    row.setContentsMargins(3, 3, 3, 3)
    row.setSpacing(2)
    for index, label in enumerate(labels):
        button = QPushButton(label)
        button.setCheckable(True)
        button.setChecked(index == active)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(24)
        row.addWidget(button)
    return holder


def _row(title: str, subtitle: str, control: QWidget) -> QFrame:
    frame = QFrame()
    frame.setObjectName("rowCard")
    frame.setStyleSheet("QFrame#rowCard { background: #ffffff; border-radius: 12px; }")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(18, 12, 18, 12)
    row = QHBoxLayout()
    text = QVBoxLayout()
    name = QLabel(title)
    name.setStyleSheet("font-size: 13px; font-weight: 600; color: %s;" % ui.TEXT)
    sub = QLabel(subtitle)
    sub.setStyleSheet("font-size: 12px; color: %s;" % ui.MUTED)
    text.addWidget(name)
    text.addWidget(sub)
    row.addLayout(text, 1)
    row.addWidget(control, 0, Qt.AlignVCenter)
    outer.addLayout(row)
    return frame


def _combo(variant: str) -> QComboBox:
    spec = VARIANTS[variant]
    box = QComboBox() if spec.get("native") else ChevronCombo(spec["chevron"])
    box.addItems(["数字", "电池图标"])
    box.setFixedHeight(30)
    box.setMinimumWidth(120)
    box.setStyleSheet(spec["qss"] + POPUP_QSS)
    return box


def _popup_image(combo: QComboBox) -> QImage:
    combo.showPopup()
    for _ in range(5):
        QApplication.instance().processEvents()
    image = combo.view().window().grab().toImage()
    combo.hidePopup()
    QApplication.instance().processEvents()
    return image


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "combo-samples.png"
    app = QApplication([])

    def grab_row(title: str, subtitle: str, control: QWidget):
        frame = _row(title, subtitle, control)
        frame.resize(700, frame.sizeHint().height())
        frame.show()
        for _ in range(4):
            app.processEvents()
        image = frame.grab().toImage()
        frame.hide()
        return image, frame

    kept = []
    tiles = []
    for key in ("A", "B", "C", "D"):
        combo = _combo(key)
        combo.setCurrentIndex(1)
        image, frame = grab_row("托盘图标", VARIANTS[key]["title"], combo)
        kept.append(frame)
        tiles.append((VARIANTS[key]["title"], image, _popup_image(combo)))

    seg = _segmented(["数字", "电池图标"], 0)
    seg_frame, seg_holder = grab_row("托盘图标", "两档用分段控件：数字 / 电池图标", seg)
    kept.append(seg_holder)
    pair_combo = _combo("B")
    pair_combo.setCurrentIndex(1)
    pair_frame, pair_holder = grab_row("刷新间隔", "多档仍用下拉（分段 + 下拉组合）", pair_combo)
    kept.append(pair_holder)
    pair_popup = _popup_image(pair_combo)

    pad = 18
    label_h = 20
    width = max(max(t[1].width() for t in tiles), seg_frame.width()) + pad * 2
    height = pad
    for _title, closed, popup in tiles:
        height += label_h + closed.height() + popup.height() + pad
    height += label_h + seg_frame.height() + label_h + pair_frame.height() + pair_popup.height() + pad
    sheet = QImage(width, height, QImage.Format.Format_ARGB32)
    sheet.fill(QColor("#f5f7fb"))
    painter = QPainter(sheet)
    y = pad
    for title, closed, popup in tiles:
        painter.setPen(QColor(ui.TEXT))
        painter.drawText(pad, y + 14, title)
        y += label_h
        painter.drawImage(pad, y, closed)
        y += closed.height()
        painter.drawImage(pad + 24, y + 4, popup)
        y += popup.height() + pad
    painter.setPen(QColor(ui.TEXT))
    painter.drawText(pad, y + 14, "E 两档用分段控件；多档仍用下拉")
    y += label_h
    painter.drawImage(pad, y, seg_frame)
    y += seg_frame.height() + 8
    painter.drawImage(pad, y, pair_frame)
    y += pair_frame.height()
    painter.drawImage(pad + 24, y + 4, pair_popup)
    painter.end()
    sheet.save(out)
    print("saved", out, sheet.width(), "x", sheet.height())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
