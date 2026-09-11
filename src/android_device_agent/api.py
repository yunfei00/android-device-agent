from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from .adb import AdbClient, AdbError

adb = AdbClient()
router = APIRouter(prefix="/api/v1")


class ShellRequest(BaseModel):
    command: list[str]
    timeout: float = Field(default=10.0, ge=0.1, le=120.0)


class TapRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class SwipeRequest(BaseModel):
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(ge=0)
    y2: int = Field(ge=0)
    duration_ms: int = Field(default=300, ge=1, le=10000)


class TextRequest(BaseModel):
    text: str


class KeyRequest(BaseModel):
    keycode: str


class AppRequest(BaseModel):
    package: str
    activity: str | None = None


def _shell_or_500(serial: str, command: list[str], timeout: float = 10.0) -> dict:
    try:
        result = adb.shell(serial, command, timeout)
    except (AdbError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return asdict(result)


@router.get("/devices")
def list_devices() -> dict:
    try:
        return {"devices": adb.devices()}
    except AdbError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/devices/{serial}/info")
def device_info(serial: str) -> dict:
    try:
        return adb.device_info(serial)
    except AdbError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/devices/{serial}/shell")
def shell(serial: str, payload: ShellRequest) -> dict:
    return _shell_or_500(serial, payload.command, payload.timeout)


@router.post("/devices/{serial}/input/tap")
def tap(serial: str, payload: TapRequest) -> dict:
    return _shell_or_500(serial, ["input", "tap", str(payload.x), str(payload.y)])


@router.post("/devices/{serial}/input/swipe")
def swipe(serial: str, payload: SwipeRequest) -> dict:
    return _shell_or_500(
        serial,
        [
            "input",
            "swipe",
            str(payload.x1),
            str(payload.y1),
            str(payload.x2),
            str(payload.y2),
            str(payload.duration_ms),
        ],
    )


@router.post("/devices/{serial}/input/text")
def input_text(serial: str, payload: TextRequest) -> dict:
    safe_text = payload.text.replace(" ", "%s")
    return _shell_or_500(serial, ["input", "text", safe_text])


@router.post("/devices/{serial}/input/key")
def input_key(serial: str, payload: KeyRequest) -> dict:
    return _shell_or_500(serial, ["input", "keyevent", payload.keycode])


@router.post("/devices/{serial}/apps/start")
def app_start(serial: str, payload: AppRequest) -> dict:
    if payload.activity:
        return _shell_or_500(serial, ["am", "start", "-n", f"{payload.package}/{payload.activity}"])
    return _shell_or_500(
        serial,
        ["monkey", "-p", payload.package, "-c", "android.intent.category.LAUNCHER", "1"],
    )


@router.post("/devices/{serial}/apps/stop")
def app_stop(serial: str, payload: AppRequest) -> dict:
    return _shell_or_500(serial, ["am", "force-stop", payload.package])


@router.post("/devices/{serial}/reboot")
def reboot(serial: str) -> dict:
    try:
        result = adb.run(["-s", serial, "reboot"], timeout=10)
    except AdbError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return asdict(result)


@router.get("/devices/{serial}/screenshot")
def screenshot(serial: str) -> Response:
    try:
        png = adb.screenshot(serial)
    except AdbError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


def create_app() -> FastAPI:
    app = FastAPI(title="Android Device Agent", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "adb_available": adb.available}

    app.include_router(router)
    return app
