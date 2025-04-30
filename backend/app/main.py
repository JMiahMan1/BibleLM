import asyncio
import logging
import logging.config
import os
import shutil
import uuid
import httpx

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

# Import updated crud, schemas, tasks
from . import crud, schemas, tasks
# Import enums from constants.py
from .constants import DocumentStatus, DocumentType, ChatMessageRole # Import enums from constants
# Import get_db from database.py and AsyncSessionLocal, engine
from .database import get_db, AsyncSessionLocal, engine, init_db # Import init_db
from .config import settings
# Import dependencies including CurrentRagHandler
from .dependencies import CurrentSettings, DBSession, CurrentRagHandler
# Import file_processor, summarizer modules
from .utils import file_processor, summarizer
# Import RagHandler class explicitly for type hinting
from .utils.rag_handler import RagHandler

# Import models
from .models import Base, ChatSession, ChatMessage, Document, Source, Audio, AudioFile
from sqlalchemy import select # Keep import for direct queries if needed

from typing import AsyncGenerator, List
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel # Keep BaseModel import

DATABASE_PATH = settings.full_data_dir / "db" / "app.db"
# Ensure database directory exists
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb.db.duckdb").setLevel(logging.WARNING)
# Set whisper logging level carefully, can be verbose
logging.getLogger("whisper").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
# Use the lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting API server...")
    logger.info(f"Data directory: {settings.full_data_dir}")
    logger.info(f"Ollama URL: {settings.ollama.base_url}")
    logger.info(f"Vector store path: {settings.full_vector_store_path}")
    logger.info(f"Database path: {DATABASE_PATH}")
    try:
        # Initialize database tables using init_db from database.py
        logger.info("Calling database.init_db() in lifespan...")
        await init_db() # Call init_db from database module
        logger.info("database.init_db() completed.")
    except Exception as e:
        logger.error(f"Critical Error during database initialization in lifespan: {e}")
        # *** Re-raise the exception to halt application startup ***
        # This is crucial to prevent the app from running without a functional database.
        raise e

    # Ensure necessary directories exist
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_exports_dir.mkdir(parents=True, exist_ok=True)
    settings.db_dir.mkdir(parents=True, exist_ok=True)
    # Ensure vector store directory exists
    Path(settings.full_vector_store_path).mkdir(parents=True, exist_ok=True)
    logger.info("Data directories ensured.")

    # Optional: Health check for Ollama at startup
    try:
        # This uses the config setting for the base URL
        test_url = f"{settings.ollama.base_url}/api/tags" # A simple endpoint to check if Ollama is running
        async with httpx.AsyncClient() as client:
            response = await client.get(test_url, timeout=5)
            response.raise_for_status() # Raise an exception for bad status codes
        logger.info("Successfully connected to Ollama.")
    except httpx.HTTPStatusError as e:
        logger.error(f"Could not connect to Ollama at {settings.ollama.base_url}. Status code: {e.response.status_code}")
        logger.error("Please ensure Ollama is running and accessible.")
    except httpx.RequestError as e:
         logger.error(f"Could not connect to Ollama at {settings.ollama.base_url}. Request error: {e}")
         logger.error("Please ensure Ollama is running and accessible.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Ollama connection test: {e}")


    yield # Application startup complete

    logger.info("Shutting down API server...")
    # Clean up resources here if needed

# Initialize FastAPI app with the lifespan
app = FastAPI(title="Local NotebookLM Clone API", lifespan=lifespan)


# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Add other origins as needed for your frontend deployment
    # Example for Docker Compose frontend service name:
    "http://frontend:8080",
    # Add the origin where your frontend is being served from:
    "http://192.168.2.211:5000",
    # Add the backend API's own origin if you're testing from a tool on the server itself:
    "http://192.168.2.211:8000", # Optional, but can be helpful for testing
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in origins], # Convert PathLike objects to string if necessary
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Application State for WebSocket Connections ---
# Using a dictionary to map document ID to a list of connected websockets
websocket_connections: dict[int, list[WebSocket]] = {}

