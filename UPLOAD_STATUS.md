# 发布状态

2026-10-31：`0.4.0-dev` 已在 [Releases](https://github.com/xiexianhao666-sys/KeyMouseBattery/releases/latest) 提供 Windows 64 位便携包，下载解压即可运行，无需安装 Python。

## 仓库内容

- 源码：`keymousebattery/`（Python 3.13 + PySide6 6.12）
- 入口 / 打包：`KeyMouseBattery.pyw`、`KeyMouseBattery.spec`、`build.ps1`
- 测试：`tests/`，157 项
- 文档与素材：`README.md`、`docs/screenshots/`、`CREDITS.md`、`LICENSE`

仓库不含运行数据、设备记录、日志、构建目录与二进制包；便携包只在 Release 中提供。

## 已发布制品

| 制品 | 大小 | SHA-256 |
| --- | --- | --- |
| `KeyMouseBattery-0.4.0-dev-win64.zip` | 48 817 770 B | `a3cf11e8c5000381b6805989f2def6dfc5f25a81f9c9ad2f6e3e1f6cbdc77319` |
| 包内 `KeyMouseBattery.exe` | 2 971 741 B | `92e144c33d0747684e4062d7085c6be017a2f66d03d27e8afb991a73aa885d61` |

发布前验证：`157` 项单元测试通过；冻结版 `--version` / `--probe` / `--shot` 均 exit 0；解压后版本串为 `KeyMouseBattery · 键鼠电量 0.4.0-dev`。

## 当前状态

- 同类别 BLE 记录与独立 USB 设备并存的显示问题已修复（`poller.merge_usb_channels`）。
- 蓝牙单轮枚举 8 台、候选池 64 台，按轮转继续读取。
- 未验证：真实登录自启（注册表写入）、高 DPI 150%/200%、多屏、任务栏左右/顶部位置。
- 程序未签名，SmartScreen 会提示未知发布者。

## 历史

- 早期快照（2026-10-31 上午）：仅源码、未发布 Release，用于确认更名后的构建与测试链路。
