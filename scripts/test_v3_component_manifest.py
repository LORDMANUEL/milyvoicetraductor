#!/usr/bin/env python3
"""Contract check for the MilyVoice 3 component composition manifest."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests" / "milyvoice-3.components.json"
COMPONENT_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
CONTRACT = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*/v[1-9][0-9]*$")


def fail(message: str) -> None:
    raise AssertionError(message)


def expected_components() -> dict[str, dict[str, object]]:
    return {
        "supervisor": {
            "id": "supervisor",
            "version": "1.0.0",
            "contract": "supervisor/v1",
            "stage": "candidate",
            "required": True,
        },
        "compute": {
            "id": "compute",
            "version": "2.0.0",
            "contract": "compute/v1",
            "stage": "certified",
            "required": True,
        },
        "audio": {
            "id": "audio",
            "version": "1.0.0",
            "contract": "audio/v1",
            "stage": "candidate",
            "required": True,
        },
        "realtime": {
            "id": "realtime",
            "version": "1.0.0",
            "contract": "realtime/v1",
            "stage": "candidate",
            "required": True,
        },
        "engine-host": {
            "id": "engine-host",
            "version": "1.0.0",
            "contract": "engine/v1",
            "stage": "candidate",
            "required": True,
        },
        "asr": {
            "id": "asr",
            "version": "1.0.0",
            "contract": "asr/v1",
            "stage": "candidate",
            "required": True,
        },
        "linguistic": {
            "id": "linguistic",
            "version": "1.0.0",
            "contract": "linguistic/v1",
            "stage": "candidate",
            "required": True,
        },
        "mt": {
            "id": "mt",
            "version": "1.0.0",
            "contract": "mt/v1",
            "stage": "candidate",
            "required": True,
        },
    }


def main() -> int:
    if not MANIFEST.is_file():
        fail(f"missing V3 component manifest: {MANIFEST.relative_to(ROOT)}")

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    product = payload.get("product")
    if product != {"name": "MilyVoiceTraductor", "version": "3.0.0-alpha.4-dev.3"}:
        fail(f"unexpected product descriptor: {product!r}")

    components = payload.get("components")
    if not isinstance(components, list) or not components:
        fail("components must be a non-empty list")

    ids: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            fail("every component entry must be an object")
        component_id = component.get("id")
        version = component.get("version")
        contract = component.get("contract")
        stage = component.get("stage")
        required = component.get("required")

        if not isinstance(component_id, str) or component_id in ids:
            fail(f"invalid or duplicate component id: {component_id!r}")
        ids.add(component_id)
        if not COMPONENT_VERSION.fullmatch(str(version)):
            fail(f"invalid component version for {component_id}: {version!r}")
        if not CONTRACT.fullmatch(str(contract)):
            fail(f"invalid component contract for {component_id}: {contract!r}")
        if stage not in {"experimental", "development", "candidate", "certified", "frozen"}:
            fail(f"invalid component stage for {component_id}: {stage!r}")
        if not isinstance(required, bool):
            fail(f"required must be boolean for {component_id}")

    expected = expected_components()
    if ids != set(expected):
        fail(f"unexpected V3 component ids: {sorted(ids)}; expected {sorted(expected)}")

    by_id = {component["id"]: component for component in components}
    for component_id, descriptor in expected.items():
        if by_id.get(component_id) != descriptor:
            fail(f"unexpected {component_id} descriptor: {by_id.get(component_id)!r}")

    print("V3 component manifest contract: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, json.JSONDecodeError) as exc:
        print(f"V3 component manifest contract: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
