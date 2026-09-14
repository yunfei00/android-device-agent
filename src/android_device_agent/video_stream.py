from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass


class VideoStreamError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VideoQuality:
    max_size: int | None
    bit_rate: int


VIDEO_QUALITIES: dict[str, VideoQuality] = {
    "smooth": VideoQuality(max_size=1280, bit_rate=2_500_000),
    "balanced": VideoQuality(max_size=1600, bit_rate=4_000_000),
    "high": VideoQuality(max_size=1920, bit_rate=6_000_000),
    "native": VideoQuality(max_size=None, bit_rate=8_000_000),
}


class AdbH264Streamer:
    """Stream the Android screen as a continuous raw H.264 byte stream."""

    def __init__(self, adb_executable: str = "adb") -> None:
        self.adb_executable = adb_executable

    def quality(self, name: str) -> VideoQuality:
        try:
            return VIDEO_QUALITIES[name]
        except KeyError as exc:
            choices = ", ".join(VIDEO_QUALITIES)
            raise VideoStreamError(f"unknown video quality {name!r}; choose: {choices}") from exc

    def _screen_size(self, serial: str) -> tuple[int, int] | None:
        try:
            cp = subprocess.run(
                [self.adb_executable, "-s", serial, "shell", "wm", "size"],
                capture_output=True,
                timeout=3,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        text = cp.stdout.decode("utf-8", errors="replace")
        match = re.search(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", text)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _encoder_size(self, serial: str, quality: VideoQuality) -> tuple[int, int] | None:
        size = self._screen_size(serial)
        if size is None:
            return None
        width, height = size
        max_size = quality.max_size
        if max_size is None or max(width, height) <= max_size:
            return width - width % 2, height - height % 2
        scale = max_size / max(width, height)
        scaled_w = max(2, int(width * scale))
        scaled_h = max(2, int(height * scale))
        return scaled_w - scaled_w % 2, scaled_h - scaled_h % 2

    def preflight(self, serial: str, quality_name: str = "balanced") -> dict[str, object]:
        if not serial:
            raise VideoStreamError("serial is required")
        quality = self.quality(quality_name)
        try:
            cp = subprocess.run(
                [self.adb_executable, "-s", serial, "shell", "screenrecord", "--help"],
                capture_output=True,
                timeout=5,
                check=False,
                shell=False,
            )
        except OSError as exc:
            raise VideoStreamError(f"failed to run screenrecord: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoStreamError("screenrecord capability check timed out") from exc
        output = (cp.stdout + cp.stderr).decode("utf-8", errors="replace")
        encoder_size = self._encoder_size(serial, quality)
        return {
            "available": cp.returncode == 0 or "screenrecord" in output.lower(),
            "h264_option_reported": "output-format" in output or "h264" in output.lower(),
            "quality": quality_name,
            "encoder_size": f"{encoder_size[0]}x{encoder_size[1]}" if encoder_size else None,
            "bit_rate": quality.bit_rate,
        }

    def stream(self, serial: str, quality_name: str = "balanced") -> Iterator[bytes]:
        if not serial:
            raise VideoStreamError("serial is required")
        quality = self.quality(quality_name)

        while True:
            process = self._start(serial, quality)
            emitted = False
            try:
                if process.stdout is None:
                    raise VideoStreamError("screenrecord stdout is unavailable")
                while True:
                    chunk = process.stdout.read1(8 * 1024)
                    if not chunk:
                        break
                    emitted = True
                    yield chunk
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()

            if process.returncode not in (0, None):
                stderr = b""
                if process.stderr is not None:
                    stderr = process.stderr.read()
                message = stderr.decode("utf-8", errors="replace").strip()
                raise VideoStreamError(message or "adb screenrecord h264 stream failed")
            if not emitted:
                raise VideoStreamError("screenrecord produced no H.264 data")

    def _start(self, serial: str, quality: VideoQuality) -> subprocess.Popen[bytes]:
        command = [
            self.adb_executable,
            "-s",
            serial,
            "exec-out",
            "screenrecord",
            "--output-format=h264",
            "--bit-rate",
            str(quality.bit_rate),
        ]
        encoder_size = self._encoder_size(serial, quality)
        if encoder_size is not None:
            command.extend(["--size", f"{encoder_size[0]}x{encoder_size[1]}"])
        command.append("-")
        try:
            return subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )
        except OSError as exc:
            raise VideoStreamError(f"failed to start h264 stream for {serial}: {exc}") from exc
