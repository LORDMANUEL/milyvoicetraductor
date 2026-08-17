import tempfile
import unittest
from pathlib import Path

from mily_ai.security import PairingTokenService, sanitize_text


class SecurityTests(unittest.TestCase):
    def test_token_is_persisted_with_high_entropy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge-token.txt"
            service = PairingTokenService(path)
            token = service.get_or_create()
            self.assertGreaterEqual(len(token), 40)
            self.assertEqual(service.get_or_create(), token)

    def test_logs_redact_known_secret_patterns(self):
        text = sanitize_text("token=abc password=hunter2 user=C:\\Users\\Luis\\file")
        self.assertNotIn("abc", text)
        self.assertNotIn("hunter2", text)
        self.assertIn("<USER_PATH>", text)


if __name__ == "__main__":
    unittest.main()
