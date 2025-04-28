import yaml
from pydantic import BaseModel, Field
from pathlib import Path
import os

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml" # Path relative to this file

class OllamaConfig(BaseModel):
    base_url: str

class WhisperConfig(BaseModel):
    model: str
    device: str

class TesseractConfig(BaseModel):
    cmd: str
    lang: str

class RAGConfig(BaseModel):
    chunk_size: int
    chunk_overlap: int
    embedding_model_name: str
    vector_store_path: str

class SummaryConfig(BaseModel):
    tts_engine: str
    tts_speaker_1: str | None = None
    tts_speaker_2: str | None = None
    summary_max_length: int

class AppConfig(BaseModel):
    data_dir: str
    ollama: OllamaConfig
    whisper: WhisperConfig
    tesseract: TesseractConfig
    rag: RAGConfig
    background_tasks: dict = Field(default_factory=lambda: {"max_concurrent_jobs": 2})
    summary: SummaryConfig
    database_url: str

    # Derived paths
    @property
    def full_data_dir(self) -> Path:
        return Path(self.data_dir)

    @property
    def uploads_dir(self) -> Path:
        return self.full_data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.full_data_dir / "processed"

    @property
    def audio_exports_dir(self) -> Path:
        return self.full_data_dir / "audio_exports"

    @property
    def db_dir(self) -> Path:
        return self.full_data_dir / "db"

    @property
    def full_vector_store_path(self) -> str:
         # ChromaDB needs a directory path
        return str(self.processed_dir / self.rag.vector_store_path.split('/')[-1])


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at {path}")
    with open(path, 'r') as f:
        config_data = yaml.safe_load(f)

    config = AppConfig(
        data_dir=config_data.get("data_dir", "/app/data"),
        ollama=OllamaConfig(**config_data.get("ollama", {})),
        whisper=WhisperConfig(**config_data.get("whisper", {})),
        tesseract=TesseractConfig(**config_data.get("tesseract", {})),
        rag=RAGConfig(**config_data.get("rag", {})),
        background_tasks=config_data.get("background_tasks", {}),
        summary=SummaryConfig(**config_data.get("summary", {})),
        database_url=config_data.get("database_url", "sqlite+aiosqlite:////app/data/db/app.db")
    )

    # Ensure directories exist after loading config
    config.full_data_dir.mkdir(parents=True, exist_ok=True)
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    config.processed_dir.mkdir(parents=True, exist_ok=True)
    config.audio_exports_dir.mkdir(parents=True, exist_ok=True)
    config.db_dir.mkdir(parents=True, exist_ok=True)
    Path(config.full_vector_store_path).mkdir(parents=True, exist_ok=True) # Ensure vector store dir exists


    # Set Tesseract command path if specified
    if config.tesseract.cmd != 'tesseract':
         # This line might be needed if pytesseract doesn't find the cmd automatically
         # import pytesseract
         # pytesseract.pytesseract.tesseract_cmd = config.tesseract.cmd
         pass # Usually setting PATH in Dockerfile is sufficient

    return config

# Global config instance (or use dependency injection)
settings = load_config()

# --- Environment Variable Override (Optional) ---
# You could override specific config values using environment variables here
# For example: settings.ollama.base_url = os.getenv("OLLAMA_BASE_URL", settings.ollama.base_url)
