"""
TCP Networking Utitlities For JobService and Workers

Format:
    [4 bytes: header length big-endian]
    [N bytes: JSON header]
    [M bytes: binary payload (if byte_length is in header)]
"""

from __future__ import annotations

import json
import logging
import socket
import struct
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from .files import extract_files
from .protocol import SendFiles

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10.0
RECV_TIMEOUT = 30.0
SEND_TIMEOUT = 30.0


class TCPError(Exception):
    """Base Exception for TCP Operations."""
    pass


class ConnectionFailed(TCPError):
    """Raised when connection can't be established."""
    pass

class SendFailed(TCPError):
    """Raised when sending data fails."""
    pass

class RecvFailed(TCPError):
    """Raised when receiving data fails."""
    pass


def recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise RecvFailed(f"Connection closed after {len(buf)}/{n} bytes")
        buf += chunk
    return buf


def send_tcp(host: str, port: int, msg: dict[str, Any]) -> None:
    header_bytes = json.dumps(msg).encode("utf-8")
    prefix = struct.pack(">I", len(header_bytes))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect((host, port))
            sock.settimeout(SEND_TIMEOUT)
            sock.sendall(prefix)
            sock.sendall(header_bytes)
    except socket.timeout as e:
        raise ConnectionFailed(f"Timeout connecting to {host}:{port}") from e
    except OSError as e:
        raise ConnectionFailed(f"Failed to connect to {host}:{port}: {e}") from e


def send_file_tcp(host: str, port: int, images_ready: SendFiles) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(CONNECT_TIMEOUT)    
            s.connect((host, port))
            s.settimeout(SEND_TIMEOUT)
            s.sendall(images_ready.prefix)
            s.sendall(images_ready.header)
            s.sendall(images_ready.file_bytes)

    except socket.timeout as e:
        raise ConnectionFailed(f"Timout connection to {host}:{port}") from e
    except OSError as e:
        raise ConnectionFailed(f"Failed to connect to {host}:{port}: {e}") from e

MessageHandler = Callable[[dict[str, Any]], None]

def tcp_server(
    host: str, 
    port: int, 
    storage_path: Path, 
    shutdown_event: threading.Event, 
    message_handler: MessageHandler,
) -> None:
    """Run TCP server that receives messages and optional file payloads."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(5) 

        sock.settimeout(1.0)

        logger.info("TCP Server listening on %s:%d", host, port)

        while not shutdown_event.is_set():
            try:
                conn, addr = sock.accept()
            except socket.timeout:
                continue
            except OSError as e:
                if shutdown_event.is_set():
                    break
                logger.error("Accept failed %s", e)
                continue

            with conn:
                conn.settimeout(RECV_TIMEOUT)

                try:
                    _handle_connection(conn, addr, storage_path, message_handler)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("Invalid message from %s: %s", addr, e)
                except (ConnectionError, socket.timeout) as e:
                    logger.warning("Connection error from %s: %s", addr, e)
                except Exception:
                    logger.exception("Unexpected error handling connection from %s", addr)

        logger.info("TCP Server shutting down")

def _handle_connection(
    conn: socket.socket,
    addr: tuple[str, int],
    storage_path: Path,
    message_handler: MessageHandler,
) -> None:
    header_len_bytes = recv_exact(conn, 4)
    header_len = struct.unpack(">I", header_len_bytes)[0]
    if header_len > 10_000_000:
        raise ValueError(f"Header too large: {header_len} bytes")
    
    header_bytes = recv_exact(conn, header_len)
    header = json.loads(header_bytes.decode("utf-8"))
    print(json.dumps(header, indent=2))
    msg_type = header.get("type")

    logger.debug("Received %s from %s", msg_type, addr)
    if msg_type in ("new_job", "images_ready"):
        if not storage_path.exists():
            storage_path.mkdir(parents=True, exist_ok=True)

        logger.info("Received header: %s", json.dumps(header, indent=2))
        byte_length = header.get("byte_length")
        if byte_length is None or byte_length < 0:
            raise ValueError(f"Invalid byte_length: {byte_length}")

        filename = header.get("filename", "upload.bin")
        filename = Path(filename).name
        payload = recv_exact(conn, byte_length)

        suffix = Path(filename).suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png"):
            out_path = storage_path / filename
            out_path.write_bytes(payload)
            header["saved_path"] = str(out_path)
        elif suffix == ".zip":
            zip_path = Path(storage_path) / filename
            if Path(zip_path).is_dir() or zip_path.suffix != ".zip":
                zip_path = zip_path.with_suffix(".zip")
            zip_path = zip_path.resolve()
            zip_path.write_bytes(payload)
            job_id = header.get("job_id", "unknown")
            batch_id = header.get("batch_id", "unknown")
            dest = storage_path / str(batch_id) / str(job_id)
            dest = dest.resolve()
            files = extract_files(zip_path, dest)
            header["paths"] = files
            header["saved_path"] = str(dest)
        else:
            out_path = storage_path / filename
            out_path.write_bytes(payload)
            header["saved_path"] = str(out_path)
        
    message_handler(header)