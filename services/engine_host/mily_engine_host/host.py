"""Lightweight adapter lifecycle and health host for MilyVoice 3."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AdapterKind(StrEnum):
    ASR = "asr"
    MT = "mt"
    TTS = "tts"
    EXTERNAL = "external"


class AdapterStatus(StrEnum):
    REGISTERED = "registered"
    LOADING = "loading"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNLOADED = "unloaded"


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    id: str
    kind: AdapterKind
    title: str
    version: str
    contract: str

    def __post_init__(self) -> None:
        if not self.id or not self.title or not self.version or not self.contract:
            raise ValueError("El descriptor del adapter no puede tener campos vacíos")
        if not isinstance(self.kind, AdapterKind):
            raise ValueError("kind debe ser AdapterKind")


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    adapter_id: str
    status: AdapterStatus
    loaded: bool
    failures: int
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class EngineInvocation:
    request_id: str
    route: str
    frame: Any = field(default=None, repr=False, compare=False)
    metadata: Mapping[str, object] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.request_id or not self.route:
            raise ValueError("request_id y route son obligatorios")


@dataclass(frozen=True, slots=True)
class EngineHostSnapshot:
    loaded_adapters: int
    max_loaded_adapters: int
    adapters: tuple[AdapterHealth, ...]


class EngineHostError(RuntimeError):
    def __init__(self, code: str, message: str, *, adapter_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.adapter_id = adapter_id


@dataclass(slots=True)
class _RuntimeRecord:
    descriptor: AdapterDescriptor
    factory: Callable[[], object]
    instance: object | None = None
    status: AdapterStatus = AdapterStatus.REGISTERED
    failures: int = 0
    last_error: str | None = None


class EngineHost:
    """Own adapter lifecycle without owning provider selection/model policy."""

    def __init__(self, *, max_loaded_adapters: int = 2) -> None:
        if (
            not isinstance(max_loaded_adapters, int)
            or isinstance(max_loaded_adapters, bool)
            or max_loaded_adapters <= 0
        ):
            raise ValueError("max_loaded_adapters debe ser un entero positivo")
        self.max_loaded_adapters = max_loaded_adapters
        self._records: dict[str, _RuntimeRecord] = {}

    def register(
        self,
        descriptor: AdapterDescriptor,
        factory: Callable[[], object],
    ) -> None:
        if descriptor.id in self._records:
            raise EngineHostError(
                "ADAPTER_ALREADY_REGISTERED",
                f"El adapter {descriptor.id} ya está registrado",
                adapter_id=descriptor.id,
            )
        if not callable(factory):
            raise ValueError("factory debe ser callable")
        self._records[descriptor.id] = _RuntimeRecord(descriptor, factory)

    def descriptors(self) -> tuple[AdapterDescriptor, ...]:
        return tuple(record.descriptor for record in self._records.values())

    def _record(self, adapter_id: str) -> _RuntimeRecord:
        record = self._records.get(adapter_id)
        if record is None:
            raise EngineHostError(
                "ADAPTER_NOT_REGISTERED",
                f"Adapter no registrado: {adapter_id}",
                adapter_id=adapter_id,
            )
        return record

    @staticmethod
    def _health(record: _RuntimeRecord) -> AdapterHealth:
        return AdapterHealth(
            adapter_id=record.descriptor.id,
            status=record.status,
            loaded=record.instance is not None,
            failures=record.failures,
            last_error=record.last_error,
        )

    def health(self, adapter_id: str, *, refresh: bool = False) -> AdapterHealth:
        record = self._record(adapter_id)
        if refresh:
            self._refresh_health(record)
        return self._health(record)

    def _loaded_count(self) -> int:
        return sum(record.instance is not None for record in self._records.values())

    def snapshot(self, *, refresh_health: bool = False) -> EngineHostSnapshot:
        if refresh_health:
            for record in self._records.values():
                self._refresh_health(record)
        return EngineHostSnapshot(
            loaded_adapters=self._loaded_count(),
            max_loaded_adapters=self.max_loaded_adapters,
            adapters=tuple(self._health(record) for record in self._records.values()),
        )

    def load(
        self,
        adapter_id: str,
        config: Mapping[str, object] | None = None,
    ) -> AdapterHealth:
        record = self._record(adapter_id)
        if record.instance is not None:
            if record.status in {AdapterStatus.HEALTHY, AdapterStatus.DEGRADED}:
                return self._health(record)
            raise EngineHostError(
                "ADAPTER_UNHEALTHY",
                f"El adapter {adapter_id} requiere unload/reload explícito",
                adapter_id=adapter_id,
            )
        if self._loaded_count() >= self.max_loaded_adapters:
            raise EngineHostError(
                "HOST_CAPACITY",
                "Engine Host alcanzó su límite de adapters cargados",
                adapter_id=adapter_id,
            )

        record.status = AdapterStatus.LOADING
        record.last_error = None
        instance: object | None = None
        try:
            instance = record.factory()
            loader = getattr(instance, "load", None)
            if not callable(loader):
                raise TypeError("adapter no implementa load(config)")
            loader(dict(config or {}))
        except Exception as exc:
            if instance is not None:
                cleanup = getattr(instance, "unload", None)
                if callable(cleanup):
                    try:
                        cleanup()
                    except Exception:
                        pass
            record.instance = None
            record.status = AdapterStatus.UNHEALTHY
            record.failures += 1
            record.last_error = str(exc)
            raise EngineHostError(
                "ADAPTER_LOAD_FAILED",
                f"No se pudo cargar {adapter_id}: {exc}",
                adapter_id=adapter_id,
            ) from exc

        record.instance = instance
        record.status = AdapterStatus.HEALTHY
        record.last_error = None
        return self._health(record)

    def unload(self, adapter_id: str) -> AdapterHealth:
        record = self._record(adapter_id)
        if record.instance is None:
            record.status = AdapterStatus.UNLOADED
            record.last_error = None
            return self._health(record)

        unloader = getattr(record.instance, "unload", None)
        try:
            if not callable(unloader):
                raise TypeError("adapter no implementa unload()")
            unloader()
        except Exception as exc:
            record.status = AdapterStatus.UNHEALTHY
            record.failures += 1
            record.last_error = str(exc)
            raise EngineHostError(
                "ADAPTER_UNLOAD_FAILED",
                f"No se pudo descargar {adapter_id}: {exc}",
                adapter_id=adapter_id,
            ) from exc

        record.instance = None
        record.status = AdapterStatus.UNLOADED
        record.last_error = None
        return self._health(record)

    def invoke(self, adapter_id: str, request: EngineInvocation) -> object:
        record = self._record(adapter_id)
        if record.instance is None:
            raise EngineHostError(
                "ADAPTER_NOT_LOADED",
                f"Adapter no cargado: {adapter_id}",
                adapter_id=adapter_id,
            )
        if record.status is AdapterStatus.UNHEALTHY:
            raise EngineHostError(
                "ADAPTER_UNHEALTHY",
                f"Adapter no saludable: {adapter_id}",
                adapter_id=adapter_id,
            )

        invoker = getattr(record.instance, "invoke", None)
        try:
            if not callable(invoker):
                raise TypeError("adapter no implementa invoke(request)")
            return invoker(request)
        except Exception as exc:
            record.status = AdapterStatus.UNHEALTHY
            record.failures += 1
            record.last_error = str(exc)
            raise EngineHostError(
                "ADAPTER_INVOKE_FAILED",
                f"Falló la invocación de {adapter_id}: {exc}",
                adapter_id=adapter_id,
            ) from exc

    def _refresh_health(self, record: _RuntimeRecord) -> None:
        if record.instance is None or record.status is AdapterStatus.UNHEALTHY:
            return
        probe = getattr(record.instance, "health", None)
        if not callable(probe):
            record.status = AdapterStatus.HEALTHY
            return
        try:
            healthy = probe()
        except Exception as exc:
            record.status = AdapterStatus.DEGRADED
            record.failures += 1
            record.last_error = str(exc)
            return
        record.status = AdapterStatus.HEALTHY if healthy is not False else AdapterStatus.DEGRADED
        if record.status is AdapterStatus.HEALTHY:
            record.last_error = None
