#!/usr/bin/env python3
"""Validate MilyVoice 3 language-neutral contracts and compatibility locks."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
INDEX = CONTRACTS / "index.json"
CONTRACT_ID = re.compile(r"^(?P<name>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/v(?P<major>[1-9][0-9]*)$")
COMPONENT_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ALLOWED_STATUS = {"candidate", "certified", "frozen"}
ALLOWED_COMPATIBILITY = {"additive-within-major"}
PRIMITIVE_TYPES = {"string", "boolean", "number", "integer", "object"}


class ContractFailure(AssertionError):
    pass


def fail(message: str) -> None:
    raise ContractFailure(message)


def load_json(path: Path) -> Any:
    if not path.is_file():
        fail(f"missing required contract file: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def validate_field_type(
    field_name: str,
    spec: Any,
    messages: dict[str, Any],
    enums: dict[str, Any],
) -> None:
    if not isinstance(spec, dict):
        fail(f"field {field_name} definition must be an object")
    field_type = spec.get("type")
    if not isinstance(field_type, str):
        fail(f"field {field_name} must declare string type")
    if "nullable" in spec and not isinstance(spec["nullable"], bool):
        fail(f"field {field_name} nullable must be boolean")

    if field_type in PRIMITIVE_TYPES:
        if field_type == "object":
            target = spec.get("message")
            if not isinstance(target, str) or target not in messages:
                fail(f"field {field_name} object must reference an existing message")
        elif "message" in spec:
            fail(f"field {field_name} uses message reference with non-object type")
        return

    if field_type.startswith("array:"):
        target = field_type.split(":", 1)[1]
        if not target or target not in messages:
            fail(f"field {field_name} references unknown array message {target!r}")
        return

    if field_type.startswith("enum:"):
        target = field_type.split(":", 1)[1]
        if not target or target not in enums:
            fail(f"field {field_name} references unknown enum {target!r}")
        return

    fail(f"field {field_name} has unsupported type {field_type!r}")


def validate_contract_descriptor(contract: Any, expected_id: str, expected_owner: str) -> None:
    if not isinstance(contract, dict):
        fail(f"contract {expected_id} must be an object")
    if contract.get("id") != expected_id:
        fail(f"contract id mismatch: expected {expected_id}, got {contract.get('id')!r}")
    if contract.get("owner") != expected_owner:
        fail(f"contract owner mismatch for {expected_id}")
    if contract.get("status") not in ALLOWED_STATUS:
        fail(f"invalid status for {expected_id}: {contract.get('status')!r}")
    if contract.get("encoding") != "json":
        fail(f"{expected_id} must use json encoding in Contracts Kernel v1")
    if contract.get("compatibility") not in ALLOWED_COMPATIBILITY:
        fail(f"invalid compatibility mode for {expected_id}")

    messages = contract.get("messages")
    enums = contract.get("enums")
    if not isinstance(messages, dict) or not messages:
        fail(f"{expected_id} must define messages")
    if not isinstance(enums, dict):
        fail(f"{expected_id} enums must be an object")

    for enum_name, values in enums.items():
        if not isinstance(enum_name, str) or not enum_name:
            fail(f"invalid enum name in {expected_id}")
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value for value in values)
        ):
            fail(f"enum {enum_name} must contain non-empty string values")
        if len(values) != len(set(values)):
            fail(f"enum {enum_name} contains duplicate values")

    for message_name, message in messages.items():
        if not isinstance(message_name, str) or not message_name:
            fail(f"invalid message name in {expected_id}")
        if not isinstance(message, dict):
            fail(f"message {message_name} must be an object")
        fields = message.get("fields")
        required = message.get("required")
        if not isinstance(fields, dict) or not fields:
            fail(f"message {message_name} must define fields")
        if not isinstance(required, list) or any(
            not isinstance(item, str) for item in required
        ):
            fail(f"message {message_name} required must be a string list")
        if len(required) != len(set(required)):
            fail(f"message {message_name} contains duplicate required fields")
        missing = [item for item in required if item not in fields]
        if missing:
            fail(f"message {message_name} requires undefined fields: {missing}")
        for field_name, spec in fields.items():
            if not isinstance(field_name, str) or not field_name:
                fail(f"message {message_name} contains invalid field name")
            validate_field_type(f"{message_name}.{field_name}", spec, messages, enums)


def validate_compatibility(contract: dict[str, Any], lock: Any) -> None:
    if not isinstance(lock, dict):
        fail("compatibility lock must be an object")
    if lock.get("contract") != contract.get("id"):
        fail("compatibility lock contract id mismatch")

    contract_messages = contract["messages"]
    locked_messages = lock.get("messages")
    if not isinstance(locked_messages, dict) or not locked_messages:
        fail("compatibility lock must contain messages")

    for message_name, locked_message in locked_messages.items():
        current = contract_messages.get(message_name)
        if not isinstance(current, dict):
            fail(f"breaking change: locked message removed: {message_name}")
        locked_fields = locked_message.get("fields")
        if not isinstance(locked_fields, dict):
            fail(f"lock for {message_name} must define fields")
        current_fields = current["fields"]
        current_required = set(current["required"])

        for field_name, locked_spec in locked_fields.items():
            current_spec = current_fields.get(field_name)
            if current_spec is None:
                fail(f"breaking change: removed locked field {message_name}.{field_name}")
            if not isinstance(locked_spec, dict):
                fail(f"invalid lock definition for {message_name}.{field_name}")
            expected_type = locked_spec.get("type")
            expected_nullable = bool(locked_spec.get("nullable", False))
            expected_required = locked_spec.get("required")
            if current_spec.get("type") != expected_type:
                fail(f"breaking change: type changed for {message_name}.{field_name}")
            if bool(current_spec.get("nullable", False)) != expected_nullable:
                fail(f"breaking change: nullability changed for {message_name}.{field_name}")
            if (field_name in current_required) != expected_required:
                fail(f"breaking change: requiredness changed for {message_name}.{field_name}")

            expected_message = locked_spec.get("message")
            if expected_message is not None and current_spec.get("message") != expected_message:
                fail(
                    f"breaking change: object target changed for "
                    f"{message_name}.{field_name}"
                )

        locked_field_names = set(locked_fields)
        new_required = current_required - locked_field_names
        if new_required:
            fail(
                f"breaking change: new required fields in {message_name}: "
                f"{sorted(new_required)}"
            )

    contract_enums = contract["enums"]
    locked_enums = lock.get("enums")
    if not isinstance(locked_enums, dict):
        fail("compatibility lock enums must be an object")
    for enum_name, locked_values in locked_enums.items():
        current_values = contract_enums.get(enum_name)
        if not isinstance(current_values, list):
            fail(f"breaking change: locked enum removed: {enum_name}")
        missing_values = [value for value in locked_values if value not in current_values]
        if missing_values:
            fail(f"breaking change: enum values removed from {enum_name}: {missing_values}")


def validate_value(
    value: Any,
    spec: dict[str, Any],
    contract: dict[str, Any],
    path: str,
) -> None:
    if value is None:
        if spec.get("nullable") is True:
            return
        fail(f"{path} cannot be null")

    field_type = spec["type"]
    if field_type == "string":
        if not isinstance(value, str):
            fail(f"{path} must be a string")
        return
    if field_type == "boolean":
        if not isinstance(value, bool):
            fail(f"{path} must be a boolean")
        return
    if field_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail(f"{path} must be a number")
        return
    if field_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            fail(f"{path} must be an integer")
        return
    if field_type == "object":
        if not isinstance(value, dict):
            fail(f"{path} must be an object")
        validate_message(value, spec["message"], contract, path)
        return
    if field_type.startswith("array:"):
        if not isinstance(value, list):
            fail(f"{path} must be an array")
        target = field_type.split(":", 1)[1]
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                fail(f"{path}[{index}] must be an object")
            validate_message(item, target, contract, f"{path}[{index}]")
        return
    if field_type.startswith("enum:"):
        enum_name = field_type.split(":", 1)[1]
        if value not in contract["enums"][enum_name]:
            fail(f"{path} has invalid {enum_name} value: {value!r}")
        return
    fail(f"{path} has unsupported type {field_type}")


def validate_message(
    value: Any,
    message_name: str,
    contract: dict[str, Any],
    path: str,
) -> None:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    message = contract["messages"].get(message_name)
    if not isinstance(message, dict):
        fail(f"unknown message {message_name}")
    fields = message["fields"]
    for field_name in message["required"]:
        if field_name not in value:
            fail(f"{path} missing required field {field_name}")
    unknown = set(value) - set(fields)
    if unknown:
        fail(f"{path} contains fields outside contract: {sorted(unknown)}")
    for field_name, field_value in value.items():
        validate_value(field_value, fields[field_name], contract, f"{path}.{field_name}")


def validate_examples(contract_path: Path, contract: dict[str, Any]) -> None:
    examples = contract.get("examples")
    if not isinstance(examples, dict) or not examples:
        fail(f"{contract['id']} must declare examples")
    for example_name, descriptor in examples.items():
        if not isinstance(descriptor, dict):
            fail(f"example {example_name} descriptor must be an object")
        message = descriptor.get("message")
        relative_path = descriptor.get("path")
        if not isinstance(message, str) or message not in contract["messages"]:
            fail(f"example {example_name} references unknown message")
        if not isinstance(relative_path, str) or not relative_path:
            fail(f"example {example_name} path must be a string")
        fixture_path = contract_path.parent / relative_path
        fixture = load_json(fixture_path)
        validate_message(fixture, message, contract, example_name)


def first_locked_field(lock: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    for message_name, message in lock.get("messages", {}).items():
        fields = message.get("fields", {}) if isinstance(message, dict) else {}
        for field_name, spec in fields.items():
            if isinstance(spec, dict):
                return message_name, field_name, spec
    fail("validator self-test requires at least one locked field")


def self_test_compatibility(contract: dict[str, Any], lock: dict[str, Any]) -> None:
    """Probe the compatibility checker without assuming any domain names."""
    base = copy.deepcopy(contract)
    validate_compatibility(base, lock)

    message_name, field_name, locked_spec = first_locked_field(lock)

    removed = copy.deepcopy(base)
    removed["messages"][message_name]["fields"].pop(field_name)
    expect_compatibility_failure(removed, lock, "field removal")

    changed_type = copy.deepcopy(base)
    current_type = changed_type["messages"][message_name]["fields"][field_name]["type"]
    changed_type["messages"][message_name]["fields"][field_name]["type"] = (
        "boolean" if current_type != "boolean" else "string"
    )
    expect_compatibility_failure(changed_type, lock, "type change")

    required_added = copy.deepcopy(base)
    required_added["messages"][message_name]["fields"]["compatRequiredProbe"] = {
        "type": "string"
    }
    required_added["messages"][message_name]["required"].append("compatRequiredProbe")
    expect_compatibility_failure(required_added, lock, "new required field")

    optional_added = copy.deepcopy(base)
    optional_added["messages"][message_name]["fields"]["compatOptionalProbe"] = {
        "type": "string",
        "nullable": True,
    }
    validate_contract_descriptor(optional_added, base["id"], base["owner"])
    validate_compatibility(optional_added, lock)

    locked_enums = lock.get("enums", {})
    if not isinstance(locked_enums, dict):
        fail("compatibility lock enums must be an object")
    for enum_name, values in locked_enums.items():
        if isinstance(values, list) and values:
            enum_removed = copy.deepcopy(base)
            enum_removed["enums"][enum_name].remove(values[0])
            expect_compatibility_failure(enum_removed, lock, "enum removal")
            break

    if locked_spec.get("type") == "object" and locked_spec.get("message") is not None:
        available_messages = [
            name for name in base["messages"] if name != locked_spec["message"]
        ]
        if available_messages:
            object_target_changed = copy.deepcopy(base)
            object_target_changed["messages"][message_name]["fields"][field_name]["message"] = (
                available_messages[0]
            )
            expect_compatibility_failure(
                object_target_changed,
                lock,
                "object message target change",
            )


def expect_compatibility_failure(
    contract: dict[str, Any],
    lock: dict[str, Any],
    label: str,
) -> None:
    try:
        validate_compatibility(contract, lock)
    except ContractFailure:
        return
    fail(f"validator self-test failed: {label} was incorrectly accepted")


def main() -> int:
    registry = load_json(INDEX)
    if not isinstance(registry, dict) or registry.get("schemaVersion") != 1:
        fail("contracts/index.json must declare schemaVersion 1")
    entries = registry.get("contracts")
    if not isinstance(entries, list) or not entries:
        fail("contracts registry must contain at least one contract")

    ids: set[str] = set()
    paths: set[str] = set()
    supervisor_seen = False

    for entry in entries:
        if not isinstance(entry, dict):
            fail("contract registry entries must be objects")
        contract_id = entry.get("id")
        owner = entry.get("owner")
        status = entry.get("status")
        relative_path = entry.get("path")

        if not isinstance(contract_id, str) or not CONTRACT_ID.fullmatch(contract_id):
            fail(f"invalid registry contract id: {contract_id!r}")
        if contract_id in ids:
            fail(f"duplicate registry contract id: {contract_id}")
        ids.add(contract_id)
        if not isinstance(owner, str) or not COMPONENT_ID.fullmatch(owner):
            fail(f"invalid contract owner for {contract_id}: {owner!r}")
        if status not in ALLOWED_STATUS:
            fail(f"invalid registry status for {contract_id}: {status!r}")
        if not isinstance(relative_path, str) or relative_path in paths:
            fail(f"invalid or duplicate contract path for {contract_id}: {relative_path!r}")
        paths.add(relative_path)

        match = CONTRACT_ID.fullmatch(contract_id)
        assert match is not None
        expected_path = f"{match.group('name')}/v{match.group('major')}/contract.json"
        if relative_path != expected_path:
            fail(f"registry path/id mismatch for {contract_id}: expected {expected_path}")

        contract_path = CONTRACTS / relative_path
        contract = load_json(contract_path)
        validate_contract_descriptor(contract, contract_id, owner)
        if contract.get("status") != status:
            fail(f"registry/descriptor status mismatch for {contract_id}")

        lock_path = contract_path.parent / "compatibility.lock.json"
        lock = load_json(lock_path)
        validate_compatibility(contract, lock)
        validate_examples(contract_path, contract)
        self_test_compatibility(contract, lock)

        if contract_id == "supervisor/v1":
            supervisor_seen = True

    if not supervisor_seen:
        fail("Contracts Kernel F2 requires supervisor/v1")

    print(f"V3 contracts kernel: PASS ({len(entries)} contract(s))")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractFailure as exc:
        print(f"V3 contracts kernel: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
