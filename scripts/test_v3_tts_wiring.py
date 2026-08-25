#!/usr/bin/env python3
"""Static F9 guard for Chromium TTS wiring and failure isolation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ext = root / "apps" / "extension"
background = (ext / "background.js").read_text(encoding="utf-8")
offscreen = (ext / "offscreen.js").read_text(encoding="utf-8")
tts = (ext / "tts.js").read_text(encoding="utf-8")
server = (root / "services" / "ai" / "mily_ai" / "server.py").read_text(encoding="utf-8")

assert "TtsQueueController" in tts, "TTS must own a bounded queue"
assert "enqueue: false" in tts, "Chromium queue must stay disabled; MilyVoice owns sequencing"
assert "maxPending: 3" in tts and "maxAgeMs: 4000" in tts, "F9 queue bounds changed"

assert "import { speakTranslation, stopSpeech } from './tts.js';" in background, (
    "background must use the TTS component stop path"
)
assert "await stopSpeech('CANCELLED')" in background, "capture stop must clear bounded TTS state"
assert "chrome.tts.stop()" not in background, "background must not bypass the TTS controller"

translation_block = background.split("if (message?.type === 'TRANSLATION_EVENT'", 1)[1].split(
    "if (message?.type === 'ENGINE_EVENT')", 1
)[0]
assert "duckingEnabled" in translation_block and "duckingLevel" in translation_block, (
    "actual TTS start must forward ducking policy to offscreen"
)
assert "type: 'TTS_STARTED'" in translation_block, "anti-feedback start event must be preserved"
assert "type: 'TTS_FINISHED'" in translation_block, "anti-feedback finish event must be preserved"

assert "from './tts/ducking.js'" in offscreen, "offscreen must import the tested ducking policy"
assert "let playbackGainNode = null;" in offscreen, "playback gain must survive beyond startCapture scope"
assert "playbackGainNode = audioContext.createGain()" in offscreen, "tab reinjection must use the owned gain node"

start_block = offscreen.split("if (message.type === 'TTS_STARTED')", 1)[1].split(
    "if (message.type === 'TTS_FINISHED')", 1
)[0]
finish_block = offscreen.split("if (message.type === 'TTS_FINISHED')", 1)[1].split(
    "return false;", 1
)[0]
cleanup_block = offscreen.split("async function cleanup()", 1)[1].split("async function startCapture", 1)[0]

assert "setDuckingGain" in start_block, "TTS_STARTED must apply ducking to local playback"
assert "restoreGain" in finish_block, "TTS_FINISHED must restore local playback"
assert "restoreGain" in cleanup_block, "cleanup must restore playback even on cancellation/error"

for label, block in (("TTS_STARTED", start_block), ("TTS_FINISHED", finish_block)):
    assert "audio.stop" not in block, f"{label} must not stop the audio session"
    assert "cleanup()" not in block, f"{label} must not tear down capture"
    assert ".close(" not in block, f"{label} must not close the websocket/audio context"
    assert "getTracks" not in block, f"{label} must not stop MediaStream tracks"

assert "pipeline.register_tts(message.tts_text)" in server, (
    "engine must continue registering synthesized text for EchoGuard anti-feedback"
)
assert "message.type == \"tts.started\"" in server and "message.type == \"tts.finished\"" in server

print("V3 TTS wiring/isolation guard: OK")
