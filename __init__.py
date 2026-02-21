"""
app/__init__.py
───────────────
Flask application factory.

Usage:
    from app import create_app
    app = create_app()
"""

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import Config
from app.logger import logger

# Limiter is created here so it can be imported by blueprints
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[Config.RATE_LIMIT_DEFAULT],
    storage_uri="memory://",          # swap for redis:// in production
)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = Config.SECRET_KEY

    # ── CORS (restrict origins in production) ──────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Rate limiter ───────────────────────────────────────────────────────────
    limiter.init_app(app)

    # ── Register blueprints ────────────────────────────────────────────────────
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Pre-warm the RAG chain on startup ─────────────────────────────────────
    try:
        from app.rag import get_rag_chain
        get_rag_chain()
    except FileNotFoundError as exc:
        logger.warning("Vector store not found at startup — %s", exc)

    logger.info("Flask app created (env=%s)", Config.FLASK_ENV)
    return app
