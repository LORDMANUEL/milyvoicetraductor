import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.cloud_providers import GoogleChirpV2Asr
from mily_ai.safe_optional_providers import MoonshineResultAsr
from mily_ai.vosk_provider import VoskAsr


class FakeVoskRecognizer:
    def __init__(self, model, rate):
        self.model = model
        self.rate = rate
        self.words = False
    def SetWords(self, enabled): self.words = enabled
    def AcceptWaveform(self, payload): return True
    def FinalResult(self):
        return json.dumps({"text":"hello world","result":[{"start":0.0,"end":0.3,"word":"hello"},{"start":0.3,"end":0.7,"word":"world"}]})


class FakeVoskModule:
    loads = 0
    class Model:
        def __init__(self, path): FakeVoskModule.loads += 1; self.path = path
    KaldiRecognizer = FakeVoskRecognizer
    @staticmethod
    def SetLogLevel(_level): return None


class FakeMoonshineTranscriber:
    created = []
    def __init__(self, *args, **kwargs): self.created.append((args, kwargs))


class FakeCloudSpeech:
    class ExplicitDecodingConfig:
        class AudioEncoding: LINEAR16 = 1
        def __init__(self, **kwargs): self.kwargs = kwargs
    class RecognitionConfig:
        def __init__(self, **kwargs): self.kwargs = kwargs
    class RecognizeRequest:
        def __init__(self, **kwargs): self.kwargs = kwargs


class FakeChirpClient:
    def __init__(self): self.requests = []
    def recognize(self, *, request):
        self.requests.append(request)
        return types.SimpleNamespace(results=[types.SimpleNamespace(alternatives=[types.SimpleNamespace(transcript="hello from cloud")], language_code="en-US")])


class OptionalEngineAdapterTests(unittest.TestCase):
    def test_vosk_keeps_model_loaded_and_returns_words(self):
        FakeVoskModule.loads = 0
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {"vosk":FakeVoskModule}):
            provider = VoskAsr(Path(tmp), word_timestamps=True)
            first = provider.transcribe([0.0,0.2,-0.2], "en")
            second = provider.transcribe([0.1,0.0], "en")
            self.assertEqual(first[0].text, "hello world")
            self.assertEqual([word.text for word in first[0].words], ["hello","world"])
            self.assertEqual(second[0].text, "hello world")
            self.assertEqual(FakeVoskModule.loads, 1)
            provider.unload()
            self.assertIsNone(provider._model)

    def test_moonshine_passes_model_arch_and_disables_audio_return(self):
        fake_module = types.SimpleNamespace(Transcriber=FakeMoonshineTranscriber)
        FakeMoonshineTranscriber.created.clear()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {"moonshine_voice":fake_module}):
            root = Path(tmp)
            (root / "moonshine-config.json").write_text(json.dumps({"modelArch":2,"updateInterval":0.25}), encoding="utf-8")
            provider = MoonshineResultAsr(root)
            provider._load()
        args, kwargs = FakeMoonshineTranscriber.created[0]
        self.assertEqual(args[0], str(root))
        self.assertEqual(args[1], 2)
        self.assertEqual(kwargs["update_interval"], 0.25)
        self.assertFalse(kwargs["options"]["return_audio_data"])

    def test_google_chirp_requires_consent_before_network(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT":"demo"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "consentimiento"):
                GoogleChirpV2Asr(Path(".")).transcribe([0.1], "en")

    def test_google_chirp_builds_chirp3_v2_request(self):
        client = FakeChirpClient()
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT":"demo","MILY_GOOGLE_CLOUD_REGION":"us","MILY_GOOGLE_CHIRP_CONSENT":"1"}, clear=True):
            provider = GoogleChirpV2Asr(Path("."), client=client, speech_types=FakeCloudSpeech)
            result = provider.transcribe([0.0,0.25,-0.25], "en")
        self.assertEqual(result[0].text, "hello from cloud")
        request = client.requests[0]
        self.assertEqual(request.kwargs["config"].kwargs["model"], "chirp_3")
        self.assertEqual(request.kwargs["recognizer"], "projects/demo/locations/us/recognizers/_")
        self.assertTrue(request.kwargs["content"])


if __name__ == "__main__":
    unittest.main()
