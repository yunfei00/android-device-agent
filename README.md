# Android Device Agent

用于实验室环境的 Android 手机远程控制工具。手机连接在 Agent 电脑上，远端电脑通过局域网选择 ADB `serial`，查看屏幕并执行点击、滑动、按键、文字输入、App 控制等操作。

## V0.2 功能

- `adb devices -l` 设备发现
- ADB `serial` 作为唯一设备 ID
- 多设备选择与控制
- 查询设备型号、Android 版本、电量、屏幕尺寸
- 远程 ADB shell
- 点击、滑动、文字输入、Home / Back / Power
- App 启动 / 停止、设备重启
- PNG 截图接口
- H.264 持续视频流接口
- PyAV 实时 H.264 解码显示
- H.264 不可用时自动回退 PNG 截图模式
- 每个 serial 维护持久 ADB shell，降低输入控制延迟
- Windows PySide6 远程客户端
- GitHub Actions 自动测试和 Windows 打包
- `v*` tag 自动创建 GitHub Release

## V0.2 低延迟链路

```text
Android 手机
   | USB / ADB
   v
Agent 电脑
   |-- persistent adb shell  ---> 点击 / 滑动 / 按键
   |-- screenrecord H.264     ---> 持续视频流
   |
   +---------- LAN -----------> Remote Client
                                  |
                                  +-- PyAV 实时解码
                                  +-- 鼠标映射手机坐标
```

旧版 V0.1 每次画面刷新都执行 `adb exec-out screencap -p`，每次输入也会创建新的 `adb shell` 子进程。V0.2 默认改为持续 H.264 流和持久 ADB shell，以降低画面反馈和操作延迟。

如果设备 ROM 不支持 `screenrecord --output-format=h264 -`，客户端会自动继续使用 PNG 截图模式，不影响基本远程控制。

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

检查：

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/api/v1/devices
```

V0.2 `/health` 应看到：

```json
{
  "status": "ok",
  "adb_available": true,
  "input_mode": "persistent-adb-shell",
  "video_mode": "h264-stream-with-screenshot-fallback"
}
```

Agent 电脑需要允许 Windows 防火墙放行 TCP 18080。只建议用于可信实验室/局域网，不要直接暴露到公网。

## 启动远程客户端

```bash
uv run android-remote-client
```

客户端中填写 Agent 地址，例如：

```text
http://192.168.1.100:18080
```

点击“刷新设备”，选择目标设备号。状态栏出现：

```text
<serial> | H.264低延迟投屏
```

表示已经进入 V0.2 视频通道。

如果状态栏显示：

```text
H.264不可用，已回退截图模式
```

说明当前手机/ROM 的 `screenrecord` H.264 stdout 模式不可用，但控制和截图模式仍可使用。

远程操作：

- 鼠标单击：手机点击
- 鼠标拖动：手机滑动
- 返回
- 主页
- 电源键
- 发送文本

## API

查看设备：

```text
GET /api/v1/devices
```

H.264 视频流：

```text
GET /api/v1/devices/{serial}/video/h264
```

截图回退：

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

执行 shell：

```text
POST /api/v1/devices/{serial}/shell
{"command": ["getprop", "ro.product.model"], "timeout": 10}
```

## 自动构建与 Release

每次提交到 `main` 或 PR 自动执行：

1. `ruff check`
2. `pytest`
3. Windows 打包
4. 生成 Actions artifact

创建正式版本：

```bash
git tag v0.2.0
git push origin v0.2.0
```

自动生成：

```text
android-device-agent-windows-x64.zip
```

包含：

```text
android-device-agent.exe
android-remote-client.exe
README.md
```

并自动发布到 GitHub Releases。

## 后续

- 进一步评估 scrcpy server 原生 video/control socket 接入
- WebSocket 控制通道
- Agent Token 鉴权
- ADB offline / 拔插自动恢复
- 多设备并发视频会话优化
- APK 安装/卸载
- push/pull 文件
- logcat / 录屏
- CMW500 自动化测试平台集成
