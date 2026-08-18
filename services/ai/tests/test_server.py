import logging
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient

    HAS_FASTAPI = True
except Exception:
    HAS_FASTAPI = False

from mily_ai.runtime import RuntimePaths
from mily_ai.security import PairingTokenService


class OriginPolicyTests(unittest.TestCase):
    def test_only_pinned_extension_and_loopback_web_origins_are_allowed(self):
        from mily_ai.server import websocket_origin_allowed

        self.assertTrue(websocket_origin_allowed("chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm"))
        self.assertTrue(websocket_origin_allowed("http://127.0.0.1:1420"))
        self.assertFalse(websocket_origin_allowed("chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
        self.assertFalse(websocket_origin_allowed("https://example.com"))


@unittest.skipUnless(HAS_FASTAPI, "FastAPI/TestClient no disponibles")
class LocalServerTests(unittest.TestCase):
    def make_paths(self, root: Path) -> RuntimePaths:
        return RuntimePaths(
            data_dir=root / "data",
            config_dir=root / "config",
            cache_dir=root / "cache",
            models_dir=root / "models",
            logs_dir=root / "logs",
            sessions_dir=root / "sessions",
        )

    def test_health_and_auth_are_local_contracts(self):
        from mily_ai.server import create_app

        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            app = create_app(paths)
            with TestClient(app) as client:
                health = client.get("/health")
                self.assertEqual(health.status_code, 200)
                self.assertTrue(health.json()["ok"])
                self.assertEqual(health.json()["protocol"], 1)
                self.assertEqual(client.get("/v1/models").status_code, 401)

            # El lifespan debe liberar el RotatingFileHandler. En Windows, dejarlo
            # abierto impide que TemporaryDirectory elimine ai-engine.log.
            self.assertEqual(logging.getLogger("milyvoice.ai").handlers, [])

    def test_websocket_rejects_session_without_model_pack(self):
        from mily_ai.server import create_app

        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_paths(Path(tmp))
            app = create_app(paths)
            token = PairingTokenService(
                paths.config_dir / "bridge-token.txt"
            ).get_or_create()
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws?token={token}") as ws:
                    self.assertEqual(ws.receive_json()["type"], "engine.ready")
                    ws.send_json(
                        {
                            "protocol": 1,
                            "type": "client.hello",
                            "sourceLanguage": "auto",
                            "targetLanguage": "es",
                            "persistTranscript": False,
                        }
                    )
                    error = ws.receive_json()
                    self.assertEqual(error["type"], "engine.error")
                    self.assertEqual(error["code"], "MODEL_NOT_INSTALLED")


if __name__ == "__main__":
    unittest.main()
