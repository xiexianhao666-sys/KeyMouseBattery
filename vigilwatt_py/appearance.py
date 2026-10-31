"""窗口外观（Windows 11 标题栏着色）。

Windows 11 会让标题栏跟随系统强调色。本应用是灰白界面，若标题栏变成
整条强调色（例如橙色），在视觉上就像一条很粗的顶部边框。这里把标题栏、
文字与窗口描边显式设成界面自己的颜色，让标题栏和内容连成一片。
"""

from __future__ import annotations

import logging
import sys

LOG = logging.getLogger("vigilwatt")

DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def _colorref(colour: str) -> int:
    """'#rrggbb' -> Win32 COLORREF（0x00BBGGRR）。"""
    value = colour.lstrip("#")
    red, green, blue = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def set_title_bar_colours(hwnd: int, caption: str = "#f6f6f6",
                          text: str = "#252525", border: str = "#dedede") -> bool:
    """把窗口标题栏、标题文字、窗口描边设成指定颜色。

    仅在 Windows 11（内部版本 22000+）生效；不支持的平台静默返回 False，
    调用方不需要为此改变任何界面逻辑。
    """
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
    except ImportError:  # pragma: no cover - 非 Windows 平台
        return False
    try:
        dwm = ctypes.windll.dwmapi
        values = (
            (DWMWA_CAPTION_COLOR, _colorref(caption)),
            (DWMWA_TEXT_COLOR, _colorref(text)),
            (DWMWA_BORDER_COLOR, _colorref(border)),
        )
        for attribute, value in values:
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attribute,
                                      ctypes.byref(data), ctypes.sizeof(data))
        return True
    except Exception as error:  # pragma: no cover - 老系统上属性不存在
        LOG.debug("设置标题栏颜色失败：%s", error)
        return False
