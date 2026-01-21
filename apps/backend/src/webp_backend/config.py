"""Configuration management for the WebP backend."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Backend configuration loaded from environment variables."""

    tcp_host: str = "127.0.0.1"
    tcp_port: int = 5055
    udp_port: int = 5056
    upload_dir: Path = Path("uploads")
    extract_dir: Path = Path("extracted")
    results_dir: Path = Path("results")
    heartbeat_timeout: float = 10.0

    @classmethod
    def load(cls) -> Config:
        """Load configuration from environment variables."""
        return cls(
            tcp_host=os.getenv("WEBP_TCP_HOST", "127.0.0.1"),
            tcp_port=int(os.getenv("WEBP_TCP_PORT", "5055")),
            udp_port=int(os.getenv("WEBP_UDP_PORT", "5056")),
            upload_dir=Path(os.getenv("WEBP_UPLOAD_DIR", "uploads")),
            extract_dir=Path(os.getenv("WEBP_EXTRACT_DIR", "extracted")),
            results_dir=Path(os.getenv("WEBP_RESULTS_DIR", "results")),
            heartbeat_timeout=float(os.getenv("WEBP_HEARTBEAT_TIMEOUT", "10.0")),
        )

    def ensure_directories(self) -> None:
        """Create all required directories."""
        if self.upload_dir.exists():
            shutil.rmtree(self.upload_dir)
        if self.extract_dir.exists():
            shutil.rmtree(self.extract_dir)
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.extract_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
