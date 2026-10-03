from __future__ import annotations

import base64
import binascii
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error as urlerror
from urllib import request


class SarvamVoiceError(RuntimeError):
    """Raised when a Sarvam voice request cannot be completed."""


@dataclass(frozen=True)
class SarvamVoiceConfig:
    api_key: str | None = None
    stt_model: str = "saaras:v4"
    stt_mode: str = "transcribe"
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "shubh"
    timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "SarvamVoiceConfig":
        return cls(
            api_key=os.getenv("SARVAM_API_KEY"),
            stt_model=os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
            stt_mode=os.getenv("SARVAM_STT_MODE", "transcribe"),
            tts_model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            tts_speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
            timeout_seconds=float(os.getenv("SARVAM_VOICE_TIMEOUT", "45")),
        )


_LANGUAGE_CODES = {
    "hi": "hi-IN",
    "mr": "mr-IN",
    "en": "en-IN",
}


def language_code(language: str | None) -> str:
    return _LANGUAGE_CODES.get((language or "en").lower(), "en-IN")


def _encode_multipart(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> tuple[bytes, str]:
    boundary = f"----KiranaKavach{uuid.uuid4().hex}"
    boundary_bytes = boundary.encode("ascii")
    body = bytearray()

    for name, value in fields.items():
        body.extend(b"--" + boundary_bytes + b"\r\n")
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(
                "utf-8"
            )
        )
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(b"--" + boundary_bytes + b"\r\n")
    body.extend(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode(
            "utf-8"
        )
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
    body.extend(content)
    body.extend(b"\r\n")
    body.extend(b"--" + boundary_bytes + b"--\r\n")

    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _json_request(
    *,
    url: str,
    payload: dict[str, Any],
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": api_key,
        },
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urlerror.HTTPError, urlerror.URLError, TimeoutError) as exc:
        raise SarvamVoiceError(f"Sarvam request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SarvamVoiceError("Sarvam returned invalid JSON") from exc


def transcribe_audio(
    *,
    audio: bytes,
    filename: str,
    content_type: str,
    config: SarvamVoiceConfig,
) -> dict[str, str]:
    if not config.api_key:
        raise SarvamVoiceError("SARVAM_API_KEY is required for voice input")

    body, multipart_type = _encode_multipart(
        fields={
            "model": config.stt_model,
            **({"mode": config.stt_mode} if config.stt_model == "saaras:v3" else {}),
        },
        file_field="file",
        filename=filename,
        content_type=content_type or "audio/wav",
        content=audio,
    )

    req = request.Request(
        "https://api.sarvam.ai/speech-to-text",
        data=body,
        method="POST",
        headers={
            "Content-Type": multipart_type,
            "api-subscription-key": config.api_key,
        },
    )

    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urlerror.HTTPError, urlerror.URLError, TimeoutError) as exc:
        raise SarvamVoiceError(f"Sarvam speech-to-text failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SarvamVoiceError("Sarvam speech-to-text returned invalid JSON") from exc

    transcript = payload.get("transcript")
    detected_language = payload.get("language_code") or "unknown"
    if not isinstance(transcript, str) or not transcript.strip():
        raise SarvamVoiceError("Sarvam returned an empty transcript")

    return {
        "transcript": transcript.strip(),
        "language_code": str(detected_language),
    }


def synthesize_speech(
    *,
    text: str,
    language_code_value: str,
    config: SarvamVoiceConfig,
) -> dict[str, str]:
    if not config.api_key:
        raise SarvamVoiceError("SARVAM_API_KEY is required for voice output")

    payload = _json_request(
        url="https://api.sarvam.ai/text-to-speech",
        payload={
            "text": text,
            "language_code": language_code_value,
            "speaker": config.tts_speaker,
            "model": config.tts_model,
            "output_audio_codec": "wav",
            "speech_sample_rate": 24000,
        },
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )

    audios = payload.get("audios")
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
        raise SarvamVoiceError("Sarvam text-to-speech returned no audio")

    audio_base64 = audios[0]
    try:
        base64.b64decode(audio_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SarvamVoiceError("Sarvam text-to-speech returned invalid audio") from exc

    return {
        "audio_base64": audio_base64,
        "audio_mime_type": "audio/wav",
        "request_id": str(payload.get("request_id", "")),
    }
