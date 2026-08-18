import unittest
from types import SimpleNamespace

from mily_ai.event_payloads import pipeline_event_fields


class EventPayloadTests(unittest.TestCase):
    def test_word_timestamps_are_serialized_only_when_present(self):
        event = SimpleNamespace(
            start=1.0,
            end=2.0,
            original="hello",
            language="en",
            translation="hola",
            words=(SimpleNamespace(start=1.0, end=1.4, text="hello"),),
        )
        fields = pipeline_event_fields(event)
        self.assertEqual(
            fields["words"],
            [{"start": 1.0, "end": 1.4, "text": "hello"}],
        )

    def test_meeting_payload_has_no_empty_words_field(self):
        event = SimpleNamespace(
            start=1.0,
            end=2.0,
            original="hello",
            language="en",
            translation="",
            words=(),
        )
        fields = pipeline_event_fields(event)
        self.assertNotIn("words", fields)
        self.assertNotIn("translation", fields)


if __name__ == "__main__":
    unittest.main()
