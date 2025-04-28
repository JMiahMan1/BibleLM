import logging
import logging.config
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import shutil
import os
import uuid

from . import schemas, crud, tasks, database
from .config import settings
from .dependencies import DBSession, CurrentSettings
from .utils import file_processor, rag_handler
from .database import DocumentStatus, DocumentType

# --- Logging Setup ---
# Basic logging config (customize as needed, e.g., using logging.yaml)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Suppress overly verbose libraries if needed
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb.db.duckdb").setLevel(logging.WARNING) # Chroma can be verbose
logging.getLogger("whisper").setLevel(logging.INFO) # Keep Whisper info
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(title="Local NotebookLM Clone API")

# --- CORS Middleware ---
# Allow requests from your frontend development server and deployed frontend
origins = [
    "http://localhost:3000",  # Common React/Next.js dev port
    "http://127.0.0.1:3000",
    # Add deployed frontend URL here if applicable
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    logger.info("Starting API server...")
    logger.info(f"Data directory: {settings.full_data_dir}")
    logger.info(f"Ollama URL: {settings.ollama.base_url}")
    logger.info(f"Vector store path: {settings.full_vector_store_path}")
    # Initialize database tables
    await database.init_db()
    logger.info("Database initialized.")
    # Check Ollama connection (optional but helpful)
    try:
        llm = rag_handler.get_llm()
        # A simple way to test connection, might vary by Langchain version
        # This might make startup slow, consider doing it async or removing
        # await llm.ainvoke("Respond with OK")
        logger.info("Successfully connected to Ollama.")
    except Exception as e:
        logger.error(f"Could not connect to Ollama at {settings.ollama.base_url}: {e}")
        # Decide if this should prevent startup? For now, just log error.

    # Ensure required directories exist (also done in config loading, but good practice)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_exports_dir.mkdir(parents=True, exist_ok=True)
    settings.db_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.full_vector_store_path).mkdir(parents=True, exist_ok=True)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down API server...")
    # Add any cleanup tasks here if needed
    # await database.engine.dispose() # Close DB connections gracefully


# --- API Endpoints ---

