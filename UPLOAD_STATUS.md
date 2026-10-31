# 发布状态

2026-10-31：`0.4.2-dev` 已在 [Releases](https://github.com/xiexianhao666-sys/KeyMouseBattery/releases/latest) 提供 Windows 64 位便携包，下载解压即可运行，无需安装 Python。

## 仓库内容

- 源码：`keymousebattery/`（Python 3.13 + PySide6 6.12）
- 入口 / 打包：`KeyMouseBattery.pyw`、`KeyMouseBattery.spec`、`build.ps1`
- 测试：`tests/`，157 项
- 文档与素材：`README.md`、`docs/screenshots/`、`CREDITS.md`、`LICENSE`

仓库不含运行数据、设备记录、日志、构建目录与二进制包；便携包只在 Release 中提供。

## 已发布制品

| 制品 | 大小 | SHA-256 |
| --- | --- | --- |
| `KeyMouseBattery-0.4.2-dev-win64.zip` | 48 813 055 B | `29adb964fb9a0316544cf88d510a135253be245c5afab8406708394cf4f3e392` |
| 包内 `KeyMouseBattery.exe` | 2 974 635 B | `1e5e50186d4042069490a6c3fd66c997d5d6c1bfdc587942ed80698493a696df` |

发布前验证：`169` 项单元测试通过；冻结版 `--version` / `--probe` / `--shot` 均 exit 0；解压后版本串为 `KeyMouseBattery · 键鼠电量 0.4.2-dev`。

## 当前状态

- 同类别 BLE 记录与独立 USB 设备并存的显示问题已修复（`poller.merge_usb_channels`，只在与在线蓝牙同类别时合并）。
- 0.4.1：修复「立即刷新」按钮一直停在“刷新中…”；插上接收器但读不到电量时仍显示卡片（“电量暂不可用”）。
- 0.4.2：离线设备卡不再残留电量条；右键设备卡可自定义名称（存进 devices.json，可恢复默认）。
- 蓝牙单轮枚举 8 台、候选池 64 台，按轮转继续读取。
- 未验证：真实登录自启（注册表写入）、高 DPI 150%/200%、多屏、任务栏左右/顶部位置。
- 程序未签名，SmartScreen 会提示未知发布者。

## 历史

- 早期快照（2026-10-31 上午）：仅源码、未发布 Release，用于确认更名后的构建与测试链路。
