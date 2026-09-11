# Android Device Agent

用于实验室环境的 Android 手机远程控制工具。手机连接在 Agent 电脑上，远端电脑通过局域网选择 ADB `serial`，查看屏幕并执行点击、滑动、按键、文字输入、App 控制等操作。

## V0.1 功能

- `adb devices -l` 设备发现
- 以 ADB `serial` 作为唯一设备 ID
- 查询设备型号、Android 版本、电量、屏幕尺寸
- 远程 ADB shell
- 点击、滑动、文字输入
- Home / Back / Power 等按键
- App 启动 / 停止
- 设备重启
- PNG 截图接口
- Windows PySide6 远程客户端
- 连续截图刷新形成基础远程投屏
- 鼠标点击/拖动映射到手机触控
- GitHub Actions 自动测试和 Windows 打包
- `v*` tag 自动创建 GitHub Release

> 当前 V0.1 的画面通道采用 ADB `screencap` 连续刷新，目标是优先打通稳定的“远程看 + 远程控”链路。后续版本将把画面通道升级为 scrcpy/H.264 低延迟视频流，同时保留现有 serial、API 和客户端结构。

## 架构

```text
电脑 A（远程）
  android-remote-client.exe
          |
          | HTTP / LAN
          v
电脑 B（实验室）
  android-device-agent.exe
          |
          | adb -s <serial>
          v
      Android 手机
```

一台 Agent 电脑可以连接多台手机。所有设备相关操作都必须指定 `serial`，不会默认选择第一台设备。

## 开发环境

要求：

- Python 3.11+
- uv
- Android Platform Tools (`adb`)

安装：

```bash
uv sync --dev
```

确认手机：

```bash
adb devices -l
```

## 启动 Agent

```bash
uv run android-device-agent --host 0.0.0.0 --port 18080
```

或者：

```bash
uv run python -m android_device_agent.agent_main --host 0.0.0.0 --port 18080
```

检查：

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/api/v1/devices
```

Agent 电脑需要允许 Windows 防火墙放行 TCP 18080。只建议用于可信实验室/局域网，不要直接暴露到公网。

## 启动远程客户端

在远端电脑运行：

```bash
uv run android-remote-client
```

客户端中填写 Agent 地址，例如：

```text
http://192.168.1.100:18080
```

点击“刷新设备”，选择目标设备号。选定后会持续刷新手机画面，并支持：

- 鼠标单击：手机点击
- 鼠标拖动：手机滑动
- 返回
- 主页
- 电源键
- 发送文本

## API 示例

查看设备：

```text
GET /api/v1/devices
```

指定设备截图：

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
{"x1": 500, "y1": 1500, "x2": 500, "y2": 500, "duration_ms": 300}
```

执行 shell：

```text
POST /api/v1/devices/{serial}/shell
{"command": ["getprop", "ro.product.model"], "timeout": 10}
```

## 自动构建与 Release

每次提交到 `main` 或 PR：

1. `ruff check`
2. `pytest`
3. Windows 构建
4. 生成 Actions artifact

创建 tag：

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions 会自动生成：

```text
android-device-agent-windows-x64.zip
```

压缩包包含：

```text
android-device-agent.exe
android-remote-client.exe
README.md
```

并自动发布到 GitHub Releases。

## 下一阶段

- scrcpy/H.264 低延迟远程视频流
- Agent Token 鉴权
- ADB offline / 拔插自动恢复
- 多设备并发画面会话
- 安装/卸载 APK
- push/pull 文件
- logcat
- 录屏
- CMW500 自动化测试平台集成
