import unittest

from mily_engine_host import (
    AdapterDescriptor,
    AdapterKind,
    AdapterStatus,
    EngineHost,
    EngineHostError,
    EngineInvocation,
)


def descriptor(adapter_id: str):
    return AdapterDescriptor(
        id=adapter_id,
        kind=AdapterKind.ASR,
        title=adapter_id,
        version="1.0.0",
        contract="asr/v1",
    )


class GoodAdapter:
    def __init__(self):
        self.loaded = False

    def load(self, config):
        self.loaded = True

    def unload(self):
        self.loaded = False

    def invoke(self, request):
        return request.request_id

    def health(self):
        return True


class LoadFailureAdapter(GoodAdapter):
    def load(self, config):
        raise RuntimeError("model corrupt")


class InvokeFailureAdapter(GoodAdapter):
    def invoke(self, request):
        raise RuntimeError("native inference failure")


class HealthFailureAdapter(GoodAdapter):
    def health(self):
        raise RuntimeError("probe failure")


class UnloadFailureAdapter(GoodAdapter):
    def unload(self):
        raise RuntimeError("native handle stuck")


class EngineHostFailureIsolationTests(unittest.TestCase):
    def test_factory_failure_is_contained_without_capacity_leak(self):
        host = EngineHost(max_loaded_adapters=1)

        def broken_factory():
            raise RuntimeError("factory failed")

        host.register(descriptor("broken"), broken_factory)
        with self.assertRaises(EngineHostError) as context:
            host.load("broken")

        self.assertEqual(context.exception.code, "ADAPTER_LOAD_FAILED")
        health = host.health("broken")
        self.assertEqual(health.status, AdapterStatus.UNHEALTHY)
        self.assertFalse(health.loaded)
        self.assertEqual(health.failures, 1)
        self.assertEqual(host.snapshot().loaded_adapters, 0)

    def test_load_failure_cleanup_does_not_consume_host_capacity(self):
        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("broken"), LoadFailureAdapter)
        host.register(descriptor("good"), GoodAdapter)

        with self.assertRaises(EngineHostError):
            host.load("broken")
        self.assertEqual(host.snapshot().loaded_adapters, 0)

        self.assertEqual(host.load("good").status, AdapterStatus.HEALTHY)
        self.assertEqual(host.snapshot().loaded_adapters, 1)

    def test_invoke_failure_marks_only_that_adapter_unhealthy(self):
        host = EngineHost(max_loaded_adapters=2)
        host.register(descriptor("broken"), InvokeFailureAdapter)
        host.register(descriptor("good"), GoodAdapter)
        host.load("broken")
        host.load("good")

        with self.assertRaises(EngineHostError) as context:
            host.invoke("broken", EngineInvocation(request_id="a", route="asr"))
        self.assertEqual(context.exception.code, "ADAPTER_INVOKE_FAILED")

        broken = host.health("broken")
        good = host.health("good")
        self.assertEqual(broken.status, AdapterStatus.UNHEALTHY)
        self.assertEqual(broken.failures, 1)
        self.assertEqual(good.status, AdapterStatus.HEALTHY)
        self.assertEqual(host.invoke("good", EngineInvocation(request_id="b", route="asr")), "b")

        with self.assertRaises(EngineHostError) as second:
            host.invoke("broken", EngineInvocation(request_id="c", route="asr"))
        self.assertEqual(second.exception.code, "ADAPTER_UNHEALTHY")

    def test_health_probe_failure_degrades_adapter_without_breaking_snapshot(self):
        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("probe"), HealthFailureAdapter)
        host.load("probe")

        snapshot = host.snapshot(refresh_health=True)
        health = snapshot.adapters[0]

        self.assertEqual(health.status, AdapterStatus.DEGRADED)
        self.assertTrue(health.loaded)
        self.assertEqual(health.failures, 1)
        self.assertIn("probe failure", health.last_error)

    def test_unload_failure_remains_loaded_and_keeps_capacity_reserved(self):
        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("stuck"), UnloadFailureAdapter)
        host.register(descriptor("other"), GoodAdapter)
        host.load("stuck")

        with self.assertRaises(EngineHostError) as context:
            host.unload("stuck")
        self.assertEqual(context.exception.code, "ADAPTER_UNLOAD_FAILED")

        health = host.health("stuck")
        self.assertEqual(health.status, AdapterStatus.UNHEALTHY)
        self.assertTrue(health.loaded)
        self.assertEqual(host.snapshot().loaded_adapters, 1)

        with self.assertRaises(EngineHostError) as capacity:
            host.load("other")
        self.assertEqual(capacity.exception.code, "HOST_CAPACITY")

    def test_explicit_unload_reload_recovers_from_invoke_failure_with_new_instance(self):
        created = []

        def factory():
            adapter = InvokeFailureAdapter() if not created else GoodAdapter()
            created.append(adapter)
            return adapter

        host = EngineHost(max_loaded_adapters=1)
        host.register(descriptor("recoverable"), factory)
        host.load("recoverable")

        with self.assertRaises(EngineHostError):
            host.invoke("recoverable", EngineInvocation(request_id="bad", route="asr"))
        self.assertEqual(host.health("recoverable").status, AdapterStatus.UNHEALTHY)

        self.assertEqual(host.unload("recoverable").status, AdapterStatus.UNLOADED)
        self.assertEqual(host.load("recoverable").status, AdapterStatus.HEALTHY)
        self.assertEqual(len(created), 2)
        self.assertEqual(
            host.invoke("recoverable", EngineInvocation(request_id="good", route="asr")),
            "good",
        )


if __name__ == "__main__":
    unittest.main()
