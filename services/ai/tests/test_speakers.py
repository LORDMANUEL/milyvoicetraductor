import math
import unittest

from mily_ai.speakers import SpeakerClusterer


def tone(frequency: float, seconds: float = 1.0, rate: int = 16000) -> list[float]:
    return [0.25 * math.sin(2.0 * math.pi * frequency * i / rate) for i in range(int(rate * seconds))]


class SpeakerClustererTests(unittest.TestCase):
    def test_same_voice_signature_keeps_stable_id(self):
        clusterer = SpeakerClusterer(sample_rate=16000, similarity_threshold=0.88)
        first = clusterer.assign(tone(220.0), update=True)
        second = clusterer.assign(tone(225.0), update=True)
        self.assertEqual(first, "speaker-a")
        self.assertEqual(second, first)

    def test_distinct_spectral_signature_gets_new_id(self):
        clusterer = SpeakerClusterer(sample_rate=16000, similarity_threshold=0.88)
        first = clusterer.assign(tone(180.0), update=True)
        second = clusterer.assign(tone(980.0), update=True)
        self.assertEqual(first, "speaker-a")
        self.assertEqual(second, "speaker-b")

    def test_dominant_speaker_uses_final_assignment_counts(self):
        clusterer = SpeakerClusterer(sample_rate=16000, similarity_threshold=0.88)
        a = clusterer.assign(tone(180.0), update=True)
        b = clusterer.assign(tone(980.0), update=True)
        clusterer.assign(tone(985.0), update=True)
        clusterer.assign(tone(990.0), update=True)
        self.assertNotEqual(a, b)
        self.assertEqual(clusterer.dominant_id, b)


if __name__ == "__main__":
    unittest.main()