# --- Helper function to broadcast status updates via WebSocket ---
async def broadcast_status(doc_id: int, status: str, error_message: str | None = None):
    if doc_id in websocket_connections:
        # Create a JSON compatible message
        message_data = {"doc_id": doc_id, "status": status}
        if error_message:
            message_data["error_message"] = error_message

        # Send message to all connected websockets for this document ID
        # Create a copy of the list to safely iterate while allowing modifications
        for websocket in websocket_connections[doc_id][:]:
            try:
                await websocket.send_json(message_data)
            except WebSocketDisconnect:
                # If a websocket disconnects, remove it from the list
                logger.info(f"WebSocket disconnected for doc_id {doc_id}. Removing.")
                await remove_websocket_connection(doc_id, websocket)
            except Exception as e:
                logger.warning(f"Error broadcasting status to WebSocket for doc_id {doc_id}: {e}")
                # Consider removing websocket on other errors too
                # await remove_websocket_connection(doc_id, websocket)


# Helper function to remove a websocket connection safely
async def remove_websocket_connection(doc_id: int, websocket: WebSocket):
     if doc_id in websocket_connections:
        try:
            websocket_connections[doc_id].remove(websocket)
            if not websocket_connections[doc_id]:
                # Clean up the list if it becomes empty
                del websocket_connections[doc_id]
            logger.info(f"WebSocket removed for doc_id {doc_id}. Remaining connections: {len(websocket_connections.get(doc_id, []))}")
        except ValueError:
            logger.warning(f"Attempted to remove non-existent websocket for doc_id {doc_id}")
        except Exception as e:
            logger.error(f"Error removing websocket connection for doc_id {doc_id}: {e}")


# --- Background Tasks (modified to include WebSocket updates) ---

async def process_document_task_with_ws(db: AsyncSession, doc_id: int):
    """Background task for processing a document, broadcasting status via WebSocket."""
    # Ensure DB session is closed correctly after the task
    try:
        await broadcast_status(doc_id, DocumentStatus.PROCESSING.name)
        # Pass the async session to the task function
        await tasks.process_document_task(db, doc_id)
        # After the task completes, fetch the final status and broadcast
        doc = await crud.get_document(db, doc_id)
        if doc:
            # Broadcast the status name
            await broadcast_status(doc_id, doc.status.name, doc.error_message)
    except Exception as e:
        logger.exception(f"Error processing document {doc_id}: {e}", exc_info=True)
        # Update status to FAILED and broadcast error
        await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=str(e))
        # Broadcast the status name
        await broadcast_status(doc_id, DocumentStatus.FAILED.name, str(e))
    finally:
        # Ensure session is closed, especially in background tasks
        await db.close()


async def generate_summary_task_with_ws(db: AsyncSession, summary_request_data: dict):
    """Background task for generating summaries, broadcasting status via WebSocket."""
    # Reconstruct Pydantic model from dict
    request = schemas.SummaryRequest(**summary_request_data)
    doc_ids = request.document_ids
    output_format = request.format
    # Create a task identifier based on document IDs and format
    task_prefix = f"summary_{'_'.join(map(str, doc_ids))}_{output_format}"
    logger.info(f"Starting summary generation task ({task_prefix}) for docs: {doc_ids}")

    # Broadcast a starting status to relevant documents (if tracking per document)
    # Or implement a separate status tracking for summary tasks
    for doc_id in doc_ids:
         # You might want a more specific status like "SUMMARIZING"
         await broadcast_status(doc_id, f"SUMMARY_STARTED ({task_prefix})")

    try:
        # Pass the async session and request data (as a dictionary) to the background task
        # The task function will handle its own DB interactions and potentially WS updates
        await tasks.generate_summary_task(db, summary_request_data) # Pass dict or Pydantic model

        # After the task completes, broadcast a completion status
        for doc_id in doc_ids:
             # You might want a more specific status like "SUMMARY_COMPLETE"
             await broadcast_status(doc_id, f"SUMMARY_COMPLETED ({task_prefix})")

    except Exception as e:
        logger.exception(f"Error generating summary ({task_prefix}) for docs {doc_ids}: {e}", exc_info=True)
        # Broadcast a failed status
        for doc_id in doc_ids:
            # You might want a more specific status like "SUMMARY_FAILED"
            await broadcast_status(doc_id, f"SUMMARY_FAILED ({task_prefix})", str(e))
    finally:
        # Ensure session is closed
        await db.close()


# --- API Endpoints ---

# --- Document Endpoints ---

