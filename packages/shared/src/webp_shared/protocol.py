"""
Protocol definitions for CwebP conversion pipeline.

Message Flow:
    Worker -> Backend: type = new_convertor (register worker)
    Backend -> Worker: type = ack (Tell worker it's registered)
    Worker -> Backend: type = heartbeat (UDP, every 1-2s)
    Backend -> Worker: type = new_batch (clears Worker's state)
    Backend -> Worker: type = new_job (A job is one file)
    Worker -> Backend: type = images_ready (sends a zip of converted versions)
    Either -> Either: type = shutdown (terminate all. Only allow Worker -> Backend for simplicity and ease of testing)
"""
from __future__ import annotations

import time
import json
import struct
from dataclasses import dataclass, asdict
from typing import Literal, Any
from pathlib import Path

PROTOCOL_VERSION: Literal[1] = 1

# Type literal
SizeType = Literal["banner", "content", "thumbnail", "icon", "other"]
ImageType = Literal["complex", "graphic", "product", "default"]
JobStage = Literal["convert", "zip", "unknown"]
JobState = Literal["queued", "running", "done", "error"]


class ProtocolError(Exception):
    """Raised when a message fails validation or version check."""
    pass


def validate_version(msg: dict[str, Any]) -> None:
    version = msg.get("v")
    if version is not None and version != PROTOCOL_VERSION:
        raise ProtocolError(
            f"Protocol version mismatch: expected {PROTOCOL_VERSION}."
        )


@dataclass
class FileOptions:
    """
    Conversion options for an image. Each of these options can
    be speciefied on the frontend.
    """
    lossless: bool = False
    text_focus: bool = False
    has_text: bool = False

    type: ImageType = "default"

    crop_size_w: int | None = None
    crop_size_h: int | None = None
    crop_top_x: int | None = None
    crop_top_y: int | None = None
    crop_w: int | None = None
    crop_h: int | None = None

    size_type: SizeType = "content"
    width: int | None = None
    height: int | None = None

    def has_crop(self) -> bool:
        """True if all crop parameters are set."""
        return all(
            v is not None
            for v in [
                self.crop_size_w, self.crop_size_h,
                self.crop_top_x, self.crop_top_y,
                self.crop_w, self.crop_h,
            ]
        )
    

    def has_explicit_size(self) -> bool:
        """True if explicit width or height is set."""
        return self.width is not None or self.height is not None

@dataclass
class SendFiles:
    """For sending new_job to workers or images_ready to app."""
    prefix: bytes | None = None
    header: bytes | None = None
    file_bytes: bytes | None = None

    @classmethod
    def start_job(
        cls,
        batch_id: int,
        job_id: int,
        input_file: Path,
        filename: str,
        options: FileOptions,
    ) -> "SendFiles":
        if not input_file.exists():
            raise ProtocolError(
                "Input file doesn't exist for new_job."
            )
        img_bytes = input_file.read_bytes()
        byte_len = len(img_bytes)
        filename = input_file.name
        header_bytes = StartJob.from_submitted(
            batch_id, job_id, filename, options, byte_len
        ).get_bytes()
        prefix = struct.pack(">I", len(header_bytes))

        return cls(
            prefix=prefix,
            header=header_bytes,
            file_bytes=img_bytes,
        )
    

    @classmethod
    def img_ready_msg(
        cls,
        batch_id: int,
        job_id: int,
        w_id: int,
        in_file: Path,
    ) -> "SendFiles":
        if not in_file.exists():
            raise FileNotFoundError(f"Input file not found: {in_file}")

        img_bytes = in_file.read_bytes()
        byte_len = len(img_bytes)
        filename = in_file.name
        header_bytes = ImagesReadyHeader.make_header(
            batch_id, job_id, w_id, filename, byte_len
        ).get_bytes()
        prefix = struct.pack(">I", len(header_bytes))

        return cls(
            prefix=prefix,
            header=header_bytes,
            file_bytes=img_bytes,
        )


