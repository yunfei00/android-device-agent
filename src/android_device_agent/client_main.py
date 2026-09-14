from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import av
import requests
from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

QUALITY_OPTIONS = [
    ("流畅 1280 / 2.5M", "smooth"),
    ("平衡 1600 / 4M", "balanced"),
    ("高清 1920 / 6M", "high"),
    ("原生 / 8M", "native"),
]


class VideoThread(QThread):
    stream_error = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self._running = True
        self._latest_lock = threading.Lock()
        self._latest_image: QImage | None = None

    def stop(self) -> None:
        self._running = False
        self.requestInterruption()

    def take_latest_frame(self) -> QImage | None:
        with self._latest_lock:
            image = self._latest_image
            self._latest_image = None
        return image

    def _store_latest_frame(self, image: QImage) -> None:
        with self._latest_lock:
            self._latest_image = image

    def run(self) -> None:
        codec = av.CodecContext.create("h264", "r")
        try:
            with requests.get(self.url, stream=True, timeout=(3, None)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8 * 1024):
                    if not self._running or self.isInterruptionRequested():
                        return
                    if not chunk:
                        continue
                    for packet in codec.parse(chunk):
                        for frame in codec.decode(packet):
                            if not self._running or self.isInterruptionRequested():
                                return
                            rgb = frame.reformat(format="rgb24")
                            plane = rgb.planes[0]
                            image = QImage(
                                bytes(plane),
                                rgb.width,
                                rgb.height,
                                plane.line_size,
                                QImage.Format.Format_RGB888,
                            ).copy()
                            self._store_latest_frame(image)
        except (requests.RequestException, av.error.FFmpegError, OSError, AttributeError) as exc:
            if self._running and not self.isInterruptionRequested():
                self.stream_error.emit(str(exc))


