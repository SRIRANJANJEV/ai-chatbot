"""
run.py
──────
Development entry point.
For production use gunicorn (see Dockerfile / deployment docs).
"""

from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=(Config.FLASK_ENV == "development"),
    )
