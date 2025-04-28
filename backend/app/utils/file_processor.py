from pathlib import Path
import logging
from pypdf import PdfReader
from docx import Document as DocxDocument
from ebooklib import epub, ITEM_DOCUMENT
from typing import Tuple

from .transcription import transcribe_audio
from .ocr import perform_ocr
from ..database import DocumentType

logger = logging.getLogger(__name__)

def get_document_type(filepath: Path) -> DocumentType:
    """Determines the DocumentType based on file extension."""
    suffix = filepath.suffix.lower()
    if suffix == '.pdf': return DocumentType.PDF
    if suffix == '.docx': return DocumentType.DOCX
    if suffix == '.epub': return DocumentType.EPUB
    if suffix == '.txt': return DocumentType.TXT
    if suffix in ['.mp3', '.wav', '.m4a', '.ogg']: return DocumentType.MP3 # Consolidate audio types
    if suffix in ['.mp4', '.mov', '.avi', '.mkv']: return DocumentType.MP4 # Consolidate video types
    if suffix in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']: return DocumentType.JPG # Consolidate image types
    return DocumentType.UNKNOWN

def extract_text_from_file(filepath: Path, doc_type: DocumentType) -> str:
    """Extracts text content based on file type, handling transcription and OCR."""
    logger.info(f"Extracting text from: {filepath} (Type: {doc_type.name})")
    text_content = ""

    try:
        if doc_type == DocumentType.PDF:
            reader = PdfReader(filepath)
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        elif doc_type == DocumentType.DOCX:
            doc = DocxDocument(filepath)
            for para in doc.paragraphs:
                text_content += para.text + "\n"
        elif doc_type == DocumentType.EPUB:
            book = epub.read_epub(filepath)
            for item in book.get_items_of_type(ITEM_DOCUMENT):
                # Basic handling, might need HTML parsing for cleaner text
                text_content += item.get_content().decode('utf-8', errors='ignore') + "\n"
        elif doc_type == DocumentType.TXT:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
        elif doc_type in [DocumentType.MP3, DocumentType.WAV, DocumentType.MP4, DocumentType.MOV]: # Audio/Video types
            # Assume video files have been pre-processed to audio (e.g., by downloader or separate step)
            # If handling video directly, extract audio first using ffmpeg-python or similar
            logger.info(f"Detected media file, attempting transcription: {filepath}")
            text_content = transcribe_audio(filepath)
        elif doc_type in [DocumentType.PNG, DocumentType.JPG]: # Image types
             logger.info(f"Detected image file, attempting OCR: {filepath}")
             text_content = perform_ocr(filepath)
        else:
            logger.warning(f"Unsupported file type for text extraction: {doc_type.name}")
            raise ValueError(f"Unsupported file type: {doc_type.name}")

        logger.info(f"Successfully extracted text from {filepath} (Length: {len(text_content)})")
        return text_content

    except Exception as e:
        logger.error(f"Failed to extract text from {filepath}: {e}")
        # Re-raise to be caught by the background task handler
        raise
