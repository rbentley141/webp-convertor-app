"""
WebP Backend - Flask API and job orchestration

This app is deployed on backend server. It:
1. Accepts uploads from frontend
2. Orchestrates jobs to workers over TCP
3. Receives results and serves them to clients

Deployment:
    pip install webp-shared webp-backend
    flask --app webp_backend.app:create_app run
"""

from .app import create_app
from .config import Config

__all__ = ["create_app", "Config"]