from __future__ import annotations

import subprocess
from collections.abc import Iterator


class VideoStreamError(RuntimeError):
    pass


class AdbH264Streamer:
    """Stream the Android screen as a continuous raw H.264 byte stream."""

    def __init__(self, adb_executable: str = "adb", bit_rate: int = 4_000_000) -> None:
        self.adb_executable = adb_executable
        self.bit_rate = bit_rate

    def stream(self, serial: str) -> Iterator[bytes]:
        if not serial:
            raise VideoStreamError("serial is required")

        # Android screenrecord normally ends after its platform time limit. Restarting the
        # producer keeps the HTTP stream alive; H.264 decoders receive fresh SPS/PPS data
        # when each producer starts.
        while True:
            process = self._start(serial)
            try:
                if process.stdout is None:
                    raise VideoStreamError("screenrecord stdout is unavailable")
                while True:
                    chunk = process.stdout.read(64 * 1024)
                    if not chunk:
                        break
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

    def _start(self, serial: str) -> subprocess.Popen[bytes]:
        command = [
            self.adb_executable,
            "-s",
            serial,
            "exec-out",
            "screenrecord",
            "--output-format=h264",
            "--bit-rate",
            str(self.bit_rate),
            "-",
        ]
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
