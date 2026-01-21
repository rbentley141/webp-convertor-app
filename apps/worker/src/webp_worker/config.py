"""Configuration for the WebP worker."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerConfig:
    """Worker configuration."""

    host: str = "127.0.0.1"
    port: int = 5057
    backend_host: str = "127.0.0.1"
    backend_tcp_port: int = 5055
    backend_udp_port: int = 5056
    jobs_dir: Path = Path("jobs-input")
    output_dir: Path = Path("jobs-output")

    @classmethod
    def load(cls) -> WorkerConfig:
        """Load from environment variables."""
        return cls(
            host=os.getenv("WEBP_WORKER_HOST", "127.0.0.1"),
            port=int(os.getenv("WEBP_WORKER_PORT", "5057")),
            backend_host=os.getenv("WEBP_BACKEND_HOST", "127.0.0.1"),
            backend_tcp_port=int(os.getenv("WEBP_BACKEND_TCP_PORT", "5055")),
            backend_udp_port=int(os.getenv("WEBP_BACKEND_UDP_PORT", "5056")),
        )

    def ensure_directories(self) -> None:
        if self.jobs_dir.exists():
            shutil.rmtree(self.jobs_dir)
            shutil.rmtree(self.output_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
