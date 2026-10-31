"""低电量提醒：只在"在线且本次读数有效"时跨阈值提醒一次。

- 启动时已经低电量的设备允许提醒一次（首次见到就提醒，而不是只等"跨入"）；
- 同一设备一次低电量只提醒一次；回到阈值以上至少 5 个百分点才算重新武装；
- 断连/旧读数不提醒，也不改变武装状态（避免一次断线让提醒永远不再触发）。
"""

from __future__ import annotations

import dataclasses
import time
from typing import Dict, List, Optional, Sequence

from .model import Device

RECOVER_MARGIN = 5


@dataclasses.dataclass
class Alert:
    kind: str
    key: str
    title: str
    text: str


class Alerts:
    def __init__(self) -> None:
        self._armed: Dict[str, bool] = {}

    def reset(self) -> None:
        self._armed.clear()

    def check(self, devices: Sequence[Device], threshold: int,
              now: Optional[float] = None) -> List[Alert]:
        now = time.time() if now is None else now
        out: List[Alert] = []
        if threshold <= 0:
            self._armed.clear()
            return out
        seen = set()
        for device in devices:
            seen.add(device.key)
            sample = device.sample
            armed = self._armed.get(device.key, True)
            level = sample.level
            fresh = sample.online and not device.stale and level is not None and 0 < level <= 100
            if fresh and level > threshold + RECOVER_MARGIN - 1:
                self._armed[device.key] = True
                continue
            if not fresh:
                # 断连/旧值/未知：保持原武装状态，不触发。
                self._armed.setdefault(device.key, True)
                continue
            if level <= threshold and armed:
                self._armed[device.key] = False
                out.append(Alert(
                    kind="low",
                    key=device.key,
                    title="电量偏低",
                    text="%s 剩余 %d%%，建议尽快充电。" % (device.name, level),
                ))
        for key in list(self._armed):
            if key not in seen:
                self._armed.pop(key, None)
        return out
