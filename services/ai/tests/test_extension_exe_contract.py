import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKGROUND = (ROOT / "apps/extension/background.js").read_text(encoding="utf-8")
OFFSCREEN = (ROOT / "apps/extension/offscreen.js").read_text(encoding="utf-8")
REGISTER = (ROOT / "installer/windows/register-native-host.ps1").read_text(encoding="utf-8")
BRIDGE_RUNTIME = (ROOT / "crates/mily-bridge/src/runtime.rs").read_text(encoding="utf-8")
MANIFEST = (ROOT / "apps/extension/manifest.json").read_text(encoding="utf-8")


class ExtensionExeContractTests(unittest.TestCase):
    def test_native_requests_are_serialized_instead_of_rejected_during_status_poll(self):
        self.assertIn("let bridgeRequestChain = Promise.resolve()", BACKGROUND)
        self.assertIn("function requestBridgeNow", BACKGROUND)
        self.assertIn("bridgeRequestChain.then(execute, execute)", BACKGROUND)
        self.assertNotIn("El bridge local está atendiendo otra solicitud", BACKGROUND)

    def test_capture_is_not_reported_ready_before_engine_session_started(self):
        self.assertIn("let sessionReady = false", OFFSCREEN)
        self.assertIn("const readyPromise = new Promise", OFFSCREEN)
        self.assertIn("payload.type === 'session.started'", OFFSCREEN)
        self.assertIn("await readyPromise", OFFSCREEN)
        self.assertIn("!sessionReady", OFFSCREEN)

    def test_audio_is_never_sent_before_session_negotiation(self):
        marker = "workletNode.port.onmessage"
        self.assertIn(marker, OFFSCREEN)
        block = OFFSCREEN.split(marker, 1)[1].split("try {", 1)[0]
        self.assertIn("websocket?.readyState !== WebSocket.OPEN || !sessionReady", block)
        self.assertIn("websocket.send(event.data)", block)

    def test_native_host_identity_is_exactly_pinned_everywhere(self):
        host = "com.milyvoice.traductor"
        origin = "chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/"
        self.assertIn(host, BACKGROUND)
        self.assertIn(host, REGISTER)
        self.assertIn(origin, REGISTER)
        self.assertIn(origin, BRIDGE_RUNTIME)
        self.assertIn('"key"', MANIFEST)

    def test_prepare_route_is_the_capture_path_that_requests_ephemeral_session(self):
        capture = BACKGROUND.split("async function startCapture", 1)[1].split(
            "async function stopCapture", 1
        )[0]
        self.assertIn("requestBridge('prepare-route'", capture)
        self.assertIn("route: routeKey", capture)
        self.assertIn("bridge.credential", capture)
        self.assertIn("bridge.port", capture)
        self.assertIn("credential: bridge.credential", capture)
        self.assertIn("enginePort: bridge.port", capture)
        self.assertLess(capture.index("requestBridge('prepare-route'"), capture.index("ensureOverlay(tab.id)"))

    def test_status_queries_never_issue_capture_credential(self):
        self.assertIn("should_issue_credential(ensure_started", BRIDGE_RUNTIME)
        self.assertIn("status_never_issues_a_credential", BRIDGE_RUNTIME)
        self.assertIn("self.status(true)", BRIDGE_RUNTIME)

    def test_offscreen_connection_timeout_cleans_failed_capture(self):
        self.assertIn("8000", OFFSCREEN)
        self.assertIn("await cleanup();", OFFSCREEN)
        self.assertIn("El motor local no confirmó la sesión de audio a tiempo.", OFFSCREEN)


if __name__ == "__main__":
    unittest.main()
