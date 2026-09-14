from __future__ import annotations

import shlex
import subprocess
import threading
from dataclasses import dataclass


class FastInputError(RuntimeError):
    pass


@dataclass(slots=True)
class _ShellSession:
    process: subprocess.Popen[str]
    lock: threading.Lock


class FastInputManager:
    """Keep one interactive adb shell alive per device for low-latency input."""

    def __init__(self, adb_executable: str = "adb") -> None:
        self.adb_executable = adb_executable
        self._sessions: dict[str, _ShellSession] = {}
        self._guard = threading.Lock()

    def _start(self, serial: str) -> _ShellSession:
        try:
            process = subprocess.Popen(
                [self.adb_executable, "-s", serial, "shell"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                shell=False,
            )
        except OSError as exc:
            raise FastInputError(f"failed to start adb shell for {serial}: {exc}") from exc
        return _ShellSession(process=process, lock=threading.Lock())

    def _session(self, serial: str) -> _ShellSession:
        if not serial:
            raise FastInputError("serial is required")
        with self._guard:
            current = self._sessions.get(serial)
            if current is None or current.process.poll() is not None:
                if current is not None:
                    self._close_session(current)
                current = self._start(serial)
                self._sessions[serial] = current
            return current

    def send(self, serial: str, command: list[str]) -> None:
        if not command:
            raise FastInputError("command is required")
        session = self._session(serial)
        line = shlex.join(command)
        with session.lock:
            if session.process.poll() is not None or session.process.stdin is None:
                with self._guard:
                    self._sessions.pop(serial, None)
                session = self._session(serial)
            try:
                assert session.process.stdin is not None
                session.process.stdin.write(line + "\n")
                session.process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                with self._guard:
                    self._sessions.pop(serial, None)
                self._close_session(session)
                raise FastInputError(f"adb input channel failed for {serial}: {exc}") from exc

    def tap(self, serial: str, x: int, y: int) -> None:
        self.send(serial, ["input", "tap", str(x), str(y)])

    def swipe(self, serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self.send(
            serial,
            ["input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
        )

    def key(self, serial: str, keycode: str) -> None:
        self.send(serial, ["input", "keyevent", keycode])

    def text(self, serial: str, value: str) -> None:
        self.send(serial, ["input", "text", value.replace(" ", "%s")])

    @staticmethod
    def _close_session(session: _ShellSession) -> None:
        process = session.process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()

    def close(self, serial: str) -> None:
        with self._guard:
            session = self._sessions.pop(serial, None)
        if session is not None:
            self._close_session(session)

    def close_all(self) -> None:
        with self._guard:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            self._close_session(session)
