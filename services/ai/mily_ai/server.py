"""Servidor localhost autenticado para la extensión y el escritorio."""

import asyncio
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from .audio import decode_pcm16_base64, decode_pcm16_bytes
from .event_payloads import pipeline_event_fields
from .logging_safe import build_logger, close_logger
from .model_advisor import ModelAdvisor
from .model_operations import download_pack
from .models import HuggingFacePackInstaller, ModelCatalog, ModelOperationError
from .pipeline import RealtimePipeline
from .protocol import ClientMessage, ProtocolError, event
from .queueing import (
    CoalescingTranslationQueue,
    enqueue_translation,
    serial_translation_action,
)
from .resource_governor import ResourceGovernor, ResourceLimits
from .runtime import EngineSettings, RuntimePaths, parent_process_alive
from .runtime_discovery import discover_runtime_inventory
from .security import EphemeralCredentialService, PairingTokenService
from .sessions import SessionRecorder
from .system_loopback import LoopbackError, WasapiLoopbackSource
from .telemetry import LatencyController

PINNED_EXTENSION_ORIGIN = "chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm"
AUDIO_QUEUE_MAX = 16
TRANSLATION_QUEUE_MAX = 8
AUDIO_CHUNK_MS = 100
TELEMETRY_INTERVAL_SECONDS = 0.5
SERIAL_FINAL_DEFER_SECONDS = 0.18
SERIAL_DEFER_STEP_SECONDS = 0.02


def websocket_origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    normalized = origin.rstrip("/")
    if normalized == PINNED_EXTENSION_ORIGIN:
        return True
    return normalized.startswith("http://127.0.0.1:") or normalized.startswith(
        "http://localhost:"
    )


