"""Servidor localhost autenticado para la extensión y el escritorio."""

import asyncio
import json
import os
import secrets
import time
from contextlib import asynccontextmanager

from .audio import decode_pcm16_base64, decode_pcm16_bytes
from .logging_safe import build_logger, close_logger
from .models import HuggingFacePackInstaller, ModelCatalog, ModelOperationError
from .pipeline import RealtimePipeline
from .protocol import ClientMessage, ProtocolError, event
from .runtime import EngineSettings, RuntimePaths, parent_process_alive
from .security import EphemeralCredentialService, PairingTokenService
from .sessions import SessionRecorder

PINNED_EXTENSION_ORIGIN = "chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm"


def websocket_origin_allowed(origin: str) -> bool:
    """Solo la extensión fijada o vistas loopback del propio producto pueden entrar."""
    if not origin:
        # Clientes internos/diagnóstico no siempre envían Origin.
        return True
    normalized = origin.rstrip("/")
    if normalized == PINNED_EXTENSION_ORIGIN:
        return True
    return normalized.startswith("http://127.0.0.1:") or normalized.startswith(
        "http://localhost:"
    )


def create_app(paths: RuntimePaths, port: int = 8765, parent_pid: int | None = None):
    """Crea FastAPI de forma diferida para que CLI/tests básicos sigan ligeros."""
    try:
        from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI no está instalado") from exc

    paths.ensure()
    settings = EngineSettings.load(paths.config_dir)
    logger = build_logger(paths.logs_dir, settings.log_level)
    token_service = PairingTokenService(paths.config_dir / "bridge-token.txt")
    internal_token = token_service.get_or_create()
    ephemeral_credentials = EphemeralCredentialService(
        paths.config_dir / "native-credential.json"
    )
    catalog = ModelCatalog(paths.models_dir)
    installer = HuggingFacePackInstaller(catalog)
    heartbeat_path = paths.data_dir / "extension-heartbeat.json"

    @asynccontextmanager
    async def lifespan(_app):
        async def watch_parent():
            while parent_pid:
                await asyncio.sleep(2)
                if not parent_process_alive(parent_pid):
                    os._exit(0)

        task = asyncio.create_task(watch_parent()) if parent_pid else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            close_logger(logger)

    app = FastAPI(
        title="MilyVoiceTraductor Local Engine",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    def valid_token(candidate: str | None) -> bool:
        if not candidate:
            return False
        if len(candidate) == len(internal_token) and secrets.compare_digest(
            candidate, internal_token
        ):
            return True
        return ephemeral_credentials.is_valid(candidate)

    def authenticated(request: Request) -> None:
        authorization = request.headers.get("authorization", "")
        candidate = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not valid_token(candidate):
            raise HTTPException(status_code=401, detail="No autorizado")

    @app.get("/health")
    async def health():
        active = catalog.active_pack()
        return {
            "ok": True,
            "version": "1.0.5",
            "protocol": 1,
            "modelPack": f"{active.id}@{active.version}" if active else None,
            "extensionConnected": heartbeat_path.exists()
            and time.time() - heartbeat_path.stat().st_mtime < 30,
        }

    @app.get("/v1/models")
    async def models(request: Request):
        authenticated(request)
        return {
            "definitions": catalog.definitions(),
            "installed": [
                {
                    "id": p.id,
                    "version": p.version,
                    "active": p.active,
                    "title": p.title,
                    "commercialUse": p.commercial_use,
                }
                for p in catalog.installed()
            ],
        }

    @app.post("/v1/models/install/{pack_id}")
    async def install_model(pack_id: str, request: Request):
        authenticated(request)
        loop = asyncio.get_running_loop()
        try:
            pack = await loop.run_in_executor(None, installer.install, pack_id)
        except ModelOperationError as exc:
            logger.warning("Fallo de instalación de modelo: %s", exc.code)
            return JSONResponse(
                status_code=400,
                content={"ok": False, "code": exc.code, "message": exc.message},
            )
        except Exception as exc:
            logger.warning("Fallo de instalación de modelo: %s", exc.__class__.__name__)
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "code": "MODEL_PROVIDER_ERROR",
                    "message": "El proveedor de modelos no pudo completar la operación.",
                },
            )
        return {"ok": True, "id": pack.id, "version": pack.version}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        origin = websocket.headers.get("origin", "")
        if not websocket_origin_allowed(origin):
            await websocket.close(code=4403)
            return
        if not valid_token(websocket.query_params.get("token")):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        pipeline: RealtimePipeline | None = None
        recorder: SessionRecorder | None = None
        binary_pcm_enabled = False

        async def process_samples(samples) -> None:
            nonlocal pipeline
            if pipeline is None:
                await websocket.send_json(
                    event(
                        "engine.error",
                        code="SESSION_NOT_STARTED",
                        message="Inicia una sesión antes de enviar audio.",
                    )
                )
                return
            try:
                segments = await asyncio.get_running_loop().run_in_executor(
                    None, pipeline.push, samples
                )
            except Exception as exc:
                logger.warning("Error procesando audio: %s", exc.__class__.__name__)
                await websocket.send_json(
                    event(
                        "engine.error",
                        code="AUDIO_PROCESS",
                        message="No se pudo procesar un fragmento de audio.",
                    )
                )
                return
            heartbeat_path.write_text(
                json.dumps({"at": time.time()}), encoding="utf-8"
            )
            for segment in segments:
                await websocket.send_json(
                    event(
                        "translation.final",
                        start=segment.start,
                        end=segment.end,
                        original=segment.original,
                        translation=segment.translation,
                    )
                )

        try:
            await websocket.send_json(
                event("engine.ready", version="1.0.5", protocolVersion=1)
            )
            while True:
                packet = await websocket.receive()
                if packet.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect(packet.get("code", 1000))

                raw_bytes = packet.get("bytes")
                if raw_bytes is not None:
                    if not binary_pcm_enabled:
                        await websocket.send_json(
                            event(
                                "engine.error",
                                code="PROTOCOL",
                                message="PCM binario no fue negociado para esta sesión.",
                            )
                        )
                        continue
                    try:
                        samples = decode_pcm16_bytes(raw_bytes)
                    except ValueError:
                        await websocket.send_json(
                            event(
                                "engine.error",
                                code="AUDIO_PROCESS",
                                message="No se pudo procesar un fragmento de audio.",
                            )
                        )
                        continue
                    await process_samples(samples)
                    continue

                raw = packet.get("text")
                if raw is None:
                    continue
                try:
                    message = ClientMessage.parse(raw)
                except ProtocolError:
                    await websocket.send_json(
                        event("engine.error", code="PROTOCOL", message="Mensaje no válido.")
                    )
                    continue

                if message.type == "ping":
                    await websocket.send_json(event("pong"))
                    continue

                if message.type == "client.hello":
                    heartbeat_path.write_text(
                        json.dumps({"at": time.time()}), encoding="utf-8"
                    )
                    active = catalog.active_pack()
                    if active is None:
                        await websocket.send_json(
                            event(
                                "engine.error",
                                code="MODEL_NOT_INSTALLED",
                                message="El modelo se está preparando en MilyVoiceTraductor.",
                            )
                        )
                        continue
                    recorder = SessionRecorder(
                        paths.sessions_dir,
                        message.persist_transcript or settings.persist_transcripts,
                    )
                    session_id = recorder.start(
                        message.source_language, message.target_language
                    )
                    await websocket.send_json(
                        event("engine.loading", modelPack=f"{active.id}@{active.version}")
                    )
                    try:
                        pipeline = RealtimePipeline(
                            active,
                            message.source_language,
                            settings.compute_profile,
                            recorder,
                        )
                    except Exception as exc:
                        logger.error(
                            "No se pudo preparar pipeline: %s", exc.__class__.__name__
                        )
                        await websocket.send_json(
                            event(
                                "engine.error",
                                code="PIPELINE_INIT",
                                message="No se pudo iniciar el motor local.",
                            )
                        )
                        pipeline = None
                        continue
                    binary_pcm_enabled = message.binary_pcm
                    await websocket.send_json(
                        event(
                            "session.started",
                            sessionId=session_id,
                            binaryPcm=binary_pcm_enabled,
                        )
                    )
                    continue

                if message.type == "audio.chunk":
                    try:
                        samples = decode_pcm16_base64(message.audio_base64 or "")
                    except ValueError:
                        await websocket.send_json(
                            event(
                                "engine.error",
                                code="AUDIO_PROCESS",
                                message="No se pudo procesar un fragmento de audio.",
                            )
                        )
                        continue
                    await process_samples(samples)
                    continue

                if message.type == "audio.stop":
                    if pipeline is not None:
                        try:
                            remaining = await asyncio.get_running_loop().run_in_executor(
                                None, pipeline.flush
                            )
                            for segment in remaining:
                                await websocket.send_json(
                                    event(
                                        "translation.final",
                                        start=segment.start,
                                        end=segment.end,
                                        original=segment.original,
                                        translation=segment.translation,
                                    )
                                )
                        except Exception as exc:
                            logger.warning(
                                "No se pudo vaciar buffer: %s", exc.__class__.__name__
                            )
                    result = recorder.finish() if recorder is not None else None
                    await websocket.send_json(
                        event(
                            "session.finished",
                            sessionId=result.session_id if result else None,
                            persisted=bool(result and result.metadata_path),
                        )
                    )
                    pipeline = None
                    recorder = None
                    binary_pcm_enabled = False
        except WebSocketDisconnect:
            logger.info("Extensión desconectada.")
        except Exception as exc:
            logger.error("Conexión finalizó con error: %s", exc.__class__.__name__)
            try:
                await websocket.close(code=1011)
            except Exception:
                pass

    return app
