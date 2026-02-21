"""
app/security.py
───────────────
Input sanitisation, prompt-injection detection, and medical safety guardrails.
"""

import re
from typing import Optional

import bleach

from app.logger import logger

# ── Max input length (tokens are ~4 chars each; 500 tokens ≈ 2000 chars) ─────────
MAX_QUERY_LENGTH = 2000

# ── Prompt-injection patterns ──────────────────────────────────────────────────
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+your\s+system\s+prompt",
    r"you\s+are\s+now\s+a?\s+\w+\s+AI",
    r"forget\s+everything",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    r"pretend\s+you\s+are",
    r"reveal\s+your\s+system\s+prompt",
    r"output\s+your\s+instructions",
    r"bypass\s+(safety|guardrail|filter)",
    r"jailbreak",
    r"<\s*script",        # XSS attempt via query
    r"--\s*drop\s+table",  # SQL-injection style
]
_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS), re.IGNORECASE | re.DOTALL
)

# ── Dangerous medical advice triggers (refuse rather than answer) ─────────────
_DANGEROUS_PATTERNS = [
    r"how\s+to\s+(commit\s+suicide|kill\s+(my)?self|overdose\s+on)",
    r"lethal\s+dose\s+of",
    r"how\s+much\s+\w+\s+to\s+die",
    r"poison\s+someone",
]
_DANGEROUS_RE = re.compile(
    "|".join(_DANGEROUS_PATTERNS), re.IGNORECASE | re.DOTALL
)


def sanitize_input(text: str) -> Optional[str]:
    """
    Clean and validate user input.

    Returns the cleaned string, or None if the input fails validation.
    Raises ValueError with a user-facing message for safe errors.
    """
    if not text or not text.strip():
        raise ValueError("Query cannot be empty.")

    # Strip HTML tags / JavaScript via bleach
    cleaned = bleach.clean(text, tags=[], strip=True).strip()

    if len(cleaned) > MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query is too long. Please limit to {MAX_QUERY_LENGTH} characters."
        )

    # Normalise whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned


def check_prompt_injection(text: str) -> bool:
    """Return True if the text looks like a prompt-injection attempt."""
    if _INJECTION_RE.search(text):
        logger.warning("Prompt-injection attempt detected: %.100s", text)
        return True
    return False


def check_dangerous_content(text: str) -> bool:
    """Return True if the query requests genuinely dangerous medical content."""
    if _DANGEROUS_RE.search(text):
        logger.warning("Dangerous content request detected: %.100s", text)
        return True
    return False


DISCLAIMER = (
    "\n\n---\n"
    "⚠️ **Medical Disclaimer:** This response is for informational purposes only "
    "and does not constitute professional medical advice, diagnosis, or treatment. "
    "Always consult a licensed physician or qualified healthcare provider for any "
    "medical concerns."
)

CRISIS_RESPONSE = (
    "I'm not able to provide information that could cause harm. "
    "If you or someone you know is in crisis, please contact the "
    "**National Suicide Prevention Lifeline** at **988** (US), "
    "or your local emergency services immediately."
)
