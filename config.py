import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration for AICTE Integrated Institution Complaint Monitoring System."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "aicte-portal-secret-key-2026-demo-environment")
    
    # Instance directory for SQLite database
    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    
    DB_PATH = INSTANCE_DIR / "aicte_monitoring.db"
    
    # Resolve database URL with POSIX slashes for Windows compatibility
    _raw_db_url = os.environ.get("DATABASE_URL")
    if _raw_db_url:
        if _raw_db_url.startswith("sqlite:///") and not _raw_db_url.startswith("sqlite:////") and not (len(_raw_db_url) > 11 and _raw_db_url[10] == ":"):
            _rel_path = _raw_db_url.replace("sqlite:///", "")
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{(BASE_DIR / _rel_path).as_posix()}"
        else:
            SQLALCHEMY_DATABASE_URI = _raw_db_url
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH.as_posix()}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # AI Model & Overlap Thresholds
    AI_MODEL_NAME = os.environ.get("AI_MODEL_NAME", "all-MiniLM-L6-v2")
    AI_USE_SENTENCE_TRANSFORMERS = os.environ.get("AI_USE_SENTENCE_TRANSFORMERS", "true").lower() in ("true", "1", "yes")
    OVERLAP_STRONG_THRESHOLD = float(os.environ.get("OVERLAP_STRONG_THRESHOLD", 0.80))
    OVERLAP_POSSIBLE_THRESHOLD = float(os.environ.get("OVERLAP_POSSIBLE_THRESHOLD", 0.50))

    # Session and Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max request size
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}
    UPLOAD_FOLDER = INSTANCE_DIR / "uploads"
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


class TestConfig(Config):
    """Configuration for automated test suite."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AI_USE_SENTENCE_TRANSFORMERS = False  # Faster, deterministic fallback for fast unit tests
