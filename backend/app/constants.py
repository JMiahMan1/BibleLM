# app/constants.py
import enum

# --- Define Enums ---
# Define DocumentStatus and DocumentType enums here
class DocumentStatus(enum.Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class DocumentType(enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    EPUB = "EPUB"
    TXT = "TXT"
    MP3 = "MP3"
    WAV = "WAV"
    MP4 = "MP4"
    MOV = "MOV"
    PNG = "PNG"
    JPG = "JPG"
    URL = "URL"
    UNKNOWN = "UNKNOWN"

# Define ChatMessage role enum here
class ChatMessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
