"""设备记录：跨重启保留"见过谁"，把身份、上次连接时间与排序序号存到 data 里。

为什么不把记录写进采样循环：采样每 60 秒一轮，每次都写盘只会让文件和磁盘抖动，
而且没有新信息。只在"连接状态变了"或"出现新设备"时落盘。
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .model import CONNECTION_LABELS, Device, Sample

LOGGER = logging.getLogger("keymousebattery.records")

VERSION = 1
KIND_LABELS = {"keyboard": "键盘", "mouse": "鼠标", "headset": "耳机",
               "gamepad": "手柄", "device": "设备"}


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, KIND_LABELS["device"])


@dataclasses.dataclass
class Record:
    """一台被记住过的设备；last_level 只用于内部过渡，不作为用户读数展示。"""

    key: str
    name: str
    kind: str = "device"
    connection: str = "unknown"
    order: int = 0
    last_connected: Optional[float] = None
    last_level: Optional[int] = None
    last_seen: Optional[float] = None

    def to_json(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "kind": self.kind,
            "connection": self.connection,
            "order": int(self.order),
            "last_connected": self.last_connected,
            "last_level": self.last_level,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_json(cls, raw: Dict[str, object]) -> "Record":
        key = str(raw.get("key") or "").strip()
        if not key:
            raise ValueError("record without key")
        kind = str(raw.get("kind") or "device")
        if kind not in KIND_LABELS:
            kind = "device"
        connection = str(raw.get("connection") or "unknown")
        if connection not in CONNECTION_LABELS:
            connection = "unknown"

        def _num(value: object) -> Optional[float]:
            if isinstance(value, bool) or value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            return None

        level = raw.get("last_level")
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 100:
            level = None
        return cls(
            key=key,
            name=str(raw.get("name") or key),
            kind=kind,
            connection=connection,
            order=int(_num(raw.get("order")) or 0),
            last_connected=_num(raw.get("last_connected")),
            last_level=level,
            last_seen=_num(raw.get("last_seen")),
        )

    def offline_device(self) -> Device:
        return Device(key=self.key, name=self.name, kind=self.kind,
                      connection=self.connection, source="record",
                      sample=Sample(level=None, charging=None, online=False),
                      stale=False, last_connected=self.last_connected, order=self.order)

    def live_device(self, device: Device) -> Device:
        return dataclasses.replace(device, last_connected=self.last_connected,
                                   order=self.order)


class RecordStore:
    """records.json 的读写；损坏时留档改名，宁可重来也不让程序起不来。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.records: Dict[str, Record] = {}
        self.next_order = 1

    # ---------- 读写 ----------
    def load(self) -> List[Record]:
        self.records, self.next_order = {}, 1
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            LOGGER.warning("设备记录损坏，已隔离：%s", exc)
            self._quarantine()
            return []
        if not isinstance(data, dict) or data.get("version") != VERSION:
            LOGGER.warning("设备记录版本不支持，已隔离")
            self._quarantine()
            return []
        raw_records = data.get("devices")
        if not isinstance(raw_records, list):
            self._quarantine()
            return []
        for raw in raw_records:
            if not isinstance(raw, dict):
                continue
            try:
                record = Record.from_json(raw)
            except ValueError:
                continue
            self.records[record.key] = record
        self.next_order = max([self.next_order] + [r.order + 1 for r in self.records.values()])
        return list(self.records.values())

    def _quarantine(self) -> None:
        try:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            self.path.replace(self.path.with_name(self.path.name + ".bad-" + stamp))
        except OSError:
            LOGGER.warning("隔离损坏的设备记录失败", exc_info=True)

    def save(self) -> bool:
        data = {
            "version": VERSION,
            "next_order": self.next_order,
            "devices": [self.records[key].to_json() for key in sorted(self.records)],
        }
        folder = self.path.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix=".records-", dir=str(folder))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        except OSError as exc:
            LOGGER.warning("保存设备记录失败：%s", exc)
            return False
        return True

    # ---------- 更新 ----------
    def observe(self, devices: Iterable[Device], now: Optional[float] = None) -> bool:
        """把一轮采集结果写进记录；返回"需要落盘"。

        只有"已确认的在线证据"才能新增记录：仅枚举到或仅配对不代表连接过。
        """
        now = now or time.time()
        changed = False
        for device in devices:
            sample = device.sample
            confirmed_online = bool(sample.online) and bool(sample.confirmed)
            record = self.records.get(device.key)
            if record is None:
                if not confirmed_online:
                    # 陌生/离线/未确认的设备不进历史，避免把配对表整个抄进来。
                    continue
                record = Record(key=device.key, name=device.name, kind=device.kind,
                                connection=device.connection, order=self.next_order)
                self.next_order += 1
                self.records[device.key] = record
                changed = True
            for attr, value in (("name", device.name), ("kind", device.kind),
                                ("connection", device.connection)):
                if getattr(record, attr) != value:
                    setattr(record, attr, value)
                    changed = True
            if confirmed_online:
                if record.last_seen is None:
                    # 从"未连接/未知"变成在线：这才是新连接，更新序号与时间。
                    record.order = self.next_order
                    self.next_order += 1
                    record.last_connected = now
                    changed = True
                record.last_seen = now
                if sample.level is not None and record.last_level != sample.level:
                    record.last_level = sample.level
                    changed = True
            elif not sample.confirmed:
                # 失去状态证据：保留最后确认的排序位置，不写连接/断开事件。
                continue
            elif record.last_seen is not None:
                # 采集端明确报告"不在了"才算断开；读不到电量不等于断开。
                record.last_seen = None
                changed = True
        return changed

    # ---------- 排序视图 ----------
    @staticmethod
    def sort_key(device: Device) -> tuple:
        """已连接在上（最新连接优先），未连接按最后连接时间倒序，再用稳定 key 兜底。"""
        online = 1 if device.sample.online else 0
        return (-online, -int(device.order or 0), -float(device.last_connected or 0.0), device.key)

    def merge(self, live: Iterable[Device]) -> List[Device]:
        """live 覆盖记录；记录里没有 live 的设备以离线卡片出现。"""
        live_map = {device.key: device for device in live}
        out: List[Device] = []
        for key, record in self.records.items():
            device = live_map.get(key)
            if device is None:
                out.append(record.offline_device())
            else:
                out.append(record.live_device(device))
        for key, device in live_map.items():
            if key not in self.records and device.sample.online and device.sample.confirmed:
                out.append(device)
        return sorted(out, key=self.sort_key)
