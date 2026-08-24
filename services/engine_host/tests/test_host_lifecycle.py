import unittest

from mily_engine_host import (
    AdapterDescriptor,
    AdapterKind,
    AdapterStatus,
    EngineHost,
    EngineHostError,
    EngineInvocation,
)


class FakeAdapter:
    def __init__(self):
        self.load_calls = 0
        self.unload_calls = 0
        self.invocations = []

    def load(self, config):
        self.load_calls += 1
        self.config = dict(config)

    def unload(self):
        self.unload_calls += 1

    def invoke(self, request):
        self.invocations.append(request)
        return {"requestId": request.request_id, "route": request.route}

    def health(self):
        return True


def descriptor(adapter_id: str, kind: AdapterKind = AdapterKind.ASR):
    return AdapterDescriptor(
        id=adapter_id,
        kind=kind,
        title=adapter_id,
        version="1.0.0",
        contract="asr/v1" if kind is AdapterKind.ASR else "mt/v1",
    )


class EngineHostLifecycleTests(unittest.TestCase):
    def test_registration_is_unique_and_descriptor_order_is_deterministic(self):
        host = EngineHost(max_loaded_adapters=2)
        host.register(descriptor("asr-a"), FakeAdapter)
        host.register(descriptor("mt-a", AdapterKind.MT), FakeAdapter)

        self.assertEqual([item.id for item in host.descriptors()], ["asr-a", "mt-a"])

        with self.assertRaises(EngineHostError) as context:
            host.register(descriptor("asr-a"), FakeAdapter)
        self.assertEqual(context.exception.code, "ADAPTER_ALREADY_REGISTERED")

    def test_load_marks_adapter_healthy_and_duplicate_load_is_idempotent(self):
        created = []

        def factory():
            adapter = FakeAdapter()
            created.append(adapter)
            return adapter

        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("asr-a"), factory)

        first = host.load("asr-a", {"model": "tiny"})
        second = host.load("asr-a", {"model": "ignored-on-idempotent-load"})

        self.assertEqual(first.status, AdapterStatus.HEALTHY)
        self.assertEqual(second.status, AdapterStatus.HEALTHY)
        self.assertTrue(first.loaded)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].load_calls, 1)
        self.assertEqual(created[0].config, {"model": "tiny"})

    def test_unload_releases_adapter_and_is_idempotent(self):
        created = []

        def factory():
            adapter = FakeAdapter()
            created.append(adapter)
            return adapter

        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("asr-a"), factory)
        host.load("asr-a")

        health = host.unload("asr-a")
        again = host.unload("asr-a")

        self.assertEqual(health.status, AdapterStatus.UNLOADED)
        self.assertFalse(health.loaded)
        self.assertEqual(again.status, AdapterStatus.UNLOADED)
        self.assertEqual(created[0].unload_calls, 1)
        self.assertEqual(host.snapshot().loaded_adapters, 0)

    def test_invoke_routes_request_to_loaded_adapter(self):
        created = []

        def factory():
            adapter = FakeAdapter()
            created.append(adapter)
            return adapter

        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("asr-a"), factory)
        host.load("asr-a")
        request = EngineInvocation(request_id="req-1", route="asr:en", metadata={"lang": "en"})

        result = host.invoke("asr-a", request)

        self.assertEqual(result, {"requestId": "req-1", "route": "asr:en"})
        self.assertIs(created[0].invocations[0], request)

    def test_invoke_requires_loaded_adapter(self):
        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("asr-a"), FakeAdapter)

        with self.assertRaises(EngineHostError) as context:
            host.invoke("asr-a", EngineInvocation(request_id="r", route="asr"))
        self.assertEqual(context.exception.code, "ADAPTER_NOT_LOADED")

    def test_capacity_refuses_extra_load_without_evicting_existing_adapter(self):
        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("asr-a"), FakeAdapter)
        host.register(descriptor("mt-a", AdapterKind.MT), FakeAdapter)
        host.load("asr-a")

        with self.assertRaises(EngineHostError) as context:
            host.load("mt-a")

        self.assertEqual(context.exception.code, "HOST_CAPACITY")
        snapshot = host.snapshot()
        self.assertEqual(snapshot.loaded_adapters, 1)
        by_id = {item.adapter_id: item for item in snapshot.adapters}
        self.assertTrue(by_id["asr-a"].loaded)
        self.assertFalse(by_id["mt-a"].loaded)

    def test_invalid_capacity_is_rejected(self):
        for value in [0, -1, True]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    EngineHost(max_loaded_adapters=value)


if __name__ == "__main__":
    unittest.main()
