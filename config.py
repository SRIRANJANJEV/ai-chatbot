"""
app/config.py
─────────────
Central configuration loaded from environment variables.
All secrets are read here so the rest of the codebase never
calls os.getenv() directly.
"""

import os
from dotenv import load_dotenv

# Load .env only in development; in production set env-vars at the OS level.
load_dotenv()


class Config:
    # ── OpenAI ──────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )

    # ── Vector Store ─────────────────────────────────────────────────────────────
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", "data/vector_store")

    # ── Pinecone (optional) ───────────────────────────────────────────────────────
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENV: str = os.getenv("PINECONE_ENV", "")
    PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "medical-index")
    USE_PINECONE: bool = bool(PINECONE_API_KEY and PINECONE_ENV)

    # ── Flask ─────────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ["FLASK_SECRET_KEY"]
    FLASK_ENV: str = os.getenv("FLASK_ENV", "production")
    PORT: int = int(os.getenv("FLASK_PORT", 5000))

    # ── Basic Auth ────────────────────────────────────────────────────────────────
    API_USERNAME: str = os.environ["API_USERNAME"]
    API_PASSWORD: str = os.environ["API_PASSWORD"]

    # ── Rate Limiting ─────────────────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "30 per minute")
    RATE_LIMIT_CHAT: str = os.getenv("RATE_LIMIT_CHAT", "10 per minute")

    # ── RAG ───────────────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", 800))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", 100))
    RETRIEVER_TOP_K: int = int(os.getenv("RETRIEVER_TOP_K", 4))

    # ── Logging ───────────────────────────────────────────────────────────────────
    LOG_DIR: str = "logs"
    LOG_FILE: str = "logs/app.log"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
