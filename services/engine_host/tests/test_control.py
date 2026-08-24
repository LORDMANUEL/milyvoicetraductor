import io
import json
import unittest

from mily_engine_host import AdapterDescriptor, AdapterKind, EngineHost
from mily_engine_host.control import handle_request, serve_stream


class FakeAdapter:
    def load(self, config):
        self.config = dict(config)

    def unload(self):
        pass

    def invoke(self, request):
        return None

    def health(self):
        return True


def host_with_adapter() -> EngineHost:
    host = EngineHost(max_loaded_adapters=1)
    host.register(
        AdapterDescriptor(
            id="fake-asr",
            kind=AdapterKind.ASR,
            title="Fake ASR",
            version="1.0.0",
            contract="asr/v1",
        ),
        FakeAdapter,
    )
    return host


class EngineHostControlTests(unittest.TestCase):
    def test_ping_and_discover_are_structured(self):
        host = host_with_adapter()

        ping = handle_request(host, {"requestId": "p1", "operation": "ping"})
        discover = handle_request(host, {"requestId": "d1", "operation": "discover"})

        self.assertTrue(ping["ok"])
        self.assertEqual(ping["requestId"], "p1")
        self.assertEqual(ping["result"]["version"], "1.0.0")
        self.assertEqual(discover["result"]["adapters"][0]["id"], "fake-asr")
        self.assertEqual(discover["result"]["adapters"][0]["kind"], "asr")

    def test_load_snapshot_and_unload_control_lifecycle(self):
        host = host_with_adapter()

        loaded = handle_request(
            host,
            {
                "requestId": "l1",
                "operation": "load",
                "adapterId": "fake-asr",
                "config": {"model": "tiny"},
            },
        )
        snapshot = handle_request(host, {"requestId": "s1", "operation": "snapshot"})
        unloaded = handle_request(
            host,
            {"requestId": "u1", "operation": "unload", "adapterId": "fake-asr"},
        )

        self.assertTrue(loaded["ok"])
        self.assertEqual(loaded["result"]["status"], "healthy")
        self.assertEqual(snapshot["result"]["loadedAdapters"], 1)
        self.assertEqual(snapshot["result"]["adapters"][0]["status"], "healthy")
        self.assertTrue(unloaded["ok"])
        self.assertEqual(unloaded["result"]["status"], "unloaded")

    def test_unknown_operation_and_missing_adapter_are_errors_not_exceptions(self):
        host = host_with_adapter()
        unknown = handle_request(host, {"requestId": "x", "operation": "explode"})
        missing = handle_request(host, {"requestId": "m", "operation": "load"})

        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["errorCode"], "CONTROL_OPERATION")
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["errorCode"], "CONTROL_ADAPTER_REQUIRED")

    def test_host_errors_are_returned_with_stable_codes(self):
        host = host_with_adapter()
        result = handle_request(
            host,
            {"requestId": "missing", "operation": "load", "adapterId": "does-not-exist"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["errorCode"], "ADAPTER_NOT_REGISTERED")

    def test_stream_survives_malformed_json_and_serves_next_request(self):
        host = host_with_adapter()
        source = io.StringIO('{not-json}\n{"requestId":"p2","operation":"ping"}\n')
        output = io.StringIO()

        serve_stream(host, source, output)

        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(responses), 2)
        self.assertFalse(responses[0]["ok"])
        self.assertEqual(responses[0]["errorCode"], "CONTROL_JSON")
        self.assertTrue(responses[1]["ok"])
        self.assertEqual(responses[1]["requestId"], "p2")

    def test_non_object_json_is_rejected_and_loop_continues(self):
        host = host_with_adapter()
        source = io.StringIO('[]\n{"requestId":"d2","operation":"discover"}\n')
        output = io.StringIO()

        serve_stream(host, source, output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]

        self.assertEqual(responses[0]["errorCode"], "CONTROL_REQUEST")
        self.assertTrue(responses[1]["ok"])
        self.assertEqual(responses[1]["result"]["adapters"][0]["id"], "fake-asr")


if __name__ == "__main__":
    unittest.main()
