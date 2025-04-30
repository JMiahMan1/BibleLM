import asyncio
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import os
import shutil

# Import get_db from database.py for session management in tasks
from .database import get_db
# Import Document model from models.py
from .models import Document
# Import Enums from constants.py
from .constants import DocumentStatus, DocumentType
from .utils import file_processor, summarizer, rag_handler
from .config import settings # Import settings

logger = logging.getLogger(__name__)

async def process_document_task(db: AsyncSession, doc_id: int):
    """
    Background task to process an uploaded or ingested document.
    Includes: downloading (if URL), text extraction, chunking, and embedding.
    """
    logger.info(f"Starting processing for document ID: {doc_id}")
    doc = await crud.get_document(db, doc_id) # Use await with async crud function
    if not doc:
        logger.error(f"Document with ID {doc_id} not found for processing.")
        # The broadcast_status will handle sending NOT_FOUND if called from main.py
        return

    # Use the status enum member directly
    await crud.update_document_status(db, doc_id, DocumentStatus.PROCESSING)

    try:
        original_path = Path(doc.original_path)
        processed_path = None # Initialize processed_path

        # 1. Download the document if it's a URL
        if doc.document_type == DocumentType.URL:
            logger.info(f"Document {doc_id} is a URL, attempting download: {doc.original_path}")
            await crud.update_document_status(db, doc_id, DocumentStatus.DOWNLOADING) # Update status
            try:
                 # downloader.download_url is assumed to be async or run in executor
                 # Ensure downloader.download_url is defined and correctly handles paths
                 # Assuming downloader.download_url saves to uploads_dir and returns the path
                 downloaded_path = await file_processor.download_url(doc.original_path, settings.uploads_dir)
                 original_path = Path(downloaded_path) # Use the downloaded file path
                 logger.info(f"Downloaded URL {doc_id} to: {original_path}")
                 await crud.update_document_status(db, doc_id, DocumentStatus.PROCESSING) # Back to processing after download

            except Exception as e:
                 logger.error(f"Failed to download URL {doc_id}: {e}")
                 await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=f"Download failed: {e}")
                 return # Stop processing if download fails


        # 2. Extract text based on document type
        logger.info(f"Extracting text for document {doc_id} ({doc.document_type.name}) from {original_path}")
        try:
            # file_processor.extract_text is assumed to handle various types and be async or run in executor
            # It should return the path to the processed text file (e.g., in processed_dir)
            extracted_text_path = await file_processor.extract_text(original_path, doc.document_type, settings.processed_dir)
            processed_path = Path(extracted_text_path)
            logger.info(f"Text extracted for document {doc_id} to: {processed_path}")
            await crud.update_document_processed_path(db, doc_id, str(processed_path)) # Update DB with processed path

        except Exception as e:
            logger.error(f"Failed to extract text for document {doc_id}: {e}")
            await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=f"Text extraction failed: {e}")
            return # Stop processing if extraction fails


        # 3. Chunk and Embed the text
        if processed_path and processed_path.exists():
            logger.info(f"Chunking and embedding text for document {doc_id} from {processed_path}")
            try:
                # rag_handler.add_document_to_vector_store should read the text, chunk, and embed
                # It needs the document ID to associate chunks with the source document
                await rag_handler.add_document_to_vector_store(processed_path, doc_id=doc_id)
                logger.info(f"Chunking and embedding completed for document {doc_id}.")
                await crud.update_document_status(db, doc_id, DocumentStatus.COMPLETED) # Mark as completed

            except Exception as e:
                logger.error(f"Failed to chunk and embed document {doc_id}: {e}")
                await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=f"Embedding failed: {e}")
                return # Stop processing if embedding fails
        else:
             logger.error(f"Processed text file not found for document {doc_id} at {processed_path}")
             await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message="Processed text file not found.")
             return


    except Exception as e:
        # Catch any other unexpected errors during processing
        logger.error(f"An unexpected error occurred during processing for document {doc_id}: {e}", exc_info=True)
        await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=f"Unexpected error during processing: {e}")

    logger.info(f"Finished processing for document ID: {doc_id}")
    # The status is updated at various stages and finally marked COMPLETED or FAILED


