"""CLI única del motor: servidor, modelos, token y diagnóstico."""

from __future__ import annotations

import argparse
import json
import sys

from .models import (
    HuggingFacePackInstaller,
    ModelCatalog,
    ModelOperationError,
    classify_model_exception,
)
from .runtime import RuntimePaths
from .security import PairingTokenService


def _paths(args) -> RuntimePaths:
    paths = RuntimePaths.discover(
        {
            "data_dir": getattr(args, "data_dir", None),
            "config_dir": getattr(args, "config_dir", None),
            "cache_dir": getattr(args, "cache_dir", None),
            "models_dir": getattr(args, "models_dir", None),
        }
    )
    paths.ensure()
    return paths


def _emit_model_error(error: ModelOperationError) -> int:
    """Escribe una única línea JSON estable que Rust puede interpretar sin traceback."""
    print(
        json.dumps(
            {"ok": False, "code": error.code, "message": error.message},
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 10


def cmd_serve(args) -> int:
    paths = _paths(args)
    try:
        import uvicorn
    except ImportError:
        print("uvicorn no está instalado", file=sys.stderr)
        return 2
    from .server import create_app

    uvicorn.run(
        create_app(paths, args.port, args.parent_pid),
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        access_log=False,
    )
    return 0


def cmd_token(args) -> int:
    paths = _paths(args)
    print(PairingTokenService(paths.config_dir / "bridge-token.txt").get_or_create())
    return 0


def cmd_models(args) -> int:
    paths = _paths(args)
    catalog = ModelCatalog(paths.models_dir)
    installer = HuggingFacePackInstaller(catalog)
    try:
        if args.model_action == "list":
            print(
                json.dumps(
                    {
                        "definitions": catalog.definitions(),
                        "installed": [
                            {"id": p.id, "version": p.version, "active": p.active}
                            for p in catalog.installed()
                        ],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if args.model_action == "install":
            pack = installer.install(args.pack_id)
            print(
                json.dumps(
                    {"ok": True, "id": pack.id, "version": pack.version},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.model_action == "rollback":
            pack = installer.rollback()
            print(
                json.dumps(
                    {"ok": True, "active": f"{pack.id}@{pack.version}"},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.model_action == "verify":
            ok = installer.verify(args.pack_id, args.version)
            if not ok:
                return _emit_model_error(
                    ModelOperationError(
                        "MODEL_HASH_MISMATCH",
                        "El pack local no pasó la verificación de integridad.",
                    )
                )
            print(
                json.dumps(
                    {"ok": True, "id": args.pack_id, "version": args.version},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.model_action == "remove":
            installer.remove(args.pack_id, args.version)
            print(json.dumps({"ok": True}, ensure_ascii=False))
            return 0
        return 2
    except ModelOperationError as exc:
        return _emit_model_error(exc)
    except BaseException as exc:
        return _emit_model_error(classify_model_exception(exc))


def cmd_diagnose(args) -> int:
    paths = _paths(args)
    checks = {}
    for module in (
        "fastapi",
        "uvicorn",
        "numpy",
        "faster_whisper",
        "ctranslate2",
        "transformers",
        "torch",
        "huggingface_hub",
        "sentencepiece",
    ):
        try:
            __import__(module)
            checks[module] = True
        except Exception:
            checks[module] = False
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
    except Exception:
        cuda = False
    active = ModelCatalog(paths.models_dir).active_pack()
    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "dependencies": checks,
                "cuda": cuda,
                "activeModelPack": f"{active.id}@{active.version}" if active else None,
            },
            indent=2,
        )
    )
    return 0 if all(checks.values()) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mily-ai-engine")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir")
    common.add_argument("--config-dir")
    common.add_argument("--cache-dir")
    common.add_argument("--models-dir")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", parents=[common])
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--parent-pid", type=int)
    serve.set_defaults(func=cmd_serve)
    token = sub.add_parser("token", parents=[common])
    token.set_defaults(func=cmd_token)
    diagnose = sub.add_parser("diagnose", parents=[common])
    diagnose.set_defaults(func=cmd_diagnose)
    models = sub.add_parser("models", parents=[common])
    model_sub = models.add_subparsers(dest="model_action", required=True)
    model_sub.add_parser("list").set_defaults(func=cmd_models)
    install = model_sub.add_parser("install")
    install.add_argument("pack_id")
    install.set_defaults(func=cmd_models)
    rollback = model_sub.add_parser("rollback")
    rollback.set_defaults(func=cmd_models)
    verify = model_sub.add_parser("verify")
    verify.add_argument("pack_id")
    verify.add_argument("version")
    verify.set_defaults(func=cmd_models)
    remove = model_sub.add_parser("remove")
    remove.add_argument("pack_id")
    remove.add_argument("version")
    remove.set_defaults(func=cmd_models)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
