"""Rutas y configuración del runtime del sidecar."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class RuntimePaths:
    data_dir: Path
    config_dir: Path
    cache_dir: Path
    models_dir: Path
    logs_dir: Path
    sessions_dir: Path

    @classmethod
    def discover(cls, overrides: dict[str, str | None] | None = None) -> "RuntimePaths":
        overrides = overrides or {}
        if os.name == "nt":
            local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            base = local / "MilyVoiceTraductor"
            config_base = base / "config"
        else:
            data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            base = data_home / "MilyVoiceTraductor"
            config_base = config_home / "MilyVoiceTraductor"
        data_dir = Path(overrides.get("data_dir") or base)
        config_dir = Path(overrides.get("config_dir") or config_base)
        cache_dir = Path(overrides.get("cache_dir") or (base / "cache"))
        models_dir = Path(overrides.get("models_dir") or (base / "models"))
        return cls(
            data_dir=data_dir,
            config_dir=config_dir,
            cache_dir=cache_dir,
            models_dir=models_dir,
            logs_dir=data_dir / "logs",
            sessions_dir=data_dir / "sessions",
        )

    def ensure(self) -> None:
        for path in (self.data_dir, self.config_dir, self.cache_dir, self.models_dir, self.logs_dir, self.sessions_dir):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class EngineSettings:
    source_language: str = "auto"
    target_language: str = "es"
    compute_profile: str = "auto"
    persist_transcripts: bool = False
    active_model_pack: str = "realtime-m2m100"
    log_level: str = "info"

    @classmethod
    def load(cls, config_dir: Path) -> "EngineSettings":
        path = config_dir / "engine.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls(
            source_language=data.get("sourceLanguage", "auto") if data.get("sourceLanguage") in {"auto", "en", "zh"} else "auto",
            target_language="es",
            compute_profile=data.get("computeProfile", "auto") if data.get("computeProfile") in {"auto", "cpu", "gpu"} else "auto",
            persist_transcripts=bool(data.get("persistTranscripts", False)),
            active_model_pack=str(data.get("activeModelPack", "realtime-m2m100")),
            log_level=data.get("logLevel", "info") if data.get("logLevel") in {"error", "warn", "info", "debug"} else "info",
        )


def parent_process_alive(pid: int | None) -> bool:
    """Comprueba si el proceso padre sigue vivo sin instalar psutil."""
    if not pid or pid <= 0:
        return True
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return bool(ok) and exit_code.value == STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
