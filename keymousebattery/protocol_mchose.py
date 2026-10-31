"""迈从 V1 协议（20 字节 report 0x13）：只做会话、电量查询与推送解析。

依据：上游 docs/hardware/mchose.md §1、§5；MchoseV1Codec.cs / MchoseMouseCodec.cs。
"""

from __future__ import annotations

import dataclasses
from typing import Optional

REPORT_ID = 0x13
SESSION_CMD = 0x05
BATTERY_CMD = 0x4A
PUSH_CMD = 0x0A
FRAME_SIZE = 20

PUSH_TYPE_BATTERY = 0x05
PUSH_TYPE_STATE = 0x02

CHARGING_BIT = 0x10
ON_BATTERY_FLAG = 0x01

# 上游对 0/1% 的过滤是协议策略（dongle 缓存帧会出现 0），原始值仍随诊断输出。
INVALID_PERCENT_FLOOR = 1

MODELS = {
    "03000000021C": "G87",
    "030000000077": "K99",
    "0300000001DF": "K99 V2",
    "030000000132": "G98",
    "0300000000D6": "X75",
    "0A0000000003": "G98 Pro",
    "0300000001C6": "X75 V2",
    "030000000115": "G75 Pro",
    "0A0000000018": "G98 V2",
    "0A000000002B": "UT98",
    "0A0000000001": "Z75",
    "0A0000000009": "Z75S",
    "0300000001C7": "KX75",
    "030000000174": "GX87",
    "0300000001ED": "GX87 V2",
    "030000000135": "K87",
    "030000000335": "G75 V2",
    "0A0000000034": "G87 V2",
}

TARGET_KEY = "mchose:3554fa09"
TARGET_VID = 0x3554
TARGET_PID = 0xFA09
# 本机实测的接收器是 FA07（产品串同为 MCHOSE G75 5.0，ACK 密码仍是 G75 Pro）：
# 同一固件族不同批次换了 PID 后缀，认不认领仍由会话 ACK 型号密码决定。
TARGET_PIDS = (0xFA09, 0xFA07)
TARGET_IDS = tuple((TARGET_VID, pid) for pid in TARGET_PIDS)
TARGET_USAGE_PAGE = 0xFF02
TARGET_USAGE = 0x0002


def checksum(payload: bytes) -> int:
    return sum(payload[: FRAME_SIZE - 1]) & 0xFF


def frame(cmd: int, param: int = 0) -> bytes:
    body = bytearray(FRAME_SIZE)
    body[0] = REPORT_ID
    body[1] = cmd
    body[2] = param
    body[FRAME_SIZE - 1] = checksum(body)
    return bytes(body)


def session_frame() -> bytes:
    return frame(SESSION_CMD, 0x01)


def battery_frame() -> bytes:
    return frame(BATTERY_CMD, 0x01)


def is_valid_frame(data: bytes) -> bool:
    return len(data) >= FRAME_SIZE and data[0] == REPORT_ID and data[FRAME_SIZE - 1] == checksum(data)


def model_from_password(chunk: bytes) -> Optional[str]:
    if len(chunk) < 6:
        return None
    return MODELS.get(chunk[:6].hex().upper())


def model_from_session_ack(data: bytes) -> Optional[str]:
    """ACK 的密码在 [5..10]；[6] 只为兼容多一个填充字节的旧样本。"""
    for offset in (0, 1):
        if len(data) < offset + 12:
            continue
        if data[offset] != REPORT_ID or data[offset + 1] != SESSION_CMD:
            continue
        model = model_from_password(data[offset + 5 : offset + 11])
        if model:
            return model
        model = model_from_password(data[offset + 6 : offset + 12])
        if model:
            return model
    return None


@dataclasses.dataclass(frozen=True)
class Battery:
    percent: int
    charging: Optional[bool]
    raw_percent: int
    raw_flag: int
    valid: bool


def percent_is_usable(raw: int) -> bool:
    return INVALID_PERCENT_FLOOR < raw <= 100


def parse_battery(data: bytes) -> Optional[Battery]:
    if len(data) < FRAME_SIZE or data[0] != REPORT_ID or data[1] != BATTERY_CMD:
        return None
    if data[FRAME_SIZE - 1] != checksum(data):
        return None
    raw_percent = data[5]
    raw_flag = data[6]
    charging: Optional[bool]
    if raw_flag & CHARGING_BIT:
        charging = True
    elif raw_flag == ON_BATTERY_FLAG:
        charging = False
    else:
        charging = None
    return Battery(
        percent=raw_percent,
        charging=charging,
        raw_percent=raw_percent,
        raw_flag=raw_flag,
        valid=percent_is_usable(raw_percent),
    )


@dataclasses.dataclass(frozen=True)
class Push:
    kind: str
    percent: Optional[int] = None
    charging: Optional[bool] = None
    payload: int = 0


def parse_push(data: bytes) -> Optional[Push]:
    """[5] 是消息类型位：0x05 才是电量，0x02 是状态通知（[6] 不是电量）。"""
    for offset in (0, 1):
        if len(data) < offset + FRAME_SIZE:
            continue
        chunk = data[offset:]
        if chunk[0] != REPORT_ID or chunk[1] != PUSH_CMD:
            continue
        if chunk[FRAME_SIZE - 1] != checksum(chunk):
            continue
        kind = chunk[5]
        if kind == PUSH_TYPE_BATTERY:
            raw = chunk[6]
            flag = chunk[7]
            charging = True if flag & CHARGING_BIT else (False if flag == ON_BATTERY_FLAG else None)
            return Push("battery", percent=raw if percent_is_usable(raw) else None,
                        charging=charging, payload=raw)
        if kind == PUSH_TYPE_STATE:
            return Push("state", payload=chunk[6])
        return Push("other", payload=kind)
    return None
