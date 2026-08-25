import unittest

from mily_engine_host import (
    AdapterDescriptor,
    AdapterKind,
    AdapterStatus,
    EngineHost,
    EngineHostError,
    EngineInvocation,
)
from mily_linguistic import (
    ContextBuffer,
    TerminologyBook,
    TerminologyRule,
    prepare_translation_input,
)
from mily_mt import MarianEnEsMtAdapter, MarianZhEsCascadeMtAdapter


class Provider:
    def __init__(self, output):
        self.output = output
        self.calls = []
        self.unloaded = False

    def translate(self, text, source_language):
        self.calls.append((text, source_language))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def unload(self):
        self.unloaded = True


class EngineHostMtIntegrationTests(unittest.TestCase):
    @staticmethod
    def adapter_factory(cls, provider):
        def build(component, model_path, compute_profile, cpu_budget):
            return provider

        return lambda: cls(
            provider_builder=build,
            cpu_budget_builder=lambda profile, physical: {
                "profile": profile,
                "physical": physical,
            },
        )

    def host(self, en_provider, zh_provider):
        host = EngineHost(max_loaded_adapters=2)
        host.register(
            AdapterDescriptor(
                id="mt-marian-en-es",
                kind=AdapterKind.MT,
                title="Marian EN ES",
                version="1.0.0",
                contract="mt/v1",
            ),
            self.adapter_factory(MarianEnEsMtAdapter, en_provider),
        )
        host.register(
            AdapterDescriptor(
                id="mt-marian-zh-es",
                kind=AdapterKind.MT,
                title="Marian ZH ES",
                version="1.0.0",
                contract="mt/v1",
            ),
            self.adapter_factory(MarianZhEsCascadeMtAdapter, zh_provider),
        )
        return host

    def test_real_linguistic_input_flows_through_engine_host_for_both_routes(self):
        en_provider = Provider("No cancele el pedido 1038")
        zh_provider = Provider("No cancele el pedido 1038")
        host = self.host(en_provider, zh_provider)
        host.load("mt-marian-en-es", {"modelPath": "en-model"})
        host.load("mt-marian-zh-es", {"modelPath": "zh-model"})

        context = ContextBuffer(max_items=2, max_chars=100)
        context.append("Earlier context", "en")
        terminology = TerminologyBook(
            [TerminologyRule("order", "pedido", "en", "es")]
        )
        en_input = prepare_translation_input(
            "  Do not cancel order 1038.  ",
            "en",
            "es",
            terminology=terminology,
            context=context,
        )
        zh_input = prepare_translation_input("不要取消订单 1038。", "zh", "es")

        en_result = host.invoke(
            "mt-marian-en-es",
            EngineInvocation(
                "req-en",
                "mt:en-es",
                frame=en_input,
                metadata={"utteranceId": "utt-en"},
            ),
        )
        zh_result = host.invoke(
            "mt-marian-zh-es",
            EngineInvocation(
                "req-zh",
                "mt:zh-es",
                frame=zh_input,
                metadata={"utteranceId": "utt-zh"},
            ),
        )

        self.assertEqual(en_provider.calls, [(en_input.text, "en")])
        self.assertEqual(zh_provider.calls, [(zh_input.text, "zh")])
        self.assertEqual(en_result.source_text, "Do not cancel order 1038.")
        self.assertEqual(en_input.terminology[0].target, "pedido")
        self.assertEqual(en_input.context[0].text, "Earlier context")
        self.assertTrue(en_result.accepted)
        self.assertTrue(zh_result.accepted)
        self.assertEqual(host.snapshot().loaded_adapters, 2)

    def test_one_mt_failure_isolated_by_engine_host(self):
        en_provider = Provider(RuntimeError("decoder failed"))
        zh_provider = Provider("Pedido 1038 confirmado")
        host = self.host(en_provider, zh_provider)
        host.load("mt-marian-en-es", {"modelPath": "en-model"})
        host.load("mt-marian-zh-es", {"modelPath": "zh-model"})

        en_input = prepare_translation_input("Confirm order 1038.", "en", "es")
        with self.assertRaises(EngineHostError) as failed:
            host.invoke(
                "mt-marian-en-es",
                EngineInvocation(
                    "req-en",
                    "mt:en-es",
                    frame=en_input,
                    metadata={"utteranceId": "u-en"},
                ),
            )
        self.assertEqual(failed.exception.code, "ADAPTER_INVOKE_FAILED")
        self.assertEqual(
            host.health("mt-marian-en-es").status,
            AdapterStatus.UNHEALTHY,
        )

        zh_input = prepare_translation_input("确认订单 1038。", "zh", "es")
        zh_result = host.invoke(
            "mt-marian-zh-es",
            EngineInvocation(
                "req-zh",
                "mt:zh-es",
                frame=zh_input,
                metadata={"utteranceId": "u-zh"},
            ),
        )
        self.assertTrue(zh_result.accepted)
        self.assertEqual(
            host.health("mt-marian-zh-es").status,
            AdapterStatus.HEALTHY,
        )


if __name__ == "__main__":
    unittest.main()
