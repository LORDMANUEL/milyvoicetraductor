import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from mily_mt import (
    MarianEnEsMtAdapter,
    MarianZhEsCascadeMtAdapter,
    MtAdapterError,
)


@dataclass(frozen=True)
class Prepared:
    text: str = "Do not cancel order 1038."
    source_language: str = "en"
    target_language: str = "es"
    segments: tuple[str, ...] = ("Do not cancel order 1038.",)
    terminology: tuple = ()
    context: tuple = ()


@dataclass(frozen=True)
class Invocation:
    request_id: str
    route: str
    frame: object
    metadata: dict


class FakeProvider:
    def __init__(self, output="No cancele el pedido 1038"):
        self.output = output
        self.calls = []
        self.unload_calls = 0

    def translate(self, text, source_language):
        self.calls.append((text, source_language))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def unload(self):
        self.unload_calls += 1


class FakeClock:
    def __init__(self, *values):
        self._values = iter(values)

    def __call__(self):
        return next(self._values)


class MtAdapterTests(unittest.TestCase):
    def adapter(self, cls=MarianEnEsMtAdapter, *, provider=None, clock=None):
        provider = provider or FakeProvider()
        build_calls = []
        budget_calls = []

        def budget_builder(profile, physical_cores):
            budget = {"profile": profile, "physical": physical_cores}
            budget_calls.append((profile, physical_cores, budget))
            return budget

        def provider_builder(component, model_path, compute_profile, cpu_budget):
            build_calls.append(
                (dict(component), str(model_path), compute_profile, cpu_budget)
            )
            return provider

        instance = cls(
            provider_builder=provider_builder,
            cpu_budget_builder=budget_builder,
            clock_ns=clock or FakeClock(100, 200),
        )
        return instance, provider, build_calls, budget_calls

    def test_concrete_adapters_have_stable_routes_and_provider_ids(self):
        en, *_ = self.adapter(MarianEnEsMtAdapter)
        zh, *_ = self.adapter(MarianZhEsCascadeMtAdapter)
        self.assertEqual(
            (en.engine_id, en.provider_id, en.source_language, en.target_language),
            ("marian-en-es", "marian-ct2", "en", "es"),
        )
        self.assertEqual(
            (zh.engine_id, zh.provider_id, zh.source_language, zh.target_language),
            ("marian-zh-es", "marian-cascade-ct2", "zh", "es"),
        )

    def test_load_maps_config_to_existing_translation_factory_signature(self):
        adapter, _provider, calls, budgets = self.adapter()
        adapter.load(
            {
                "modelPath": "models/opus",
                "component": {
                    "repoId": "demo/repo",
                    "sourceLanguage": "en",
                    "targetLanguage": "es",
                },
                "computeProfile": "cuda",
                "cpuProfile": "light",
                "physicalCores": 2,
            }
        )
        self.assertEqual(budgets[0][:2], ("light", 2))
        component, model_path, compute, budget = calls[0]
        self.assertEqual(component["provider"], "marian-ct2")
        self.assertEqual(component["sourceLanguage"], "en")
        self.assertEqual(component["targetLanguage"], "es")
        self.assertEqual(component["repoId"], "demo/repo")
        self.assertTrue(model_path.endswith("models/opus"))
        self.assertEqual(compute, "cuda")
        self.assertIs(budget, budgets[0][2])
        self.assertTrue(adapter.health())

    def test_missing_model_conflicting_provider_and_route_are_rejected(self):
        adapter, *_ = self.adapter()
        with self.assertRaises(MtAdapterError) as missing:
            adapter.load({})
        self.assertEqual(missing.exception.code, "MT_MODEL_PATH_REQUIRED")

        with self.assertRaises(MtAdapterError) as provider:
            adapter.load(
                {
                    "modelPath": "model",
                    "component": {"provider": "qwen"},
                }
            )
        self.assertEqual(provider.exception.code, "MT_PROVIDER_CONFLICT")

        with self.assertRaises(MtAdapterError) as route:
            adapter.load(
                {
                    "modelPath": "model",
                    "component": {"sourceLanguage": "zh", "targetLanguage": "es"},
                }
            )
        self.assertEqual(route.exception.code, "MT_ROUTE_CONFLICT")

    def test_invoke_normalizes_result_metrics_and_preserves_prepared_text(self):
        adapter, provider, *_ = self.adapter(
            clock=FakeClock(1_000_000_000, 1_125_000_000)
        )
        adapter.load({"modelPath": "model"})
        prepared = Prepared()
        result = adapter.invoke(
            Invocation(
                "req-1",
                "mt:en-es",
                prepared,
                {"utteranceId": "utt-7"},
            )
        )
        self.assertEqual(provider.calls, [(prepared.text, "en")])
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(result.utterance_id, "utt-7")
        self.assertEqual(result.engine_id, "marian-en-es")
        self.assertEqual(result.provider_id, "marian-ct2")
        self.assertEqual(result.source_language, "en")
        self.assertEqual(result.target_language, "es")
        self.assertEqual(result.source_text, prepared.text)
        self.assertEqual(result.target_text, "No cancele el pedido 1038")
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason, "OK")
        self.assertTrue(result.quality.passed)
        self.assertTrue(result.fidelity.passed)
        self.assertEqual(result.elapsed_ms, 125.0)

    def test_lost_negation_or_number_is_rejected_without_source_fallback(self):
        provider = FakeProvider("Cancele el pedido")
        adapter, *_ = self.adapter(provider=provider, clock=FakeClock(10, 20))
        adapter.load({"modelPath": "model"})
        result = adapter.invoke(
            Invocation("r", "mt:en-es", Prepared(), {"utteranceId": "u"})
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "NUMBER_LOST")
        self.assertEqual(result.target_text, "Cancele el pedido")
        self.assertNotEqual(result.target_text, result.source_text)

    def test_repetitive_output_is_rejected(self):
        repeated = (
            "No cancele el pedido 1038 y no cancele el pedido 1038 y "
            "no cancele el pedido 1038."
        )
        adapter, *_ = self.adapter(
            provider=FakeProvider(repeated), clock=FakeClock(10, 20)
        )
        adapter.load({"modelPath": "model"})
        result = adapter.invoke(
            Invocation("r", "mt:en-es", Prepared(), {"utteranceId": "u"})
        )
        self.assertFalse(result.accepted)
        self.assertIn(
            result.reason,
            {"REPEATED_SENTENCE", "REPEATED_NGRAM", "REPETITION_RATIO"},
        )
        self.assertFalse(result.quality.passed)
        self.assertTrue(result.fidelity.passed)

    def test_invalid_prepared_input_is_rejected_before_provider_call(self):
        adapter, provider, *_ = self.adapter()
        adapter.load({"modelPath": "model"})
        invalid = [
            None,
            Prepared(text=""),
            Prepared(source_language="zh"),
            Prepared(target_language="en"),
        ]
        for frame in invalid:
            with self.subTest(frame=frame):
                with self.assertRaises(MtAdapterError) as context:
                    adapter.invoke(
                        Invocation("r", "mt:en-es", frame, {"utteranceId": "u"})
                    )
                self.assertEqual(context.exception.code, "MT_INPUT_INVALID")
        self.assertEqual(provider.calls, [])

        with self.assertRaises(MtAdapterError) as metadata:
            adapter.invoke(Invocation("r", "mt:en-es", Prepared(), {}))
        self.assertEqual(metadata.exception.code, "MT_METADATA_INVALID")
        self.assertEqual(provider.calls, [])

    def test_unload_releases_provider_and_health_becomes_false(self):
        adapter, provider, *_ = self.adapter()
        adapter.load({"modelPath": "model"})
        adapter.unload()
        self.assertEqual(provider.unload_calls, 1)
        self.assertFalse(adapter.health())


if __name__ == "__main__":
    unittest.main()
