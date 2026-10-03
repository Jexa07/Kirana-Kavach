from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import asyncio
import base64
import json

from app.voice import (
    _encode_multipart,
    language_code,
)


def test_language_code_mapping():
    assert language_code("hi") == "hi-IN"
    assert language_code("mr") == "mr-IN"
    assert language_code("en") == "en-IN"
    assert language_code(None) == "en-IN"


def test_multipart_contains_audio_file_and_fields():
    body, content_type = _encode_multipart(
        fields={"model": "saaras:v4", "mode": "transcribe"},
        file_field="file",
        filename="voice.webm",
        content_type="audio/webm",
        content=b"fake-audio",
    )

    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="model"' in body
    assert b'saaras:v4' in body
    assert b'name="mode"' in body
    assert b'transcribe' in body
    assert b'filename="voice.webm"' in body
    assert b'Content-Type: audio/webm' in body
    assert b"fake-audio" in body


def test_tts_audio_base64_is_decodable():
    audio = b"RIFFfakewav"
    encoded = base64.b64encode(audio).decode("ascii")
    payload = {"audios": [encoded]}

    assert base64.b64decode(payload["audios"][0]) == audio


def test_default_saaras_v4_multipart_does_not_send_v3_only_mode():
    body, _ = _encode_multipart(
        fields={"model": "saaras:v4"},
        file_field="file",
        filename="voice.wav",
        content_type="audio/wav",
        content=b"audio",
    )
    assert b'name="mode"' not in body
    assert b'saaras:v4' in body


def test_ensure_merchant_profile_seeded_is_idempotent():
    from app.memory import InMemoryStore, ensure_merchant_profile_seeded, reset_seeded_merchants
    from app.data_store import get_merchant

    reset_seeded_merchants()
    store = InMemoryStore()
    merchant = get_merchant("M1001")

    async def run():
        first = await ensure_merchant_profile_seeded(store, merchant)
        second = await ensure_merchant_profile_seeded(store, merchant)
        assert first is True
        assert second is False
        # Profile stored exactly once in merchant records bucket
        assert len(store.records["M1001"]) == 1

    asyncio.run(run())


def test_tts_endpoint_returns_base64_audio(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    def mock_synthesize_speech(*, text, language_code_value, config):
        return {
            "audio_base64": "UklGRmZha2V3YXZhdWRpbw==",
            "audio_mime_type": "audio/wav",
            "request_id": "test-req-123",
        }

    monkeypatch.setattr("app.main.synthesize_speech", mock_synthesize_speech)

    client = TestClient(app)
    res = client.post(
        "/api/merchants/M1001/tts",
        json={"text": "नमस्ते Kavach", "language": "hi"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["merchant_id"] == "M1001"
    assert data["text"] == "नमस्ते Kavach"
    assert data["audio"]["audio_base64"] == "UklGRmZha2V3YXZhdWRpbw=="
    assert data["audio"]["audio_mime_type"] == "audio/wav"


