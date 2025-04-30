# app/utils/file_processor.py
import logging
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
import zipfile # Needed for EPUB

# Import DocumentType from constants.py
from ..constants import DocumentType, DocumentStatus # Assuming DocumentStatus might be used later
from ..config import settings

logger = logging.getLogger(__name__)

# --- Helper Function to Determine Document Type ---
def get_document_type(file_path: Path) -> DocumentType:
    """Determines document type based on file extension and mimetype."""
    # Guess mimetype first
    mime_type, _ = mimetypes.guess_type(file_path.as_uri())
    logger.debug(f"Guessed mimetype for {file_path.name}: {mime_type}")

    if mime_type:
        if mime_type == 'application/pdf':
            return DocumentType.PDF
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return DocumentType.DOCX
        elif mime_type == 'application/epub+zip':
             return DocumentType.EPUB
        elif mime_type.startswith('text/'):
            return DocumentType.TXT
        elif mime_type.startswith('audio/'):
            # Differentiate audio types if needed, or return a generic AUDIO
             if mime_type == 'audio/mpeg': return DocumentType.MP3
             elif mime_type == 'audio/wav' or mime_type == 'audio/x-wav': return DocumentType.WAV
             # Add other audio types as necessary
             return DocumentType.UNKNOWN # Default for audio
        elif mime_type.startswith('video/'):
            # Differentiate video types if needed, or return a generic VIDEO
             if mime_type == 'video/mp4': return DocumentType.MP4
             elif mime_type == 'video/quicktime': return DocumentType.MOV
             # Add other video types as necessary
             return DocumentType.UNKNOWN # Default for video
        elif mime_type.startswith('image/'):
            # Differentiate image types if needed
            if mime_type == 'image/png': return DocumentType.PNG
            elif mime_type == 'image/jpeg': return DocumentType.JPG
            # Add other image types
            return DocumentType.UNKNOWN # Default for image


    # If mimetype is not specific enough or not available, rely on extension
    extension = file_path.suffix.lower()
    if extension == '.pdf':
        return DocumentType.PDF
    elif extension == '.docx':
        return DocumentType.DOCX
    elif extension == '.epub':
         return DocumentType.EPUB
    elif extension == '.txt':
        return DocumentType.TXT
    elif extension == '.mp3':
        return DocumentType.MP3
    elif extension == '.wav':
        return DocumentType.WAV
    elif extension == '.mp4':
        return DocumentType.MP4
    elif extension == '.mov':
        return DocumentType.MOV
    elif extension == '.png':
        return DocumentType.PNG
    elif extension == '.jpg' or extension == '.jpeg':
        return DocumentType.JPG
    # Handle URLs explicitly if not caught by mimetype (though mimetype is often guessed for URLs)
    # This might require pattern matching the string itself if it's just a string path
    # if file_path.as_uri().startswith(('http://', 'https://', 'ftp://')):
    #     return DocumentType.URL

    logger.warning(f"Could not determine document type for file: {file_path.name}")
    return DocumentType.UNKNOWN


# --- Text Extraction Functions ---

