import unittest
from pathlib import Path

from mily_ai.tier1_server import route_supported_by_definition


ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "services/ai/pyproject.toml"
PRIVATE_MAIN = ROOT / "services/ai/main.py"


class ServerRouteContractTests(unittest.TestCase):
    def test_route_supported_only_when_declared_by_pack(self):
        definition = {"routes": ["en-es", "zh-es"]}
        self.assertTrue(route_supported_by_definition(definition, "en", "es"))
        self.assertFalse(route_supported_by_definition(definition, "es", "en"))
        self.assertFalse(route_supported_by_definition(definition, "es", "zh"))

    def test_auto_source_maps_only_to_receiver_spanish_route_family(self):
        definition = {"routes": ["en-es", "zh-es"]}
        self.assertTrue(route_supported_by_definition(definition, "auto", "es"))
        self.assertFalse(route_supported_by_definition(definition, "auto", "en"))

    def test_quality_pack_supports_outbound_routes(self):
        definition = {"routes": ["en-es", "zh-es", "es-en", "es-zh"]}
        self.assertTrue(route_supported_by_definition(definition, "es", "en"))
        self.assertTrue(route_supported_by_definition(definition, "es", "zh"))

    def test_console_entrypoint_uses_tier1_cli(self):
        source = PYPROJECT.read_text(encoding="utf-8")
        self.assertIn('mily-ai-engine = "mily_ai.tier1_cli:main"', source)

    def test_private_runtime_entrypoint_uses_tier1_cli(self):
        source = PRIVATE_MAIN.read_text(encoding="utf-8")
        self.assertIn("from mily_ai.tier1_cli import main", source)
        self.assertNotIn("from mily_ai.cli import main", source)


if __name__ == "__main__":
    unittest.main()
