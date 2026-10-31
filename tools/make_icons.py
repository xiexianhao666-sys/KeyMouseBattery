"""从品牌 SVG 生成多尺寸 ICO 与运行时 PNG。

16/20/24/32 用简化稿，48/64/128/256 用主稿；ICO 用 PNG 压缩条目，Windows Vista 以上都认。
"""

from __future__ import annotations

import io
import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
MAIN_SVG = os.path.join(ASSETS, "branding", "app-icon.svg")
SMALL_SVG = os.path.join(ASSETS, "branding", "app-icon-small.svg")

SIZES = ((16, SMALL_SVG), (20, SMALL_SVG), (24, SMALL_SVG), (32, SMALL_SVG),
         (48, MAIN_SVG), (64, MAIN_SVG), (128, MAIN_SVG), (256, MAIN_SVG))


def render(svg_path: str, size: int) -> QImage:
    renderer = QSvgRenderer(svg_path)
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def write_ico(path: str, entries: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    table = b""
    payload = b""
    for size, blob in entries:
        table += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                             0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        payload += blob
    with open(path, "wb") as handle:
        handle.write(header + table + payload)


def main(argv: list[str]) -> int:
    del argv
    icons = []
    for size, svg in SIZES:
        image = render(svg, size)
        blob = png_bytes(image)
        icons.append((size, blob))
        if size in (16, 32, 64, 256):
            image.save(os.path.join(ASSETS, "app-%d.png" % size), "PNG")
    ico = os.path.join(ASSETS, "app.ico")
    write_ico(ico, icons)
    print("wrote", ico, os.path.getsize(ico), "bytes; png sizes 16/32/64/256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