class ScreenLabel(QLabel):
    def __init__(self, owner: MainWindow) -> None:
        super().__init__()
        self.owner = owner
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(360, 640)
        self.setStyleSheet("background:#111; color:#ddd;")
        self._press_pos: QPoint | None = None

    def _to_device(self, pos: QPoint) -> tuple[int, int] | None:
        pixmap = self.pixmap()
        physical_size = self.owner.physical_device_size
        if pixmap is None or pixmap.isNull() or not physical_size:
            return None
        shown = pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        ox = (self.width() - shown.width()) // 2
        oy = (self.height() - shown.height()) // 2
        x = pos.x() - ox
        y = pos.y() - oy
        if x < 0 or y < 0 or x >= shown.width() or y >= shown.height():
            return None
        dw, dh = physical_size
        px = min(dw - 1, max(0, round(x * dw / shown.width())))
        py = min(dh - 1, max(0, round(y * dh / shown.height())))
        return px, py

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            return
        start = self._to_device(self._press_pos)
        end = self._to_device(event.position().toPoint())
        self._press_pos = None
        if not start or not end:
            return
        if abs(start[0] - end[0]) < 18 and abs(start[1] - end[1]) < 18:
            self.owner.tap(*end)
        else:
            self.owner.swipe(*start, *end)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Android Remote Client")
        self.resize(720, 900)
        self.session = requests.Session()
        self.physical_device_size: tuple[int, int] | None = None
        self.video_frame_size: tuple[int, int] | None = None
        self.video_thread: VideoThread | None = None
        self.video_active = False
        self.input_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="remote-input")

        root = QWidget()
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.endpoint = QLineEdit("http://127.0.0.1:18080")
        self.devices = QComboBox()
        refresh = QPushButton("刷新设备")
        refresh.clicked.connect(self.refresh_devices)
        top.addWidget(QLabel("Agent:"))
        top.addWidget(self.endpoint, 2)
        top.addWidget(self.devices, 2)
        top.addWidget(refresh)
        layout.addLayout(top)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("画质:"))
        self.quality = QComboBox()
        for label, value in QUALITY_OPTIONS:
            self.quality.addItem(label, value)
        self.quality.setCurrentIndex(1)
        self.quality.currentIndexChanged.connect(self.change_quality)
        quality_row.addWidget(self.quality)
        quality_row.addStretch(1)
        layout.addLayout(quality_row)

        self.screen = ScreenLabel(self)
        layout.addWidget(self.screen, 1)

        buttons = QHBoxLayout()
        for text, key in [
            ("返回", "KEYCODE_BACK"),
            ("主页", "KEYCODE_HOME"),
            ("电源", "KEYCODE_POWER"),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(lambda _checked=False, k=key: self.send_key(k))
            buttons.addWidget(btn)
        layout.addLayout(buttons)

        text_row = QHBoxLayout()
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入文字后点击发送")
        send = QPushButton("发送文本")
        send.clicked.connect(self.send_text)
        text_row.addWidget(self.text_input)
        text_row.addWidget(send)
        layout.addLayout(text_row)

        self.status = QLabel("未连接")
        layout.addWidget(self.status)
        self.setCentralWidget(root)

        self.video_render_timer = QTimer(self)
        self.video_render_timer.setInterval(16)
        self.video_render_timer.timeout.connect(self.render_latest_video_frame)
        self.video_render_timer.start()

        self.fallback_timer = QTimer(self)
        self.fallback_timer.setInterval(500)
        self.fallback_timer.timeout.connect(self.refresh_screen_fallback)
        self.fallback_timer.start()
        self.devices.currentIndexChanged.connect(self.load_device_info)

    def base(self) -> str:
        return self.endpoint.text().strip().rstrip("/")

    def serial(self) -> str:
        return self.devices.currentData() or ""

    def quality_name(self) -> str:
        return self.quality.currentData() or "balanced"

    def device_url(self, suffix: str) -> str:
        serial = quote(self.serial(), safe="")
        return f"{self.base()}/api/v1/devices/{serial}/{suffix}"

    def refresh_devices(self) -> None:
        try:
            response = self.session.get(f"{self.base()}/api/v1/devices", timeout=3)
            response.raise_for_status()
            items = response.json().get("devices", [])
            current = self.serial()
            self.stop_video_stream()
            self.devices.blockSignals(True)
            self.devices.clear()
            for item in items:
                serial = item["serial"]
                model = item.get("model", "")
                state = item.get("state", "")
                self.devices.addItem(f"{model or 'Android'} | {serial} | {state}", serial)
            if current:
                idx = self.devices.findData(current)
                if idx >= 0:
                    self.devices.setCurrentIndex(idx)
            self.devices.blockSignals(False)
            self.load_device_info()
            self.status.setText(f"发现 {len(items)} 台设备")
        except requests.RequestException as exc:
            self.status.setText(f"连接失败: {exc}")

    def load_device_info(self) -> None:
        self.stop_video_stream()
        if not self.serial():
            self.physical_device_size = None
            self.video_frame_size = None
            return
        try:
            response = self.session.get(self.device_url("info"), timeout=3)
            response.raise_for_status()
            info = response.json()
            size = info.get("screen_size")
            if size and "x" in size:
                w, h = size.split("x", 1)
                self.physical_device_size = (int(w), int(h))
            manufacturer = info.get("manufacturer", "")
            model = info.get("model", "")
            android_version = info.get("android_version", "")
            battery = info.get("battery_level", "?")
            self.status.setText(
                f"{manufacturer} {model} | Android {android_version} | 电量 {battery}% | 正在连接H.264"
            )
            self.start_video_stream()
        except (requests.RequestException, ValueError) as exc:
            self.status.setText(f"读取设备信息失败: {exc}")

    def change_quality(self) -> None:
        if not self.serial():
            return
        self.status.setText(f"正在切换画质: {self.quality.currentText()}")
        self.stop_video_stream()
        self.start_video_stream()

    def start_video_stream(self) -> None:
        if not self.serial():
            return
        self.video_active = False
        quality = quote(self.quality_name(), safe="")
        thread = VideoThread(f"{self.device_url('video/h264')}?quality={quality}")
        thread.stream_error.connect(self.on_video_error)
        self.video_thread = thread
        thread.start()

    def stop_video_stream(self) -> None:
        thread = self.video_thread
        self.video_thread = None
        self.video_active = False
        if thread is not None:
            thread.stop()
            thread.wait(150)

    def render_latest_video_frame(self) -> None:
        thread = self.video_thread
        if thread is None:
            return
        image = thread.take_latest_frame()
        if image is None:
            return
        self.video_active = True
        self.video_frame_size = (image.width(), image.height())
        self.show_pixmap(QPixmap.fromImage(image))
        self.status.setText(
            f"{self.serial()} | {self.quality.currentText()} | "
            f"屏幕{self.physical_device_size} | 视频{self.video_frame_size}"
        )

    def on_video_error(self, message: str) -> None:
        self.video_active = False
        self.status.setText(f"H.264不可用，已回退截图模式: {message}")

    def show_pixmap(self, pixmap: QPixmap) -> None:
        self.screen.setPixmap(
            pixmap.scaled(
                self.screen.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def refresh_screen_fallback(self) -> None:
        if self.video_active or not self.serial():
            return
        try:
            response = self.session.get(self.device_url("screenshot"), timeout=2)
            response.raise_for_status()
        except requests.RequestException:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(response.content, "PNG"):
            self.show_pixmap(pixmap)

    def _post_now(self, url: str, payload: dict) -> None:
        try:
            response = requests.post(url, json=payload, timeout=2)
            response.raise_for_status()
        except requests.RequestException:
            return

    def post(self, suffix: str, payload: dict) -> None:
        if not self.serial():
            return
        self.input_executor.submit(self._post_now, self.device_url(suffix), payload)

    def tap(self, x: int, y: int) -> None:
        self.post("input/tap", {"x": x, "y": y})

    def swipe(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.post(
            "input/swipe",
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration_ms": 120},
        )

    def send_key(self, keycode: str) -> None:
        self.post("input/key", {"keycode": keycode})

    def send_text(self) -> None:
        text = self.text_input.text()
        if text:
            self.post("input/text", {"text": text})
            self.text_input.clear()

    def closeEvent(self, event) -> None:
        self.stop_video_stream()
        self.input_executor.shutdown(wait=False, cancel_futures=True)
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.refresh_devices()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