@app.post("/upload", response_model=schemas.UploadResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    db: DBSession,
    config: CurrentSettings,
    file: UploadFile = File(...)
):
    """
    Handles file uploads, saves the file, creates a DB record,
    and triggers background processing.
    """
    if not file.filename:
         raise HTTPException(status_code=400, detail="No filename provided.")

    # Sanitize filename (optional but recommended)
    safe_filename = f"{uuid.uuid4()}_{file.filename.replace(' ', '_')}"
    upload_path = config.uploads_dir / safe_filename
    logger.info(f"Receiving file: {file.filename}, saving to: {upload_path}")

    try:
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File saved successfully: {upload_path}")
    except Exception as e:
        logger.error(f"Failed to save uploaded file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        file.file.close()

    doc_type = file_processor.get_document_type(upload_path)
    if doc_type == DocumentType.UNKNOWN:
         # Optionally delete the file or mark as failed immediately
         # upload_path.unlink(missing_ok=True)
         logger.warning(f"Uploaded file type unknown/unsupported: {file.filename}")
         # Create a record anyway but mark as failed? Or reject upload?
         # For now, let's reject it.
         upload_path.unlink(missing_ok=True)
         raise HTTPException(status_code=400, detail=f"Unsupported file type: {upload_path.suffix}")


    # Create DB entry
    db_doc = await crud.create_document(db, filename=file.filename, original_path=str(upload_path), doc_type=doc_type)

    # Add processing task to background
    background_tasks.add_task(tasks.process_document_task, db, db_doc.id)
    logger.info(f"Added background task for processing document ID: {db_doc.id}")

    # Use the ORM model directly with Pydantic's orm_mode
    doc_response = schemas.DocumentResponse.from_orm(db_doc)

    return schemas.UploadResponse(
        message="File uploaded successfully, processing started.",
        document=doc_response
    )

@app.post("/ingest", response_model=schemas.UploadResponse, status_code=202)
async def ingest_url(
    request: schemas.IngestURLRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    config: CurrentSettings,
):
    """
    Handles URL ingestion, creates a DB record, and triggers background processing (download + process).
    """
    logger.info(f"Received URL for ingestion: {request.url}")
    # Create DB entry with URL as original path and type URL
    db_doc = await crud.create_document(db, filename=request.url, original_path=request.url, doc_type=DocumentType.URL)

    # Add processing task to background (will handle download first)
    background_tasks.add_task(tasks.process_document_task, db, db_doc.id)
    logger.info(f"Added background task for downloading and processing URL, document ID: {db_doc.id}")

    doc_response = schemas.DocumentResponse.from_orm(db_doc)

    return schemas.UploadResponse(
        message="URL received successfully, download and processing started.",
        document=doc_response
    )


@app.get("/documents", response_model=list[schemas.DocumentResponse])
async def get_documents_list(db: DBSession, skip: int = 0, limit: int = 100):
    """Lists available documents and their status."""
    documents = await crud.get_documents(db, skip=skip, limit=limit)
    return documents

@app.get("/documents/{doc_id}", response_model=schemas.DocumentResponse)
async def get_document_details(doc_id: int, db: DBSession):
    """Gets details for a specific document."""
    db_doc = await crud.get_document(db, doc_id)
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return db_doc

@app.get("/status/{doc_id}", response_model=schemas.TaskStatusResponse)
async def get_task_status(doc_id: int, db: DBSession):
    """Gets the processing status for a specific document."""
    db_doc = await crud.get_document(db, doc_id)
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return schemas.TaskStatusResponse(
        task_id=db_doc.id,
        status=db_doc.status,
        filename=db_doc.filename,
        error_message=db_doc.error_message
    )


@app.post("/chat", response_model=schemas.ChatResponse)
async def chat_with_documents(request: schemas.ChatRequest, db: DBSession):
    """Handles chat messages, performs RAG against specified documents."""
    logger.info(f"Received chat message: '{request.message[:50]}...' for docs: {request.document_ids}")

    # 1. Validate that requested documents exist and are processed
    relevant_docs_db = []
    if request.document_ids:
        relevant_docs_db = await crud.get_completed_documents_by_ids(db, request.document_ids)
        if len(relevant_docs_db) != len(request.document_ids):
             found_ids = {doc.id for doc in relevant_docs_db}
             missing_ids = set(request.document_ids) - found_ids
             # Check status of missing ones
             failed_or_pending = []
             for missing_id in missing_ids:
                 doc = await crud.get_document(db, missing_id)
                 if not doc:
                     failed_or_pending.append(f"ID {missing_id} (Not Found)")
                 elif doc.status != DocumentStatus.COMPLETED:
                     failed_or_pending.append(f"ID {missing_id} (Status: {doc.status.name})")

             logger.warning(f"Chat request included non-completed documents: {failed_or_pending}")
             # Option 1: Error out
             # raise HTTPException(status_code=400, detail=f"Cannot chat with non-completed documents: {', '.join(failed_or_pending)}")
             # Option 2: Proceed with only the completed ones (chosen here)
             if not relevant_docs_db:
                  raise HTTPException(status_code=400, detail="None of the specified documents are ready for chat.")

    # 2. Perform RAG query
    try:
        # Pass only the IDs of the successfully processed documents
        completed_doc_ids = [doc.id for doc in relevant_docs_db]
        rag_result = await rag_handler.query_rag(request.message, completed_doc_ids)
        answer = rag_result.get("result", "Sorry, I couldn't find an answer based on the provided documents.")

        # 3. Format response with sources
        source_docs_info = []
        source_doc_ids_used = set()
        if rag_result.get("source_documents"):
            for source_chunk in rag_result["source_documents"]:
                metadata = source_chunk.metadata
                source_doc_id = metadata.get("source_doc_id")
                if source_doc_id:
                     source_doc_ids_used.add(int(source_doc_id))

        # Create DocumentResponse objects for the sources used
        source_docs_response = [schemas.DocumentResponse.from_orm(doc) for doc in relevant_docs_db if doc.id in source_doc_ids_used]

        return schemas.ChatResponse(response=answer, sources=source_docs_response)

    except RuntimeError as e:
         logger.error(f"RAG query failed during chat: {e}")
         raise HTTPException(status_code=500, detail=f"Error during RAG processing: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error during chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


@app.post("/summary", response_model=schemas.SummaryResponse, status_code=202)
async def generate_summary(
    request: schemas.SummaryRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    config: CurrentSettings
):
    """
    Triggers summary generation. For text-based formats, it might return
    directly or start a background task. For audio, it always starts a
    background task.
    """
    logger.info(f"Received summary request: Format={request.format}, Docs={request.document_ids}")

    if not request.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided for summary.")

    # Check if documents are ready
    docs_to_summarize = await crud.get_completed_documents_by_ids(db, request.document_ids)
    if len(docs_to_summarize) != len(request.document_ids):
        found_ids = {doc.id for doc in docs_to_summarize}
        missing_ids = set(request.document_ids) - found_ids
        failed_or_pending = []
        for missing_id in missing_ids:
            doc = await crud.get_document(db, missing_id)
            if not doc:
                failed_or_pending.append(f"ID {missing_id} (Not Found)")
            elif doc.status != DocumentStatus.COMPLETED:
                failed_or_pending.append(f"ID {missing_id} (Status: {doc.status.name})")
        if not docs_to_summarize:
            raise HTTPException(status_code=400, detail="None of the specified documents are ready for summarization.")
        else:
            # Proceed with available ones, but maybe notify the user?
            logger.warning(f"Generating summary, but some documents are not ready: {failed_or_pending}")


    # Trigger background task for all formats for consistency and responsiveness
    # Pass request data as a dict because Pydantic models might not be directly serializable
    # depending on the background task runner (though FastAPI's default often handles them).
    background_tasks.add_task(tasks.generate_summary_task, db, request.dict())

    # Task ID for client polling (optional, needs tracking mechanism)
    summary_task_id = f"summary_{'_'.join(map(str, request.document_ids))}_{request.format}"

    return schemas.SummaryResponse(
        message=f"Summary generation ({request.format}) started in background. Task ID: {summary_task_id}",
        task_id=None # No simple way to return generated task ID from FastAPI BackgroundTasks
        # To return a real task ID, you'd need Celery or similar,
        # or store summary task status in the DB.
    )

# Endpoint to download generated summaries (if saved as files)
# Note: Requires knowing the filename. The frontend might poll a status endpoint
# which returns the filename/URL once the background task is complete.
@app.get("/download/{file_type}/{filename}")
async def download_file(file_type: str, filename: str, config: CurrentSettings):
    """Allows downloading of generated summary files."""
    logger.info(f"Download request for type '{file_type}', filename '{filename}'")
    allowed_types = ["audio", "summary"] # Define allowed download types/folders
    if file_type == "audio":
        base_path = config.audio_exports_dir
    elif file_type == "summary": # e.g., docx, txt scripts
         base_path = config.audio_exports_dir # Or a different 'exports' dir if preferred
    else:
        raise HTTPException(status_code=400, detail="Invalid file type for download.")

    file_path = base_path / filename

    if not file_path.is_file():
        logger.error(f"Download failed: File not found at {file_path}")
        raise HTTPException(status_code=404, detail="File not found.")

    # Security check: Ensure the path doesn't escape the intended directory
    try:
        resolved_path = file_path.resolve()
        base_resolved = base_path.resolve()
        if not str(resolved_path).startswith(str(base_resolved)):
            logger.error(f"Download forbidden: Path traversal attempt: {filename}")
            raise HTTPException(status_code=403, detail="Access forbidden.")
    except Exception as e: # Catch potential resolution errors too
         logger.error(f"Error resolving download path {file_path}: {e}")
         raise HTTPException(status_code=500, detail="Error accessing file path.")


    logger.info(f"Sending file for download: {file_path}")
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')


# Optional: Add WebSocket endpoint for real-time status updates
# from fastapi import WebSocket, WebSocketDisconnect
# @app.websocket("/ws/status")
# async def websocket_status_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             # Example: Client sends doc ID it's interested in
#             data = await websocket.receive_text()
#             doc_id = int(data)
#             # Periodically check status and send update
#             # This needs a more robust mechanism (e.g., pub/sub from background tasks)
#             # For now, just simulate checking status
#             async with database.AsyncSessionLocal() as session:
#                  status = await crud.get_document(session, doc_id)
#                  if status:
#                       await websocket.send_json({"doc_id": doc_id, "status": status.status.name})
#                  else:
#                       await websocket.send_json({"doc_id": doc_id, "status": "NOT_FOUND"})
#             await asyncio.sleep(5) # Poll every 5 seconds
#     except WebSocketDisconnect:
#         logger.info("WebSocket client disconnected")
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")
#         await websocket.close(code=1011)
