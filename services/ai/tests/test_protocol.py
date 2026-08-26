import json
import unittest

from mily_ai.protocol import ClientMessage, ProtocolError


class ProtocolTests(unittest.TestCase):
    def test_audio_chunk_requires_base64_payload(self):
        with self.assertRaises(ProtocolError):
            ClientMessage.parse(json.dumps({"protocol": 1, "type": "audio.chunk"}))

    def test_valid_hello_is_parsed(self):
        message = ClientMessage.parse(json.dumps({
            "protocol": 1,
            "type": "client.hello",
            "sourceLanguage": "auto",
            "targetLanguage": "es",
            "binaryPcm": True,
        }))
        self.assertEqual(message.type, "client.hello")
        self.assertEqual(message.source_language, "auto")
        self.assertEqual(message.target_language, "es")
        self.assertEqual(message.session_mode, "meeting")
        self.assertTrue(message.binary_pcm)

    def test_accepts_all_four_explicit_tier1_routes(self):
        for source, target in (("en", "es"), ("zh", "es"), ("es", "en"), ("es", "zh")):
            with self.subTest(route=f"{source}-{target}"):
                message = ClientMessage.parse(json.dumps({
                    "protocol": 1,
                    "type": "client.hello",
                    "sourceLanguage": source,
                    "targetLanguage": target,
                }))
                self.assertEqual((message.source_language, message.target_language), (source, target))

    def test_auto_is_only_valid_when_translating_to_spanish(self):
        accepted = ClientMessage.parse(json.dumps({
            "protocol": 1,
            "type": "client.hello",
            "sourceLanguage": "auto",
            "targetLanguage": "es",
        }))
        self.assertEqual((accepted.source_language, accepted.target_language), ("auto", "es"))

        for target in ("en", "zh"):
            with self.subTest(target=target), self.assertRaises(ProtocolError):
                ClientMessage.parse(json.dumps({
                    "protocol": 1,
                    "type": "client.hello",
                    "sourceLanguage": "auto",
                    "targetLanguage": target,
                }))

    def test_rejects_non_tier1_language_pairs(self):
        for source, target in (("en", "zh"), ("zh", "en"), ("es", "es"), ("en", "en")):
            with self.subTest(route=f"{source}-{target}"), self.assertRaises(ProtocolError):
                ClientMessage.parse(json.dumps({
                    "protocol": 1,
                    "type": "client.hello",
                    "sourceLanguage": source,
                    "targetLanguage": target,
                }))

    def test_karaoke_session_mode_is_parsed(self):
        message = ClientMessage.parse(json.dumps({
            "protocol": 1,
            "type": "client.hello",
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "sessionMode": "karaoke",
        }))
        self.assertEqual(message.session_mode, "karaoke")

    def test_loopback_and_speaker_controls_are_parsed(self):
        message = ClientMessage.parse(json.dumps({
            "protocol": 1,
            "type": "client.hello",
            "sourceMode": "system_loopback",
            "externalPcm": True,
            "speakerDetection": True,
            "speakerFocusMode": "fixed",
            "speakerId": "speaker-a",
        }))
        self.assertEqual(message.source_mode, "system_loopback")
        self.assertTrue(message.external_pcm)
        self.assertTrue(message.speaker_detection)
        self.assertEqual(message.speaker_focus_mode, "fixed")
        self.assertEqual(message.speaker_id, "speaker-a")

    def test_fixed_speaker_focus_requires_speaker_id(self):
        with self.assertRaises(ProtocolError):
            ClientMessage.parse(json.dumps({
                "protocol": 1,
                "type": "speaker.focus",
                "speakerFocusMode": "fixed",
            }))

    def test_tts_started_requires_text(self):
        with self.assertRaises(ProtocolError):
            ClientMessage.parse(json.dumps({"protocol": 1, "type": "tts.started"}))

    def test_unknown_session_mode_is_rejected(self):
        with self.assertRaises(ProtocolError):
            ClientMessage.parse(json.dumps({
                "protocol": 1,
                "type": "client.hello",
                "sessionMode": "vr",
            }))

    def test_unknown_protocol_is_rejected(self):
        with self.assertRaises(ProtocolError):
            ClientMessage.parse(json.dumps({"protocol": 999, "type": "client.hello"}))


if __name__ == "__main__":
    unittest.main()
