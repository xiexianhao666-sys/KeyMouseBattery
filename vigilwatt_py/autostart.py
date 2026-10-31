"""开机自启：只写当前用户 HKCU Run 下的一个值，不加引号就会在含空格的路径上炸掉。

规则（对应规格第 6 条）：
- 只有冻结版、且用户在设置页明确开启后才写；
- 命令是"绝对 exe 路径加引号 + --background"，不要求管理员；
- 读取实际注册结果，写入失败返回原因由界面恢复开关，禁止假成功；
- 关闭只删除本程序的值，不碰其它启动项。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import identity

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "VigilWattPy"
BACKGROUND_FLAG = "--background"


@dataclass(frozen=True)
class AutostartState:
    """一次读取的完整结果：把"没登记"和"读不到"分开，界面才不会误判。"""

    supported: bool
    readable: bool
    registered: bool
    raw: str
    note: str

    @property
    def state(self) -> str:
        """dev / error / registered / other / missing。"""
        if not self.supported:
            return "dev"
        if not self.readable:
            return "error"
        if self.registered:
            return "registered"
        return "other" if self.raw else "missing"



class Registry:
    """最小注册表接口，测试用内存后端替换。"""

    def get(self, name: str) -> Optional[str]:
        raise NotImplementedError

    def set(self, name: str, value: str) -> None:
        raise NotImplementedError

    def delete(self, name: str) -> bool:
        raise NotImplementedError


class WinRegistry(Registry):
    def _open(self, access: int):
        import winreg

        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)

    def get(self, name: str) -> Optional[str]:
        import winreg

        try:
            with self._open(winreg.KEY_READ) as key:
                value, _kind = winreg.QueryValueEx(key, name)
                return str(value)
        except FileNotFoundError:
            return None
        except OSError as exc:
            if getattr(exc, "winerror", None) in (2, 3):
                return None
            raise

    def set(self, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
                return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            if getattr(exc, "winerror", None) in (2, 3):
                return False
            raise


_BACKEND: Registry = WinRegistry()


def set_backend(backend: Registry) -> None:
    global _BACKEND
    _BACKEND = backend


def backend() -> Registry:
    return _BACKEND


def is_supported() -> bool:
    return identity.is_frozen()


def target_command(exe: Optional[Path] = None) -> str:
    """路径可能含空格与中文：整体加引号，再追一个后台参数。"""
    path = Path(exe) if exe is not None else Path(sys.executable)
    return '"%s" %s' % (path, BACKGROUND_FLAG)


def _current_exe() -> Path:
    return Path(sys.executable).resolve()


def inspect(exe: Optional[Path] = None) -> AutostartState:
    """给界面用的一次性快照：读不到就说读不到，不冒充"没登记"。"""
    if not is_supported():
        return AutostartState(False, True, False, "", "源码运行不会登记开机启动，打包后可用")
    try:
        command = _BACKEND.get(VALUE_NAME)
    except OSError as exc:
        return AutostartState(True, False, False, "", "无法读取启动项：%s" % exc)
    if not command:
        return AutostartState(True, True, False, "", "未登记开机启动")
    expected = target_command(exe or _current_exe())
    if command.strip().lower() == expected.strip().lower():
        return AutostartState(True, True, True, command, "已登记：登录 Windows 后在后台启动")
    return AutostartState(True, True, False, command,
                          "启动项指向其它位置，请重新启用：%s" % command)


def read_state(exe: Optional[Path] = None) -> Tuple[bool, str, str]:
    """返回 (是否注册且指向当前程序, 原始命令, 说明)。"""
    state = inspect(exe)
    if not state.readable:
        return False, "", state.note
    return state.registered, state.raw, state.note



def enable(exe: Optional[Path] = None) -> Tuple[bool, str]:
    if not is_supported():
        return False, "源码运行不支持开机自启，请使用便携包里的 exe"
    command = target_command(exe or _current_exe())
    try:
        _BACKEND.set(VALUE_NAME, command)
    except OSError as exc:
        return False, "写入启动项失败：%s" % exc
    state = inspect(exe)
    if not state.readable:
        return False, "写入后无法回读注册表，不能确认已开启：%s" % state.note
    if not state.registered:
        return False, "写入后校验失败：%s" % state.note
    return True, "已开启：登录 Windows 后在后台启动"


def disable() -> Tuple[bool, str]:
    """删除后必须回读到"读得到且确实没有本程序的值"，才算关闭。"""
    try:
        removed = _BACKEND.delete(VALUE_NAME)
    except OSError as exc:
        return False, "删除启动项失败：%s" % exc
    readable, raw = _raw_value()
    if not readable:
        return False, "删除后无法回读注册表，不能确认已关闭（原值可能仍在，请稍后重试）"
    if raw:
        return False, "删除后仍存在启动项，请检查权限"
    return True, "已关闭开机自启" if removed else "开机自启本来就是关闭的"


def sync_runtime(desired: bool) -> Tuple[bool, str]:
    """把配置里的期望值落到注册表，返回 (结果, 说明)。"""
    if desired:
        return enable()
    return disable()


def _raw_value() -> Tuple[bool, str]:
    """(是否读到, 原始命令)；与"是否支持自启"无关，方便判断该项是否真的存在。"""
    try:
        return True, _BACKEND.get(VALUE_NAME) or ""
    except OSError:
        return False, ""


def ensure_registered(desired: bool) -> Tuple[bool, str, bool]:
    """把注册表对齐到 desired，返回 (是否达成, 说明, 是否改动过)。

    以注册表实际状态为准，而不是配置里的旧值：程序被移动过、或注册项指向
    其它位置时，即使配置已经是"开启"也必须重写一次。
    读不到注册表时一律失败且不增删：空字符串不等于"没有这个值"。
    """
    readable, raw = _raw_value()
    if not readable:
        return False, "无法读取注册表，未改动开机启动项（原状态未知，请重试）", False
    if desired and raw:
        expected = target_command()
        if raw.strip().lower() == expected.strip().lower():
            return True, "已注册", False
    if not desired and not raw:
        return True, "未注册", False
    done, message = (enable() if desired else disable())
    return done, message, True


def configured_command_matches(exe: Optional[Path] = None) -> bool:
    ok, _raw, _note = read_state(exe)
    return ok
