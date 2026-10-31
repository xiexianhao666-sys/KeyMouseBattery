"""统一状态模型：null 表示未知，绝不用 0 顶替。"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from typing import Optional

CONNECTION_LABELS = {
    "usb": "USB 接收器",
    "ble": "蓝牙",
    "unknown": "连接方式未知",
}


@dataclasses.dataclass(frozen=True)
class Sample:
    """一次采样结果；level None = 没读到，不是 0%。"""

    level: Optional[int] = None
    charging: Optional[bool] = None
    online: bool = False
    raw_level: Optional[int] = None
    error: str = ""
    # 本轮是否有拿到覆盖该设备的有效证据；False 表示"状态待确认"，不可当断开。
    confirmed: bool = True
    sampled_at: Optional[float] = None

    def age(self, now: Optional[float] = None) -> Optional[float]:
        if self.sampled_at is None:
            return None
        return max(0.0, (now or _dt.datetime.now().timestamp()) - self.sampled_at)


@dataclasses.dataclass(frozen=True)
class Device:
    key: str
    name: str
    kind: str
    connection: str
    source: str
    sample: Sample
    stale: bool = False
    # 设备记录：最近一次真实连接的时间与连接序号，用于排序（新连接置顶）。
    last_connected: Optional[float] = None
    order: int = 0
    # 用户自定义名称；空表示用采集到的原始名称。
    alias: str = ""

    @property
    def online(self) -> bool:
        return bool(self.sample.online and not self.stale)

    @property
    def level_text(self) -> str:
        if self.sample.level is None:
            return "—"
        return "%d%%" % self.sample.level

    @property
    def charging_text(self) -> str:
        if self.sample.charging is None:
            return "充电状态未知"
        return "充电中" if self.sample.charging else "未在充电"

    @property
    def connection_text(self) -> str:
        return CONNECTION_LABELS.get(self.connection, CONNECTION_LABELS["unknown"])

    @property
    def state_text(self) -> str:
        if not self.sample.online:
            return "未连接" if not self.stale else "上次读数"
        if self.sample.error:
            return "读取异常"
        return "已连接"

    def updated_text(self, now: Optional[float] = None) -> str:
        age = self.sample.age(now)
        if age is None:
            return "无有效读数"
        if age < 60:
            return "刚刚更新"
        if age < 3600:
            return "%d 分钟前" % int(age // 60)
        return "%d 小时前" % int(age // 3600)


def unknown_sample(error: str = "") -> Sample:
    return Sample(level=None, charging=None, online=False, error=error)
