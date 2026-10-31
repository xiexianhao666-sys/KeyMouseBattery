# 来源与致谢

## 早期协议参考资料

- VigilWatt `v1.3.1`：https://github.com/evren-oct/vigil-watt
- tag `v1.3.1`，commit `4df830043296760f5d5c273f4cdc0ea9456c4bc7`
- 许可：MIT，Copyright (c) 2026 evren
- 早期开发参考其公开协议文档与可观察行为；当前项目独立维护，未复制其 C# 源码

参考文档（VigilWatt v1.3.1）：

- `docs/hardware/mchose.md`：迈从 G75 Pro 接收器接口、20 字节 `0x13` 帧、会话/查询/推送报文与型号密码表
- `docs/hardware/aula.md`：同一指纹被 AULA 机型共用的事实，用于说明为什么必须核对 ACK 密码
- `docs/hardware/safety.md`：零写入原则、禁止命令枚举、失败熔断与退避
- `docs/dev/runtime-pitfalls.md` §20：Low 完整性级别导致的托盘/注册表症状

## 第三方库

| 库 | 用途 | 许可 |
| --- | --- | --- |
| PySide6 (Qt for Python) | 面板与托盘 | LGPL-3.0（动态链接，未修改） |
| hidapi | 2.4G 接收器只读查询 | BSD-3-Clause / 原项目许可 |
| PyWinRT (winrt-runtime 与 Windows.* 投影) | 蓝牙 GATT 读取 | MIT |
| PyInstaller | 便携打包 | GPL-2.0 with bootloader exception |

## 图标

| 素材 | 用途 | 许可 |
| --- | --- | --- |
| [Lucide](https://lucide.dev) 图标（`keyboard`、`mouse`、`gamepad-2`、`headphones`、`circle-question-mark`、`monitor-smartphone`、`settings`） | 卡片设备类型图标、侧栏导航图标、桌面电量条图形 | ISC |

图标原始 SVG 存放在 `assets/icons/lucide/`，随包分发时保留 `LICENSE` 文件；
渲染时只替换 `currentColor` 与 `stroke-width`，未改动图形路径。


## 本机实测设备

- `MCHOSE G75 5.0`（键盘，蓝牙 GATT 0x180F/0x2A19；另有 2.4G 接收器 `3554:FA07` 备用路径）
- `ELECOM EX-G`（鼠标，蓝牙 GATT 0x180F/0x2A19）
