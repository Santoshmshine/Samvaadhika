"""
Samvaadhika - Configuration
All settings for the offline multilingual translation platform.
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
CACHE_DIR = BASE_DIR / "cache"
OUTPUTS_DIR = BASE_DIR / "outputs"
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"

# Ensure directories exist
for d in [DATA_DIR, UPLOADS_DIR, CACHE_DIR, OUTPUTS_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HF_CACHE_DIR = CACHE_DIR / "huggingface"
HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))

# Database
DATABASE_URL = f"sqlite:///{DATA_DIR}/samvaadhika.db"

# Security
SECRET_KEY = os.environ.get("SECRET_KEY", "samvaadhika-baif-offline-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# Session
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET", "samvaadhika-session-secret-baif-2024")

# App settings
APP_NAME = "Samvaadhika"
APP_TAGLINE = "Bridging BAIF's eLearning Languages"
APP_VERSION = "1.0.0"
HOST = "127.0.0.1"
PORT = 8000

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "mr": "Marathi (मराठी)",
}

# File upload limits
MAX_TEXT_LENGTH = 10_000          # characters
MAX_AUDIO_SIZE_MB = 150           # MB (WAV) / 50 MB compressed
MAX_VIDEO_SIZE_MB = 200           # MB
MAX_DOCUMENT_SIZE_MB = 50         # MB
MAX_AUDIO_DURATION_SEC = 1800     # 30 minutes
MAX_VIDEO_DURATION_SEC = 900      # 15 minutes

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ALLOWED_DOCUMENT_EXTENSIONS = {".docx", ".pptx", ".pdf", ".xlsx", ".csv"}

# Worker thread pool
WORKER_THREADS = 2

# Whisper model size (tiny/base/small/medium — small is best CPU balance)
WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# Tesseract
TESSERACT_LANGUAGES = "eng+hin+mar"

# Cache
CACHE_ENABLED = True

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = DATA_DIR / "samvaadhika.log"

# Admin defaults (change on first run)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Samvaadhika@2024"
DEFAULT_ADMIN_EMAIL = "admin@baif.org.in"