async def extract_text(input_path: Path, doc_type: DocumentType, output_dir: Path) -> Path:
    """
    Extracts text from various document types.
    Returns the path to the resulting text file.
    """
    logger.info(f"Attempting to extract text from {input_path.name} (Type: {doc_type.name})")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"{input_path.stem}_processed.txt"
    output_path = output_dir / output_filename

    try:
        if doc_type == DocumentType.PDF:
            # Use subprocess or a library like PyMuPDF/pdfminer.six
            # Example using subprocess with pdftotext (must be installed)
            if shutil.which("pdftotext"):
                subprocess.run(["pdftotext", "-layout", str(input_path), str(output_path)], check=True)
                logger.info(f"Extracted PDF text using pdftotext to {output_path}")
            else:
                 logger.warning("pdftotext not found. Install it for PDF extraction.")
                 # Fallback to a Python library or raise error
                 raise EnvironmentError("pdftotext not found. Cannot process PDF.")

        elif doc_type == DocumentType.DOCX:
            # Use a library like python-docx
            try:
                from docx import Document as DocxDocument
                doc = DocxDocument(input_path)
                with open(output_path, 'w', encoding='utf-8') as f:
                    for para in doc.paragraphs:
                        f.write(para.text + "\n")
                logger.info(f"Extracted DOCX text using python-docx to {output_path}")
            except ImportError:
                logger.warning("python-docx not found. Install it for DOCX extraction (pip install python-docx).")
                raise ImportError("python-docx not found. Cannot process DOCX.")

        elif doc_type == DocumentType.EPUB:
             # EPUB is a zip file containing XHTML/HTML. Extract text from content files.
             try:
                 extracted_text = ""
                 with zipfile.ZipFile(input_path, 'r') as zf:
                     for entry in zf.infolist():
                         # Look for common content file extensions (xhtml, html)
                         if entry.filename.endswith(('.xhtml', '.html', '.htm', '.xml')):
                             try:
                                 with zf.open(entry, 'r') as content_file:
                                     # Simple HTML stripping (consider a more robust parser like BeautifulSoup)
                                     content_bytes = content_file.read()
                                     # Attempt decoding with common encodings
                                     try:
                                         content = content_bytes.decode('utf-8')
                                     except UnicodeDecodeError:
                                         content = content_bytes.decode('latin-1', errors='ignore') # Fallback

                                     # Basic HTML tag stripping
                                     import re
                                     clean_text = re.sub('<.*?>', '', content)
                                     extracted_text += clean_text + "\n\n" # Add separator

                             except Exception as e:
                                 logger.warning(f"Error reading or processing EPUB entry {entry.filename}: {e}")
                                 continue # Skip to next entry

                 if extracted_text.strip():
                     with open(output_path, 'w', encoding='utf-8') as f:
                         f.write(extracted_text.strip())
                     logger.info(f"Extracted EPUB text to {output_path}")
                 else:
                     logger.warning(f"No extractable text found in EPUB {input_path.name}.")
                     # Create an empty or placeholder file
                     with open(output_path, 'w', encoding='utf-8') as f:
                         f.write("")
                     # Consider raising an error if no text is a failure condition
                     # raise ValueError("No extractable text found in EPUB.")


             except FileNotFoundError:
                 logger.error(f"EPUB file not found: {input_path}")
                 raise FileNotFoundError(f"EPUB file not found: {input_path}")
             except zipfile.BadZipFile:
                 logger.error(f"Bad EPUB file (invalid zip): {input_path}")
                 raise zipfile.BadZipFile(f"Bad EPUB file (invalid zip): {input_path}")
             except Exception as e:
                 logger.error(f"Failed to extract EPUB text for {input_path.name}: {e}")
                 raise RuntimeError(f"Failed to extract EPUB text: {e}") from e


        elif doc_type == DocumentType.TXT:
            # Simply copy the file
            shutil.copy(input_path, output_path)
            logger.info(f"Copied TXT file to {output_path}")

        elif doc_type in [DocumentType.MP3, DocumentType.WAV]:
             # Assuming transcription for audio
             try:
                 from .transcription import transcribe_audio
                 # transcribe_audio should be async or run in executor
                 # It should save the transcript to a text file
                 transcript_path = await transcribe_audio(input_path, output_dir)
                 # Move the transcript to the expected processed path
                 shutil.move(transcript_path, output_path)
                 logger.info(f"Transcribed audio to text at {output_path}")
             except ImportError:
                 logger.warning("Transcription dependencies (like openai-whisper) not found. Cannot process audio.")
                 raise ImportError("Transcription dependencies not found. Cannot process audio.")
             except Exception as e:
                 logger.error(f"Failed to transcribe audio {input_path.name}: {e}")
                 raise RuntimeError(f"Failed to transcribe audio: {e}") from e

        elif doc_type in [DocumentType.MP4, DocumentType.MOV]:
             # Assuming transcription for video (extract audio then transcribe)
             try:
                 from .transcription import transcribe_video
                 # transcribe_video should be async or run in executor
                 # It should save the transcript to a text file
                 transcript_path = await transcribe_video(input_path, output_dir)
                 # Move the transcript to the expected processed path
                 shutil.move(transcript_path, output_path)
                 logger.info(f"Transcribed video audio to text at {output_path}")
             except ImportError:
                 logger.warning("Transcription dependencies (like openai-whisper, moviepy) not found. Cannot process video.")
                 raise ImportError("Transcription dependencies not found. Cannot process video.")
             except Exception as e:
                 logger.error(f"Failed to transcribe video audio for {input_path.name}: {e}")
                 raise RuntimeError(f"Failed to transcribe video audio: {e}") from e

        elif doc_type in [DocumentType.PNG, DocumentType.JPG]:
             # Assuming OCR for images
             try:
                 from .ocr import perform_ocr
                 # perform_ocr should be async or run in executor
                 # It should save the extracted text to a file
                 ocr_text_path = await perform_ocr(input_path, output_dir)
                 # Move the OCR text to the expected processed path
                 shutil.move(ocr_text_path, output_path)
                 logger.info(f"Performed OCR on image to text at {output_path}")
             except ImportError:
                 logger.warning("OCR dependencies (like pytesseract) not found. Cannot process images.")
                 raise ImportError("OCR dependencies not found. Cannot process images.")
             except Exception as e:
                 logger.error(f"Failed to perform OCR on {input_path.name}: {e}")
                 raise RuntimeError(f"Failed to perform OCR: {e}") from e


        elif doc_type == DocumentType.URL:
             # This case is reached if a URL was downloaded but its *downloaded file type* was UNKNOWN
             # or if the URL itself is the content (e.g., a plain text URL) - unlikely for extraction
             # If the URL downloader saved a file, its type would be handled above.
             # If the URL *is* the content (e.g., a simple text file URL), fetch its content.
             # This would require a separate function to fetch URL content directly as text.
             # For now, handle as an error if the downloaded file type was UNKNOWN.
             if not input_path.exists() or doc_type == DocumentType.UNKNOWN: # Check if download failed or resulted in unknown type
                  raise ValueError(f"Could not process URL content of unknown or unsupported type: {input_path.name}")
             # If input_path exists and has a known type, it's handled above.
             pass # Already handled if downloaded file had a recognized type


        else:
            logger.warning(f"No extraction method implemented for document type: {doc_type.name}")
            # Create an empty or placeholder file
            with open(output_path, 'w', encoding='utf-8') as f:
                 f.write("")
            raise NotImplementedError(f"Text extraction not implemented for type: {doc_type.name}")

        # Check if the output file was actually created
        if not output_path.exists() or output_path.stat().st_size == 0:
             logger.warning(f"Text extraction for {input_path.name} resulted in an empty file at {output_path}")
             # Decide if this is a failure or just no text was found
             # For now, let's treat an empty file as a potential issue but not necessarily a hard failure
             # depending on the downstream RAG behavior with empty text.
             # If it should be a failure:
             # raise RuntimeError("Text extraction resulted in an empty file.")

        return output_path

    except FileNotFoundError as e:
         logger.error(f"File not found during extraction: {e}")
         raise e
    except NotImplementedError as e:
         logger.error(f"Extraction method not implemented: {e}")
         raise e
    except Exception as e:
        logger.error(f"An error occurred during text extraction for {input_path.name}: {e}", exc_info=True)
        raise RuntimeError(f"Text extraction failed: {e}") from e


