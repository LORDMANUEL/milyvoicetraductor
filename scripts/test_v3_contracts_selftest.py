#!/usr/bin/env python3
"""Regression tests for domain-neutral and numeric Contracts Kernel behavior."""

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
                "required": ["backend", "rtf", "memoryMb"],
                "fields": {
                    "backend": {"type": "enum:Backend"},
                    "rtf": {"type": "number"},
                    "memoryMb": {"type": "integer"},
                    "note": {"type": "string", "nullable": True},
                },
            }
        },
        "enums": {"Backend": ["cpu", "cuda"]},
        "examples": {
            "observation": {
                "message": "BackendObservation",
                "path": "example.json",
            }
        },
    }


def synthetic_lock() -> dict:
    return {
        "contract": "compute/v1",
        "messages": {
            "BackendObservation": {
                "fields": {
                    "backend": {"type": "enum:Backend", "required": True},
                    "rtf": {"type": "number", "required": True},
                    "memoryMb": {"type": "integer", "required": True},
                    "note": {"type": "string", "nullable": True, "required": False},
                }
            }
        },
        "enums": {"Backend": ["cpu", "cuda"]},
    }


def expect_value_failure(value: dict) -> None:
    try:
        module.validate_message(value, "BackendObservation", synthetic_contract(), "probe")
    except module.ContractFailure:
        return
    raise AssertionError(f"invalid numeric fixture was accepted: {value!r}")


def main() -> int:
    contract = synthetic_contract()
    lock = synthetic_lock()
    module.validate_contract_descriptor(contract, "compute/v1", "compute")
    module.validate_compatibility(contract, lock)
    module.self_test_compatibility(contract, lock)

    module.validate_message(
        {"backend": "cpu", "rtf": 0.42, "memoryMb": 512},
        "BackendObservation",
        contract,
        "probe",
    )
    module.validate_message(
        {"backend": "cuda", "rtf": 1, "memoryMb": 1024, "note": None},
        "BackendObservation",
        contract,
        "probe",
    )

    expect_value_failure({"backend": "cpu", "rtf": "0.42", "memoryMb": 512})
    expect_value_failure({"backend": "cpu", "rtf": 0.42, "memoryMb": 512.5})
    expect_value_failure({"backend": "cpu", "rtf": True, "memoryMb": 512})

    print("V3 contracts generic/numeric self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
