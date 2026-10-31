"""命令行：--version / --probe / --shot。默认启动图形界面。"""

from __future__ import annotations

import json
import sys
from typing import List

from . import identity


def _console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def version() -> List[str]:
    return [
        "%s · %s %s" % (identity.APP_ID, identity.APP_NAME, identity.APP_VERSION),
        identity.APP_DESCRIPTION,
        identity.PROJECT_URL,
        "解释器 %s" % sys.version.split()[0],
    ]


def probe() -> List[str]:
    from .ble_watcher import BleSensor
    from .mchose_plugin import KeyboardSensor

    lines = ["probe: KeyMouseBattery %s" % identity.APP_VERSION]
    sensors = (
        ("ble-keyboard", BleSensor("keyboard", "MCHOSE", "蓝牙键盘")),
        ("ble-mouse", BleSensor("mouse", "ELECOM", "蓝牙鼠标")),
    )
    try:
        for label, sensor in sensors:
            try:
                result = sensor.probe()
                lines.append(json.dumps({
                    "device": label,
                    "target": sensor.name_hint,
                    "source": result.source,
                    "found": result.found,
                    "name": result.name,
                    "level": result.sample.level,
                    "charging": result.sample.charging,
                    "online": result.sample.online,
                    "error": result.error,
                }, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                lines.append(json.dumps({"device": label,
                                         "error": "%s: %s" % (type(exc).__name__, exc)},
                                        ensure_ascii=False))
    finally:
        for _, sensor in sensors:
            sensor.stop()
    try:
        dongle = KeyboardSensor().probe()
        lines.append(json.dumps({
            "device": "mchose-dongle",
            "target": "3554:FA09 / 3554:FA07 usage_page=0xFF02 usage=0x0002",
            "found": dongle.found,
            "model": dongle.model,
            "session_ack": dongle.session_ack,
            "level": dongle.sample.level,
            "charging": dongle.sample.charging,
            "online": dongle.sample.online,
            "error": dongle.error,
        }, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        lines.append(json.dumps({"device": "mchose-dongle",
                                 "error": "%s: %s" % (type(exc).__name__, exc)},
                                ensure_ascii=False))
    return lines


def _emit(lines: List[str], out: str = "") -> int:
    """窗口模式没有控制台：`--out` 把结果写到文件，双份证据才算数。"""
    text = "\n".join(lines) + "\n"
    if out:
        try:
            with open(out, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            sys.stderr.write("无法写入 %s：%s\n" % (out, exc))
            return 2
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            try:
                stream.write(text)
                stream.flush()
            except (ValueError, OSError):
                pass
    return 0


def main(argv: List[str]) -> int:
    _console_utf8()
    args = list(argv[1:])
    out = ""
    if "--out" in args:
        index = args.index("--out")
        if index + 1 >= len(args):
            sys.stderr.write("--out 需要一个输出路径\n")
            return 2
        out = args[index + 1]
    if "--version" in args:
        return _emit(version(), out)
    if "--probe" in args:
        return _emit(probe(), out)
    shot = ""
    if "--shot" in args:
        index = args.index("--shot")
        if index + 1 >= len(args):
            sys.stderr.write("--shot 需要一个输出路径\n")
            return 2
        shot = args[index + 1]
    background = "--background" in args
    page = "devices"
    if "--page" in args:
        index = args.index("--page")
        if index + 1 < len(args):
            page = args[index + 1]
    from .app import App

    return App(shot=shot, verbose="--verbose" in args, background=background,
               shot_page=page).run()
