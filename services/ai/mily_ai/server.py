"""Servidor localhost autenticado para la extensión y el escritorio."""

import asyncio
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from .audio import decode_pcm16_base64, decode_pcm16_bytes
from .event_payloads import pipeline_event_fields
from .logging_safe import build_logger, close_logger
from .models import HuggingFacePackInstaller, ModelCatalog, ModelOperationError
from .pipeline import RealtimePipeline
from .protocol import ClientMessage, ProtocolError, event
from .queueing import enqueue_translation
from .runtime import EngineSettings, RuntimePaths, parent_process_alive
from .security import EphemeralCredentialService, PairingTokenService
from .sessions import SessionRecorder
from .telemetry import LatencyController

PINNED_EXTENSION_ORIGIN = "chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm"
AUDIO_QUEUE_MAX = 16
TRANSLATION_QUEUE_MAX = 8
AUDIO_CHUNK_MS = 100
TELEMETRY_INTERVAL_SECONDS = 0.5


def websocket_origin_allowed(origin: str) -> bool:
    """Solo la extensión fijada o vistas loopback del propio producto pueden entrar."""
    if not origin:
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
        audio_queue: asyncio.Queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX)
        translation_queue: asyncio.Queue = asyncio.Queue(maxsize=TRANSLATION_QUEUE_MAX)
        asr_executor: ThreadPoolExecutor | None = None
        translation_executor: ThreadPoolExecutor | None = None
        audio_task: asyncio.Task | None = None
        translation_task: asyncio.Task | None = None
        send_lock = asyncio.Lock()
        latency_controller = LatencyController()
        last_telemetry_emit = 0.0

        async def safe_send(payload: dict) -> None:
            async with send_lock:
                await websocket.send_json(payload)

        async def send_pipeline_events(items) -> None:
            for item in items:
                await safe_send(event(item.type, **pipeline_event_fields(item)))

        def telemetry_snapshot(current: RealtimePipeline):
            snapshot = current.telemetry.snapshot(
                audio_queue_ms=audio_queue.qsize() * AUDIO_CHUNK_MS,
                translation_queue_depth=translation_queue.qsize(),
            )
            pressure = latency_controller.classify(
                snapshot.audio_queue_ms,
                snapshot.translation_queue_depth,
                snapshot.real_time_factor,
            )
            return snapshot, pressure

        async def emit_realtime_status(current: RealtimePipeline) -> None:
            nonlocal last_telemetry_emit
            now = time.monotonic()
            if now - last_telemetry_emit < TELEMETRY_INTERVAL_SECONDS:
                return
            last_telemetry_emit = now
            level = current.audio_level
            snapshot, pressure = telemetry_snapshot(current)
            await safe_send(
                event(
                    "audio.level",
                    rms=round(level.rms, 5),
                    peak=round(level.peak, 5),
                    silentMs=level.silent_ms,
                    speech=level.speech,
                )
            )
            await safe_send(
                event(
                    "pipeline.metrics",
                    asrP50Ms=round(snapshot.asr_p50_ms, 1),
                    asrP95Ms=round(snapshot.asr_p95_ms, 1),
                    translationP50Ms=round(snapshot.translation_p50_ms, 1),
                    translationP95Ms=round(snapshot.translation_p95_ms, 1),
                    realTimeFactor=round(snapshot.real_time_factor, 3),
                    audioQueueMs=snapshot.audio_queue_ms,
                    translationQueueDepth=snapshot.translation_queue_depth,
                    pressure=pressure,
                    cpuProfile=current.cpu_budget.profile,
                )
            )

        async def queue_translation_requests(requests) -> None:
            current = pipeline
            for request in requests:
                if not request.final and current is not None:
                    _snapshot, pressure = telemetry_snapshot(current)
                    if not latency_controller.allow_partial_translation(pressure):
                        logger.debug(
                            "Parcial omitido por presión realtime: %s", pressure
                        )
                        continue
                accepted = await enqueue_translation(translation_queue, request)
                if not accepted:
                    logger.debug("Parcial de traducción omitido por backpressure.")

        async def audio_worker() -> None:
            nonlocal pipeline
            loop = asyncio.get_running_loop()
            while True:
                samples = await audio_queue.get()
                try:
                    if samples is None:
                        return
                    current = pipeline
                    executor = asr_executor
                    if current is None or executor is None:
                        continue
                    try:
                        events, requests = await loop.run_in_executor(
                            executor, current.ingest, samples
                        )
                    except Exception as exc:
                        logger.warning(
                            "Error procesando audio ASR: %s", exc.__class__.__name__
                        )
                        await safe_send(
                            event(
                                "engine.error",
                                code="AUDIO_PROCESS",
                                message="No se pudo procesar un fragmento de audio.",
                            )
                        )
                        continue
                    heartbeat_path.write_text(
                        json.dumps({"at": time.time()}), encoding="utf-8"
                    )
                    await send_pipeline_events(events)
                    await queue_translation_requests(requests)
                    await emit_realtime_status(current)
                finally:
                    audio_queue.task_done()

        async def translation_worker() -> None:
            nonlocal pipeline
            loop = asyncio.get_running_loop()
            while True:
                request = await translation_queue.get()
                try:
                    if request is None:
                        return
                    current = pipeline
                    executor = translation_executor
                    if current is None or executor is None:
                        continue
                    try:
                        translated = await loop.run_in_executor(
                            executor, current.execute_translation, request
                        )
                    except Exception as exc:
                        logger.warning(
                            "Error en traducción local: %s", exc.__class__.__name__
                        )
                        if request.final:
                            await safe_send(
                                event(
                                    "engine.error",
                                    code="TRANSLATION_PROCESS",
                                    message="No se pudo traducir una frase final.",
                                )
                            )
                        continue
                    await send_pipeline_events([translated])
                finally:
                    translation_queue.task_done()

        async def start_workers() -> None:
            nonlocal audio_queue, translation_queue
            nonlocal asr_executor, translation_executor, audio_task, translation_task
            if pipeline is None:
                return
            audio_queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX)
            translation_queue = asyncio.Queue(maxsize=TRANSLATION_QUEUE_MAX)
            asr_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="mily-asr"
            )
            if pipeline.cpu_budget.parallel_stages:
                translation_executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="mily-translate"
                )
            else:
                translation_executor = asr_executor
            audio_task = asyncio.create_task(audio_worker(), name="mily-audio-worker")
            translation_task = asyncio.create_task(
                translation_worker(), name="mily-translation-worker"
            )

        async def warm_up_workers() -> None:
            current = pipeline
            asr_pool = asr_executor
            translation_pool = translation_executor
            if current is None or asr_pool is None or translation_pool is None:
                return
            loop = asyncio.get_running_loop()
            await asyncio.gather(
                loop.run_in_executor(asr_pool, current.warm_up_asr),
                loop.run_in_executor(translation_pool, current.warm_up_translation),
            )

        def shutdown_executors(*, wait: bool) -> None:
            nonlocal asr_executor, translation_executor
            seen: set[int] = set()
            for executor in (translation_executor, asr_executor):
                if executor is None or id(executor) in seen:
                    continue
                seen.add(id(executor))
                executor.shutdown(wait=wait, cancel_futures=True)
            asr_executor = None
            translation_executor = None

        async def finish_workers(*, flush: bool) -> None:
            nonlocal audio_task, translation_task
            current = pipeline
            executor = asr_executor
            if audio_task is None and translation_task is None:
                return

            if flush and current is not None and executor is not None:
                await audio_queue.join()
                try:
                    events, requests = await asyncio.get_running_loop().run_in_executor(
                        executor, current.flush_ingest
                    )
                    await send_pipeline_events(events)
                    await queue_translation_requests(requests)
                except Exception as exc:
                    logger.warning(
                        "No se pudo finalizar buffer ASR: %s", exc.__class__.__name__
                    )
                await translation_queue.join()

            await audio_queue.put(None)
            await translation_queue.put(None)
            await asyncio.gather(
                *(task for task in (audio_task, translation_task) if task is not None),
                return_exceptions=True,
            )
            audio_task = None
            translation_task = None
            shutdown_executors(wait=True)

        async def abort_workers() -> None:
            nonlocal audio_task, translation_task
            for task in (audio_task, translation_task):
                if task is not None:
                    task.cancel()
            await asyncio.gather(
                *(task for task in (audio_task, translation_task) if task is not None),
                return_exceptions=True,
            )
            audio_task = None
            translation_task = None
            shutdown_executors(wait=False)

        async def enqueue_audio(samples) -> None:
            if pipeline is None or audio_task is None:
                await safe_send(
                    event(
                        "engine.error",
                        code="SESSION_NOT_STARTED",
                        message="Inicia una sesión antes de enviar audio.",
                    )
                )
                return
            await audio_queue.put(samples)

        try:
            await safe_send(event("engine.ready", version="1.0.5", protocolVersion=1))
            while True:
                packet = await websocket.receive()
                if packet.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect(packet.get("code", 1000))

                raw_bytes = packet.get("bytes")
                if raw_bytes is not None:
                    if not binary_pcm_enabled:
                        await safe_send(
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
                        await safe_send(
                            event(
                                "engine.error",
                                code="AUDIO_PROCESS",
                                message="No se pudo procesar un fragmento de audio.",
                            )
                        )
                        continue
                    await enqueue_audio(samples)
                    continue

                raw = packet.get("text")
                if raw is None:
                    continue
                try:
                    message = ClientMessage.parse(raw)
                except ProtocolError:
                    await safe_send(
                        event("engine.error", code="PROTOCOL", message="Mensaje no válido.")
                    )
                    continue

                if message.type == "ping":
                    await safe_send(event("pong"))
                    continue

                if message.type == "client.hello":
                    if pipeline is not None:
                        await finish_workers(flush=True)
                        if recorder is not None:
                            recorder.finish()
                    heartbeat_path.write_text(
                        json.dumps({"at": time.time()}), encoding="utf-8"
                    )
                    active = catalog.active_pack()
                    if active is None:
                        await safe_send(
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
                    await safe_send(
                        event(
                            "engine.loading",
                            modelPack=f"{active.id}@{active.version}",
                            phase="warming",
                        )
                    )
                    try:
                        pipeline = RealtimePipeline(
                            active,
                            message.source_language,
                            settings.compute_profile,
                            recorder,
                            session_mode=message.session_mode,
                        )
                    except Exception as exc:
                        logger.error(
                            "No se pudo preparar pipeline: %s", exc.__class__.__name__
                        )
                        await safe_send(
                            event(
                                "engine.error",
                                code="PIPELINE_INIT",
                                message="No se pudo iniciar el motor local.",
                            )
                        )
                        pipeline = None
                        recorder = None
                        continue
                    await start_workers()
                    try:
                        await warm_up_workers()
                    except Exception as exc:
                        logger.error(
                            "No se pudo precalentar pipeline: %s", exc.__class__.__name__
                        )
                        await finish_workers(flush=False)
                        pipeline = None
                        recorder = None
                        await safe_send(
                            event(
                                "engine.error",
                                code="PIPELINE_WARMUP",
                                message="No se pudieron preparar los modelos locales.",
                            )
                        )
                        continue
                    last_telemetry_emit = 0.0
                    binary_pcm_enabled = message.binary_pcm
                    await safe_send(
                        event(
                            "session.started",
                            sessionId=session_id,
                            sessionMode=message.session_mode,
                            binaryPcm=binary_pcm_enabled,
                            parallelStages=pipeline.cpu_budget.parallel_stages,
                        )
                    )
                    continue

                if message.type == "audio.chunk":
                    try:
                        samples = decode_pcm16_base64(message.audio_base64 or "")
                    except ValueError:
                        await safe_send(
                            event(
                                "engine.error",
                                code="AUDIO_PROCESS",
                                message="No se pudo procesar un fragmento de audio.",
                            )
                        )
                        continue
                    await enqueue_audio(samples)
                    continue

                if message.type == "audio.stop":
                    await finish_workers(flush=True)
                    result = recorder.finish() if recorder is not None else None
                    await safe_send(
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
            await abort_workers()
        except Exception as exc:
            logger.error("Conexión finalizó con error: %s", exc.__class__.__name__)
            await abort_workers()
            try:
                await websocket.close(code=1011)
            except Exception:
                pass

    return app
