from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODELS_PAGE = ROOT / "apps/desktop/src/pages/Models.svelte"


class StableModelManagerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODELS_PAGE.read_text(encoding="utf-8")

    def test_install_button_is_disabled_while_any_model_operation_is_running(self) -> None:
        self.assertIn(
            "disabled={pack.active || Boolean(busy)}",
            self.source,
            "Otra instalación no debe poder arrancar mientras verify/remove/rollback/install está en curso.",
        )

    def test_every_operation_clears_previous_public_error_before_starting(self) -> None:
        for function_name in ("install", "verify", "remove", "rollback"):
            start = self.source.index(f"async function {function_name}")
            next_function = self.source.find("\n  async function ", start + 1)
            block = self.source[start : next_function if next_function != -1 else len(self.source)]
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


if __name__ == "__main__":
    unittest.main()
