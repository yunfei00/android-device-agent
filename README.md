# Android Device Agent

Android Device Agent 是面向实验室环境的 Android 手机远程投屏与控制工具。

手机通过 USB/ADB 连接 Agent 电脑，远端电脑通过局域网连接 Agent，按 ADB `serial` 选择设备，实现实时画面、点击、滑动、按键、文字输入和基础设备控制。

> 当前首个正式发布版本：**v0.2.0**

## v0.2.0 功能

- `adb devices -l` 自动发现设备
- ADB `serial` 作为唯一设备 ID，支持多设备选择
- 查询型号、Android 版本、电量和真实屏幕尺寸
- 远程 ADB shell
- 鼠标点击、拖动滑动、文字输入
- Home / Back / Power
- App 启动 / 停止、设备重启
- PNG 截图接口与截图模式回退
- H.264 持续视频流
- PyAV 实时 H.264 解码
- H.264 不可用时自动回退截图模式
- H.264 画面只显示最新帧，避免旧帧排队造成额外延迟
- 触控坐标始终映射到手机真实物理分辨率，视频缩放不影响点击位置
- 每个 serial 使用持久 ADB shell，减少输入命令进程启动开销
- 点击/滑动异步发送，避免阻塞客户端 UI
- Windows PySide6 Remote Client
- Windows Agent 控制台 UTF-8 输出并关闭 ANSI 彩色控制字符
- GitHub Actions 自动测试、Windows 打包和 Tag Release

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

当前 v0.2.0 使用 `screenrecord` H.264 持续视频流和持久 ADB shell。它已经可以满足实验室远程查看与基础控制，但操作延迟仍有继续优化空间，后续计划评估 scrcpy server 原生 video/control socket。

## 运行要求

源码运行：

- Python 3.11+
- uv
- Android Platform Tools (`adb`)

Release 软件包运行：

- Windows x64
- Android Platform Tools (`adb`) 已安装并可在命令行直接执行
- Agent 电脑与 Remote Client 电脑网络互通

首先确认手机：

```bash
adb devices -l
```

## 源码安装

```bash
git clone git@github.com:yunfei00/android-device-agent.git
cd android-device-agent
uv sync --dev
```

## 启动 Agent

电脑 B（手机通过 USB 连接到这台电脑）：

```bash
uv run android-device-agent --host 0.0.0.0 --port 18080
```

Release 包则直接运行：

```text
android-device-agent.exe
```

默认监听 TCP 18080。

检查服务：

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/api/v1/devices
```

Agent 电脑需要允许 Windows 防火墙访问 TCP 18080。该工具仅建议用于可信实验室/局域网，**不要直接暴露到公网**。

## 启动 Remote Client

源码：

```bash
uv run android-remote-client
```

Release 包：

```text
android-remote-client.exe
```

客户端填写 Agent 地址，例如：

```text
http://192.168.1.100:18080
```

然后：

1. 点击“刷新设备”
2. 按设备型号和 serial 选择目标手机
3. 等待实时画面出现
4. 直接在手机画面上点击或拖动

状态栏显示：

```text
<serial> | H.264低延迟投屏 | 屏幕(...) | 视频(...)
```

表示 H.264 通道已建立。其中“屏幕”是真实手机触控分辨率，“视频”是传输/显示分辨率，两者可以不同。

如果显示：

```text
H.264不可用，已回退截图模式
```

说明当前手机/ROM 无法使用该 H.264 输出方式，客户端会继续使用 PNG 截图模式完成基本控制。

## API 示例

查看设备：

```text
GET /api/v1/devices
```

设备信息：

```text
GET /api/v1/devices/{serial}/info
```

H.264 能力：

```text
GET /api/v1/devices/{serial}/video/capabilities
```

H.264 视频流：

```text
GET /api/v1/devices/{serial}/video/h264
```

截图：

```text
GET /api/v1/devices/{serial}/screenshot
```

点击：

```text
POST /api/v1/devices/{serial}/input/tap
{"x": 500, "y": 1000}
```

滑动：

```text
POST /api/v1/devices/{serial}/input/swipe
{"x1": 500, "y1": 1500, "x2": 500, "y2": 500, "duration_ms": 180}
```

Shell：

```text
POST /api/v1/devices/{serial}/shell
{"command": ["getprop", "ro.product.model"], "timeout": 10}
```

## v0.2.0 已验证

目前实际验证通过：

- Agent 可发现 ADB 手机
- Remote Client 可发现远端 Agent
- Remote Client 可查看手机实时画面
- H.264 投屏链路可进入工作状态
- 鼠标点击可控制手机
- 鼠标拖动可控制手机滑动
- 刷新设备不会再触发 `NoneType ... readline` 异常
- Agent 控制台异常前缀/乱码已修复
- H.264 视频缩放与真实触控坐标已经分离

当前已知限制：操作与画面反馈仍存在一定延迟，v0.2.0 暂接受当前效果，后续版本继续优化低延迟控制链路。

## 自动构建与 Release

提交到 `main` 或创建 PR 时，GitHub Actions 自动执行：

1. Ruff
2. Pytest
3. Windows x64 打包
4. 上传 Actions Artifact

推送 `v*` Tag 时，在以上流程成功后自动创建 GitHub Release。

首个正式版本：

```bash
git tag -a v0.2.0 -m "Android Device Agent v0.2.0"
git push origin v0.2.0
```

Release 附件名称：

```text
android-device-agent-v0.2.0-windows-x64.zip
```

ZIP 内保持稳定的程序名称：

```text
android-device-agent.exe
android-remote-client.exe
README.md
```

## 后续计划

- scrcpy server 原生 video/control socket 低延迟方案
- WebSocket/长连接控制通道
- 进一步降低画面编码、传输、解码延迟
- ADB offline / USB 拔插自动恢复
- Agent Token 鉴权
- 多设备并发视频会话优化
- APK 安装/卸载
- push/pull 文件
- logcat / 录屏
- CMW500 自动化测试平台集成
