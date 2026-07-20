"""Audio / TTS models (app.routes.tts).

TTSRequest mirrors the tts-service TTSGenerateRequest schema so that
`request.model_dump()` forwards every field the microservice expects.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """Text-to-speech generation request forwarded to the tts-service."""

    text: str = Field(..., min_length=1, max_length=5000, description="Text to speak")
    language: str = Field(default="en", description="Language code")
    speaker_wav: str | None = Field(
        default=None, description="Path to a reference wav for voice cloning"
    )
    speaker: str | None = Field(
        default=None, description="Named speaker to use, if any"
    )
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
