from __future__ import annotations

import sys
from urllib.parse import quote

import requests
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ScreenLabel(QLabel):
    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self.owner = owner
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(360, 640)
        self.setStyleSheet("background:#111; color:#ddd;")
        self._press_pos: QPoint | None = None

    def _to_device(self, pos: QPoint) -> tuple[int, int] | None:
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull() or not self.owner.device_size:
            return None
        shown = pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        ox = (self.width() - shown.width()) // 2
        oy = (self.height() - shown.height()) // 2
        x = pos.x() - ox
        y = pos.y() - oy
        if x < 0 or y < 0 or x >= shown.width() or y >= shown.height():
            return None
        dw, dh = self.owner.device_size
        return int(x * dw / shown.width()), int(y * dh / shown.height())

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
        if abs(start[0] - end[0]) < 12 and abs(start[1] - end[1]) < 12:
            self.owner.tap(*end)
        else:
            self.owner.swipe(*start, *end)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Android Remote Client")
        self.resize(720, 900)
        self.session = requests.Session()
        self.device_size: tuple[int, int] | None = None

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

        self.screen = ScreenLabel(self)
        layout.addWidget(self.screen, 1)

        buttons = QHBoxLayout()
        for text, key in [("返回", "KEYCODE_BACK"), ("主页", "KEYCODE_HOME"), ("电源", "KEYCODE_POWER")]:
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

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh_screen)
        self.timer.start()
        self.devices.currentIndexChanged.connect(self.load_device_info)

    def base(self) -> str:
        return self.endpoint.text().strip().rstrip("/")

    def serial(self) -> str:
        return self.devices.currentData() or ""

    def device_url(self, suffix: str) -> str:
        return f"{self.base()}/api/v1/devices/{quote(self.serial(), safe='')}/{suffix}"

    def refresh_devices(self) -> None:
        try:
            response = self.session.get(f"{self.base()}/api/v1/devices", timeout=3)
            response.raise_for_status()
            items = response.json().get("devices", [])
            current = self.serial()
            self.devices.blockSignals(True)
            self.devices.clear()
            for item in items:
                serial = item["serial"]
                model = item.get("model", "")
                state = item.get("state", "")
                self.devices.addItem(f"{model or 'Android'} | {serial} | {state}", serial)
            self.devices.blockSignals(False)
            if current:
                idx = self.devices.findData(current)
                if idx >= 0:
                    self.devices.setCurrentIndex(idx)
            self.load_device_info()
            self.status.setText(f"发现 {len(items)} 台设备")
        except Exception as exc:
            self.status.setText(f"连接失败: {exc}")

    def load_device_info(self) -> None:
        if not self.serial():
            self.device_size = None
            return
        try:
            response = self.session.get(self.device_url("info"), timeout=3)
            response.raise_for_status()
            info = response.json()
            size = info.get("screen_size")
            if size and "x" in size:
                w, h = size.split("x", 1)
                self.device_size = (int(w), int(h))
            self.status.setText(
                f"{info.get('manufacturer', '')} {info.get('model', '')} | Android {info.get('android_version', '')} | 电量 {info.get('battery_level', '?')}%"
            )
        except Exception as exc:
            self.status.setText(f"读取设备信息失败: {exc}")

    def refresh_screen(self) -> None:
        if not self.serial():
            return
        try:
            response = self.session.get(self.device_url("screenshot"), timeout=2)
            response.raise_for_status()
            pixmap = QPixmap()
            if pixmap.loadFromData(response.content, "PNG"):
                self.screen.setPixmap(
                    pixmap.scaled(
                        self.screen.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        except Exception:
            pass

    def post(self, suffix: str, payload: dict) -> None:
        if not self.serial():
            return
        try:
            response = self.session.post(self.device_url(suffix), json=payload, timeout=3)
            response.raise_for_status()
        except Exception as exc:
            self.status.setText(f"操作失败: {exc}")

    def tap(self, x: int, y: int) -> None:
        self.post("input/tap", {"x": x, "y": y})

    def swipe(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.post("input/swipe", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration_ms": 300})

    def send_key(self, keycode: str) -> None:
        self.post("input/key", {"keycode": keycode})

    def send_text(self) -> None:
        text = self.text_input.text()
        if text:
            self.post("input/text", {"text": text})
            self.text_input.clear()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.refresh_devices()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
