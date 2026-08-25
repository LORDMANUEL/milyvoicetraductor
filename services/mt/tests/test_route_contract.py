import unittest
from dataclasses import dataclass

from mily_mt import MarianEnEsMtAdapter, MtAdapterError


@dataclass(frozen=True)
class Prepared:
    text: str = "Hello"
    source_language: str = "en"
    target_language: str = "es"
    segments: tuple[str, ...] = ("Hello",)
    terminology: tuple = ()
    context: tuple = ()


@dataclass(frozen=True)
class Invocation:
    request_id: str
    route: str
    frame: object
    metadata: dict


class Provider:
    def translate(self, text, source_language):
        return "Hola"

    def unload(self):
        return None


class MtRouteContractTests(unittest.TestCase):
    def test_request_route_must_match_adapter_route_before_provider_call(self):
        calls = []
        provider = Provider()

        def build(component, model_path, compute_profile, cpu_budget):
            calls.append((component, model_path, compute_profile, cpu_budget))
            return provider

        adapter = MarianEnEsMtAdapter(
            provider_builder=build,
            cpu_budget_builder=lambda profile, physical: object(),
        )
        adapter.load({"modelPath": "model"})

        with self.assertRaises(MtAdapterError) as context:
            adapter.invoke(
                Invocation(
                    "r",
                    "mt:zh-es",
                    Prepared(),
                    {"utteranceId": "u"},
                )
            )

        self.assertEqual(context.exception.code, "MT_ROUTE_INVALID")


if __name__ == "__main__":
    unittest.main()