# --- URL Downloading Function (Kept from original) ---
# This was likely in downloader.py based on the dump structure, moved here for simplicity or keep in downloader.py and import
async def download_url(url: str, download_dir: Path) -> Path:
    """Downloads content from a URL to a file."""
    logger.info(f"Attempting to download URL: {url}")
    download_dir.mkdir(parents=True, exist_ok=True)

    # Attempt to get a filename from the URL or headers
    filename = os.path.basename(url)
    if not filename or len(filename) > 100: # Basic filename check
        # Generate a more robust filename if needed
        import hashlib
        filename = f"download_{hashlib.md5(url.encode()).hexdigest()[:10]}"

    # Add extension if missing based on mimetype (requires a HEAD request first)
    # or guess based on URL suffix
    if '.' not in filename:
         url_path = url.split('?')[0].split('#')[0] # Remove query params/fragment
         guessed_ext = os.path.splitext(url_path)[1]
         if guessed_ext:
              filename += guessed_ext
         else:
             # If still no extension, make an educated guess or default
             # This is tricky without a HEAD request or downloading a chunk
             filename += ".dat" # Default generic extension

    download_path = download_dir / filename
    logger.debug(f"Saving download to: {download_path}")

    async with httpx.AsyncClient() as client:
        try:
            # Use stream=True for potentially large files
            async with client.stream("GET", url, follow_redirects=True, timeout=30) as response: # Increased timeout
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                with open(download_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
            logger.info(f"Successfully downloaded URL to {download_path}")
            return download_path

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading {url}: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"HTTP error downloading URL: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error downloading {url}: {e}")
            raise RuntimeError(f"Request error downloading URL: {e}") from e
        except Exception as e:
             logger.error(f"An unexpected error occurred during download of {url}: {e}")
             raise RuntimeError(f"Unexpected error during download: {e}") from e


# --- Chunking is handled in rag_handler.py ---
