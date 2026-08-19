"""CLI única del motor: servidor, modelos, token y diagnóstico."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .external_sources import download_external_pack
from .model_advisor import ModelAdvisor
from .model_operations import download_pack
from .models import (
    HuggingFacePackInstaller,
    ModelCatalog,
    ModelOperationError,
    classify_model_exception,
)
from .resource_governor import ResourceGovernor, ResourceLimits
from .runtime import RuntimePaths
from .runtime_discovery import discover_runtime_inventory
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
    print(
        json.dumps(
            {"ok": False, "code": error.code, "message": error.message},
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 10


def _emit_pack(pack) -> None:
    print(
        json.dumps(
            {
                "ok": True,
                "id": pack.id,
                "version": pack.version,
                "active": pack.active,
            },
            ensure_ascii=False,
        )
    )


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


def _definition_resource(definition: dict) -> dict:
    governor = ResourceGovernor(ResourceLimits())
    decision = governor.preflight_model(
        model_ram_mb=float(definition.get("ramMb", 0)),
        dedicated_vram_mb=float(definition.get("vramMb", 0)),
        shared_gpu_mb=float(definition.get("sharedGpuMb", 0)),
    )
    return {
        "allowed": decision.allowed,
        "mode": decision.mode,
        "reason": decision.reason,
        "effectiveProcessMb": decision.effective_process_mb,
        "productReserveMb": governor.limits.product_reserve_mb,
        "processHeadroomMb": decision.process_headroom_mb,
        "vramHeadroomMb": decision.vram_headroom_mb,
    }


def cmd_models(args) -> int:
    paths = _paths(args)
    catalog = ModelCatalog(paths.models_dir)
    installer = HuggingFacePackInstaller(catalog)
    try:
        if args.model_action == "list":
            definitions = []
            for definition in catalog.definitions():
                enriched = dict(definition)
                enriched["resource"] = _definition_resource(definition)
                definitions.append(enriched)
            inventory = discover_runtime_inventory()
            print(
                json.dumps(
                    {
                        "definitions": definitions,
                        "installed": [
                            {"id": p.id, "version": p.version, "active": p.active}
                            for p in catalog.installed()
                        ],
                        "runtimes": sorted(inventory.runtimes),
                        "backends": sorted(inventory.backends),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if args.model_action == "install":
            definition = catalog.definition(args.pack_id)
            if not args.download_only:
                resource = _definition_resource(definition)
                if not resource["allowed"]:
                    raise ModelOperationError(
                        str(resource["reason"]),
                        "El modelo supera el límite total de 2 GB o 384 MB de VRAM.",
                    )
            pack = download_pack(installer, catalog, args.pack_id)
            if not args.download_only:
                installer.activate(pack.id, pack.version)
                pack = next(
                    item
                    for item in catalog.installed()
                    if item.id == pack.id and item.version == pack.version
                )
            _emit_pack(pack)
            return 0
        if args.model_action == "activate":
            definition = catalog.definition(args.pack_id)
            resource = _definition_resource(definition)
            if not resource["allowed"]:
                raise ModelOperationError(
                    str(resource["reason"]),
                    "El modelo supera el límite total de 2 GB o 384 MB de VRAM.",
                )
            installer.activate(args.pack_id, args.version)
            print(
                json.dumps(
                    {"ok": True, "active": f"{args.pack_id}@{args.version}"},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.model_action == "import":
            _emit_pack(installer.import_pack(Path(args.archive)))
            return 0
        if args.model_action == "import-url":
            staging = paths.models_dir / ".staging" / "external-downloads"
            archive = download_external_pack(args.url, staging)
            try:
                pack = installer.import_pack(archive)
            finally:
                archive.unlink(missing_ok=True)
            _emit_pack(pack)
            return 0
        if args.model_action == "auto-select":
            advisor = ModelAdvisor(catalog, installer)
            selection, reports = advisor.optimize(
                args.route,
                allow_cloud=args.allow_cloud,
                force_benchmark=args.force_benchmark,
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "selected": selection.candidate.id,
                        "backend": selection.backend,
                        "score": round(selection.score, 4),
                        "rejected": selection.rejected,
                        "benchmarks": reports,
                    },
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
    required_modules = (
        "fastapi",
        "uvicorn",
        "numpy",
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "sentencepiece",
    )
    optional_modules = (
        "transformers",
        "torch",
        "moonshine_voice",
        "sherpa_onnx",
        "onnxruntime",
    )
    required: dict[str, bool] = {}
    optional: dict[str, bool] = {}
    for module in required_modules:
        try:
            __import__(module)
            required[module] = True
        except Exception:
            required[module] = False
    for module in optional_modules:
        try:
            __import__(module)
            optional[module] = True
        except Exception:
            optional[module] = False
    inventory = discover_runtime_inventory()
    active = ModelCatalog(paths.models_dir).active_pack()
    limits = ResourceLimits()
    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "dependencies": required,
                "optionalDependencies": optional,
                "runtimes": sorted(inventory.runtimes),
                "backends": sorted(inventory.backends),
                "cuda": "cuda" in inventory.backends,
                "activeModelPack": f"{active.id}@{active.version}" if active else None,
                "resourceLimits": {
                    "processMb": limits.hard_process_mb,
                    "desktopReserveMb": limits.desktop_reserve_mb,
                    "bridgeReserveMb": limits.bridge_reserve_mb,
                    "productReserveMb": limits.product_reserve_mb,
                    "liteSteadyMb": limits.lite_steady_mb,
                    "litePeakMb": limits.lite_peak_mb,
                    "rescueMb": limits.rescue_mb,
                    "vramMb": limits.vram_budget_mb,
                },
            },
            indent=2,
        )
    )
    return 0 if all(required.values()) else 1


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
    install.add_argument("--download-only", action="store_true")
    install.set_defaults(func=cmd_models)
    activate = model_sub.add_parser("activate")
    activate.add_argument("pack_id")
    activate.add_argument("version")
    activate.set_defaults(func=cmd_models)
    import_pack = model_sub.add_parser("import")
    import_pack.add_argument("archive")
    import_pack.set_defaults(func=cmd_models)
    import_url = model_sub.add_parser("import-url")
    import_url.add_argument("url")
    import_url.set_defaults(func=cmd_models)
    auto = model_sub.add_parser("auto-select")
    auto.add_argument("--route", default="en-es")
    auto.add_argument("--allow-cloud", action="store_true")
    auto.add_argument("--force-benchmark", action="store_true")
    auto.set_defaults(func=cmd_models)
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
