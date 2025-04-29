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

from . import crud, database, schemas, tasks
from .config import settings
from .dependencies import CurrentSettings, DBSession
from .utils import file_processor, rag_handler
from .database import DocumentStatus, DocumentType, engine, Base

from typing import AsyncGenerator
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .database import AsyncSessionLocal, engine, Base
from sqlalchemy import select
from .models import Source, Chat, Audio
from pydantic import BaseModel

DATABASE_PATH = settings.full_data_dir / "db" / "app.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb.db.duckdb").setLevel(logging.WARNING)
logging.getLogger("whisper").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(title="Local NotebookLM Clone API")

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Application State for WebSocket Connections ---
websocket_connections: dict[int, list[WebSocket]] = {}


# --- Event Handlers ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting API server...")
    logger.info(f"Data directory: {settings.full_data_dir}")
    logger.info(f"Ollama URL: {settings.ollama.base_url}")
    logger.info(f"Vector store path: {settings.full_vector_store_path}")
    logger.info(f"Database path: {DATABASE_PATH}")
    try:
        await database.init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.error(f"Error during database initialization in lifespan: {e}")
        # Consider raising the exception here to prevent the app from starting
        # if the database fails to initialize.
        # raise

    try:
        llm = rag_handler.get_llm()
        logger.info("Successfully connected to Ollama.")
    except Exception as e:
        logger.error(f"Could not connect to Ollama at {settings.ollama.base_url}: {e}")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_exports_dir.mkdir(parents=True, exist_ok=True)
    settings.db_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.full_vector_store_path).mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down API server...")


app = FastAPI(title="Local NotebookLM Clone API", lifespan=lifespan)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    await create_db_and_tables()
    global rag_handler
    rag_handler = RagHandler()
    await rag_handler.ainit()

chat_router = APIRouter(prefix="/api", tags=["chat"])

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str

@chat_router.post("/chat/")
async def chat_with_ollama(chat_request: ChatRequest, session: AsyncSession = Depends(get_db)):
    user_question = chat_request.question

    if rag_handler is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")

    relevant_info = await rag_handler.query(user_question)

    prompt = f"""Answer the following question based on the provided context:
    Context: {relevant_info}
    Question: {user_question}
    Answer: """

    try:
        async with httpx.AsyncClient() as client:
            ollama_url = "{settings.ollama.base_url}/api/generate"
            response = await client.post(ollama_url, json={"prompt": prompt, "stream": False})
            response.raise_for_status()
            ollama_response_data = response.json()
            ollama_answer = ollama_response_data.get("response", "")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Ollama: {e}")
    except ImportError:
        raise HTTPException(status_code=500, detail="httpx library is required. Install it: pip install httpx")

    new_chat = Chat(question=user_question, answer=ollama_answer)
    session.add(new_chat)
    await session.commit()
    await session.refresh(new_chat)

    return ChatResponse(answer=ollama_answer)

async def broadcast_status(doc_id: int, status: str, error_message: str | None = None):
    if doc_id in websocket_connections:
        for websocket in websocket_connections[doc_id]:
            try:
                await websocket.send_json({"doc_id": doc_id, "status": status, "error_message": error_message})
            except Exception as e:
                logger.warning(f"Error broadcasting status to WebSocket for doc_id {doc_id}: {e}")


async def process_document_task_with_ws(db: DBSession, doc_id: int):
    await broadcast_status(doc_id, DocumentStatus.PROCESSING.name)
    try:
        await tasks.process_document_task(db, doc_id)
        doc = await crud.get_document(db, doc_id)
        if doc:
            await broadcast_status(doc_id, doc.status.name, doc.error_message)
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {e}")
        await crud.update_document_status(db, doc_id, DocumentStatus.FAILED, error_message=str(e))
        await broadcast_status(doc_id, DocumentStatus.FAILED.name, str(e))


async def generate_summary_task_with_ws(db: DBSession, summary_request: dict):
    doc_ids = summary_request.get("document_ids", [])
    task_prefix = f"summary_{'_'.join(map(str, doc_ids))}_{summary_request.get('format')}"
    for doc_id in doc_ids:
        await broadcast_status(doc_id, f"SUMMARIZING ({task_prefix})")
    try:
        await tasks.generate_summary_task(db, summary_request)
        for doc_id in doc_ids:
            await broadcast_status(doc_id, f"SUMMARY_COMPLETE ({task_prefix})")
    except Exception as e:
        logger.error(f"Error generating summary for {doc_ids}: {e}")
        for doc_id in doc_ids:
            await broadcast_status(doc_id, f"SUMMARY_FAILED ({task_prefix})", str(e))


