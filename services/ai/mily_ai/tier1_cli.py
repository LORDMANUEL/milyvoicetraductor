"""CLI 2.1: delega comandos estables y sustituye sólo extensiones Tier 1."""

from __future__ import annotations

import sys

from . import cli as base_cli
from . import provider_factory
from .tier1_marian_cascade import Tier1MarianCascadeTranslator
from .tier1_model_advisor import Tier1ModelAdvisor
from .tier1_model_operations import download_pack as tier1_download_pack
from .tier1_server import create_app


def _install_tier1_provider_hooks() -> None:
    provider_factory.CTranslate2MarianCascadeTranslator = Tier1MarianCascadeTranslator


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
    # Los símbolos son puntos de extensión deliberados de la capa 2.1. El CLI
    # estable conserva parser, errores y comandos; sólo cambiamos las piezas que
    # necesitan conocer las rutas salientes.
    _install_tier1_provider_hooks()
    base_cli.cmd_serve = cmd_serve
    base_cli.download_pack = tier1_download_pack
    base_cli.ModelAdvisor = Tier1ModelAdvisor
    return base_cli.main(argv)
