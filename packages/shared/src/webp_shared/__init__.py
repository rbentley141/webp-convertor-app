"""
Shared networking and protocol types for WebP conversion

The package is a dependency of both backend and worker:
- Backend uses it for TCP/UDP servers and protocol types
- Worker uses it for TCP/UDP clients and protocol types

Deployment:
    pip install webp-shared
"""

from .protocol import (
    PROTOCOL_VERSION,
    FileOptions,
    Heartbeat,
    SendFiles,
    StartJob,
    ImagesReadyHeader,
    JobError,
    NewBatch,
    ProtocolError,
    Shutdown,
    WorkerAck,
    WorkerJob,
    WorkerRegistration,
    parse_file_options,
    validate_version,
)
from .tcp import (
    ConnectionFailed,
    RecvFailed,
    SendFailed,
    TCPError,
    send_file_tcp,
    send_tcp,
    tcp_server,
)
from .udp import (
    send_heartbeats,
    send_udp,
    udp_server,
)
from .files import (
    ALLOWED_IMG_EXTS,
    extract_files,
    find_free_tcp_port,
    is_in_dir,
)

__all__ = [
    # Protocol
    "PROTOCOL_VERSION",
    "ProtocolError",
    "validate_version",
    "FileOptions",
    "SendFiles",
    "StartJob",
    "ImagesReadyHeader",
    "WorkerJob",
    "JobError",
    "Heartbeat",
    "WorkerRegistration",
    "WorkerAck",
    "NewBatch",
    "Shutdown",
    "parse_file_options",
    # TCP
    "TCPError",
    "ConnectionFailed",
    "SendFailed",
    "RecvFailed",
    "send_tcp",
    "send_file_tcp",
    "tcp_server",
    # UDP
    "send_udp",
    "send_heartbeats",
    "udp_server",
    # Files
    "ALLOWED_IMG_EXTS",
    "is_in_dir",
    "extract_files",
    "find_free_tcp_port",
]