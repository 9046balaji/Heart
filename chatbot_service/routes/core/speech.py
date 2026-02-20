"""
Speech Routes
=============
Audio transcription (STT) and text-to-speech (TTS) endpoints.
Endpoints:
    POST /speech/transcribe
    POST /speech/synthesize
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("speech")

router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TranscribeRequest(BaseModel):
    audio: str  # base64-encoded audio data


class TranscribeResponse(BaseModel):
    text: str
    language: Optional[str] = "en"
    confidence: Optional[float] = None
    duration_ms: Optional[float] = None


class SynthesizeRequest(BaseModel):
    text: str
    voice: Optional[str] = "default"
    speed: Optional[float] = 1.0


class SynthesizeResponse(BaseModel):
    audio: str  # base64-encoded audio
    format: str = "wav"
    duration_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# STT / TTS integration
# ---------------------------------------------------------------------------

_stt_available = False
_tts_available = False

try:
    import google.generativeai as genai
    _stt_available = True
except ImportError:
    pass

try:
    from gtts import gTTS
    import base64
    import io
    _tts_available = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """Transcribe base64-encoded audio to text."""
    start = time.time()

    if not request.audio or len(request.audio) < 10:
        raise HTTPException(status_code=400, detail="Invalid audio data")

    # Attempt real transcription via Google Generative AI (Gemini multimodal)
    if _stt_available:
        try:
            import base64 as b64
            audio_bytes = b64.b64decode(request.audio)
            # Use Gemini for audio transcription if available
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content([
                "Transcribe the following audio accurately. Return only the transcription text.",
                {"mime_type": "audio/wav", "data": audio_bytes},
            ])
            elapsed = round((time.time() - start) * 1000, 1)
            return TranscribeResponse(
                text=response.text.strip(),
                language="en",
                confidence=0.9,
                duration_ms=elapsed,
            )
        except Exception as e:
            logger.warning(f"Gemini STT failed, using fallback: {e}")

    # Fallback: acknowledge receipt but indicate transcription is unavailable
    elapsed = round((time.time() - start) * 1000, 1)
    return TranscribeResponse(
        text="[Transcription service is initializing. Please try again shortly.]",
        language="en",
        confidence=0.0,
        duration_ms=elapsed,
    )


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(request: SynthesizeRequest):
    """Convert text to speech, returning base64-encoded audio."""
    start = time.time()

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    if len(request.text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")

    # Attempt TTS via gTTS
    if _tts_available:
        try:
            import base64 as b64
            tts = gTTS(text=request.text, lang="en", slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            audio_b64 = b64.b64encode(buf.read()).decode("utf-8")
            elapsed = round((time.time() - start) * 1000, 1)
            return SynthesizeResponse(audio=audio_b64, format="mp3", duration_ms=elapsed)
        except Exception as e:
            logger.warning(f"gTTS failed: {e}")

    # Fallback: return empty audio
    elapsed = round((time.time() - start) * 1000, 1)
    return SynthesizeResponse(audio="", format="wav", duration_ms=elapsed)
