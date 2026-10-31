"""蓝牙设备电量：只读标准电量服务 0x180F/0x2A19，不写任何特征值。

两台设备实测都走蓝牙：MCHOSE G75 5.0（键盘）与 ELECOM EX-G（鼠标）。
Windows AEP 电量属性键在 PyWinRT 里没有合法写法（`System.Devices.Aep.Battery_Level`
会报 Property key syntax error），所以只走 GATT。充电状态 Windows 不提供，保持 unknown。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import dataclasses
import threading
import time
import uuid
from typing import Any, Optional

from . import log
from .model import Sample

LOGGER = log.get("ble")

NAME_PROP = "System.ItemNameDisplay"
CONNECTED_PROP = "System.Devices.Aep.IsConnected"
ADDRESS_PROP = "System.Devices.Aep.DeviceAddress"
GATT_TIMEOUT = 6.0
BATTERY_SERVICE = uuid.UUID("0000180f-0000-1000-8000-00805f9b34fb")
BATTERY_LEVEL_CHAR = uuid.UUID("00002a19-0000-1000-8000-00805f9b34fb")
KEY_PREFIX = "ble:"


def _normalize(value: Any) -> str:
    return str(value).strip("{}").lower()


def _prop(props: Any, key: str) -> Any:
    if props is None:
        return None
    try:
        return props.lookup(key)
    except Exception:  # noqa: BLE001 - IMapView 的 Python 协议不一定有 lookup
        pass
    try:
        return props[key]
    except Exception:  # noqa: BLE001
        return None


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        return ""


def _device_name(info: Any) -> str:
    """`properties` 里取到的 HSTRING 是未投影的 Object，只能靠 DeviceInformation.name。"""
    name = _text(getattr(info, "name", "")).strip()
    if name:
        return name
    return _text(_prop(getattr(info, "properties", None), NAME_PROP)).strip()


@dataclasses.dataclass
class BleProbe:
    found: bool = False
    name: str = ""
    address: str = ""
    source: str = ""
    sample: Sample = dataclasses.field(default_factory=Sample)
    error: str = ""


class BleSensor:
    """一台蓝牙设备：按名字提示挑设备，再逐次只读电量特征。"""

    def __init__(self, kind: str, name_hint: str, default_name: str,
                 enabled: bool = True) -> None:
        self.kind = kind
        self.name_hint = name_hint
        self.enabled = enabled
        self.default_name = default_name
        self.name = default_name
        self.last = Sample()
        self.last_ok = 0.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    @property
    def key(self) -> str:
        return KEY_PREFIX + self.kind

    # ---- 线程与事件循环 ----
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, name="ble-%s" % self.kind, daemon=True)
        self._thread.start()
        self._ready.wait(5.0)

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        loop.run_forever()

    def stop(self) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)
        self._thread = None
        self._loop = None
        self._ready.clear()

    def _submit(self, coro, timeout: float) -> Any:
        if self._loop is None:
            raise RuntimeError("BLE 线程未启动")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            # 修 R3：超时后显式取消，别把协程留在事件循环里继续跑。
            future.cancel()
            raise

    # ---- 采集 ----
    def probe(self) -> BleProbe:
        result = BleProbe()
        if not self.enabled:
            result.error = "蓝牙采集已关闭"
            return result
        try:
            import winrt.windows.devices.enumeration  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            result.error = "缺少 PyWinRT：%s" % exc
            return result
        try:
            self.start()
            return self._submit(self._probe_async(), GATT_TIMEOUT * 3)
        except Exception as exc:  # noqa: BLE001
            result.error = "%s: %s" % (type(exc).__name__, exc)
            return result

    async def _paired_devices(self):
        from winrt.windows.devices.bluetooth import BluetoothLEDevice
        from winrt.windows.devices.enumeration import DeviceInformation

        selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
        return await asyncio.wait_for(
            DeviceInformation.find_all_async(selector, [NAME_PROP, CONNECTED_PROP], 1), GATT_TIMEOUT
        )

    async def _probe_async(self) -> BleProbe:
        devices = await self._paired_devices()
        info = self._pick(devices)
        if info is None:
            return BleProbe(error="未找到匹配的蓝牙设备（%s）" % self.name_hint)
        name = _device_name(info)
        result = BleProbe(found=True, name=name or self.default_name, source="GATT 180F/2A19",
                          address=self._mask(_prop(info.properties, ADDRESS_PROP)))
        try:
            level, error = await asyncio.wait_for(self._read_gatt(info), GATT_TIMEOUT * 2)
        except asyncio.TimeoutError:
            result.error = "读取超时"
            return result
        if level is None:
            result.error = error
            return result
        result.sample = Sample(level=level, charging=None, online=True, sampled_at=time.time())
        return result

    def _pick(self, devices):
        hint = self.name_hint.lower()
        for info in devices or []:
            name = _device_name(info)
            if hint and hint.lower() in name.lower():
                return info
        return None

    @staticmethod
    def _mask(address: Any) -> str:
        """地址只留末三组：界面能区分同型号多机，又不落完整 MAC。"""
        if address is None:
            return "**"
        text = str(address)
        if ":" in text:
            groups = [part for part in text.split(":") if part]
        else:
            try:
                value = int(text, 16) if isinstance(address, str) else int(address)
            except (TypeError, ValueError):
                return "**"
            groups = ["%02X" % ((value >> shift) & 0xFF) for shift in (40, 32, 24, 16, 8, 0)]
        if len(groups) < 4:
            return "**"
        return "**:**:**:" + ":".join(groups[-3:])

    async def _read_gatt(self, info) -> tuple[Optional[int], str]:
        from winrt.windows.devices.bluetooth import BluetoothCacheMode, BluetoothLEDevice
        from winrt.windows.storage.streams import DataReader

        device = await BluetoothLEDevice.from_id_async(info.id)
        if device is None:
            return None, "无法连接设备"
        try:
            # 修 R3：实时读数必须 UNCACHED，缓存值不能刷新"最后成功读取时间"。
            services_result = await device.get_gatt_services_for_uuid_async(
                BATTERY_SERVICE, BluetoothCacheMode.UNCACHED)
            services = list(services_result.services)
            if not services:
                return None, "设备没有标准电量服务"
            chars_result = await services[0].get_characteristics_for_uuid_async(BATTERY_LEVEL_CHAR)
            chars = list(chars_result.characteristics)
            if not chars:
                return None, "设备没有标准电量特征"
            read = await chars[0].read_value_async(BluetoothCacheMode.UNCACHED)
            status = getattr(read.status, "value", read.status)
            if status not in (0, None):
                return None, "读取失败（状态 %s）" % status
            value = DataReader.from_buffer(read.value).read_byte()
            if 0 <= value <= 100:
                return int(value), ""
            return None, "电量值越界：%d" % value
        finally:
            try:
                device.close()
            except Exception:  # noqa: BLE001
                pass

    def read(self) -> Sample:
        probe = self.probe()
        if probe.sample.level is not None:
            self.last = probe.sample
            self.name = probe.name or self.default_name
            self.last_ok = time.monotonic()
            return self.last
        previous = self.last
        # 修 R1：失败也要写回快照，否则 device() 永远拿到上一次的"在线"状态。
        self.last = Sample(level=previous.level, charging=None, online=False,
                           error=probe.error or "读取失败", sampled_at=previous.sampled_at)
        return self.last

    def device(self) -> object:
        from .model import Device

        return Device(key=self.key, name=self.name, kind=self.kind, connection="ble",
                      source="windows-ble", sample=self.last,
                      stale=self.last.level is not None and not self.last.online)


# ---------------------------------------------------------------------------
# 多设备：按"所有已配对且在线"的蓝牙 LE 设备枚举，逐台读标准电量特征。
# 固定两台的老实现只按名字提示挑第一台，无法表达"列表随设备增减"。
# ---------------------------------------------------------------------------

MAX_SCAN_DEVICES = 8      # 单轮读取上限（预算），不是设备总量上限
SCAN_BUDGET = 12.0        # 单轮总时间预算（秒）
SCAN_CANDIDATE_LIMIT = 64  # 枚举候选上限，防止异常环境下无限扩张

KIND_KEYWORDS = (
    ("keyboard", ("keyboard", "键盘", "g75", "k99", "k87", "k618", "f75", "f87", "aula")),
    ("mouse", ("mouse", "鼠标", "ex-g", "elecom", "mx master", "g304", "g502", "g pro")),
    ("headset", ("headset", "耳机", "headphone", "wh-", "arctic")),
    ("gamepad", ("gamepad", "手柄", "controller", "xbox", "dualsense", "dualshock")),
)


def infer_kind(name: str) -> str:
    """按名称里能确认的线索推类型；认不出就归为 device，绝不猜成键盘或鼠标。"""
    lowered = (name or "").lower()
    for kind, words in KIND_KEYWORDS:
        for word in words:
            if word in lowered:
                return kind
    return "device"


def rotation_indices(total: int, cursor: int, limit: int) -> tuple:
    """把"前 N 台截断"换成游标轮转：返回 (本轮要读的下标, 新游标, 是否还有没轮到的)。

    这样第 9 台、第 10 台只是"本轮未调度"，不会被当成设备消失。
    """
    total = max(0, int(total))
    if total == 0:
        return [], 0, False
    limit = max(1, int(limit))
    start = int(cursor) % total
    count = min(limit, total)
    indices = [(start + offset) % total for offset in range(count)]
    return indices, (start + count) % total, count < total



@dataclasses.dataclass
class BleReading:
    key: str
    name: str
    kind: str = "device"
    address: str = ""
    level: Optional[int] = None
    online: bool = False
    error: str = ""
    sampled_at: float = 0.0
    # 系统枚举给出的连接状态；None 表示没拿到证据，不能据此判定断开。
    connected: Optional[bool] = None


@dataclasses.dataclass
class ScanResult:
    """一轮扫描的结果：必须能区分"读到了什么"和"这轮覆盖到哪"。"""

    readings: List[BleReading] = dataclasses.field(default_factory=list)
    attempted: Set[str] = dataclasses.field(default_factory=set)
    candidates: int = 0
    complete: bool = False
    error: str = ""
    budget_exhausted: bool = False

    def missing(self) -> bool:
        return bool(self.error) or not self.complete


class BleScanner:
    """一轮扫描返回多台设备；同一事件循环线程内顺序读取，避免并发抢占连接。"""

    def __init__(self, enabled: bool = True, max_devices: int = MAX_SCAN_DEVICES) -> None:
        self.enabled = enabled
        self.max_devices = max_devices
        self.last_error = ""
        self._cursor = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    # ---- 线程与事件循环（与 BleSensor 相同套路） ----
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, name="ble-scan", daemon=True)
        self._thread.start()
        self._ready.wait(5.0)

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        loop.run_forever()

    def stop(self) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)
        self._thread = None
        self._loop = None
        self._ready.clear()

    def _submit(self, coro, timeout: float) -> Any:
        if self._loop is None:
            raise RuntimeError("BLE 扫描线程未启动")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise

    # ---- 扫描 ----
    def scan(self) -> ScanResult:
        if not self.enabled:
            return ScanResult(complete=False, error="蓝牙扫描未启用")
        try:
            import winrt.windows.devices.enumeration  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            self.last_error = "缺少 PyWinRT：%s" % exc
            return ScanResult(complete=False, error=self.last_error)
        try:
            self.start()
            return self._submit(self._scan_async(), SCAN_BUDGET + 6.0)
        except Exception as exc:  # noqa: BLE001
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            LOGGER.warning("蓝牙扫描失败：%s", self.last_error)
            return ScanResult(complete=False, error=self.last_error)

    async def _scan_async(self) -> ScanResult:
        from winrt.windows.devices.bluetooth import BluetoothLEDevice
        from winrt.windows.devices.enumeration import DeviceInformation

        selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
        try:
            devices = await asyncio.wait_for(
                DeviceInformation.find_all_async(selector, [NAME_PROP, CONNECTED_PROP], 1), GATT_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - 枚举失败不能当"设备都没了"
            return ScanResult(complete=False, error="枚举失败：%s" % exc)
        candidates = list(devices)[:SCAN_CANDIDATE_LIMIT]
        result = ScanResult(candidates=len(candidates))
        if not candidates:
            result.complete = True
            return result
        # 游标轮转：上轮从第 cursor 台开始，本轮接着往后读，后面的设备不会永远排不到。
        indices, self._cursor, remaining = rotation_indices(
            len(candidates), self._cursor, self.max_devices)
        result.budget_exhausted = remaining
        started = time.monotonic()
        for index in indices:
            if time.monotonic() - started > SCAN_BUDGET:
                result.budget_exhausted = True
                break
            reading = await self._read_one(candidates[index])
            if reading is not None:
                result.readings.append(reading)
                result.attempted.add(reading.key)
        result.complete = (not result.budget_exhausted) and len(result.attempted) >= len(candidates)
        return result

    async def _read_one(self, info) -> Optional[BleReading]:
        name = _device_name(info).strip()
        address = _prop(info.properties, ADDRESS_PROP)
        connected = _prop(info.properties, CONNECTED_PROP)
        masked = BleSensor._mask(address)
        ident = _identity(address, getattr(info, "id", ""), name)
        if not name:
            name = "蓝牙设备 " + masked[-5:]
        kind = infer_kind(name)
        reading = BleReading(key="ble:" + ident, name=name, kind=kind, address=masked,
                             sampled_at=time.time())
        try:
            level, error = await asyncio.wait_for(self._read_gatt(info), GATT_TIMEOUT * 2)
        except asyncio.TimeoutError:
            reading.error = "读取超时"
            reading.connected = None if connected is None else bool(connected)
            reading.online = connected is True
            return reading
        reading.connected = connected if connected is None else bool(connected)
        if level is None:
            reading.error = error
            # 连上但拿不到电量：若能确认在线就显示"电量暂不可用"，否则留给上层判"状态待确认"。
            reading.online = connected is True
            return reading
        reading.level = level
        reading.online = True
        reading.connected = True
        return reading

    async def _read_gatt(self, info) -> tuple[Optional[int], str]:
        from winrt.windows.devices.bluetooth import BluetoothCacheMode, BluetoothLEDevice
        from winrt.windows.storage.streams import DataReader

        device = await BluetoothLEDevice.from_id_async(info.id)
        if device is None:
            return None, "无法连接设备"
        try:
            services_result = await device.get_gatt_services_for_uuid_async(
                BATTERY_SERVICE, BluetoothCacheMode.UNCACHED)
            services = list(services_result.services)
            if not services:
                return None, "设备没有标准电量服务"
            chars_result = await services[0].get_characteristics_for_uuid_async(BATTERY_LEVEL_CHAR)
            chars = list(chars_result.characteristics)
            if not chars:
                return None, "设备没有标准电量特征"
            read = await chars[0].read_value_async(BluetoothCacheMode.UNCACHED)
            status = getattr(read.status, "value", read.status)
            if status not in (0, None):
                return None, "读取失败（状态 %s）" % status
            value = DataReader.from_buffer(read.value).read_byte()
            if 0 <= value <= 100:
                return int(value), ""
            return None, "电量值越界：%d" % value
        finally:
            try:
                device.close()
            except Exception:  # noqa: BLE001
                pass


def _identity(address: Any, device_id: str, name: str) -> str:
    """稳定身份：优先蓝牙地址，其次枚举 id，最后才是名字（名字只作最后兜底）。"""
    if address is not None:
        try:
            value = int(address) if not isinstance(address, str) else int(str(address), 16)
            return "%012x" % (value & 0xFFFFFFFFFFFF)
        except (TypeError, ValueError):
            text = str(address).replace(":", "").strip().lower()
            if text:
                return text
    import hashlib

    if device_id:
        # 不再截尾：同后缀的不同设备曾会被合并成同一条记录。
        return "id-" + hashlib.sha256(str(device_id).strip().lower().encode("utf-8")).hexdigest()
    return "name-" + hashlib.sha256((name or "").encode("utf-8")).hexdigest()


def reading_sample(reading: BleReading) -> Sample:
    return Sample(level=reading.level, charging=None, online=reading.online,
                  error=reading.error, sampled_at=reading.sampled_at, confirmed=True)
