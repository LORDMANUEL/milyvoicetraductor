from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODELS_PAGE = ROOT / "apps/desktop/src/pages/Models.svelte"


class StableModelManagerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODELS_PAGE.read_text(encoding="utf-8")

    def _function_block(self, function_name: str) -> str:
        start = self.source.index(f"async function {function_name}")
        next_function = self.source.find("\n  async function ", start + 1)
        return self.source[start : next_function if next_function != -1 else len(self.source)]

    def test_install_button_serializes_operations_but_allows_repair_of_active_corrupt_pack(self) -> None:
        self.assertIn(
            "disabled={Boolean(busy) || (pack.active && lastFailedPack !== pack.id)}",
            self.source,
            "Una operación debe bloquear las demás, pero un pack activo que falló SHA debe poder reinstalarse.",
        )

    def test_verify_failure_marks_pack_as_repairable_hash_mismatch(self) -> None:
        block = self._function_block("verify")
        self.assertIn("lastErrorCode = 'MODEL_HASH_MISMATCH';", block)
        self.assertIn("lastFailedPack = pack.id;", block)
        self.assertIn("if (ok)", block)

    def test_every_operation_clears_previous_public_error_before_starting(self) -> None:
        for function_name in ("install", "verify", "remove", "rollback"):
            block = self._function_block(function_name)
            self.assertIn(
                "lastErrorCode = '';",
                block,
                f"{function_name} debe limpiar el error anterior antes de reportar un nuevo estado.",
            )

    def test_catalog_load_has_visible_error_recovery(self) -> None:
        start = self.source.index("async function load()")
        end = self.source.index("\n  async function install", start)
        block = self.source[start:end]
        self.assertIn("try {", block)
        self.assertIn("catch", block)
        self.assertIn("lastErrorCode", block)
        self.assertIn("modelErrorMessage", block)

    def test_busy_model_operation_error_survives_all_public_layers(self) -> None:
        rust = (ROOT / "crates/mily-models/src/lib.rs").read_text(encoding="utf-8")
        frontend_errors = (ROOT / "apps/desktop/src/lib/modelErrors.ts").read_text(encoding="utf-8")
        self.assertIn('"MODEL_OPERATION_BUSY"', rust)
        self.assertIn("MODEL_OPERATION_BUSY:", frontend_errors)
        self.assertIn("otra operación", frontend_errors.lower())


if __name__ == "__main__":
    unittest.main()
