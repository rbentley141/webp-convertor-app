"""Backend HTTP routes."""

from .jobs import jobs_bp
from .uploads import uploads_bp

__all__ = ["jobs_bp", "uploads_bp"]