@app.post("/upload", response_model=schemas.UploadResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    db: DBSession, # Use dependency
    config: CurrentSettings, # Use dependency
    file: UploadFile = File(...)
):
    """Uploads a file for processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # Generate a unique filename to prevent conflicts
    unique_filename = f"{uuid.uuid4()}_{file.filename.replace(' ', '_')}"
    upload_path = config.uploads_dir / unique_filename
    logger.info(f"Receiving file: {file.filename}, saving to: {upload_path}")

    try:
        # Ensure the upload directory exists
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        # Save the uploaded file
        with open(upload_path, "wb") as buffer:
            # Use shutil.copyfileobj for potentially large files
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File saved successfully: {upload_path}")
    except Exception as e:
        logger.error(f"Failed to save uploaded file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        # Close the uploaded file
        file.file.close()

    # Determine document type based on file extension
    doc_type = file_processor.get_document_type(upload_path)
    if doc_type == DocumentType.UNKNOWN:
        # Remove the uploaded file if type is unknown/unsupported
        upload_path.unlink(missing_ok=True)
        logger.warning(f"Uploaded file type unknown/unsupported: {file.filename}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {upload_path.suffix}")

    # Create a document record in the database
    db_doc = await crud.create_document(db, filename=file.filename, original_path=str(upload_path), doc_type=doc_type)

    # Add the document processing task to background tasks
    # Pass the DB session to the background task
    background_tasks.add_task(process_document_task_with_ws, db, db_doc.id)
    logger.info(f"Added background task for processing document ID: {db_doc.id} with WS updates.")

    # Return the response model
    doc_response = schemas.DocumentResponse.from_orm(db_doc)
    return schemas.UploadResponse(
        message="File uploaded successfully, processing started.",
        document=doc_response
    )

@app.post("/ingest", response_model=schemas.UploadResponse, status_code=202)
async def ingest_url(
    request: schemas.IngestURLRequest,
    background_tasks: BackgroundTasks,
    db: DBSession, # Use dependency
    config: CurrentSettings, # Use dependency
):
    """Ingests a URL for processing (download, transcription, etc.)."""
    logger.info(f"Received URL for ingestion: {request.url}")

    # Create a document record with URL type
    db_doc = await crud.create_document(db, filename=request.url, original_path=request.url, doc_type=DocumentType.URL)

    # Add the background task for downloading and processing the URL
    # Pass the DB session to the background task
    background_tasks.add_task(process_document_task_with_ws, db, db_doc.id)
    logger.info(f"Added background task for downloading and processing URL, document ID: {db_doc.id} with WS updates.")

    # Return the response model
    doc_response = schemas.DocumentResponse.from_orm(db_doc)
    return schemas.UploadResponse(
        message="URL received successfully, download and processing started.",
        document=doc_response
    )

@app.get("/documents", response_model=list[schemas.DocumentResponse])
async def get_documents_list(db: DBSession, skip: int = 0, limit: int = 100):
    """Gets a list of all documents."""
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
    """Gets the processing status for a document."""
    db_doc = await crud.get_document(db, doc_id)
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Return task status using the schema
    # Convert status enum value back to enum member for schema
    return schemas.TaskStatusResponse(
        task_id=db_doc.id,
        status=DocumentStatus(db_doc.status),
        filename=db_doc.filename,
        error_message=db_doc.error_message
    )

# --- Chat Session Endpoints ---

chat_router = APIRouter(prefix="/api", tags=["chat"])

@chat_router.post("/sessions", response_model=schemas.ChatSessionResponse, status_code=201)
async def create_chat_session(
    request: schemas.ChatSessionCreate,
    db: DBSession
):
    """Creates a new chat session."""
    db_session = await crud.create_chat_session(db, title=request.title, document_ids=request.document_ids)
    # You might want to return a subset of session details or the full object
    return db_session

@chat_router.get("/sessions", response_model=List[schemas.ChatSessionResponse])
async def get_chat_sessions(db: DBSession, skip: int = 0, limit: int = 100):
    """Gets a list of all chat sessions."""
    sessions = await crud.get_chat_sessions(db, skip=skip, limit=limit)
    # Ensure documents relationship is loaded if returning in response
    return sessions

@chat_router.get("/sessions/{session_id}", response_model=schemas.ChatSessionResponse)
async def get_chat_session_details(session_id: int, db: DBSession):
    """Gets details for a specific chat session."""
    db_session = await crud.get_chat_session(db, session_id)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    # Ensure documents relationship is loaded if returning in response
    return db_session


@chat_router.get("/sessions/{session_id}/messages", response_model=List[schemas.ChatMessageResponse])
async def get_chat_session_messages(session_id: int, db: DBSession, skip: int = 0, limit: int = 100):
    """Gets messages for a specific chat session."""
    messages = await crud.get_chat_messages(db, session_id, skip=skip, limit=limit)
    return messages

# This endpoint is intended for the frontend to send a user query to a session
@chat_router.post("/query", response_model=schemas.ChatQueryResponse)
async def query_chat_session(
    request: schemas.ChatQueryRequest,
    db: DBSession, # Use dependency
    # Use RagHandler class for type hinting, imported explicitly
    rag_handler: RagHandler = Depends(CurrentRagHandler) # Inject RagHandler
):
    """Processes a user query within a chat session using RAG."""
    session_id = request.session_id
    user_question = request.question
    relevant_doc_ids = request.document_ids # Document IDs for grounding

    # Ensure the chat session exists
    session = await crud.get_chat_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found.")

    # Get previous messages for context (optional, for conversational memory)
    # This could involve fetching the last N messages from the session
    # For simplicity in this example, we focus on the current question and grounding docs.
    # previous_messages = await crud.get_chat_messages(db, session_id, limit=5) # Example fetching last 5 messages

    # Add the user's message to the session history first
    await crud.create_chat_message(db, session_id=session_id, role="user", content=user_question)


    # Use RAG to get relevant information from selected documents
    # Pass relevant_doc_ids to the RAG handler
    try:
        # Use the injected rag_handler instance to call query_rag
        rag_result = await rag_handler.query_rag(user_question, relevant_doc_ids=relevant_doc_ids) # Use the updated query_rag

        ollama_answer = rag_result.get('result', '')
        source_documents_info = rag_result.get('source_documents', [])

        # Extract document IDs from source_documents_info if available
        # This depends on the structure returned by rag_handler.query_rag
        # Assuming source_documents_info items have a 'metadata' field with 'source_doc_id'
        source_doc_ids_used = []
        for source_doc in source_documents_info:
            if 'metadata' in source_doc and 'source_doc_id' in source_doc['metadata']:
                 try:
                    source_doc_ids_used.append(int(source_doc['metadata']['source_doc_id']))
                 except ValueError:
                    logger.warning(f"Could not parse source_doc_id: {source_doc['metadata']['source_doc_id']}")


        # Fetch Document objects for the source documents used in RAG
        # This allows returning detailed document info in the response
        detailed_source_documents = await crud.get_documents_by_ids(db, source_doc_ids_used)


    except Exception as e:
        logger.error(f"RAG query failed for session {session_id}: {e}")
        # Add an error message to the chat session
        error_message_content = f"Error retrieving answer: {e}"
        await crud.create_chat_message(db, session_id=session_id, role="system", content=error_message_content)
        raise HTTPException(status_code=500, detail=f"Failed to get answer from RAG system: {e}")


    # Add the assistant's reply to the session history
    await crud.create_chat_message(db, session_id=session_id, role="assistant", content=ollama_answer)

    # Return the assistant's answer and source documents
    return schemas.ChatQueryResponse(
        answer=ollama_answer,
        source_documents=[schemas.DocumentResponse.from_orm(doc) for doc in detailed_source_documents]
    )


# Optional: Endpoint to add/remove documents from a chat session after creation
# You would need to implement the CRUD logic for ChatSessionDocument in crud.py
# @chat_router.post("/sessions/{session_id}/documents")
# async def update_session_documents(session_id: int, request: schemas.UpdateSessionDocumentsRequest, db: DBSession):
#      """Adds or removes documents from a chat session."""
#      # Ensure session and documents exist
#      session = await crud.get_chat_session(db, session_id)
#      if session is None:
#          raise HTTPException(status_code=404, detail="Chat session not found")
#      documents = await crud.get_documents_by_ids(db, request.document_ids)
#      if len(documents) != len(request.document_ids):
#          raise HTTPException(status_code=404, detail="One or more documents not found")

#      if request.link:
#          await crud.link_documents_to_session(db, session_id, request.document_ids)
#      else:
#          await crud.unlink_documents_from_session(db, session_id, request.document_ids)

#      return {"message": "Session documents updated"}


app.include_router(chat_router) # Include the chat router

# --- Summary Endpoint ---

@app.post("/summary", response_model=schemas.SummaryResponse, status_code=202)
async def generate_summary(
    request: schemas.SummaryRequest,
    background_tasks: BackgroundTasks,
    db: DBSession, # Use dependency
    config: CurrentSettings # Use dependency
):
    """Generates a summary for selected documents."""
    logger.info(f"Received summary request: Format={request.format}, Docs={request.document_ids}")

    if not request.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided for summary.")

    # Check if the documents are completed and available for summarization
    docs_to_summarize = await crud.get_completed_documents_by_ids(db, request.document_ids)

    if len(docs_to_summarize) != len(request.document_ids):
        found_ids = {doc.id for doc in docs_to_summarize}
        missing_ids = set(request.document_ids) - found_ids
        failed_or_pending_info = []
        for missing_id in missing_ids:
            doc = await crud.get_document(db, missing_id)
            if not doc:
                failed_or_pending_info.append(f"ID {missing_id} (Not Found)")
            # Compare with Enum member
            elif DocumentStatus(doc.status) != DocumentStatus.COMPLETED:
                 failed_or_pending_info.append(f"ID {missing_id} (Status: {doc.status})")

        if not docs_to_summarize:
             raise HTTPException(status_code=400, detail="None of the specified documents are ready for summarization.")
        else:
             logger.warning(f"Generating summary, but some documents are not ready or found: {failed_or_pending_info}")


    # Create a unique task identifier for the summary
    summary_task_id = f"summary_{'_'.join(map(str, request.document_ids))}_{request.format}_{uuid.uuid4().hex[:6]}"
    logger.info(f"Assigning summary task ID: {summary_task_id}")

    # Add the summary generation task to background tasks
    # Pass the DB session and the request data (as a dictionary) to the background task
    background_tasks.add_task(generate_summary_task_with_ws, db, request.dict())


    # Construct the potential download URL (frontend will use this if applicable)
    # The actual file might not exist yet if the task is in progress
    download_url = None
    if request.format in ["txt", "docx", "script", "audio"]:
         # Construct a predictable filename based on doc IDs and format
         base_filename = f"summary_{'_'.join(map(str, request.document_ids))}"
         extension = "txt" if request.format == "script" else request.format # Use txt for script for now
         if request.format == "audio": extension = "mp3" # Assuming mp3 for audio output
         generated_filename = f"{base_filename}.{extension}"
         # The frontend will need to poll or use WS to know when the file is ready
         # Use app.url_path_for with _external=True if frontend is on a different host/port
         download_url = app.url_path_for("download_file", file_type="summary", filename=generated_filename)


    # Return a response indicating that the task has started
    return schemas.SummaryResponse(
        message=f"Summary generation ({request.format}) started in background.",
        task_id=summary_task_id,
        # Provide download URL for file formats where download is directly possible
        download_url=download_url if request.format in ["txt", "docx", "script"] else None
        # Note: For audio, the download might require WebSocket notification or polling
        # or a separate endpoint to check if the audio file is ready for download.
    )

# --- Download Endpoint ---

@app.get("/download/{file_type}/{filename}")
async def download_file(file_type: str, filename: str, config: CurrentSettings):
    """Downloads a generated file (summary, audio)."""
    logger.info(f"Download request for type '{file_type}', filename '{filename}'")
    allowed_types = ["audio", "summary"] # Define allowed download types

    if file_type == "audio":
        base_path = config.audio_exports_dir
    elif file_type == "summary":
        base_path = config.audio_exports_dir # Assuming summaries are also exported here
    else:
        raise HTTPException(status_code=400, detail="Invalid file type for download.")

    file_path = base_path / filename

    # Basic security check: Prevent directory traversal
    # Resolve the requested path and the base directory path
    if not file_path.is_file():
        logger.error(f"Download failed: File not found at {file_path}")
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        # Resolve paths to their absolute and real paths, following symlinks
        resolved_path = file_path.resolve()
        base_resolved = base_path.resolve()

        # Check if the resolved file path is within the resolved base directory
        if not str(resolved_path).startswith(str(base_resolved)):
            logger.error(f"Download forbidden: Path traversal attempt detected for filename: {filename}")
            raise HTTPException(status_code=403, detail="Access forbidden.")

    except Exception as e:
        logger.error(f"Error resolving download path {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error accessing file path.")

    logger.info(f"Sending file for download: {file_path}")
    # Use FileResponse to return the file
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream') # Use octet-stream for generic download


# --- WebSocket Endpoint for Status Updates ---

@app.websocket("/ws/status/{doc_id}")
async def websocket_status_endpoint(websocket: WebSocket, doc_id: int, db: DBSession):
    """WebSocket endpoint to receive status updates for a specific document."""
    await websocket.accept()
    logger.info(f"WebSocket connection established for document ID: {doc_id}")

    # Add the new websocket connection to the dictionary
    if doc_id not in websocket_connections:
        websocket_connections[doc_id] = []
    websocket_connections[doc_id].append(websocket)

    try:
        # Optionally send the current status immediately upon connection
        current_doc = await crud.get_document(db, doc_id)
        if current_doc:
            # Send the status name
            await websocket.send_json({
                "doc_id": doc_id,
                "status": DocumentStatus(current_doc.status).name,
                "filename": current_doc.filename,
                "error_message": current_doc.error_message
            })
        else:
            await websocket.send_json({"doc_id": doc_id, "status": "NOT_FOUND", "filename": "Unknown", "error_message": None})


        # Keep the connection open, waiting for disconnect
        # The actual status updates are sent by the background tasks calling broadcast_status
        while True:
            # We don't expect messages from the client on this status endpoint,
            # but we can keep the connection alive or listen for a 'close' message
            # For now, just waiting for disconnect or an error
            data = await websocket.receive_text()
            logger.debug(f"Received message from websocket for doc_id {doc_id}: {data}")
            # Optionally process a 'close' message from the client
            if data == 'close':
                await websocket.close()
                break # Exit the loop on explicit close


    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected gracefully for document ID: {doc_id}")
    except Exception as e:
        logger.error(f"WebSocket error for document ID {doc_id}: {e}")
    finally:
        # Clean up the connection from the dictionary
        await remove_websocket_connection(doc_id, websocket)
        # Ensure the DB session used in the endpoint is closed
        await db.close()


# --- Studio Endpoints (assuming these exist and function independently) ---
# Retaining existing studio endpoints, adjust if their models/dependencies change

# @app.get("/api/sources/") # This endpoint seems redundant with /documents
# async def get_sources(session: DBSession):
#     """Gets a list of sources (likely documents)."""
#     # This might need to be re-evaluated based on the 'Source' model's purpose
#     # If Source is different from Document, implement logic here.
#     # If Source is same as Document, remove this or make it call get_documents
#     result = await session.execute(select(Document)) # Assuming Source maps to Document
#     documents = result.scalars().all()
#     # You might need to convert Document objects to a Source schema if one existed
#     return documents # Returning Document objects for now


@app.get("/api/studio/overview")
async def get_audio_overview(session: DBSession):
    """Gets an overview of audio notes/files."""
    # Assuming 'Audio' model is used for audio notes
    audio_notes_result = await session.execute(select(Audio))
    audio_notes = audio_notes_result.scalars().all()

    # Assuming 'AudioFile' model is used for processed audio files
    audio_files_result = await session.execute(select(AudioFile))
    audio_files = audio_files_result.scalars().all()

    # Combine or format data as needed for the studio overview response
    # This is a placeholder, adjust the response structure based on frontend needs
    overview_data = {
        "title": "Studio Overview",
        # Convert SQLAlchemy objects to dictionaries or Pydantic models if needed for serialization
        "audio_notes": [{"id": note.id, "generated_note": note.generated_note, "tool_used": note.tool_used} for note in audio_notes],
        "audio_files": [{"id": file.id, "audio_title": file.audio_title, "file_path": file.file_path, "duration": file.duration} for file in audio_files],
        "notes_placeholder": "Saved notes will appear here.", # Example placeholder
        "quick_links": ["Generate Audio Summary", "View Notes"] # Example links
    }
    return overview_data # Return the overview data
