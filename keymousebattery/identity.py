"""应用身份与路径：所有可写数据都落在程序自己的 data 目录里。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

APP_ID = "KeyMouseBattery"
APP_NAME = "键鼠电量"
APP_TAGLINE = "电量一目了然"
APP_VERSION = "0.4.2-dev"
APP_DESCRIPTION = "Windows 无线键鼠电量工具"

MUTEX_NAME = "Local\\KeyMouseBattery_single_instance"
SHOW_EVENT_NAME = "Local\\KeyMouseBattery_show_panel"
PROJECT_URL = "https://github.com/xiexianhao666-sys/KeyMouseBattery"
PORTABLE_MARKER = "portable.txt"

CONFIG_FILE = "config.json"
LOG_FILE = "keymousebattery.log"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """打包后资源在 PyInstaller 的解包目录，源码运行时在项目根。"""
    return Path(getattr(sys, "_MEIPASS", base_dir()))


def data_dir(base: Path | None = None) -> Path:
    """便携优先：第一版始终用程序目录下的 data，不碰 %LOCALAPPDATA%。"""
    return (base or base_dir()) / "data"


def ensure_data_dir(base: Path | None = None) -> Path:
    folder = data_dir(base)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def is_writable(folder: Path) -> bool:
    probe = folder / ".write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def prepare_temp_dir(folder: Path) -> Path | None:
    """把 tempfile 指到 data\\tmp。

    宿主给的 TEMP 目录在沙箱里不可 chmod，tempfile 的清理会抛 PermissionError；
    显式指定一个自己能写的目录可以避开这条整条链路。
    """
    tmp = folder / "tmp"
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        if not is_writable(tmp):
            return None
    except OSError:
        return None
    tempfile.tempdir = str(tmp)
    return tmp


def describe_paths(base: Path | None = None) -> dict[str, str]:
    folder = data_dir(base)
    return {
        "base": str(base or base_dir()),
        "data": str(folder),
        "config": str(folder / CONFIG_FILE),
        "log": str(folder / LOG_FILE),
        "python": sys.version.split()[0],
        "frozen": str(is_frozen()),
    }


def command_line() -> list[str]:
    if is_frozen():
        return [str(Path(sys.executable).resolve())]
    script = base_dir() / "KeyMouseBattery.pyw"
    return [sys.executable, str(script)]


def is_windows() -> bool:
    return os.name == "nt"