@app.post("/upload", response_model=schemas.UploadResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    db: DBSession,
    config: CurrentSettings,
    file: UploadFile = File(...)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
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
        upload_path.unlink(missing_ok=True)
        logger.warning(f"Uploaded file type unknown/unsupported: {file.filename}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {upload_path.suffix}")

    db_doc = await crud.create_document(db, filename=file.filename, original_path=str(upload_path), doc_type=doc_type)
    background_tasks.add_task(process_document_task_with_ws, db, db_doc.id)
    logger.info(f"Added background task for processing document ID: {db_doc.id} with WS updates.")
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
    logger.info(f"Received URL for ingestion: {request.url}")
    db_doc = await crud.create_document(db, filename=request.url, original_path=request.url, doc_type=DocumentType.URL)
    background_tasks.add_task(process_document_task_with_ws, db, db_doc.id)
    logger.info(f"Added background task for downloading and processing URL, document ID: {db_doc.id} with WS updates.")
    doc_response = schemas.DocumentResponse.from_orm(db_doc)
    return schemas.UploadResponse(
        message="URL received successfully, download and processing started.",
        document=doc_response
    )

@app.get("/documents", response_model=list[schemas.DocumentResponse])
async def get_documents_list(db: DBSession, skip: int = 0, limit: int = 100):
    documents = await crud.get_documents(db, skip=skip, limit=limit)
    return documents

@app.get("/documents/{doc_id}", response_model=schemas.DocumentResponse)
async def get_document_details(doc_id: int, db: DBSession):
    db_doc = await crud.get_document(db, doc_id)
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return db_doc

@app.get("/status/{doc_id}", response_model=schemas.TaskStatusResponse)
async def get_task_status(doc_id: int, db: DBSession):
    db_doc = await crud.get_document(db, doc_id)
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return schemas.TaskStatusResponse(
        task_id=db_doc.id,
        status=db_doc.status,
        filename=db_doc.filename,
        error_message=db_doc.error_message
    )

@app.post("/summary", response_model=schemas.SummaryResponse, status_code=202)
async def generate_summary(
    request: schemas.SummaryRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    config: CurrentSettings
):
    logger.info(f"Received summary request: Format={request.format}, Docs={request.document_ids}")
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided for summary.")
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
            logger.warning(f"Generating summary, but some documents are not ready: {failed_or_pending}")
    background_tasks.add_task(generate_summary_task_with_ws, db, request.dict())
    summary_task_id = f"summary_{'_'.join(map(str, request.document_ids))}_{request.format}"
    return schemas.SummaryResponse(
        message=f"Summary generation ({request.format}) started in background. Task ID: {summary_task_id}",
        task_id=None
    )

@app.get("/download/{file_type}/{filename}")
async def download_file(file_type: str, filename: str, config: CurrentSettings):
    logger.info(f"Download request for type '{file_type}', filename '{filename}'")
    allowed_types = ["audio", "summary"]
    if file_type == "audio":
        base_path = config.audio_exports_dir
    elif file_type == "summary":
        base_path = config.audio_exports_dir
    else:
        raise HTTPException(status_code=400, detail="Invalid file type for download.")
    file_path = base_path / filename
    if not file_path.is_file():
        logger.error(f"Download failed: File not found at {file_path}")
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        resolved_path = file_path.resolve()
        base_resolved = base_path.resolve()
        if not str(resolved_path).startswith(str(base_resolved)):
            logger.error(f"Download forbidden: Path traversal attempt: {filename}")
            raise HTTPException(status_code=403, detail="Access forbidden.")
    except Exception as e:
        logger.error(f"Error resolving download path {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error accessing file path.")
    logger.info(f"Sending file for download: {file_path}")
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')

@app.websocket("/ws/status/{doc_id}")
async def websocket_status_endpoint(websocket: WebSocket, doc_id: int, db: DBSession):
    await websocket.accept()
    logger.info(f"WebSocket connection established for document ID: {doc_id}")
    if doc_id not in websocket_connections:
        websocket_connections[doc_id] = []
    websocket_connections[doc_id].append(websocket)
    try:
        while True:
            # Example: Fetch status on each message or periodically if needed
            # data = await websocket.receive_text()
            async with database.AsyncSessionLocal() as session:
                status = await crud.get_document(session, doc_id)
                if status:
                    await websocket.send_json({"doc_id": doc_id, "status": status.status.name, "error_message": status.error_message})
                else:
                    await websocket.send_json({"doc_id": doc_id, "status": "NOT_FOUND"})
            await asyncio.sleep(5)  # Send status update every 5 seconds
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for document ID: {doc_id}")
    finally:
        if doc_id in websocket_connections:
            websocket_connections[doc_id].remove(websocket)
            if not websocket_connections[doc_id]:
                del websocket_connections[doc_id]

@app.get("/api/sources/")
async def get_sources(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Source))
    sources = result.scalars().all()
    return sources

@app.get("/api/chats/")
async def get_chats(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Chat))
    chats = result.scalars().all()
    return chats

app.include_router(chat_router)

@app.get("/api/studio/overview")
async def get_audio_overview(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Audio))
    audios = result.scalars().all()
    return audios
