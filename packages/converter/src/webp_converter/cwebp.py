"""
Wrapper for the cwebp command-line tool.

This module provides a Python interface to cwebp with:
- Proper error handling and custom exceptions
- Automatic retry on partition overflow errors
- Image resizing on retry to avoid memory issues
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0


class CwebpError(RuntimeError):
    """Raised when cwebp fails to convert an image."""

    def __init__(self, command: list[str], returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"cwebp failed (rc={returncode}): {stderr.strip()}")


def run_cwebp(args: list[str], timeout: float = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    """Run cwebp with the given arguments."""
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"TimeoutExpired after {timeout}s"
    except FileNotFoundError:
        return 127, "", "cwebp not found. Install webp package."


def _is_partition_overflow(stderr: str) -> bool:
    """Check if error is a partition overflow (retry-able)."""
    if not stderr:
        return False
    return "PARTITION0_OVERFLOW" in stderr or "Error code: 6" in stderr


def _is_timeout(returncode: int) -> bool:
    """Check if the error was a timeout."""
    return returncode == 124


def _shrink_resize_args(cmd: list[str], scale: float, input_path: Path) -> list[str]:
    """Add or adjust -resize arguments to shrink the output."""
    cmd = list(cmd)

    if "-resize" in cmd:
        idx = cmd.index("-resize")
        width = int(cmd[idx + 1])
        height = int(cmd[idx + 2])

        if width > 0:
            width = max(1, int(width * scale))
        if height > 0:
            height = max(1, int(height * scale))

        cmd[idx + 1] = str(width)
        cmd[idx + 2] = str(height)
    else:
        with Image.open(input_path) as img:
            width, height = img.size
        width = max(1, int(width * scale))
        height = max(1, int(height * scale))
        cmd[2:2] = ["-resize", str(width), str(height)]

    return cmd


def convert_with_retry(
    input_path: Path,
    output_path: Path,
    cwebp_args: list[str],
    max_retries: int = 4,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """
    Convert an image to WebP, retrying with shrinking on overflow.

    Raises:
        CwebpError: If all attempts fail
        FileNotFoundError: If input file doesn't exist
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    cmd = ["cwebp", str(input_path), "-o", str(output_path), "-mt"] + cwebp_args

    logger.debug("Running: %s", " ".join(cmd))
    returncode, stdout, stderr = run_cwebp(cmd, timeout)

    if returncode == 0:
        return

    if not _is_partition_overflow(stderr) and not _is_timeout(returncode):
        raise CwebpError(cmd, returncode, stderr)

    retry_cmd = list(cmd)
    for attempt in range(1, max_retries + 1):
        scale = 1.0 - (attempt * 0.1)
        retry_cmd = _shrink_resize_args(retry_cmd, scale, input_path)

        logger.info("Retry %d/%d with scale %.1f", attempt, max_retries, scale)
        returncode, stdout, stderr = run_cwebp(retry_cmd, timeout)

        if returncode == 0:
            return

        if not _is_partition_overflow(stderr) and not _is_timeout(returncode):
            raise CwebpError(retry_cmd, returncode, stderr)

    raise CwebpError(retry_cmd, returncode, stderr)
