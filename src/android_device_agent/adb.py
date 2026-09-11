from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass


@dataclass(slots=True)
class CommandResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class AdbError(RuntimeError):
    pass


class AdbClient:
    def __init__(self, executable: str = "adb", timeout: float = 10.0) -> None:
        self.executable = executable
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def _run_bytes(self, args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
        cmd = [self.executable, *args]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout or self.timeout,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"ADB executable not found: {self.executable}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB command timed out: {' '.join(cmd)}") from exc

    def run(self, args: list[str], timeout: float | None = None) -> CommandResult:
        started = time.perf_counter()
        cp = self._run_bytes(args, timeout)
        elapsed = int((time.perf_counter() - started) * 1000)
        return CommandResult(
            success=cp.returncode == 0,
            exit_code=cp.returncode,
            stdout=cp.stdout.decode("utf-8", errors="replace").strip(),
            stderr=cp.stderr.decode("utf-8", errors="replace").strip(),
            duration_ms=elapsed,
        )

    def devices(self) -> list[dict[str, str]]:
        result = self.run(["devices", "-l"])
        if not result.success:
            raise AdbError(result.stderr or "adb devices failed")
        return parse_devices(result.stdout)

    def shell(self, serial: str, command: list[str], timeout: float | None = None) -> CommandResult:
        if not serial:
            raise ValueError("serial is required")
        if not command:
            raise ValueError("command is required")
        return self.run(["-s", serial, "shell", *command], timeout=timeout)

    def screenshot(self, serial: str) -> bytes:
        cp = self._run_bytes(["-s", serial, "exec-out", "screencap", "-p"], timeout=15)
        if cp.returncode != 0:
            raise AdbError(cp.stderr.decode("utf-8", errors="replace").strip() or "screenshot failed")
        return cp.stdout

    def getprop(self, serial: str, name: str) -> str:
        return self.shell(serial, ["getprop", name]).stdout

    def device_info(self, serial: str) -> dict[str, str | None]:
        battery = self.shell(serial, ["dumpsys", "battery"]).stdout
        size = self.shell(serial, ["wm", "size"]).stdout
        level_match = re.search(r"level:\s*(\d+)", battery)
        size_match = re.search(r"(?:Physical|Override) size:\s*(\d+x\d+)", size)
        return {
            "serial": serial,
            "manufacturer": self.getprop(serial, "ro.product.manufacturer"),
            "model": self.getprop(serial, "ro.product.model"),
            "android_version": self.getprop(serial, "ro.build.version.release"),
            "sdk": self.getprop(serial, "ro.build.version.sdk"),
            "battery_level": level_match.group(1) if level_match else None,
            "screen_size": size_match.group(1) if size_match else None,
        }


def parse_devices(output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        item: dict[str, str] = {"serial": parts[0], "state": parts[1]}
        for token in parts[2:]:
            if ":" in token:
                key, value = token.split(":", 1)
                item[key] = value
        devices.append(item)
    return devices
