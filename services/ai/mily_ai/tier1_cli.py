"""CLI 2.1: delega comandos estables y sustituye únicamente `serve`."""

from __future__ import annotations

import sys

from . import cli as base_cli
from .tier1_server import create_app


def cmd_serve(args) -> int:
    paths = base_cli._paths(args)
    try:
        import uvicorn
    except ImportError:
        print("uvicorn no está instalado", file=sys.stderr)
        return 2
    uvicorn.run(
        create_app(paths, args.port, args.parent_pid),
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        access_log=False,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    base_cli.cmd_serve = cmd_serve
    return base_cli.main(argv)