@dataclass
class StartJob:
    """Backend -> Worker to start new conversion job."""
    v: int = PROTOCOL_VERSION
    type: str = "new_job"
    batch_id: int | None = None
    job_id: int | None = None
    filename: str | None = None
    options: FileOptions | None = None
    byte_length: int | None = None


    @classmethod
    def from_submitted(
        cls,
        batch_id: int,
        job_id: int,
        filename: str,
        options: FileOptions,
        bytelength: int
    ) -> "StartJob":
        """Create from a submitted job."""
        return cls(
            batch_id=batch_id,
            job_id=job_id,
            filename=filename,
            options=options,
            byte_length=bytelength,
        )
    def get_bytes(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.options is not None:
            d["options"] = asdict(self.options)
        return d


@dataclass
class ImagesReadyHeader:
    """Class for Images Ready Header."""
    v: int = PROTOCOL_VERSION
    type: Literal["images_ready"] = "images_ready"
    batch_id: int | None = None
    job_id: int | None = None
    worker_id: int | None = None
    format: Literal["zip"] = "zip"
    filename: str | None = None
    content_type: str = "application/zip"
    byte_length: int | None = None

    @classmethod
    def make_header(
        cls,
        batch_id: int,
        job_id: int,
        worker_id: int,
        filename: str,
        byte_length: int
    ) -> "ImagesReadyHeader":
        """Make ImagesReadyHeader, called in ImagesReady class method."""
        return cls(
            batch_id=batch_id,
            job_id=job_id,
            worker_id=worker_id,
            filename=filename,
            byte_length=byte_length,
        )
    
    def get_bytes(self) -> bytes:
        d = asdict(self)
        if not d:
            raise ProtocolError(
                "images_ready is incomplete."
            )
        return json.dumps(d).encode("utf-8")




@dataclass
class WorkerJob:
    """Internal representation of a job within the worker."""
    input_file: str | None = None
    out_path: str | None = None
    batch_id: int | None = None
    job_id: int | None = None
    options: FileOptions | None = None


    @classmethod
    def from_new_job(
        cls,
        input_file: str,
        out_path: str,
        batch_id: int,
        job_id: int,
        options: FileOptions
    ) -> "WorkerJob":
        """Worker creates from new_job"""
        return cls(
            input_file=input_file,
            out_path=out_path,
            batch_id=batch_id,
            job_id=job_id,
            options=options,
        )


@dataclass
class JobError:
    """Error report from worker to backend."""

    v: int = PROTOCOL_VERSION
    type: Literal["job_error"] = "job_error"
    batch_id: int | None = None
    job_id: int | None = None
    w_id: int | None = None
    stage: JobStage = "unknown"
    error: str = ""
    traceback: str | None = None
    retryable: bool = False

    def error_dict(self):
        d = asdict(self)
        if (self.batch_id is None or self.job_id is None
            or self.w_id is None or self.traceback is None):

            raise ProtocolError(
                "Incomplete JobError Message"
            )
        return d


@dataclass
class Heartbeat:
    """UDP heartbeat from worker to backend."""

    type: Literal["heartbeat"] = "heartbeat"
    worker_id: int | None = None
    time: float | None = None

    def get_heartbeat(self) -> dict[str, Any]:
        if self.worker_id is None:
            raise ProtocolError(
                "Host or port are unspecified"
            )
        self.time = time.time()
        return asdict(self)


@dataclass
class WorkerRegistration:
    """Worker -> Backend registration message."""

    type: Literal["new_convertor"] = "new_convertor"
    host: str | None = None
    port: int | None = None

    def get_reg_dict(self) -> dict:
        d = asdict(self)
        if self.host is None or self.port is None:
            raise ProtocolError(
                "Registration message doesn't have host or port."
            )
        return d


@dataclass
class WorkerAck:
    """Backend -> Worker after backend registers worker"""

    type: Literal["ack"] = "ack"
    id: int | None = None


@dataclass
class NewBatch:
    """Backend -> Worker to clear state for new batch."""
    type: Literal["new_batch"] = "new_batch"
    batch_id: int | None = None
    # Set to false for now to override and clear state, but in
    # the future, can add the ability to finish current jobs
    # while filling up queue for the next jobs
    finish_jobs: bool = False

    def new_batch_dict(self):
        d = asdict(self)
        if self.batch_id is None:
            raise ProtocolError(
                "Unfinished new_batch msg."
            )
        return d


@dataclass
class Shutdown:
    """Shutdown signal."""
    type: Literal["shutdown"] = "shutdown"
    host: str | None = None
    port: int | None = None

    def shutdown_dict(self):
        d = asdict(self)
        if self.host is None or self.port is None:
            raise ProtocolError(
                "Unfinished shutdown msg."
            )
        return d


def parse_file_options(data: dict[str, Any] | None) -> FileOptions:
    if data is None:
        return FileOptions()
    return FileOptions(
        lossless=bool(data.get("lossless", False)),
        text_focus=bool(data.get("text_focus", False)),
        has_text=bool(data.get("has_text", False)),
        type=data.get("type", "default"),
        crop_size_w=data.get("crop_size_w"),
        crop_size_h=data.get("crop_size_h"),
        crop_top_x=data.get("crop_top_x"),
        crop_top_y=data.get("crop_top_y"),
        crop_w=data.get("crop_w"),
        crop_h=data.get("crop_h"),
        size_type=data.get("size_type", "content"),
        width=data.get("width"),
        height=data.get("height"),
    )