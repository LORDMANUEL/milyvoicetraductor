#!/usr/bin/env python3
"""Regression test: Contracts Kernel self-tests must be domain-neutral."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "test_v3_contracts.py"
SPEC = importlib.util.spec_from_file_location("v3_contracts", VALIDATOR)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def synthetic_contract() -> dict:
    return {
        "id": "compute/v1",
        "owner": "compute",
        "status": "candidate",
        "encoding": "json",
        "compatibility": "additive-within-major",
        "messages": {
            "BackendObservation": {
                "required": ["backend", "rtf"],
                "fields": {
                    "backend": {"type": "enum:Backend"},
                    "rtf": {"type": "string"},
                    "note": {"type": "string", "nullable": True},
                },
            }
        },
        "enums": {"Backend": ["cpu", "cuda"]},
        "examples": {"observation": {"message": "BackendObservation", "path": "example.json"}},
    }


def synthetic_lock() -> dict:
    return {
        "contract": "compute/v1",
        "messages": {
            "BackendObservation": {
                "fields": {
                    "backend": {"type": "enum:Backend", "required": True},
                    "rtf": {"type": "string", "required": True},
                    "note": {"type": "string", "nullable": True, "required": False},
                }
            }
        },
        "enums": {"Backend": ["cpu", "cuda"]},
    }


def main() -> int:
    contract = synthetic_contract()
    lock = synthetic_lock()
    module.validate_contract_descriptor(contract, "compute/v1", "compute")
    module.validate_compatibility(contract, lock)
    module.self_test_compatibility(contract, lock)
    print("V3 contracts generic self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
