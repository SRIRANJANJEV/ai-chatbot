"""
app/routes.py
─────────────
Two blueprints:
  main_bp  — serves the HTML frontend
  api_bp   — JSON API endpoints (protected by HTTP Basic Auth + rate limiting)
"""

import time
from flask import Blueprint, jsonify, render_template, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash

from app import limiter
from app.config import Config
from app.logger import logger
from app.rag import query_rag
from app.security import (
    CRISIS_RESPONSE,
    DISCLAIMER,
    check_dangerous_content,
    check_prompt_injection,
    sanitize_input,
)

# ── Blueprints ────────────────────────────────────────────────────────────────
main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)

# ── Basic Auth ────────────────────────────────────────────────────────────────
auth = HTTPBasicAuth()

# Store hashed password; never store plaintext passwords.
_USERS = {
    Config.API_USERNAME: generate_password_hash(Config.API_PASSWORD)
}


@auth.verify_password
def verify_password(username: str, password: str) -> str | None:
    """Return username on success, None on failure."""
    hashed = _USERS.get(username)
    if hashed and check_password_hash(hashed, password):
        return username
    logger.warning("Failed auth attempt for user='%s' from IP=%s",
                   username, request.remote_addr)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main blueprint — frontend
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/")
def index():
    """Serve the chat UI."""
    return render_template("index.html")


@main_bp.route("/health")
def health():
    """Public health-check endpoint (used by load-balancers / uptime monitors)."""
    return jsonify({"status": "ok", "timestamp": int(time.time())}), 200


# ─────────────────────────────────────────────────────────────────────────────
# API blueprint — protected endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/chat", methods=["POST"])
@auth.login_required
@limiter.limit(Config.RATE_LIMIT_CHAT)
def chat():
    """
    POST /api/chat
    Body:  { "query": "What are symptoms of diabetes?" }
    Returns: { "answer": "...", "sources": [...], "disclaimer": "..." }
    """
    start_time = time.perf_counter()

    # ── Parse request ──────────────────────────────────────────────────────────
    data = request.get_json(silent=True) or {}
    raw_query: str = data.get("query", "").strip()

    logger.info("Chat request from user='%s' IP=%s query_len=%d",
                auth.current_user(), request.remote_addr, len(raw_query))

    # ── Input validation ───────────────────────────────────────────────────────
    try:
        clean_query = sanitize_input(raw_query)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # ── Security checks ────────────────────────────────────────────────────────
    if check_prompt_injection(clean_query):
        return jsonify({
            "error": "Your message was flagged as a potential prompt-injection attempt "
                     "and could not be processed."
        }), 400

    if check_dangerous_content(clean_query):
        return jsonify({
            "answer": CRISIS_RESPONSE,
            "sources": [],
            "disclaimer": DISCLAIMER,
        }), 200

    # ── RAG query ──────────────────────────────────────────────────────────────
    try:
        result = query_rag(clean_query)
    except FileNotFoundError as exc:
        logger.error("Vector store missing: %s", exc)
        return jsonify({
            "error": "The knowledge base is not yet initialised. "
                     "Please contact the administrator."
        }), 503
    except Exception as exc:
        logger.error("Unexpected RAG error: %s", exc, exc_info=True)
        return jsonify({
            "error": "An internal error occurred. Please try again later."
        }), 500

    elapsed = round((time.perf_counter() - start_time) * 1000)
    logger.info("Chat completed in %d ms for user='%s'", elapsed,
                auth.current_user())

    return jsonify({
        "answer": result["answer"] + DISCLAIMER,
        "sources": result["sources"],
        "response_time_ms": elapsed,
    }), 200


# ── Error handlers ─────────────────────────────────────────────────────────────

@api_bp.errorhandler(429)
def rate_limit_exceeded(exc):
    logger.warning("Rate limit exceeded from IP=%s", request.remote_addr)
    return jsonify({
        "error": "Too many requests. Please wait a moment before trying again."
    }), 429


@api_bp.errorhandler(401)
def unauthorized(exc):
    return jsonify({"error": "Unauthorized. Valid credentials required."}), 401
