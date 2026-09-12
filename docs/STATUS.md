# Project Status

更新时间：2026-09-12

## 基本状态

- 状态：ACTIVE
- 优先级：P1
- 当前阶段：V0.1 主链路已打通，进入低延迟视频与可靠性增强

## 一句话目标

让实验室电脑上通过 ADB 连接的 Android 手机，能够被远端电脑按设备 serial 稳定地查看屏幕、控制触摸/按键、执行基础设备操作，并作为后续自动化测试平台的统一设备代理。

## 当前真实状态

V0.1 已经不是“刚创建仓库”的阶段。当前主链路已经基本形成：

- `adb devices -l` 设备发现
- serial 作为唯一设备 ID
- 远程 shell、点击、滑动、按键、文字输入
- App 启停、设备重启
- 截图接口
- Windows PySide6 远程客户端
- 基础连续截图投屏
- 鼠标点击/拖动映射到手机触控
- GitHub Actions 自动测试
- Windows 自动打包
- `v*` tag 自动创建 Release

当前画面链路使用连续 `adb screencap`，适合验证“远程看 + 远程控”闭环，但不适合作为最终低延迟投屏方案。

## 最近完成

- 新增 serial-aware ADB client。
- 新增远程设备 API。
- 新增 Agent server 入口。
- 新增 serial-aware 远程桌面客户端。
- 增加 ADB parser 与 health endpoint 测试。
- 建立 Windows 工具构建与 tag Release 流程。
- 修复 packaged agent import、命令结果序列化以及 CI/lint 问题。
- README 已补充安装、使用和发布说明。

## 当前问题 / 阻塞

GitHub 当前没有开放 Issue，但下一阶段工作已经比较明确：

1. 当前投屏依赖 `adb screencap` 轮询，延迟和帧率都有限。
2. Agent 当前主要假设可信局域网，缺少 Token 鉴权。
3. 设备 ADB offline、USB 拔插后的自动恢复能力还需要补强。
4. 多设备并发画面会话需要真实环境压力验证。
5. APK 安装/卸载、push/pull、logcat、录屏还未进入 V0.1 主链路。
6. 最终还需要考虑与 CMW500/仪表自动化场景的集成方式。

## 下一步唯一动作

> **把画面通道从连续 screencap 升级为 scrcpy/H.264 低延迟视频流，同时保持现有 serial、HTTP API 和客户端设备选择模型不变。**

## 后续候选动作

1. 增加 Agent Token 鉴权。
2. 增加 ADB offline / 拔插自动恢复。
3. 做多设备并发会话验证。
4. 增加 APK 安装/卸载、文件 push/pull、logcat、录屏。
5. 评估与 CMW500 自动化测试平台的统一设备接口。

## 恢复上下文提示

重新进入项目时优先查看：

1. `README.md`
2. 最近 commits
3. GitHub Actions 构建结果
4. Agent/Client 的 serial 传递链路
5. 当前 screenshot polling 的实现位置

项目核心约束：所有设备操作必须明确指定 serial，不允许默认选择第一台设备。

## 下一里程碑完成标准

- 远端能够选择指定 serial 并稳定看到低延迟画面。
- 点击、拖动、按键与画面坐标映射保持正确。
- 多设备并存时不会串设备。
- ADB 设备短暂 offline/拔插后能够恢复到可用状态。
- Windows 打包和 tag Release 继续保持自动化。
