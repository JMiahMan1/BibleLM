# Local NotebookLM Clone

This project provides a local, Dockerized alternative to NotebookLM, allowing you to ingest documents, audio, video, and images, chat with them using Retrieval-Augmented Generation (RAG) powered by a local LLM (via Ollama), and export summaries.

## Features

* **File Ingestion:** Supports `.pdf`, `.docx`, `.epub`, `.txt`, `.mp3`, `.wav`, `.mp4`, `.mov`, `.png`, `.jpg`.
* **URL Ingestion:** Download and process video/audio from YouTube, Rumble, etc. (via `yt-dlp`).
* **Transcription:** Audio files and audio from videos transcribed using `Whisper`.
* **OCR:** Text extracted from images using `Tesseract`.
* **RAG Chat:** Conversational interface to query your ingested documents using LangChain and Ollama.
* **Background Processing:** Ingestion tasks run asynchronously without blocking the UI.
* **Summarization:** Generate text summaries.
* **Export:** Download summaries as `.txt`, `.docx`, dialogue scripts, or (placeholder) audio (`.mp3`).
* **Local & Private:** Runs entirely locally using Docker and Ollama. No data leaves your machine.
* **Modular:** Designed with separate modules for easier expansion.

## Tech Stack

* **Backend:** FastAPI (Python)
* **Frontend:** Next.js/React + TailwindCSS (Requires separate setup)
* **LLM:** Ollama (connects to your running Ollama instance)
* **RAG:** LangChain
* **Embeddings:** OllamaEmbeddings (via LangChain)
* **Vector Store:** ChromaDB (local persistence)
* **Transcription:** Whisper
* **Downloading:** yt-dlp
* **OCR:** Tesseract
* **File Handling:** pypdf, python-docx, EbookLib, Pillow
* **Database:** SQLite (for metadata)
* **Configuration:** YAML
* **Containerization:** Docker, Docker Compose
* **Background Tasks:** FastAPI `BackgroundTasks` (can be swapped for Celery)
* **TTS (Placeholder):** Coqui TTS / Bark integration point provided.

## Prerequisites

1.  **Docker & Docker Compose:** Install Docker Desktop (Mac/Windows) or Docker Engine + Docker Compose (Linux). [Install Docker](https://docs.docker.com/engine/install/)
2.  **Ollama:** Install and run Ollama locally. Pull the models you intend to use (both for generation and embeddings).
    * [Install Ollama](https://ollama.com/)
    * Pull models:
        ```bash
        ollama pull llama3 # Or your preferred generation model
        ollama pull nomic-embed-text # Example embedding model from config.yaml
        ```
3.  **Tesseract:** While the Docker container installs Tesseract, if you run the backend *outside* Docker for development, you'll need Tesseract installed locally. [Tesseract Installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
4.  **(Optional) `espeak-ng`:** If you implement Coqui TTS audio summaries, you'll likely need `espeak-ng` installed (`sudo apt-get install espeak-ng` on Debian/Ubuntu, or equivalent).

## Setup & Running

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd notebooklm-clone
    ```

2.  **Configure:**
    * Review and edit `backend/config.yaml`.
        * **Crucially**, verify `ollama_base_url`. If Ollama is running directly on your Linux host (not in Docker), you might need `http://172.17.0.1:11434` (or your Docker bridge IP) instead of `http://host.docker.internal:11434`. Check your Docker network setup.
        * Adjust `whisper_model`, `embedding_model_name`, paths, etc., as needed.
    * If you change the embedding model in `config.yaml`, make sure you `ollama pull <new_embedding_model>` it.

3.  **Set up Frontend:**
    * Navigate to the `frontend/` directory.
    * Follow the instructions in `frontend/README.md` to initialize the Next.js/React app and install its dependencies.

4.  **Build and Run with Docker Compose:**
    * From the project's root directory (`notebooklm-clone/`):
        ```bash
        docker compose up --build
        ```
    * The `--build` flag ensures images are rebuilt if code changes. Omit it for faster subsequent starts if only data/config changed.
    * Use `-d` to run in detached mode (background): `docker compose up --build -d`

5.  **Access the Application:**
    * **Frontend UI:** Open your browser to `http://localhost:3000`
    * **Backend API:** Accessible at `http://localhost:8000` (e.g., `http://localhost:8000/docs` for Swagger UI)

6.  **Stopping:**
    * Press `Ctrl+C` in the terminal where `docker compose up` is running.
    * If running detached, use: `docker compose down`

## Usage

1.  **Upload Files:** Use the UI (at `http://localhost:3000`) to upload supported files or input URLs.
2.  **Monitor Progress:** The UI should show the status of ingestion tasks.
3.  **Chat:** Once documents are processed (`COMPLETED`), select them and start a chat session. Ask questions related to the content.
4.  **Summarize:** Select processed documents and request a summary in the desired format. Download links should appear once generation is complete (for file-based formats).

## Development

* **Backend:** If you mount the backend code in `docker-compose.yml`, changes to Python files should trigger Uvicorn's reload mechanism inside the container.
* **Frontend:** The standard Next.js/React development server (`npm run dev` or `yarn dev`) provides hot reloading. You might run this outside Docker during development, ensuring it points to the backend API running in Docker (e.g., `NEXT_PUBLIC_API_URL=http://localhost:8000`).
* **Database:** The SQLite database file (`app.db`) is stored in the `data/db/` directory (mounted from your host). You can inspect it using tools like DB Browser for SQLite.

## TODO / Potential Improvements

* **Frontend Implementation:** Build the actual React/Next.js UI.
* **Real-time Updates:** Implement WebSockets for smoother task status updates instead of polling.
* **TTS Implementation:** Integrate a real TTS engine (Coqui TTS, Bark, Piper) for audio summaries. Requires careful dependency management.
* **Error Handling:** More granular error reporting in the UI. Retry mechanisms for failed tasks.
* **Scalability:** Replace FastAPI `BackgroundTasks` with Celery and Redis/RabbitMQ for more robust background job processing.
* **Database:** Switch to Postgres for better scalability and concurrent access.
* **RAG:** Experiment with different chunking strategies, embedding models, vector stores (FAISS), and retrieval methods (e.g., reranking).
* **Chat Memory:** Implement persistent chat session history.
* **Authentication:** Add a user login system if needed for multi-user environments.
* **Resource Management:** Configure limits on concurrent jobs more dynamically. Monitor resource usage (CPU/Memory/GPU).
* **Testing:** Add unit and integration tests.
* **Advanced Export:** More sophisticated script formatting, chapter generation, etc.
