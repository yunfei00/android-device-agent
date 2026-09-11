from __future__ import annotations

import argparse

import uvicorn

from .api import create_app

app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Android Device Agent")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
