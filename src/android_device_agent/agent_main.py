from __future__ import annotations

import argparse
import sys

import uvicorn

from android_device_agent.api import create_app

app = create_app()


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main() -> None:
    _configure_console()
    parser = argparse.ArgumentParser(description="Android Device Agent")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        use_colors=False,
    )


if __name__ == "__main__":
    main()
