import os
import unittest
from unittest.mock import patch

from mily_ai.runtime_discovery import discover_runtime_inventory


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_bare_whisper_cli_is_not_considered_realtime_runtime(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "mily_ai.runtime_discovery._module_available", return_value=False
        ), patch(
            "mily_ai.runtime_discovery.os.path.isfile", return_value=False
        ), patch(
            "mily_ai.runtime_discovery.shutil.which",
            return_value="/tmp/whisper-cli",
        ):
            inventory = discover_runtime_inventory()
        self.assertNotIn("whisper-cpp", inventory.runtimes)

    def test_persistent_whisper_bridge_is_discovered(self):
        with patch.dict(
            os.environ,
            {"MILY_WHISPER_CPP_BRIDGE": "/tmp/mily-whispercpp-bridge"},
            clear=True,
        ), patch(
            "mily_ai.runtime_discovery._module_available", return_value=False
        ), patch(
            "mily_ai.runtime_discovery.os.path.isfile", return_value=True
        ):
            inventory = discover_runtime_inventory()
        self.assertIn("whisper-cpp", inventory.runtimes)
        self.assertEqual(
            inventory.details["whisperCppBridge"],
            "/tmp/mily-whispercpp-bridge",
        )


if __name__ == "__main__":
    unittest.main()
