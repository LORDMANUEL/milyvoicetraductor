import unittest

from mily_ai.echo_guard import EchoGuard


class EchoGuardTests(unittest.TestCase):
    def test_recent_tts_text_matches_punctuation_variants(self):
        guard = EchoGuard(ttl_seconds=5.0)
        guard.register("¡Hola, mundo!", now=10.0)
        self.assertTrue(guard.matches("hola mundo", now=11.0))
        self.assertTrue(guard.matches("Hola, mundo.", now=12.0))
        self.assertFalse(guard.matches("we need the invoice", now=12.0))

    def test_registration_expires(self):
        guard = EchoGuard(ttl_seconds=2.0)
        guard.register("hola mundo", now=10.0)
        self.assertFalse(guard.matches("hola mundo", now=13.0))


if __name__ == "__main__":
    unittest.main()
