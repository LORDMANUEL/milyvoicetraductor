import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.models import ModelCatalog


class BetaAlphaSherpaCatalogTests(unittest.TestCase):
    def test_ultralight_sherpa_packs_are_real_pinned_cpu_candidates(self):
        definitions = {
            item["id"]: item for item in ModelCatalog(Path("unused")).definitions()
        }
        expected = {
            "betaalpha-zipformer-en-es": (
                "en-es",
                "csukuangfj/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17",
                "d42f2d9f7ca24806fb667456a18a9f1b60f70d16",
                "online-transducer",
            ),
            "betaalpha-zipformer-zh-es": (
                "zh-es",
                "csukuangfj/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23",
                "204ad334e2e683fd295359930cc16fc0432a23ac",
                "online-transducer",
            ),
            "betaalpha-paraformer-zh-es": (
                "zh-es",
                "csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
                "8e40c43232a1c5c66c82111efc5820d3accca11b",
                "online-paraformer",
            ),
        }
        for pack_id, (route, repo_id, revision, mode) in expected.items():
            with self.subTest(pack_id=pack_id):
                pack = definitions[pack_id]
                self.assertEqual(pack["tier"], "lite")
                self.assertEqual(pack["supportedBackends"], ["cpu"])
                self.assertIn(route, pack["routes"])
                self.assertLessEqual(int(pack["ramMb"]), 1200)
                asr = pack["components"]["asr"]
                self.assertEqual(asr["provider"], "sherpa-onnx")
                self.assertEqual(asr["repoId"], repo_id)
                self.assertEqual(asr["revision"], revision)
                self.assertEqual(asr["sherpaMode"], mode)
                self.assertTrue(asr["allowPatterns"])


class _FakeStream:
    def __init__(self):
        self.accepted = []
        self.finished = False

    def accept_waveform(self, sample_rate, samples):
        self.accepted.append((sample_rate, list(samples)))

    def input_finished(self):
        self.finished = True


class _FakeResult:
    def __init__(self, text):
        self.text = text


class _FakeOnlineRecognizer:
    def __init__(self, kind, kwargs):
        self.kind = kind
        self.kwargs = kwargs
        self.streams = []
        self.decode_calls = 0

    def create_stream(self):
        stream = _FakeStream()
        self.streams.append(stream)
        return stream

    def is_ready(self, stream):
        return self.decode_calls == 0 or (stream.finished and self.decode_calls == 1)

    def decode_stream(self, _stream):
        self.decode_calls += 1

    def get_result_all(self, _stream):
        return _FakeResult("hello world" if self.kind == "transducer" else "你好世界")

    def reset(self, _stream):
        pass


class _FakeOnlineRecognizerFactory:
    created = []

    @classmethod
    def from_transducer(cls, **kwargs):
        item = _FakeOnlineRecognizer("transducer", kwargs)
        cls.created.append(item)
        return item

    @classmethod
    def from_paraformer(cls, **kwargs):
        item = _FakeOnlineRecognizer("paraformer", kwargs)
        cls.created.append(item)
        return item


class BetaAlphaSherpaRuntimeTests(unittest.TestCase):
    def setUp(self):
        _FakeOnlineRecognizerFactory.created.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in (
            "encoder.int8.onnx",
            "decoder.onnx",
            "joiner.int8.onnx",
            "tokens.txt",
        ):
            (self.root / name).write_bytes(b"x")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _transducer_component():
        return {
            "provider": "sherpa-onnx",
            "sherpaMode": "online-transducer",
            "language": "en",
            "encoder": "encoder.int8.onnx",
            "decoder": "decoder.onnx",
            "joiner": "joiner.int8.onnx",
            "tokens": "tokens.txt",
        }

    def test_online_transducer_is_resident_and_receives_only_new_audio(self):
        from mily_ai.sherpa_streaming_provider import SherpaStreamingAsr

        fake_module = types.SimpleNamespace(OnlineRecognizer=_FakeOnlineRecognizerFactory)
        with patch.dict(sys.modules, {"sherpa_onnx": fake_module}):
            provider = SherpaStreamingAsr(
                self.root,
                "cpu",
                cpu_budget=detect_cpu_budget("light", physical_cores=2),
                component=self._transducer_component(),
            )
            first = provider.transcribe([0.01] * 3200, "en")
            second = provider.transcribe([0.01] * 4800, "en")

        self.assertEqual(len(_FakeOnlineRecognizerFactory.created), 1)
        recognizer = _FakeOnlineRecognizerFactory.created[0]
        self.assertEqual(recognizer.kwargs["provider"], "cpu")
        self.assertLessEqual(recognizer.kwargs["num_threads"], 2)
        stream = recognizer.streams[0]
        self.assertEqual(len(stream.accepted[0][1]), 3200)
        self.assertEqual(len(stream.accepted[1][1]), 1600)
        self.assertEqual(first[0].text, "hello world")
        self.assertEqual(second[0].text, "hello world")

    def test_final_flush_adds_tail_padding_marks_input_finished_and_resets_stream(self):
        from mily_ai.sherpa_streaming_provider import SherpaStreamingAsr

        fake_module = types.SimpleNamespace(OnlineRecognizer=_FakeOnlineRecognizerFactory)
        with patch.dict(sys.modules, {"sherpa_onnx": fake_module}):
            provider = SherpaStreamingAsr(
                self.root,
                "cpu",
                cpu_budget=detect_cpu_budget("light", physical_cores=2),
                component=self._transducer_component(),
            )
            provider.transcribe([0.01] * 3200, "en")
            result = provider.transcribe_final([0.01] * 4800, "en")
            recognizer = _FakeOnlineRecognizerFactory.created[0]
            stream = recognizer.streams[0]
            self.assertTrue(stream.finished)
            self.assertEqual([len(chunk[1]) for chunk in stream.accepted], [3200, 1600, 8000])
            self.assertEqual(result[0].text, "hello world")
            provider.transcribe([0.01] * 3200, "en")

        self.assertEqual(len(recognizer.streams), 2)

    def test_online_paraformer_uses_int8_encoder_and_decoder(self):
        from mily_ai.sherpa_streaming_provider import SherpaStreamingAsr

        (self.root / "decoder.int8.onnx").write_bytes(b"x")
        fake_module = types.SimpleNamespace(OnlineRecognizer=_FakeOnlineRecognizerFactory)
        component = {
            "provider": "sherpa-onnx",
            "sherpaMode": "online-paraformer",
            "language": "zh",
            "encoder": "encoder.int8.onnx",
            "decoder": "decoder.int8.onnx",
            "tokens": "tokens.txt",
        }
        with patch.dict(sys.modules, {"sherpa_onnx": fake_module}):
            provider = SherpaStreamingAsr(
                self.root,
                "cpu",
                cpu_budget=detect_cpu_budget("light", physical_cores=1),
                component=component,
            )
            result = provider.transcribe([0.01] * 3200, "zh")

        recognizer = _FakeOnlineRecognizerFactory.created[0]
        self.assertEqual(recognizer.kind, "paraformer")
        self.assertTrue(recognizer.kwargs["encoder"].endswith("encoder.int8.onnx"))
        self.assertTrue(recognizer.kwargs["decoder"].endswith("decoder.int8.onnx"))
        self.assertEqual(result[0].language, "zh")


if __name__ == "__main__":
    unittest.main()
