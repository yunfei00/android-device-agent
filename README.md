# Android Device Agent

Android Device Agent 是面向实验室环境的 Android 手机远程投屏与控制工具。手机通过 USB/ADB 连接 Agent 电脑，远端电脑通过局域网按 ADB `serial` 选择设备，实现实时画面、点击、滑动、按键和文字输入。

> 最新正式 Release：**v0.2.0**  
> `main` 当前开发版本：**v0.3.0**

## v0.3.0：高清低延迟投屏

v0.2.0 为了优先保证投屏响应速度，将 H.264 长边限制在 1280，部分高分辨率手机的小文字不够清晰。v0.3.0 增加运行时画质选择，在不改变真实触控坐标的情况下独立调整视频编码分辨率和码率。

Remote Client 新增“画质”选择：

| 模式 | 视频最长边 | H.264 码率 | 适用场景 |
| --- | ---: | ---: | --- |
| 流畅 | 1280 | 2.5 Mbps | 网络一般、优先低延迟 |
| 平衡（默认） | 1600 | 4 Mbps | 日常实验控制 |
| 高清 | 1920 | 6 Mbps | 查看界面文字、细节 |
| 原生 | 手机原始分辨率 | 8 Mbps | 局域网条件好、优先清晰度 |

切换画质后客户端会自动重建 H.264 流，不需要重启 Agent 或重新选择设备。无论视频采用什么分辨率，鼠标点击/滑动始终映射到手机真实物理屏幕尺寸。

客户端仍然只渲染最新解码帧，旧帧直接丢弃，避免提高分辨率后因帧排队重新产生明显显示延迟。

## 架构

```text
Remote Client（电脑 A）
        |
        | LAN / HTTP + H.264
        v
Android Device Agent（电脑 B）
        |
        | USB / ADB
        v
Android 手机（serial 唯一标识）
```

控制使用持久 ADB shell；视频当前使用 Android `screenrecord` H.264 stdout。后续继续评估 scrcpy server 原生 video/control socket。

## 运行要求

- Python 3.11+（源码运行）
- uv（源码运行）
- Android Platform Tools (`adb`)
- Windows x64（Release 包）
- Agent 与 Remote Client 网络互通

确认手机：

```bash
adb devices -l
```

源码安装：

```bash
git clone git@github.com:yunfei00/android-device-agent.git
cd android-device-agent
uv sync --dev
```

## 启动 Agent

```bash
uv run android-device-agent --host 0.0.0.0 --port 18080
```

Release 包直接运行 `android-device-agent.exe`。默认监听 TCP 18080。

检查：

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/api/v1/devices
```

Agent 电脑需要允许 Windows 防火墙访问 TCP 18080。仅建议用于可信实验室/局域网，不要直接暴露到公网。

## 启动 Remote Client

```bash
uv run android-remote-client
```

Release 包直接运行 `android-remote-client.exe`。

填写 Agent 地址，例如 `http://192.168.1.100:18080`，点击“刷新设备”，选择目标 serial。v0.3.0 默认使用“平衡 1600 / 4M”；需要看清文字时可直接切到“高清”或“原生”。如果提高画质后某台电脑/网络出现明显卡顿，切回“平衡”或“流畅”。

状态栏会同时显示真实屏幕尺寸和实际视频尺寸，例如：

```text
ABC123 | 高清 1920 / 6M | 屏幕(1080, 2400) | 视频(864, 1920)
```

## 视频 API

能力检查（默认 balanced）：

```text
GET /api/v1/devices/{serial}/video/capabilities
```

指定画质：

```text
GET /api/v1/devices/{serial}/video/capabilities?quality=high
GET /api/v1/devices/{serial}/video/h264?quality=high
```

`quality` 支持：`smooth`、`balanced`、`high`、`native`。

H.264 不可用时 Remote Client 自动回退 PNG 截图模式：

```text
GET /api/v1/devices/{serial}/screenshot
```

## 控制 API

```text
POST /api/v1/devices/{serial}/input/tap
{"x": 500, "y": 1000}
```

```text
POST /api/v1/devices/{serial}/input/swipe
{"x1": 500, "y1": 1500, "x2": 500, "y2": 500, "duration_ms": 120}
```

```text
POST /api/v1/devices/{serial}/shell
{"command": ["getprop", "ro.product.model"], "timeout": 10}
```

## v0.2.0 已验证基线

- Agent/Remote Client 设备发现正常
- H.264 实时投屏可用
- 点击和滑动可远程控制手机
- H.264 视频尺寸与真实触控坐标分离
- 只显示最新视频帧，投屏响应明显改善
- 刷新设备 `NoneType ... readline` 问题已修复
- Agent Windows 控制台乱码/ANSI 前缀已修复

## 自动构建与 Release

`main` 和 PR 自动执行 Ruff、Pytest、Windows x64 打包。推送 `v*` Tag 后自动创建 GitHub Release，附件名称包含版本号，例如：

```text
android-device-agent-v0.3.0-windows-x64.zip
```

ZIP 内程序名保持稳定：

```text
android-device-agent.exe
android-remote-client.exe
README.md
```

## 后续计划

- 实机比较四档画质的清晰度、FPS 和延迟
- 根据实测决定是否加入自动动态画质
- scrcpy server 原生 video/control socket
- WebSocket/长连接控制通道
- ADB offline / USB 拔插自动恢复
- Agent Token 鉴权
- 多设备并发视频会话优化
- APK、文件、logcat 等实验室能力
- CMW500 自动化测试平台集成
