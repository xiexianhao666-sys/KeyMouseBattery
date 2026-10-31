"""采集调度：一轮扫描所有已配对的蓝牙设备，再加可选的 2.4G 接收器备用通道。

设备数量不设固定上限：列表由扫描结果决定，UI 不再预建两个槽位。
真正读不到电量的设备如实标记（在线但"电量暂不可用"），不编造 0% 或旧值。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Sequence

from .ble_watcher import BleScanner, BleReading, ScanResult, infer_kind, reading_sample
from .mchose_plugin import KeyboardSensor
from .model import Device, Sample

LOGGER = logging.getLogger("vigilwatt.poller")

DONGLE_KEY = "usb:compx-receiver"
MISS_LIMIT = 2


class Collector:
    def __init__(self, interval: int = 60, low: int = 20, bluetooth: bool = True,
                 mchose_enabled: bool = True) -> None:
        self.interval = max(5, int(interval))
        self.low = low
        self._scanner = BleScanner(enabled=bluetooth)
        self.bluetooth = bluetooth
        self._dongle = KeyboardSensor() if mchose_enabled else None
        self._lock = threading.Lock()
        self._snapshots: Dict[str, Device] = {}
        self._attempts: Dict[str, float] = {}
        self._success: Dict[str, float] = {}
        self._misses: Dict[str, int] = {}
        self._first_round = threading.Event()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._threads: List[threading.Thread] = []

    # ---------- 生命周期 ----------
    def start(self) -> None:
        self._scanner.start()
        thread = threading.Thread(target=self._ble_loop, name="ble-scan", daemon=True)
        thread.start()
        self._threads.append(thread)
        if self._dongle is not None:
            thread = threading.Thread(target=self._dongle_loop, name="dongle", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        try:
            self._scanner.stop()
        except Exception:  # noqa: BLE001 - 退出路径不能抛
            LOGGER.exception("停止蓝牙扫描失败")
        for thread in self._threads:
            thread.join(timeout=3.0)
        self._threads.clear()

    def set_interval(self, interval: int) -> None:
        self.interval = max(5, int(interval))
        self._wake.set()

    def set_low(self, low: int) -> None:
        self.low = low

    def set_bluetooth(self, enabled: bool) -> None:
        self.bluetooth = bool(enabled)
        self._scanner.enabled = bool(enabled)
        self._wake.set()

    def refresh_now(self) -> None:
        self._wake.set()

    def first_round_done(self) -> bool:
        return self._first_round.is_set()

    def attempts(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._attempts)

    # ---------- 线程 ----------
    def _wait(self) -> bool:
        self._wake.wait(timeout=self.interval)
        self._wake.clear()
        return not self._stop.is_set()

    def _ble_loop(self) -> None:
        while not self._stop.is_set():
            try:
                result = self._scanner.scan()
                self._apply_scan(result)
            except Exception:  # noqa: BLE001 - 扫描异常不能拖垮进程
                LOGGER.exception("蓝牙扫描异常")
            self._first_round.set()
            if not self._wait():
                break

    def _apply_scan(self, result: ScanResult) -> None:
        """只有拿到有效覆盖结果时才判断"谁不见了"；失败/部分覆盖一律待确认。"""
        now = time.time()
        seen = set()
        for reading in result.readings:
            key = reading.key
            seen.add(key)
            device = Device(key=key, name=reading.name,
                            kind=reading.kind or infer_kind(reading.name),
                            connection="ble", source="windows-ble",
                            sample=reading_sample(reading))
            self._publish(key, device, now)
        with self._lock:
            known = [key for key in self._snapshots if key.startswith("ble:")]
        if result.error or not result.complete:
            # 枚举失败 / 预算耗尽 / 部分覆盖：本轮不能据此宣布任何设备断开。
            for key in known:
                if key in seen:
                    continue
                previous = self._snapshots.get(key)
                if previous is None or not previous.sample.online:
                    continue
                unconfirmed = Device(key=previous.key, name=previous.name, kind=previous.kind,
                                     connection=previous.connection, source=previous.source,
                                     sample=Sample(level=previous.sample.level,
                                                   charging=previous.sample.charging,
                                                   online=True, confirmed=False,
                                                   error="本轮未覆盖，状态待确认",
                                                   sampled_at=previous.sample.sampled_at))
                self._publish(key, unconfirmed, now, quiet=True)
            self._misses.clear()
            return
        # 覆盖完整：连续两轮“确实不在枚举结果里”才判离线，避免一次抖动掉卡。
        for key in known:
            if key in seen:
                continue
            self._misses[key] = self._misses.get(key, 0) + 1
            if self._misses[key] >= MISS_LIMIT:
                previous = self._snapshots.get(key)
                if previous is not None and previous.sample.online:
                    offline = Device(key=previous.key, name=previous.name, kind=previous.kind,
                                     connection=previous.connection, source=previous.source,
                                     sample=Sample(level=None, charging=None, online=False,
                                                   error="设备不在范围内", sampled_at=now))
                    self._publish(key, offline, now)

    def _dongle_loop(self) -> None:
        # USB 接收器是独立通道：不能因为“有任意蓝牙设备在线”就停采，
        # 除非将来能确证两者是同一物理设备（目前没有这种证据）。
        assert self._dongle is not None
        while not self._stop.is_set():
            self._poll_dongle_once()
            self._first_round.set()
            if not self._wait():
                break

    def _poll_dongle_once(self) -> None:
        """USB 通道单次采集：与蓝牙是否在线无关，各通道独立按预算跑。"""
        assert self._dongle is not None
        try:
            self._dongle.read()
            device = self._dongle.device()
            sample = device.sample
            self._publish(DONGLE_KEY, Device(
                key=DONGLE_KEY, name=device.name or "2.4G 键盘", kind="keyboard",
                connection="usb", source="compx-receiver", sample=sample),
                time.time())
        except Exception:  # noqa: BLE001
            LOGGER.exception("接收器采集异常")

    def _fresh_ble_reading(self) -> bool:
        now = time.time()
        with self._lock:
            for device in self._snapshots.values():
                if (device.connection == "ble" and device.sample.online
                        and device.sample.level is not None
                        and now - (device.sample.sampled_at or 0.0) <= max(120.0, self.interval * 2.0)):
                    return True
        return False

    # ---------- 状态 ----------
    def _publish(self, key: str, device: Device, now: Optional[float] = None,
                 quiet: bool = False) -> None:
        now = now or time.time()
        with self._lock:
            self._snapshots[key] = device
            self._attempts[key] = now
            if device.sample.online and device.sample.level is not None:
                self._success[key] = now
                self._misses[key] = 0
        if quiet:
            return
        LOGGER.info("%s level=%s online=%s confirmed=%s err=%s", key, device.sample.level,
                    device.sample.online, device.sample.confirmed, device.sample.error or "-")

    def devices(self) -> List[Device]:
        with self._lock:
            return list(self._snapshots.values())

    def diagnostics(self) -> Dict[str, str]:
        with self._lock:
            return {key: (device.sample.error or "ok") for key, device in self._snapshots.items()}

    def scanner_error(self) -> str:
        return self._scanner.last_error

def model_tokens(name: str) -> set:
    """从设备名里取出型号 token：字母数字组合、含数字、长度 >=3（如 G75、K99）。"""
    tokens = set()
    word = ""
    for ch in (name or "").upper():
        if ch.isalnum():
            word += ch
        else:
            if len(word) >= 3 and any(c.isdigit() for c in word):
                tokens.add(word)
            word = ""
    if len(word) >= 3 and any(c.isdigit() for c in word):
        tokens.add(word)
    return tokens


def merge_usb_channels(devices: Sequence[Device]) -> List[Device]:
    """同一类设备只要已有蓝牙记录，就不再单列接收器那张卡。

    接收器不提供设备标识（只有“一把键盘”和一次读数），型号名还可能是旧缓存，
    无法判断是不是同一把键盘；而同一把键盘会同时出现在两条通道里。这里用结构性
    规则：某个类别（键盘/鼠标/耳机…）已经有蓝牙设备时，接收器通道的记录视为同一
    台设备的另一条通道，只保留蓝牙那张卡；该类别没有任何蓝牙设备时，接收器卡片
    照常显示，保证只插接收器也能看到电量。
    """
    ble_kinds = {device.kind for device in devices if device.connection == "ble"}
    if not ble_kinds:
        return list(devices)
    kept: List[Device] = []
    for device in devices:
        if device.connection == "usb" and device.kind in ble_kinds:
            LOGGER.info("接收器通道与蓝牙 %s 同类别，合并为一张卡：%s",
                        device.kind, device.name)
            continue
        kept.append(device)
    return kept

