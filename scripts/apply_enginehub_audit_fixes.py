#!/usr/bin/env python3
"""Parche de una sola ejecución para cerrar hallazgos de la auditoría Engine Hub."""
from pathlib import Path


def replace_once(path_name: str, old: str, new: str) -> None:
    path = Path(path_name)
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch marker not found in {path_name}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    replace_once(
        "services/ai/mily_ai/engine_benchmark.py",
        "    peak_engine_working_set = max(current, peak)\n    try:\n",
        "    peak_engine_working_set = max(current, peak)\n"
        "    asr_backend = \"\"\n"
        "    translation_backend = \"\"\n"
        "    try:\n",
    )
    replace_once(
        "services/ai/mily_ai/engine_benchmark.py",
        "            asr_ms.append(asr_elapsed)\n"
        "            mt_ms.append(mt_elapsed)\n"
        "            e2e_ms.append(asr_elapsed + mt_elapsed)\n"
        "    except Exception as exc:\n",
        "            asr_ms.append(asr_elapsed)\n"
        "            mt_ms.append(mt_elapsed)\n"
        "            e2e_ms.append(asr_elapsed + mt_elapsed)\n\n"
        "        default_asr = \"cpu\" if requested_backend == \"cpu\" else \"unknown\"\n"
        "        default_mt = \"cpu\" if requested_backend != \"cuda\" else \"unknown\"\n"
        "        asr_backend = _provider_device(asr, default_asr)\n"
        "        translation_backend = _provider_device(translator, default_mt)\n"
        "    except Exception as exc:\n",
    )
    replace_once(
        "services/ai/mily_ai/engine_benchmark.py",
        "    default_asr = \"cloud\" if requested_backend == \"cloud\" else \"cpu\"\n"
        "    default_mt = \"cuda\" if requested_backend == \"cuda\" else \"cpu\"\n"
        "    asr_backend = _provider_device(asr, default_asr)\n"
        "    translation_backend = _provider_device(translator, default_mt)\n"
        "    verified = _backend_verified(\n",
        "    if not asr_backend:\n"
        "        asr_backend = \"unknown\"\n"
        "    if not translation_backend:\n"
        "        translation_backend = \"unknown\"\n"
        "    verified = _backend_verified(\n",
    )
    replace_once(
        "services/ai/mily_ai/engine_benchmark.py",
        '        "totalProductWorkingSetMb": round(total_product_working_set, 1),\n'
        '        "productMemoryMode": product_decision.mode,\n',
        '        "totalProductWorkingSetMb": round(total_product_working_set, 1),\n'
        '        "totalProductIncludesSharedGpu": True,\n'
        '        "productMemoryMode": product_decision.mode,\n',
    )

    replace_once(
        "services/ai/mily_ai/engine_registry.py",
        "            float(candidate.total_product_mb) + float(candidate.shared_gpu_mb)\n"
        "            if candidate.total_product_mb > 0\n",
        "            float(candidate.total_product_mb)\n"
        "            if candidate.total_product_mb > 0\n",
    )
    replace_once(
        "services/ai/mily_ai/engine_registry.py",
        "                    RuntimeFootprint(\n"
        "                        process_mb=candidate.total_product_mb,\n"
        "                        shared_gpu_mb=candidate.shared_gpu_mb,\n"
        "                        dedicated_vram_mb=candidate.vram_mb,\n"
        "                    )\n",
        "                    RuntimeFootprint(\n"
        "                        process_mb=candidate.total_product_mb,\n"
        "                        dedicated_vram_mb=candidate.vram_mb,\n"
        "                    )\n",
    )

    models = Path("services/ai/mily_ai/models.py")
    text = models.read_text(encoding="utf-8")
    old_state = '''    def _state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"schemaVersion": 2, "active": None, "previous": None}
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schemaVersion": 2, "active": None, "previous": None}
        return state
'''
    new_state = '''    @staticmethod
    def _normalize_backend(value: object) -> str:
        backend = str(value or "auto").strip().lower()
        if backend == "gpu":
            backend = "cuda"
        allowed = {
            "auto", "cpu", "cuda", "vulkan", "openvino",
            "directml", "windowsml", "cloud",
        }
        return backend if backend in allowed else "auto"

    @classmethod
    def _empty_state(cls) -> dict[str, Any]:
        return {
            "schemaVersion": 2,
            "active": None,
            "backend": "auto",
            "previous": None,
            "previousBackend": "auto",
        }

    def _state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty_state()
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_state()
        if not isinstance(state, dict):
            return self._empty_state()
        normalized = self._empty_state()
        normalized.update(state)
        normalized["backend"] = self._normalize_backend(normalized.get("backend"))
        normalized["previousBackend"] = self._normalize_backend(
            normalized.get("previousBackend")
        )
        return normalized

    def active_backend(self) -> str:
        return self._normalize_backend(self._state().get("backend"))
'''
    if new_state not in text:
        if old_state not in text:
            raise SystemExit("ModelCatalog state block not found")
        text = text.replace(old_state, new_state, 1)

    old_activate = '''    def activate(self, pack_id: str, version: str) -> None:
        pack_dir = self.catalog.packs_dir / pack_id / version
        if not (pack_dir / "pack.json").exists():
            raise FileNotFoundError("Pack no instalado")
        self.catalog.models_dir.mkdir(parents=True, exist_ok=True)
        state = self.catalog._state()
        new_ref = f"{pack_id}@{version}"
        previous = (
            state.get("active")
            if state.get("active") != new_ref
            else state.get("previous")
        )
        temp = self.catalog.state_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                {"schemaVersion": 2, "active": new_ref, "previous": previous},
                indent=2,
            ),
            encoding="utf-8",
        )
        temp.replace(self.catalog.state_path)

    def rollback(self) -> InstalledPack:
        state = self.catalog._state()
        previous = state.get("previous")
        if not previous or "@" not in previous:
            raise RuntimeError("No existe un pack anterior para rollback")
        pack_id, version = previous.rsplit("@", 1)
        current = state.get("active")
        self.activate(pack_id, version)
        new_state = self.catalog._state()
        new_state["previous"] = current
        self.catalog.state_path.write_text(
            json.dumps(new_state, indent=2), encoding="utf-8"
        )
        return self.catalog.active_pack()  # type: ignore[return-value]
'''
    new_activate = '''    def activate(
        self, pack_id: str, version: str, backend: str = "auto"
    ) -> None:
        self.activate_selection(pack_id, version, backend)

    def activate_selection(
        self, pack_id: str, version: str, backend: str
    ) -> None:
        pack_dir = self.catalog.packs_dir / pack_id / version
        if not (pack_dir / "pack.json").exists():
            raise FileNotFoundError("Pack no instalado")
        self.catalog.models_dir.mkdir(parents=True, exist_ok=True)
        state = self.catalog._state()
        new_ref = f"{pack_id}@{version}"
        current_ref = state.get("active")
        current_backend = self.catalog._normalize_backend(state.get("backend"))
        if current_ref != new_ref:
            previous = current_ref
            previous_backend = current_backend
        else:
            previous = state.get("previous")
            previous_backend = self.catalog._normalize_backend(
                state.get("previousBackend")
            )
        payload = {
            "schemaVersion": 2,
            "active": new_ref,
            "backend": self.catalog._normalize_backend(backend),
            "previous": previous,
            "previousBackend": previous_backend,
        }
        temp = self.catalog.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self.catalog.state_path)

    def rollback(self) -> InstalledPack:
        state = self.catalog._state()
        previous = state.get("previous")
        if not previous or "@" not in previous:
            raise RuntimeError("No existe un pack anterior para rollback")
        pack_id, version = previous.rsplit("@", 1)
        current = state.get("active")
        current_backend = self.catalog.active_backend()
        previous_backend = self.catalog._normalize_backend(
            state.get("previousBackend")
        )
        self.activate_selection(pack_id, version, previous_backend)
        new_state = self.catalog._state()
        new_state["previous"] = current
        new_state["previousBackend"] = current_backend
        temp = self.catalog.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
        temp.replace(self.catalog.state_path)
        return self.catalog.active_pack()  # type: ignore[return-value]
'''
    if new_activate not in text:
        if old_activate not in text:
            raise SystemExit("Model activation block not found")
        text = text.replace(old_activate, new_activate, 1)
    models.write_text(text, encoding="utf-8")

    replace_once(
        "services/ai/mily_ai/cli.py",
        '''        if args.model_action == "install":
            if args.download_only:
                pack = download_pack(installer, catalog, args.pack_id)
            else:
                definition = catalog.definition(args.pack_id)
                resource = _definition_resource(definition)
                if not resource["allowed"]:
                    raise ModelOperationError(
                        str(resource["reason"]),
                        "El modelo supera el límite total de 2 GB o 384 MB de VRAM.",
                    )
                pack = installer.install(args.pack_id)
            _emit_pack(pack)
            return 0
''',
        '''        if args.model_action == "install":
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
''',
    )

    server = Path("services/ai/mily_ai/server.py")
    text = server.read_text(encoding="utf-8")
    if "from .model_operations import download_pack\n" not in text:
        text = text.replace(
            "from .model_advisor import ModelAdvisor\n",
            "from .model_advisor import ModelAdvisor\n"
            "from .model_operations import download_pack\n",
            1,
        )
    text = text.replace(
        "            pack = await loop.run_in_executor(None, installer.install, pack_id)\n",
        "            pack = await loop.run_in_executor(\n"
        "                None, download_pack, installer, catalog, pack_id\n"
        "            )\n",
        1,
    )
    text = text.replace(
        '            "modelPack": f"{active.id}@{active.version}" if active else None,\n'
        '            "resourceLimits": resource_limits_payload(),\n',
        '            "modelPack": f"{active.id}@{active.version}" if active else None,\n'
        '            "backend": catalog.active_backend(),\n'
        '            "resourceLimits": resource_limits_payload(),\n',
        1,
    )
    text = text.replace(
        '            "backends": sorted(inventory.backends),\n'
        '            "limits": resource_limits_payload(),\n',
        '            "backends": sorted(inventory.backends),\n'
        '            "activeBackend": catalog.active_backend(),\n'
        '            "limits": resource_limits_payload(),\n',
        1,
    )
    hello = '''                    if resource is None or not resource.allowed:
                        await safe_send(
                            event(
                                "engine.error",
                                code=(resource.reason if resource else "MODEL_CATALOG_INVALID"),
                                message="El modelo activo excede el presupuesto. Ejecuta Optimizar automáticamente.",
                            )
                        )
                        continue
                    recorder = SessionRecorder(
'''
    hello_new = '''                    if resource is None or not resource.allowed:
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
'''
    if "session_compute_profile = (" not in text:
        if hello not in text:
            raise SystemExit("Server session backend insertion point not found")
        text = text.replace(hello, hello_new, 1)
    text = text.replace(
        '                            modelPack=f"{active.id}@{active.version}",\n'
        '                            phase="warming",\n',
        '                            modelPack=f"{active.id}@{active.version}",\n'
        '                            backend=selected_backend,\n'
        '                            phase="warming",\n',
        1,
    )
    text = text.replace(
        "                            message.source_language,\n"
        "                            settings.compute_profile,\n"
        "                            recorder,\n",
        "                            message.source_language,\n"
        "                            session_compute_profile,\n"
        "                            recorder,\n",
        1,
    )
    text = text.replace(
        "                            processMemoryMb=round(\n"
        "                                latency_controller.last_process_memory_mb, 1\n"
        "                            ),\n",
        "                            processMemoryMb=round(\n"
        "                                latency_controller.last_process_memory_mb, 1\n"
        "                            ),\n"
        "                            selectedBackend=selected_backend,\n"
        '                            asrDevice=pipeline.compute_status["asrDevice"],\n'
        '                            translationDevice=pipeline.compute_status[\n'
        '                                "translationDevice"\n'
        "                            ],\n",
        1,
    )
    server.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
