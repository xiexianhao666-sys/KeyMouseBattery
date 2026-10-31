"""迈从键盘（3554:FA09 / FF02:0002）采集：一场会话 + 一条电量查询，认型号才接手。"""

from __future__ import annotations

import dataclasses
import time
from typing import Callable, Optional

from . import log, protocol_mchose as proto
from .model import Sample

LOGGER = log.get("mchose")

REPLY_TIMEOUT = 1.0
ATTEMPTS = 3
ATTEMPT_GAP = 0.5
BACKOFF_STEPS = (30.0, 60.0, 120.0, 240.0, 300.0)


def _new_hid():
    import hid  # 延迟导入：--version 不需要 hidapi

    return hid


def _is_target(entry: dict) -> bool:
    return (entry.get("vendor_id"), entry.get("product_id")) in proto.TARGET_IDS


def target_collections(entries: list[dict]) -> list[dict]:
    return [entry for entry in entries or [] if _is_target(entry)]


def battery_interface(entries: list[dict]) -> Optional[dict]:
    """只认 0xFF02/0x0002 那条厂商集合；同 PID 的其它集合一律不碰。"""
    for entry in entries or []:
        if not _is_target(entry):
            continue
        if entry.get("usage_page") == proto.TARGET_USAGE_PAGE and entry.get("usage") == proto.TARGET_USAGE:
            return entry
    return None


@dataclasses.dataclass
class Probe:
    found: bool = False
    model: Optional[str] = None
    session_ack: Optional[str] = None
    sample: Sample = dataclasses.field(default_factory=Sample)
    error: str = ""


class KeyboardSensor:
    """持有指纹、型号与最近一次读数；失败时保留旧值并标 stale。"""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.name = "迈从键盘"
        self.model: Optional[str] = None
        self.last: Sample = Sample()
        self.failures = 0
        self.backoff_until = 0.0
        self.backoff_index = 0
        self.last_ack = ""

    # ---- 设备层 ----
    def _open(self):
        hid = _new_hid()
        entries = []
        for vid, pid in proto.TARGET_IDS:
            entries.extend(hid.enumerate(vid, pid))
        entry = battery_interface(entries)
        if entry is None:
            return None, "未找到目标接口（FF02:0002）"
        device = hid.device()
        device.open_path(entry["path"])
        device.set_nonblocking(1)
        return device, ""

    @staticmethod
    def _read_frame(device, deadline: float) -> Optional[bytes]:
        remaining = max(0.0, deadline - time.monotonic())
        data = device.read(64, int(remaining * 1000))
        if not data:
            return None
        return bytes(data)

    def _session(self, device) -> tuple[Optional[str], str]:
        device.write(proto.session_frame())
        deadline = time.monotonic() + REPLY_TIMEOUT
        while time.monotonic() < deadline:
            raw = self._read_frame(device, deadline)
            if raw is None:
                continue
            model = proto.model_from_session_ack(raw)
            if model:
                self.last_ack = raw[:proto.FRAME_SIZE].hex(" ").upper()
                return model, ""
        return None, "会话无 ACK"

    def _query(self, device) -> tuple[Optional[proto.Battery], Optional[proto.Push], str]:
        device.write(proto.battery_frame())
        deadline = time.monotonic() + REPLY_TIMEOUT
        while time.monotonic() < deadline:
            raw = self._read_frame(device, deadline)
            if raw is None:
                continue
            battery = proto.parse_battery(raw)
            if battery is not None:
                return battery, None, ""
            push = proto.parse_push(raw)
            if push is not None and push.kind == "battery":
                return None, push, ""
        return None, None, "查询无应答"

    # ---- 对外 ----
    def probe(self) -> Probe:
        result = Probe()
        if not self.enabled:
            result.error = "插件已关闭"
            return result
        device = None
        try:
            device, error = self._open()
            if device is None:
                result.error = error
                return result
            result.found = True
            model, error = self._session(device)
            if model is None:
                result.error = error
                return result
            result.model = model
            result.session_ack = self.last_ack
            if model != "G75 Pro":
                # 其它型号共用同一指纹：不认领，避免抢 AULA 等设备
                result.error = "型号 %s 不在本阶段支持范围" % model
                return result
            self.model = model
            battery, push, error = self._query(device)
            if battery is not None:
                result.sample = self._sample_from_battery(battery)
            elif push is not None:
                result.sample = Sample(level=push.percent, charging=push.charging,
                                       online=True, sampled_at=time.time())
            else:
                result.error = error
            return result
        except OSError as exc:
            result.error = "%s: %s" % (type(exc).__name__, exc)
            return result
        finally:
            if device is not None:
                try:
                    device.close()
                except Exception:  # noqa: BLE001 - 关闭失败不该掩盖读数
                    LOGGER.debug("close failed", exc_info=True)

    @staticmethod
    def _sample_from_battery(battery: proto.Battery) -> Sample:
        if not battery.valid:
            # 过滤是协议策略（0/1 是 dongle 缓存帧），原始值留在 error 里供诊断
            return Sample(level=None, charging=battery.charging, online=True,
                          raw_level=battery.raw_percent,
                          error="读数被过滤（原始 %d%%）" % battery.raw_percent,
                          sampled_at=time.time())
        return Sample(level=battery.percent, charging=battery.charging, online=True,
                      raw_level=battery.raw_percent, sampled_at=time.time())

    def read(self) -> Sample:
        now = time.monotonic()
        if now < self.backoff_until:
            return self._stale("退避中")
        if not self.enabled:
            return self._stale("插件已关闭")
        probe = self.probe()
        if probe.sample.level is not None or probe.sample.charging is not None:
            self.last = probe.sample
            self.failures = 0
            self.backoff_index = 0
            self.backoff_until = 0.0
            return self.last
        self.failures += 1
        if self.failures >= 3:
            step = BACKOFF_STEPS[min(self.backoff_index, len(BACKOFF_STEPS) - 1)]
            self.backoff_until = now + step
            self.backoff_index += 1
            LOGGER.warning("键盘连续 %d 次失败，退避 %.0f 秒", self.failures, step)
            self.failures = 0
        return self._stale(probe.error or "读取失败")

    def _stale(self, error: str) -> Sample:
        previous = self.last
        return Sample(level=previous.level, charging=previous.charging, online=False,
                      raw_level=previous.raw_level, error=error,
                      sampled_at=previous.sampled_at)

    def device(self) -> object:
        """给 UI 用的统一设备视图。"""
        from .model import Device

        name = "迈从 %s" % (self.model or "键盘")
        return Device(
            key=proto.TARGET_KEY,
            name=name,
            kind="keyboard",
            connection="usb",
            source="mchose-v1",
            sample=self.last,
            stale=self.last.level is not None and not self.last.online,
        )
