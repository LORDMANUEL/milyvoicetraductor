import unittest

from mily_ai.marian_cascade import CTranslate2MarianCascadeTranslator
from mily_ai.optional_providers import OptionalProviderRuntimeError


class _StageOneStub:
    selected_device = "cpu"
    fallback_used = False
    fallback_reason = ""

    def __init__(self, pivot):
        self.pivot = pivot

    def translate(self, _text, _language):
        return self.pivot


class _StageTwoStub:
    selected_device = "cpu"
    fallback_used = False
    fallback_reason = ""

    def __init__(self, mapping, *, fail_full=False):
        self.mapping = dict(mapping)
        self.fail_full = fail_full
        self.calls = []

    def translate(self, text, _language):
        self.calls.append(text)
        if self.fail_full and "," in text:
            raise OptionalProviderRuntimeError("MARIAN_FIDELITY", "fixture")
        value = self.mapping.get(text)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise OptionalProviderRuntimeError("MARIAN_FIDELITY", "fixture")
        return value


def _cascade(pivot, second):
    provider = object.__new__(CTranslate2MarianCascadeTranslator)
    provider.source_language = "zh"
    provider.pivot_language = "en"
    provider.target_language = "es"
    provider._first = _StageOneStub(pivot)
    provider._second = second
    provider.selected_device = None
    provider.fallback_used = False
    provider.fallback_reason = ""
    provider._warmed = False
    return provider


class MarianCascadeClauseRescueTests(unittest.TestCase):
    def test_normal_full_translation_does_not_split(self):
        pivot = "Please send the technical report tomorrow."
        second = _StageTwoStub({pivot: "Envíe el informe técnico mañana."})
        provider = _cascade(pivot, second)

        result = provider.translate("fixture", "zh")

        self.assertEqual(result, "Envíe el informe técnico mañana.")
        self.assertEqual(second.calls, [pivot])

    def test_compound_failure_is_rescued_by_verified_clauses(self):
        pivot = "Please confirm order 1038, do not cancel order 1038."
        second = _StageTwoStub(
            {
                "Please confirm order 1038": "Confirme el pedido 1038.",
                "do not cancel order 1038.": "No cancele el pedido 1038.",
            },
            fail_full=True,
        )
        provider = _cascade(pivot, second)

        result = provider.translate("fixture", "zh")

        self.assertIn("1038", result)
        self.assertIn("No cancele", result)
        self.assertEqual(len(second.calls), 3)

    def test_rescue_rejects_combined_output_that_loses_negation(self):
        pivot = "Please confirm order 1038, do not cancel order 1038."
        second = _StageTwoStub(
            {
                "Please confirm order 1038": "Confirme el pedido 1038.",
                "do not cancel order 1038.": "Cancele el pedido 1038.",
            },
            fail_full=True,
        )
        provider = _cascade(pivot, second)

        with self.assertRaises(OptionalProviderRuntimeError):
            provider.translate("fixture", "zh")

    def test_non_fidelity_runtime_failure_is_not_hidden(self):
        pivot = "Please confirm order 1038, do not cancel order 1038."

        class _RuntimeFail(_StageTwoStub):
            def translate(self, text, _language):
                raise OptionalProviderRuntimeError("MARIAN_MODEL_LOAD", "fixture")

        provider = _cascade(pivot, _RuntimeFail({}))
        with self.assertRaisesRegex(OptionalProviderRuntimeError, "fixture"):
            provider.translate("fixture", "zh")


if __name__ == "__main__":
    unittest.main()
