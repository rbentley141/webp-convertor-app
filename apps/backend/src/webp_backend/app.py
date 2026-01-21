"""Flask application factory for the WebP backend."""

from __future__ import annotations

import logging
import sys

from flask import Flask
from flask_cors import CORS

from .config import Config
from .routes import jobs_bp, uploads_bp
from .services import JobService

logger = logging.getLogger(__name__)


def create_app(config: Config | None = None) -> Flask:
    """Create and configure the Flask application."""
    if config is None:
        config = Config.load()

    config.ensure_directories()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.config["job_service"] = JobService(config)
    app.config["upload_dir"] = config.upload_dir.resolve()
    app.config["extract_dir"] = config.extract_dir.resolve()
    app.config["results_dir"] = config.results_dir.resolve()

    app.register_blueprint(uploads_bp)
    app.register_blueprint(jobs_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    logger.info("WebP backend initialized")
    return app


def main() -> None:
    """Entry point for running the development server."""
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
