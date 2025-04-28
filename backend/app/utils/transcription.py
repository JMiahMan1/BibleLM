import whisper
import logging
from pathlib import Path
from ..config import settings # Import settings from config module

logger = logging.getLogger(__name__)

# Load model globally or within the function (consider memory usage)
# Global loading might be faster for repeated calls but uses more memory.
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {settings.whisper.model} on device: {settings.whisper.device}")
        try:
            _whisper_model = whisper.load_model(settings.whisper.model, device=settings.whisper.device)
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise RuntimeError(f"Could not load Whisper model '{settings.whisper.model}'") from e
    return _whisper_model

def transcribe_audio(audio_path: Path) -> str:
    """Transcribes an audio file using Whisper."""
    logger.info(f"Starting transcription for: {audio_path}")
    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        model = get_whisper_model()
        result = model.transcribe(str(audio_path), fp16=False) # fp16=False often more stable on CPU
        transcription = result["text"]
        logger.info(f"Transcription completed for: {audio_path} (length: {len(transcription)} chars)")
        return transcription
    except Exception as e:
        logger.error(f"Whisper transcription failed for {audio_path}: {e}")
        # Consider retrying or specific error handling
        raise RuntimeError(f"Whisper transcription failed") from e