async def generate_summary_task(db: AsyncSession, summary_request_data: dict):
    """
    Background task to generate a summary for selected documents.
    Handles different output formats (txt, docx, script, audio).
    """
    # Reconstruct Pydantic model from dict if needed, or just use the dict
    # request = schemas.SummaryRequest(**summary_request_data) # Example if reconstructing

    doc_ids = summary_request_data.get('document_ids', [])
    output_format = summary_request_data.get('format', 'txt')
    logger.info(f"Starting summary generation task for docs: {doc_ids}, format: {output_format}")

    if not doc_ids:
        logger.warning("Summary task called with no document IDs.")
        # You might need to update a status somewhere if this was triggered by a UI element
        return

    # Fetch the content from the processed text files of the selected documents
    try:
        # Use crud function to get completed documents by IDs
        completed_docs = await crud.get_completed_documents_by_ids(db, doc_ids)
        if not completed_docs:
             logger.error(f"None of the specified documents {doc_ids} are completed for summarization.")
             # Update relevant document statuses or a dedicated summary task status
             for doc_id in doc_ids:
                 await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message="Document not ready for summary")
             return

        # Concatenate text content from completed documents
        all_text = ""
        for doc in completed_docs:
            if doc.processed_text_path and Path(doc.processed_text_path).exists():
                try:
                    with open(doc.processed_text_path, 'r', encoding='utf-8') as f:
                        all_text += f.read() + "\n\n" # Add separator between documents
                except Exception as e:
                     logger.error(f"Error reading processed text for document {doc.id}: {e}")
                     # Decide how to handle: skip doc, fail task
                     continue # Skip this document's text


        if not all_text.strip():
            logger.error("No valid text content found for summarization.")
            # Update relevant document statuses or a dedicated summary task status
            for doc_id in doc_ids:
                 await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message="No text content found for summary")
            return

        # Generate the summary using the summarizer utility
        logger.info(f"Generating summary (format: {output_format}) using LLM...")
        try:
            # Assuming summarizer.generate_summary handles calling the LLM
            # Pass the concatenated text and desired format
            summary_result = await summarizer.generate_summary(all_text, output_format=output_format)
            generated_content = summary_result.get('summary') # Assuming it returns a dict with 'summary' or similar

            if not generated_content:
                 raise ValueError("Summarizer returned empty content.")

            logger.info(f"Summary generation complete. Content length: {len(generated_content)}")

            # --- Save the generated summary based on format ---
            base_filename = f"summary_{'_'.join(map(str, doc_ids))}"
            output_path = settings.audio_exports_dir # Assuming summaries are saved in audio_exports_dir

            if output_format == "txt" or output_format == "script":
                # Save as a .txt file
                filename = f"{base_filename}.txt"
                full_output_path = output_path / filename
                with open(full_output_path, 'w', encoding='utf-8') as f:
                    f.write(generated_content)
                logger.info(f"Text summary saved to: {full_output_path}")
                # Optionally, update document statuses to indicate summary availability
                # For example, add a flag or status specific to summary generated.

            elif output_format == "docx":
                 # Assuming summarizer has a function to generate docx or you do it here
                 # This would require a library like python-docx
                 logger.warning("DOCX summary generation not fully implemented. Saving as .txt.")
                 # Fallback to saving as .txt for now
                 filename = f"{base_filename}.txt"
                 full_output_path = output_path / filename
                 with open(full_output_path, 'w', encoding='utf-8') as f:
                     f.write(generated_content)
                 # TODO: Implement actual DOCX generation

            elif output_format == "audio":
                 # Assuming summarizer has a function for TTS or you do it here
                 # This would require a TTS library like Coqui TTS, Bark, or calling a service
                 logger.warning("Audio summary generation not fully implemented.")
                 # TODO: Implement actual audio generation
                 # You would save an audio file (e.g., .mp3) to output_path
                 # And potentially create an AudioFile database entry
                 # filename = f"{base_filename}.mp3"
                 # full_output_path = output_path / filename
                 # ... TTS generation code ...
                 pass # Placeholder for audio generation

            # For audio, you might need a separate mechanism to notify the frontend
            # when the file is ready for download, potentially using the WebSocket
            # or updating an AudioFile entry status in the DB.


        except Exception as e:
            logger.error(f"Failed during summary generation or saving: {e}")
            # Update relevant document statuses or a dedicated summary task status
            for doc_id in doc_ids:
                 await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message="Summary generation failed")


    except Exception as e:
        logger.error(f"An unexpected error occurred during summary task for docs {doc_ids}: {e}", exc_info=True)
        # Update relevant document statuses or a dedicated summary task status
        for doc_id in doc_ids:
            await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=f"Unexpected error in summary task: {e}")

    logger.info(f"Finished summary generation task for docs: {doc_ids}")
    # Status updates (e.g., SUMMARY_COMPLETED) would ideally be handled via WS or DB flags
