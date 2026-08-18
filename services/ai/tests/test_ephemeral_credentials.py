import tempfile
import unittest
from pathlib import Path

from mily_ai.security import EphemeralCredentialService


class EphemeralCredentialTests(unittest.TestCase):
    def test_credential_expires_and_is_not_reusable_forever(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = EphemeralCredentialService(Path(tmp) / "native-credential.json")
            issued = service.issue(ttl_seconds=60, now=1_000)
            self.assertTrue(service.is_valid(issued.token, now=1_059))
            self.assertFalse(service.is_valid(issued.token, now=1_061))

    def test_wrong_credential_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = EphemeralCredentialService(Path(tmp) / "native-credential.json")
            service.issue(ttl_seconds=60, now=1_000)
            self.assertFalse(service.is_valid("wrong", now=1_010))

    def test_ttl_is_capped_at_five_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = EphemeralCredentialService(Path(tmp) / "native-credential.json")
            issued = service.issue(ttl_seconds=9_999, now=1_000)
            self.assertEqual(issued.expires_at, 1_300)


if __name__ == "__main__":
    unittest.main()
