"""
This app is deloyed on worker machines. It:
1. Registers with the backend
2. Receives conversion jobs over TCP
3. Runs the conversion (using webp-converter package)
4. Sends results back to the backend

Deployment:
    pip install webp-shared webp-converter webp-worker
    apt install webp  # for cwebp command
    webp-worker --backend-host <backend-ip>
"""

from .config import WorkerConfig
from .server import WorkerServer

__all__ = ["WorkerConfig", "WorkerServer"]