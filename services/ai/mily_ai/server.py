"""Servidor localhost autenticado para la extensión y el escritorio."""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from .audio import decode_pcm16_base64
from .logging_safe import build_logger
from .models import HuggingFacePackInstaller, ModelCatalog
from .pipeline import RealtimePipeline
from .protocol import ClientMessage, ProtocolError, event
from .runtime import EngineSettings, RuntimePaths, parent_process_alive
from .security import PairingTokenService
from .sessions import SessionRecorder

ALLOWED_ORIGIN_PREFIXES = ("chrome-extension://", "edge-extension://", "http://localhost", "http://127.0.0.1")


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
    token = token_service.get_or_create()
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

    app = FastAPI(
        title="MilyVoiceTraductor Local Engine",
        docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )

    def authenticated(request: Request) -> None:
        if request.headers.get("authorization") != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="No autorizado")

    @app.get("/health")
    async def health():
        active = catalog.active_pack()
        return {
            "ok": True,
            "version": "1.0.0-rc.1",
            "protocol": 1,
            "modelPack": f"{active.id}@{active.version}" if active else None,
            "extensionConnected": heartbeat_path.exists() and time.time() - heartbeat_path.stat().st_mtime < 30,
        }

    @app.get("/v1/models")
    async def models(request: Request):
        authenticated(request)
        return {
            "definitions": catalog.definitions(),
            "installed": [
                {"id": p.id, "version": p.version, "active": p.active, "title": p.title, "commercialUse": p.commercial_use}
                for p in catalog.installed()
            ],
        }

    @app.post("/v1/models/install/{pack_id}")
    async def install_model(pack_id: str, request: Request):
        authenticated(request)
        loop = asyncio.get_running_loop()
        try:
            pack = await loop.run_in_executor(None, installer.install, pack_id)
        except (KeyError, RuntimeError, OSError) as exc:
            logger.warning("Fallo de instalación de modelo: %s", exc.__class__.__name__)
            return JSONResponse(status_code=400, content={"ok": False, "error": "No se pudo instalar el pack."})
        return {"ok": True, "id": pack.id, "version": pack.version}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        origin = websocket.headers.get("origin", "")
        if origin and not origin.startswith(ALLOWED_ORIGIN_PREFIXES):
            await websocket.close(code=4403)
            return
        if websocket.query_params.get("token") != token:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        pipeline: RealtimePipeline | None = None
        recorder: SessionRecorder | None = None
        try:
            await websocket.send_json(event("engine.ready", version="1.0.0-rc.1", protocolVersion=1))
            while True:
                raw = await websocket.receive_text()
                try:
                    message = ClientMessage.parse(raw)
                except ProtocolError:
                    await websocket.send_json(event("engine.error", code="PROTOCOL", message="Mensaje no válido."))
                    continue

                if message.type == "ping":
                    await websocket.send_json(event("pong"))
                    continue

                if message.type == "client.hello":
                    heartbeat_path.write_text(json.dumps({"at": time.time()}), encoding="utf-8")
                    active = catalog.active_pack()
                    if active is None:
                        await websocket.send_json(event("engine.error", code="MODEL_NOT_INSTALLED", message="Instala un pack de modelos desde MilyVoiceTraductor."))
                        continue
                    recorder = SessionRecorder(paths.sessions_dir, message.persist_transcript or settings.persist_transcripts)
                    session_id = recorder.start(message.source_language, message.target_language)
                    await websocket.send_json(event("engine.loading", modelPack=f"{active.id}@{active.version}"))
                    try:
                        pipeline = RealtimePipeline(active, message.source_language, settings.compute_profile, recorder)
                    except Exception as exc:
                        logger.error("No se pudo preparar pipeline: %s", exc.__class__.__name__)
                        await websocket.send_json(event("engine.error", code="PIPELINE_INIT", message="No se pudo iniciar el motor local."))
                        pipeline = None
                        continue
                    await websocket.send_json(event("session.started", sessionId=session_id))
                    continue

                if message.type == "audio.chunk":
                    if pipeline is None:
                        await websocket.send_json(event("engine.error", code="SESSION_NOT_STARTED", message="Inicia una sesión antes de enviar audio."))
                        continue
                    try:
                        samples = decode_pcm16_base64(message.audio_base64 or "")
                        segments = await asyncio.get_running_loop().run_in_executor(None, pipeline.push, samples)
                    except Exception as exc:
                        logger.warning("Error procesando audio: %s", exc.__class__.__name__)
                        await websocket.send_json(event("engine.error", code="AUDIO_PROCESS", message="No se pudo procesar un fragmento de audio."))
                        continue
                    heartbeat_path.write_text(json.dumps({"at": time.time()}), encoding="utf-8")
                    for segment in segments:
                        await websocket.send_json(event(
                            "translation.final",
                            start=segment.start,
                            end=segment.end,
                            original=segment.original,
                            translation=segment.translation,
                        ))
                    continue

                if message.type == "audio.stop":
                    if pipeline is not None:
                        try:
                            remaining = await asyncio.get_running_loop().run_in_executor(None, pipeline.flush)
                            for segment in remaining:
                                await websocket.send_json(event("translation.final", start=segment.start, end=segment.end, original=segment.original, translation=segment.translation))
                        except Exception as exc:
                            logger.warning("No se pudo vaciar buffer: %s", exc.__class__.__name__)
                    result = recorder.finish() if recorder is not None else None
                    await websocket.send_json(event(
                        "session.finished",
                        sessionId=result.session_id if result else None,
                        persisted=bool(result and result.metadata_path),
                    ))
                    pipeline = None
                    recorder = None
        except WebSocketDisconnect:
            logger.info("Extensión desconectada.")
        except Exception as exc:
            logger.error("Conexión finalizó con error: %s", exc.__class__.__name__)
            try:
                await websocket.close(code=1011)
            except Exception:
                pass

    return app
