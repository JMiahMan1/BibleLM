import pytesseract
from PIL import Image
import logging
from pathlib import Path
from ..config import settings

logger = logging.getLogger(__name__)

def perform_ocr(image_path: Path) -> str:
    """Performs OCR on an image file using Tesseract."""
    logger.info(f"Starting OCR for: {image_path}")
    if not image_path.exists():
        logger.error(f"Image file not found: {image_path}")
        raise FileNotFoundError(f"Image file not found: {image_path}")

    try:
        # Optional: Set Tesseract path if needed (usually handled by PATH or config.py)
        # pytesseract.pytesseract.tesseract_cmd = settings.tesseract.cmd

        text = pytesseract.image_to_string(Image.open(image_path), lang=settings.tesseract.lang)
        logger.info(f"OCR completed for: {image_path} (length: {len(text)} chars)")
        return text
    except ImportError:
         logger.error("Tesseract is not installed or not in the system's PATH.")
         raise RuntimeError("Tesseract not found. Please install it.")
    except pytesseract.TesseractNotFoundError:
        logger.error(f"Tesseract executable not found at '{settings.tesseract.cmd}' or in PATH.")
        raise RuntimeError("Tesseract executable not found.")
    except Exception as e:
        logger.error(f"Tesseract OCR failed for {image_path}: {e}")
        raise RuntimeError(f"Tesseract OCR failed") from e
