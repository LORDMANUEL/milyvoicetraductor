import unittest
from pathlib import Path
from types import SimpleNamespace

from mily_ai.marian_realtime import CTranslate2RealtimeMarianTranslator


class _SentencePieceStub:
    def encode(self, text, out_type=str):
        return [token for token in text.replace('.', ' .').split() if token]

    def decode(self, tokens):
        return ' '.join(tokens)


class _TranslatorStub:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def translate_batch(self, _sources, **_options):
        index = min(self.calls, len(self.outputs) - 1)
        self.calls += 1
        return [SimpleNamespace(hypotheses=[self.outputs[index]])]


class MarianIdentifierRestoreTests(unittest.TestCase):
    def _provider(self, outputs):
        provider = CTranslate2RealtimeMarianTranslator(
            Path('unused'),
            'cpu',
            source_language='en',
            target_language='es',
        )
        provider._translator = _TranslatorStub(outputs)
        provider._source_sp = _SentencePieceStub()
        provider._target_sp = _SentencePieceStub()
        return provider

    def test_verbalized_order_identifier_is_restored_exactly(self):
        provider = self._provider([
            ['No', 'cancele', 'el', 'pedido', 'mil', 'treinta', 'y', 'ocho']
        ])

        translated = provider.translate('Do not cancel order 1038.', 'en')

        self.assertIn('1038', translated)
        self.assertTrue(translated.casefold().startswith('no '))
        self.assertEqual(provider._translator.calls, 1)

    def test_conflicting_numeric_output_is_never_repaired(self):
        provider = self._provider([
            ['No', 'cancele', 'el', 'pedido', '1039'],
        ])

        with self.assertRaises(Exception):
            provider.translate('Do not cancel order 1038.', 'en')

        self.assertNotIn('1038', ' '.join(provider._translator.outputs[0]))

    def test_non_identifier_large_number_is_not_appended(self):
        provider = self._provider([
            ['El', 'presupuesto', 'es', 'mil', 'treinta', 'y', 'ocho'],
        ])

        with self.assertRaises(Exception):
            provider.translate('The budget is 1038.', 'en')


if __name__ == '__main__':
    unittest.main()
