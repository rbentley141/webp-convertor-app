"""
File handling utilities for app and Worker
"""

from __future__ import annotations

import errno
import logging
import shutil
import socket
import zipfile
from pathlib import Path

from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_IMG_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def is_in_dir(base: Path, target: Path) -> bool:
    """Check if target path is in base dir."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def extract_files(file_path: Path, dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()

    if suffix in ALLOWED_IMG_EXTS:
        safe_name = secure_filename(file_path.name)
        if not safe_name:
            logger.warning("Invalid filename: %s", file_path.name)
            return []
        
        out_path = dest_dir / safe_name
        if not is_in_dir(dest_dir, out_path):
            logger.warning("Path traversal attempt: %s", file_path.name)
            return []
        
        try:
            shutil.copyfile(file_path, out_path)
            return [str(out_path)]
        except OSError as e:
            logger.error("Failed to copy %s: %s", file_path, e)
            return []
    
    if suffix != ".zip":
        logger.warning("Unsupported file type: %s", suffix)
        return []
    
    extracted_files: list[str] = []
    
    try:
        with zipfile.ZipFile(file_path) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue

                raw_name = info.filename
                logger.info("raw filename: %s", str(raw_name))
                if raw_name.startswith("__MACOSX/") or raw_name.endswith(".DS_Store"):
                    continue

                ext = Path(raw_name).suffix.lower()
                if ext not in ALLOWED_IMG_EXTS:
                    logger.info("Need to check if it's webp too.")
                    continue

                safe_name = secure_filename(Path(raw_name).name)

                if not safe_name:
                    continue

                out_path = dest_dir / safe_name
                out_path = out_path.resolve()

                if not is_in_dir(dest_dir, out_path):
                    continue
                try:
                    with z.open(info) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                    extracted_files.append(str(out_path))
                except (OSError, zipfile.BadZipFile) as e:
                    logger.error("Failed to extract %s: %s", raw_name, e)
    except zipfile.BadZipFile as e:
        logger.error("Invalid ZIP file %s: %s", file_path, e)
        return []
    
    logger.info("Extracted %d files from %s", len(extracted_files), file_path.name)
    return extracted_files


def find_free_tcp_port(host: str, start_port: int, max_tries: int = 100) -> int:
    """Find an available TCP port starting from start_port."""
    if not (0 <= start_port <= 65535):
        raise ValueError(f"Port must be 0..65535, got {start_port}")

    for port in range(start_port, min(65536, start_port + max_tries)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            logger.debug("Found free port: %d", port)
            return port
        except OSError as e:
            if e.errno in (errno.EADDRINUSE, errno.EACCES):
                continue
            raise
        finally:
            sock.close()

    raise RuntimeError(f"No free TCP port found in range {start_port}-{start_port + max_tries}")