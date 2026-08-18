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
        self.assertEqual(message.session_mode, "meeting")
        self.assertTrue(message.binary_pcm)

    def test_karaoke_session_mode_is_parsed(self):
        message = ClientMessage.parse(json.dumps({
            "protocol": 1,
            "type": "client.hello",
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "sessionMode": "karaoke",
        }))
        self.assertEqual(message.session_mode, "karaoke")

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
