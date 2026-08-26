import unittest
from pathlib import Path

from mily_ai.server import route_supported_by_definition


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


if __name__ == "__main__":
    unittest.main()
