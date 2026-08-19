import unittest

from mily_ai.pipeline import RealtimePipeline


class FakeAsr:
    def __init__(self):
        self.word_timestamps = True


class PipelineResourceModeTests(unittest.TestCase):
    def pipeline(self):
        pipeline = RealtimePipeline.__new__(RealtimePipeline)
        pipeline._resource_mode = "healthy"
        pipeline._word_timestamps_requested = True
        pipeline._speaker_detection_requested = True
        pipeline.asr = FakeAsr()
        return pipeline

    def test_catch_up_disables_word_timestamps_and_speaker_detection(self):
        pipeline = self.pipeline()
        pipeline.set_resource_mode("catch_up")
        self.assertEqual(pipeline.resource_mode, "catch_up")
        self.assertFalse(pipeline.asr.word_timestamps)
        self.assertFalse(pipeline.speaker_detection_enabled)

    def test_healthy_restores_requested_features(self):
        pipeline = self.pipeline()
        pipeline.set_resource_mode("rescue")
        pipeline.set_resource_mode("healthy")
        self.assertTrue(pipeline.asr.word_timestamps)
        self.assertTrue(pipeline.speaker_detection_enabled)

    def test_unknown_mode_is_normalized_to_rescue(self):
        pipeline = self.pipeline()
        pipeline.set_resource_mode("unknown")
        self.assertEqual(pipeline.resource_mode, "rescue")


if __name__ == "__main__":
    unittest.main()
