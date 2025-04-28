import logging
from pathlib import Path
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import Document, DocumentStatus, DocumentType
from . import crud
from .utils import file_processor, downloader, rag_handler, summarizer
from .schemas import SummaryRequest

logger = logging.getLogger(__name__)

# --- Ingestion Task ---

async def process_document_task(db: AsyncSession, doc_id: int):
    """The main background task for processing a single document."""
    logger.info(f"Starting background processing for document ID: {doc_id}")
    doc = await crud.get_document(db, doc_id)
    if not doc:
        logger.error(f"Document ID {doc_id} not found in database for processing.")
        return

    try:
        # 1. Update status to PROCESSING
        await crud.update_document_status(db, doc_id, DocumentStatus.PROCESSING)

        # 2. Determine source path (uploaded file or URL)
        source_path_str = doc.original_path
        is_url = doc.document_type == DocumentType.URL
        file_to_process = None

        if is_url:
            logger.info(f"Document {doc_id} is a URL, attempting download...")
            await crud.update_document_status(db, doc_id, DocumentStatus.DOWNLOADING)
            downloaded_path = downloader.download_media(source_path_str, settings.uploads_dir)
            if downloaded_path:
                file_to_process = downloaded_path
                # Update doc record with actual filename and type after download
                doc.filename = file_to_process.name
                doc.document_type = file_processor.get_document_type(file_to_process)
                doc.original_path = str(file_to_process) # Store the path to the downloaded file now
                await crud.update_document_status(db, doc_id, DocumentStatus.PROCESSING) # Back to processing
                await db.commit() # Save changes
                await db.refresh(doc)
            else:
                raise ValueError(f"Failed to download media from URL: {source_path_str}")
        else:
            file_to_process = Path(source_path_str) # Path in uploads dir

        if not file_to_process or not file_to_process.exists():
             raise FileNotFoundError(f"Source file not found for processing: {file_to_process}")

        # 3. Extract Text (handles transcription/OCR internally)
        logger.info(f"Extracting text from {file_to_process} (Type: {doc.document_type.name})")
        extracted_text = file_processor.extract_text_from_file(file_to_process, doc.document_type)

        if not extracted_text.strip():
            logger.warning(f"No text extracted from document {doc_id}. Marking as completed (empty).")
            await crud.update_document_status(db, doc_id, DocumentStatus.COMPLETED)
            await crud.update_document_processed_path(db, doc_id, "") # Indicate no text path needed
            return # Nothing more to do

        # 4. Save Extracted Text
        processed_text_filename = f"{doc_id}_{doc.filename}.txt"
        processed_text_path = settings.processed_dir / processed_text_filename
        with open(processed_text_path, "w", encoding='utf-8') as f:
            f.write(extracted_text)
        logger.info(f"Saved extracted text to: {processed_text_path}")
        await crud.update_document_processed_path(db, doc_id, str(processed_text_path))

        # 5. Add to Vector Store (RAG)
        metadata = {"source_filename": doc.filename, "original_path": doc.original_path}
        # Run synchronous RAG indexing in executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, rag_handler.add_text_to_vector_store, extracted_text, metadata, doc_id)
        # rag_handler.add_text_to_vector_store(extracted_text, metadata, doc_id) # Sync version

        # 6. Mark as Completed
        await crud.update_document_status(db, doc_id, DocumentStatus.COMPLETED)
        logger.info(f"Successfully processed document ID: {doc_id}")

    except Exception as e:
        logger.exception(f"Error processing document ID {doc_id}: {e}", exc_info=True)
        await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=str(e))

# --- Summary Task ---

async def generate_summary_task(db: AsyncSession, request_data: dict):
    """Background task for generating summaries (especially audio)."""
    # Reconstruct Pydantic model or pass necessary data in dict
    request = schemas.SummaryRequest(**request_data)
    doc_ids = request.document_ids
    output_format = request.format
    # Create a unique ID for this summary task if needed, or use first doc ID
    task_id = f"summary_{doc_ids[0]}_{output_format}" if doc_ids else "summary_unknown"
    logger.info(f"Starting summary generation task ({task_id}): Format={output_format}, Docs={doc_ids}")

    try:
        docs_to_summarize = await crud.get_completed_documents_by_ids(db, doc_ids)
        if not docs_to_summarize:
            raise ValueError("No completed documents found for summarization.")

        full_text = ""
        for doc in docs_to_summarize:
            if doc.processed_text_path and Path(doc.processed_text_path).exists():
                with open(doc.processed_text_path, 'r', encoding='utf-8') as f:
                    full_text += f.read() + "\n\n"
            else:
                 logger.warning(f"Skipping doc {doc.id} in summary: processed text not found at {doc.processed_text_path}")


        if not full_text.strip():
             raise ValueError("No text content available in the selected documents to generate summary.")

        # Use LangChain documents for summarizer chain
        langchain_docs = [LangchainDocument(page_content=full_text)] # Treat combined text as one doc for now
        # Or re-chunk if necessary: langchain_docs = rag_handler.chunk_text(full_text)

        summary_text = await summarizer.generate_text_summary(langchain_docs)

        # Define output filename base
        base_filename = f"summary_{'_'.join(map(str, doc_ids))}"
        output_file = None

        if output_format == "txt":
            output_path = settings.audio_exports_dir / f"{base_filename}.txt" # Save text also in exports? Or just return?
            with open(output_path, "w", encoding='utf-8') as f:
                f.write(summary_text)
            output_file = output_path
        elif output_format == "docx":
            output_path = settings.audio_exports_dir / f"{base_filename}.docx"
            summarizer.save_summary_docx(summary_text, output_path)
            output_file = output_path
        elif output_format == "script":
            script_text = summarizer.create_script(summary_text)
            output_path = settings.audio_exports_dir / f"{base_filename}_script.txt"
            with open(output_path, "w", encoding='utf-8') as f:
                f.write(script_text)
            output_file = output_path
        elif output_format == "audio":
            script_text = summarizer.create_script(summary_text) # Generate script first
            output_path = settings.audio_exports_dir / f"{base_filename}.mp3"
            # Run sync TTS generation in executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, summarizer.generate_audio_summary, script_text, output_path)
            # summarizer.generate_audio_summary(script_text, output_path) # Sync version
            output_file = output_path

        logger.info(f"Summary task ({task_id}) completed. Output: {output_file}")
        # How to notify user? Could update a 'summary_tasks' table, or use websockets/polling on frontend.

    except Exception as e:
        logger.exception(f"Error generating summary ({task_id}): {e}", exc_info=True)
        # Log error, potentially update a status for the summary task if tracked separately