def create_app(paths: RuntimePaths, port: int = 8765, parent_pid: int | None = None):
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
    governor = ResourceGovernor(ResourceLimits())
    advisor = ModelAdvisor(catalog, installer, governor=governor)
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

    def definition_for(pack_id: str) -> dict:
        return catalog.definition(pack_id)

    def pack_resource_decision(pack_id: str):
        definition = definition_for(pack_id)
        return governor.preflight_model(
            model_ram_mb=float(definition.get("ramMb", 0)),
            dedicated_vram_mb=float(definition.get("vramMb", 0)),
            shared_gpu_mb=float(definition.get("sharedGpuMb", 0)),
        )

    def resource_limits_payload() -> dict[str, int]:
        limits = governor.limits
        return {
            "processMb": limits.hard_process_mb,
            "desktopReserveMb": limits.desktop_reserve_mb,
            "bridgeReserveMb": limits.bridge_reserve_mb,
            "productReserveMb": limits.product_reserve_mb,
            "liteSteadyMb": limits.lite_steady_mb,
            "litePeakMb": limits.lite_peak_mb,
            "rescueMb": limits.rescue_mb,
            "vramMb": limits.vram_budget_mb,
        }

    @app.get("/health")
    async def health():
        active = catalog.active_pack()
        return {
            "ok": True,
            "version": "2.0.1",
            "protocol": 1,
            "modelPack": f"{active.id}@{active.version}" if active else None,
            "backend": catalog.active_backend(),
            "resourceLimits": resource_limits_payload(),
            "resourceLimitMb": governor.limits.hard_process_mb,
            "vramLimitMb": governor.limits.vram_budget_mb,
            "extensionConnected": heartbeat_path.exists()
            and time.time() - heartbeat_path.stat().st_mtime < 30,
        }

    @app.get("/v1/models")
    async def models(request: Request):
        authenticated(request)
        inventory = discover_runtime_inventory()
        return {
            "definitions": advisor.describe_catalog(),
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
            "runtimes": sorted(inventory.runtimes),
            "backends": sorted(inventory.backends),
            "activeBackend": catalog.active_backend(),
            "limits": resource_limits_payload(),
        }

    @app.get("/v1/engines")
    async def engines(request: Request):
        authenticated(request)
        inventory = discover_runtime_inventory()
        return {
            "engines": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "title": item.title,
                    "routes": list(item.routes),
                    "runtime": item.runtime,
                    "cloud": item.cloud,
                    "commercialUse": item.commercial_use,
                    "available": item.runtime in inventory.runtimes,
                }
                for item in advisor.registry.descriptors
            ],
            "runtimes": sorted(inventory.runtimes),
            "backends": sorted(inventory.backends),
            "details": inventory.details,
        }

    @app.post("/v1/models/install/{pack_id}")
    async def install_model(pack_id: str, request: Request):
        authenticated(request)
        loop = asyncio.get_running_loop()
        try:
            decision = pack_resource_decision(pack_id)
            if not decision.allowed:
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "code": decision.reason,
                        "message": "Este modelo excede el presupuesto total del producto.",
                    },
                )
            pack = await loop.run_in_executor(
                None, download_pack, installer, catalog, pack_id
            )
        except ModelOperationError as exc:
            logger.warning("Fallo de instalación de modelo: %s", exc.code)
            return JSONResponse(
                status_code=400,
                content={"ok": False, "code": exc.code, "message": exc.message},
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Definición de modelo inválida: %s", exc.__class__.__name__)
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "code": "MODEL_NOT_FOUND",
                    "message": "El modelo solicitado no existe en el catálogo.",
                },
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
        return {
            "ok": True,
            "id": pack.id,
            "version": pack.version,
            "active": pack.active,
        }

    @app.post("/v1/models/activate/{pack_id}/{version}")
    async def activate_model(pack_id: str, version: str, request: Request):
        authenticated(request)
        try:
            decision = pack_resource_decision(pack_id)
            if not decision.allowed:
                raise ModelOperationError(
                    decision.reason,
                    "El modelo supera el límite total de memoria o VRAM.",
                )
            installer.activate(pack_id, version)
        except (ModelOperationError, FileNotFoundError, KeyError) as exc:
            code = getattr(exc, "code", "MODEL_NOT_INSTALLED")
            message = getattr(exc, "message", "El modelo no está instalado.")
            return JSONResponse(
                status_code=409,
                content={"ok": False, "code": code, "message": message},
            )
        return {"ok": True, "id": pack_id, "version": version}

    @app.delete("/v1/models/{pack_id}/{version}")
    async def remove_model(pack_id: str, version: str, request: Request):
        authenticated(request)
        try:
            installer.remove(pack_id, version)
        except (RuntimeError, FileNotFoundError, OSError) as exc:
            logger.warning("No se pudo eliminar el pack: %s", exc.__class__.__name__)
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "code": "MODEL_REMOVE_FAILED",
                    "message": "No se pudo eliminar el pack local. Verifica que no esté activo.",
                },
            )
        return {"ok": True}

    @app.post("/v1/models/import")
    async def import_model(request: Request):
        authenticated(request)
        payload = await request.json()
        archive = Path(str(payload.get("path", ""))).expanduser()
        loop = asyncio.get_running_loop()
        try:
            pack = await loop.run_in_executor(None, installer.import_pack, archive)
        except (ModelOperationError, FileNotFoundError) as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "code": getattr(exc, "code", "MODEL_EXTERNAL_INVALID"),
                    "message": getattr(exc, "message", "No se pudo importar el pack."),
                },
            )
        return {
            "ok": True,
            "id": pack.id,
            "version": pack.version,
            "active": pack.active,
        }

    @app.post("/v1/models/select-auto")
    async def select_auto(request: Request):
        authenticated(request)
        payload = await request.json()
        route = str(payload.get("route", "en-es")).lower()
        allow_cloud = bool(payload.get("allowCloud", False))
        force = bool(payload.get("forceBenchmark", False))
        loop = asyncio.get_running_loop()
        try:
            selection, reports = await loop.run_in_executor(
                None,
                lambda: advisor.optimize(
                    route, allow_cloud=allow_cloud, force_benchmark=force
                ),
            )
        except Exception as exc:
            logger.warning("Selección automática falló: %s", exc.__class__.__name__)
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "code": "NO_COMPATIBLE_ENGINE",
                    "message": "No existe un modelo instalado que pase velocidad y memoria.",
                },
            )
        return {
            "ok": True,
            "selected": selection.candidate.id,
            "backend": selection.backend,
            "score": round(selection.score, 4),
            "rejected": selection.rejected,
            "benchmarks": reports,
        }

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
        translation_queue = CoalescingTranslationQueue(maxsize=TRANSLATION_QUEUE_MAX)
        asr_executor: ThreadPoolExecutor | None = None
        translation_executor: ThreadPoolExecutor | None = None
        audio_task: asyncio.Task | None = None
        translation_task: asyncio.Task | None = None
        loopback_source: WasapiLoopbackSource | None = None
        loopback_task: asyncio.Task | None = None
        send_lock = asyncio.Lock()
        latency_controller = LatencyController()
        last_telemetry_emit = 0.0
        last_speaker_event: str | None = None

        async def safe_send(payload: dict) -> None:
            async with send_lock:
                await websocket.send_json(payload)

        async def send_pipeline_events(items) -> None:
            nonlocal last_speaker_event
            for item in items:
                speaker_id = getattr(item, "speaker_id", None)
                if speaker_id and speaker_id != last_speaker_event:
                    last_speaker_event = speaker_id
                    await safe_send(event("speaker.changed", speakerId=speaker_id))
                await safe_send(event(item.type, **pipeline_event_fields(item)))

        def telemetry_snapshot(current: RealtimePipeline):
            queue_age_ms = translation_queue.oldest_age_seconds() * 1000.0
            snapshot = current.telemetry.snapshot(
                audio_queue_ms=audio_queue.qsize() * AUDIO_CHUNK_MS,
                translation_queue_depth=translation_queue.qsize(),
            )
            pressure = latency_controller.classify(
                snapshot.audio_queue_ms,
                snapshot.translation_queue_depth,
                snapshot.real_time_factor,
                translation_queue_age_ms=queue_age_ms,
            )
            current.set_resource_mode(pressure)
            return snapshot, pressure, queue_age_ms

        async def emit_realtime_status(current: RealtimePipeline) -> None:
            nonlocal last_telemetry_emit
            now = time.monotonic()
            if now - last_telemetry_emit < TELEMETRY_INTERVAL_SECONDS:
                return
            last_telemetry_emit = now
            level = current.audio_level
            snapshot, pressure, queue_age_ms = telemetry_snapshot(current)
            process_memory_mb = latency_controller.last_process_memory_mb
            memory_headroom_mb = max(
                0.0, governor.limits.hard_process_mb - process_memory_mb
            )
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
                    translationQueueDepth=translation_queue.qsize(),
                    translationQueueAgeMs=round(queue_age_ms, 1),
                    processMemoryMb=round(process_memory_mb, 1),
                    memoryHeadroomMb=round(memory_headroom_mb, 1),
                    pressure=pressure,
                    resourceMode=current.resource_mode,
                    cpuProfile=current.cpu_budget.profile,
                    physicalCores=current.cpu_budget.physical_cores,
                    asrThreads=current.cpu_budget.asr_threads,
                    translationThreads=current.cpu_budget.translation_threads,
                    parallelStages=current.cpu_budget.parallel_stages,
                )
            )

        async def queue_translation_requests(requests) -> None:
            current = pipeline
            for request in requests:
                if not request.final and current is not None:
                    _snapshot, pressure, _age = telemetry_snapshot(current)
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
                    _snapshot, pressure, _age = telemetry_snapshot(current)
                    current.segmenter.set_partial_decoding(
                        latency_controller.allow_partial_asr(pressure)
                    )
                    if pressure in {"catch_up", "rescue"}:
                        removed = await translation_queue.drop_partials()
                        if removed:
                            logger.debug(
                                "Parciales MT retirados para recuperar tiempo real: %s",
                                removed,
                            )
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
                if request is None:
                    return
                try:
                    current = pipeline
                    executor = translation_executor
                    if current is None or executor is None:
                        continue
                    if not current.cpu_budget.parallel_stages:
                        action = serial_translation_action(
                            request, audio_pending=not audio_queue.empty()
                        )
                        if action == "drop":
                            logger.debug(
                                "Parcial MT descartado para priorizar ASR en CPU serial."
                            )
                            continue
                        if action == "defer":
                            deadline = time.monotonic() + SERIAL_FINAL_DEFER_SECONDS
                            while not audio_queue.empty() and time.monotonic() < deadline:
                                await asyncio.sleep(SERIAL_DEFER_STEP_SECONDS)
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

        async def loopback_worker(source: WasapiLoopbackSource) -> None:
            loop = asyncio.get_running_loop()
            try:
                while True:
                    samples = await loop.run_in_executor(None, source.read_chunk)
                    await enqueue_audio(samples)
            except asyncio.CancelledError:
                raise
            except LoopbackError as exc:
                logger.warning("WASAPI loopback terminó: %s", exc.code)
                await safe_send(event("engine.error", code=exc.code, message=exc.message))
            except Exception as exc:
                logger.warning("WASAPI loopback terminó: %s", exc.__class__.__name__)
                await safe_send(
                    event(
                        "engine.error",
                        code="LOOPBACK_CAPTURE",
                        message="Se perdió la captura del audio reproducido por Windows.",
                    )
                )

        async def start_loopback() -> tuple[bool, str | None]:
            nonlocal loopback_source, loopback_task
            source = WasapiLoopbackSource()
            try:
                info = await asyncio.get_running_loop().run_in_executor(
                    None, source.open_default
                )
            except LoopbackError as exc:
                source.close()
                await safe_send(event("engine.error", code=exc.code, message=exc.message))
                return False, None
            loopback_source = source
            loopback_task = asyncio.create_task(
                loopback_worker(source), name="mily-wasapi-loopback"
            )
            return True, info.name

        async def stop_loopback() -> None:
            nonlocal loopback_source, loopback_task
            task, source = loopback_task, loopback_source
            loopback_task = None
            loopback_source = None
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if source is not None:
                await asyncio.get_running_loop().run_in_executor(None, source.close)

        async def start_workers() -> None:
            nonlocal audio_queue, translation_queue
            nonlocal asr_executor, translation_executor, audio_task, translation_task
            if pipeline is None:
                return
            audio_queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX)
            translation_queue = CoalescingTranslationQueue(
                maxsize=TRANSLATION_QUEUE_MAX,
                partial_ttl_seconds=0.75,
            )
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
            await stop_loopback()
            current = pipeline
            executor = asr_executor
            if audio_task is None and translation_task is None:
                if current is not None:
                    current.unload()
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
            await translation_queue.close()
            await asyncio.gather(
                *(task for task in (audio_task, translation_task) if task is not None),
                return_exceptions=True,
            )
            audio_task = None
            translation_task = None
            shutdown_executors(wait=True)
            if current is not None:
                current.unload()

        async def abort_workers() -> None:
            nonlocal audio_task, translation_task
            await stop_loopback()
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
            if pipeline is not None:
                pipeline.unload()

        try:
            await safe_send(event("engine.ready", version="2.0.1", protocolVersion=1))
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
                if message.type == "speaker.focus":
                    if pipeline is None:
                        await safe_send(
                            event(
                                "engine.error",
                                code="SESSION_NOT_STARTED",
                                message="Inicia una sesión antes de cambiar el hablante.",
                            )
                        )
                    else:
                        pipeline.set_speaker_focus(
                            message.speaker_focus_mode, message.speaker_id
                        )
                        await safe_send(
                            event(
                                "speaker.changed",
                                speakerId=message.speaker_id,
                                focusMode=message.speaker_focus_mode,
                            )
                        )
                    continue
                if message.type == "tts.started":
                    if pipeline is not None and message.tts_text:
                        pipeline.register_tts(message.tts_text)
                    await safe_send(event("tts.started", speakerId=message.speaker_id))
                    continue
                if message.type == "tts.finished":
                    await safe_send(event("tts.finished", speakerId=message.speaker_id))
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
                                message="Descarga el modelo Lite desde MilyVoiceTraductor.",
                            )
                        )
                        continue
                    try:
                        resource = pack_resource_decision(active.id)
                    except (KeyError, ValueError):
                        resource = None
                    if resource is None or not resource.allowed:
                        await safe_send(
                            event(
                                "engine.error",
                                code=(resource.reason if resource else "MODEL_CATALOG_INVALID"),
                                message="El modelo activo excede el presupuesto. Ejecuta Optimizar automáticamente.",
                            )
                        )
                        continue
                    selected_backend = catalog.active_backend()
                    session_compute_profile = (
                        selected_backend
                        if selected_backend != "auto"
                        else settings.compute_profile
                    )
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
                            backend=selected_backend,
                            phase="warming",
                        )
                    )
                    try:
                        pipeline = RealtimePipeline(
                            active,
                            message.source_language,
                            session_compute_profile,
                            recorder,
                            session_mode=message.session_mode,
                            speaker_detection=message.speaker_detection,
                            speaker_focus_mode=message.speaker_focus_mode,
                            fixed_speaker_id=message.speaker_id,
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
                    latency_controller = LatencyController()
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
                    _initial_snapshot, initial_pressure, _initial_age = telemetry_snapshot(
                        pipeline
                    )
                    if (
                        latency_controller.last_process_memory_mb
                        > governor.limits.hard_process_mb
                    ):
                        await finish_workers(flush=False)
                        pipeline = None
                        recorder = None
                        await safe_send(
                            event(
                                "engine.error",
                                code="PROCESS_MEMORY_LIMIT",
                                message="El modelo superó 2 GB al cargarse. Ejecuta Optimizar automáticamente.",
                            )
                        )
                        continue
                    pipeline.set_resource_mode(initial_pressure)
                    loopback_device = None
                    native_loopback = (
                        message.source_mode == "system_loopback"
                        and not message.external_pcm
                    )
                    if native_loopback:
                        loopback_ready, loopback_device = await start_loopback()
                        if not loopback_ready:
                            await finish_workers(flush=False)
                            pipeline = None
                            recorder = None
                            continue
                    last_telemetry_emit = 0.0
                    last_speaker_event = None
                    binary_pcm_enabled = message.binary_pcm
                    await safe_send(
                        event(
                            "session.started",
                            sessionId=session_id,
                            sessionMode=message.session_mode,
                            sourceMode=message.source_mode,
                            nativeLoopback=native_loopback,
                            loopbackDevice=loopback_device,
                            speakerDetection=pipeline.speaker_detection_enabled,
                            binaryPcm=binary_pcm_enabled,
                            parallelStages=pipeline.cpu_budget.parallel_stages,
                            pressure=initial_pressure,
                            processMemoryMb=round(
                                latency_controller.last_process_memory_mb, 1
                            ),
                            selectedBackend=selected_backend,
                            asrDevice=pipeline.compute_status["asrDevice"],
                            translationDevice=pipeline.compute_status[
                                "translationDevice"
                            ],
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
