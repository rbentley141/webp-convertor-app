"""
UDP networking utilities for monitoring workers' heartbeasts.

Workers send UDP heartbeats to the backend every second. The backend
uses these to detect dead workers and reassign their jobs.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import Any, Callable
from .protocol import Heartbeat

logger = logging.getLogger(__name__)


def send_udp(host: str, port: int, msg: dict[str, Any]) -> None:
    """Send a JSON message over UDP (fire-and-forget)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            message = json.dumps(msg).encode("utf-8")
            sock.sendto(message, (host, port))
    except OSError as e:
        logger.debug("UDP send failed to %s:%d: %e", host, port, e)


HeartbeatHandler = Callable[[dict[str, Any]], None]


def send_heartbeats(
    worker_id: int,
    backend_host: str,
    backend_udp_port: int,
    shutdown_event: threading.Event,
    interval: float = 2.0,
) -> None:
    """Worker -> Backend UDP heartbeats every 2.0 seconds default."""
    logger.info(
        "Starting heartbeat sender: %d -> %s:%d",
        worker_id, backend_host, backend_udp_port,
    )
    heartbeat = Heartbeat(
        worker_id=worker_id
    )
    while not shutdown_event.is_set():
        heartbeat_dict = heartbeat.get_heartbeat()
        send_udp(
            backend_host, 
            backend_udp_port,
            heartbeat_dict
        )
        shutdown_event.wait(timeout=interval)

    logger.info("Heartbeat sender stopped")


def udp_server(
        host: str,
        port: int,
        shutdown: threading.Event,
        heartbeat_handler: HeartbeatHandler
) -> None:
    """
    Run UDP server as one of JobServices' threads to receive heartbeats and add to
    Heartbeat Queue with heartbeat handler.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.settimeout(1.0)

        logger.info("UDP server listening on %s:%d", host, port)

        while not shutdown.is_set():
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError as e:
                if shutdown.is_set():
                    break
                logger.error("UDP recv failed: %s", e)
                continue
            try:
                message = json.loads(data.decode("utf-8"))
                heartbeat_handler(message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from %s", addr)
            except Exception:
                logger.exception("Error handling heartbeat from %s", addr)
        logger.info("UDP server shutting down.")


                             


