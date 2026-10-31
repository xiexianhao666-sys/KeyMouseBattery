"""配置：JSON、逐键校验、损坏隔离、旧键迁移。

`low = 0` 表示关闭低电量提醒；界面仍按 low_visual 显示颜色，两个语义分开：
`low` 是"提醒阈值"，0 时卡片不因低电量变色。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

INTERVAL_CHOICES = (30, 60, 120, 300)
INTERVAL_DEFAULT = 60
LOW_CHOICES = (0, 10, 20, 30)
LOW_DEFAULT = 20
TRAY_ICON_CHOICES = ("number", "battery")
TRAY_ICON_DEFAULT = "number"
LOW_VISUAL_FLOOR = 20

DEFAULTS: dict[str, Any] = {
    "interval": INTERVAL_DEFAULT,
    "low": LOW_DEFAULT,
    "tray_icon": TRAY_ICON_DEFAULT,
    "desktop_bar": False,
    "bar_pos": None,
    "autostart": False,
    "keep_disconnected": True,
    "ble_target": "ELECOM",
    "ble_keyboard": "MCHOSE",
    "mchose_enabled": True,
    "percent_in_icon": True,
}


def _valid_interval(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return DEFAULTS["interval"]
    return number if number in INTERVAL_CHOICES else DEFAULTS["interval"]


def _valid_low(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return DEFAULTS["low"]
    return number if number in LOW_CHOICES else DEFAULTS["low"]


def _valid_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _valid_text(value: Any, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned[:32]
    return default


def _valid_tray_icon(value: Any) -> str:
    return value if value in TRAY_ICON_CHOICES else DEFAULTS["tray_icon"]


def _valid_pos(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return [int(value[0]), int(value[1])]
        except (TypeError, ValueError):
            return None
    return None


def low_visual(low: int) -> int:
    """提醒关闭时仍保留一个用于配色的低电量阈值。"""
    return low if low > 0 else LOW_VISUAL_FLOOR


def validate(raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """未知键丢弃；越界值回退默认；返回 (配置, 报告)。"""
    report: dict[str, Any] = {"dropped": [], "fixed": [], "migrated": []}
    cfg = dict(DEFAULTS)
    if not isinstance(raw, dict):
        report["fixed"].append("root")
        return cfg, report
    for key, value in raw.items():
        if key not in DEFAULTS:
            # 旧版本把托盘模式写成 percent_in_icon=True/False，迁移到 tray_icon。
            report["dropped"].append(key)
            continue
        if key == "interval":
            cfg[key] = _valid_interval(value)
        elif key == "low":
            cfg[key] = _valid_low(value)
        elif key == "tray_icon":
            cfg[key] = _valid_tray_icon(value)
        elif key == "bar_pos":
            cfg[key] = _valid_pos(value)
        elif key in ("desktop_bar", "autostart", "keep_disconnected", "mchose_enabled",
                     "percent_in_icon"):
            cfg[key] = _valid_bool(value, DEFAULTS[key])
        elif key in ("ble_target", "ble_keyboard"):
            cfg[key] = _valid_text(value, DEFAULTS[key])
        if cfg[key] != value:
            report["fixed"].append(key)
    if "percent_in_icon" in raw and "tray_icon" not in raw:
        migrated = "number" if raw.get("percent_in_icon") is not False else "battery"
        cfg["tray_icon"] = migrated
        report["migrated"].append("percent_in_icon->tray_icon")
    if "percent_in_icon" in raw:
        report["dropped"].append("percent_in_icon")
    return cfg, report


def load(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.exists():
        return dict(DEFAULTS), {"created": False, "missing": True}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        quarantined = path.with_suffix(path.suffix + ".bad-%d" % int(time.time()))
        try:
            os.replace(path, quarantined)
        except OSError:
            pass
        return dict(DEFAULTS), {"created": False, "quarantined": str(quarantined)}
    cfg, report = validate(raw)
    report["created"] = False
    return cfg, report


def save(path: Path, cfg: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(cfg, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def write_atomic(path: Path, cfg: dict[str, Any]) -> tuple[bool, str]:
    """给界面用：失败必须能回滚并如实反馈，不能假装成功。"""
    try:
        save(path, cfg)
        return True, ""
    except OSError as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def load_or_create(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg, report = load(path)
    if report.get("missing"):
        try:
            save(path, cfg)
            report["created"] = True
        except OSError as exc:
            report["create_error"] = "%s: %s" % (type(exc).__name__, exc)
    elif report.get("migrated") or report.get("fixed") or report.get("dropped"):
        try:
            save(path, cfg)
            report["rewritten"] = True
        except OSError as exc:
            report["create_error"] = "%s: %s" % (type(exc).__name__, exc)
    return cfg, report
