"""Worker server implementation."""

from __future__ import annotations

import logging
import shutil
import threading
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from webp_shared.tcp import send_file_tcp, send_tcp, tcp_server
from webp_shared.udp import send_heartbeats
from webp_shared import protocol
from webp_converter import ConversionJob

from .config import WorkerConfig

logger = logging.getLogger(__name__)


class WorkerServer:
    """Worker process that receives and executes conversion jobs."""

    def __init__(self, config: WorkerConfig):
        self._config = config
        config.ensure_directories()

        self._host = config.host
        self._port = config.port
        self._backend_host = config.backend_host
        self._backend_tcp_port = config.backend_tcp_port
        self._backend_udp_port = config.backend_udp_port
        self._jobs_dir = config.jobs_dir.resolve()
        self._output_dir = config.output_dir.resolve()

        self._lock = threading.Lock()
        self._batch_id = -1
        self._worker_id: int | None = None

        self._shutdown = threading.Event()
        self._new_batch = threading.Event()
        self._registered = threading.Event()
        self._job_queue: Queue[dict[str, Any]] = Queue()

    def run(self) -> None:
        """Run the worker until shutdown."""
        logger.info("Starting worker at %s:%d", self._host, self._port)

        tcp_thread = threading.Thread(
            target=tcp_server,
            args=(self._host, self._port, self._jobs_dir,
                  self._shutdown, self._handle_message),
            daemon=True,
        )
        tcp_thread.start()

        if not self._register_with_backend():
            logger.error("Failed to register")
            self._shutdown.set()
            return
        

        heartbeat_thread = threading.Thread(
            target=send_heartbeats,
            args=(self._worker_id, self._backend_host,
                  self._backend_udp_port, self._shutdown),
            daemon=True,
        )
        heartbeat_thread.start()

        self._process_jobs()

        logger.info("Worker stopped")

    def _register_with_backend(self, timeout: float = 30.0) -> bool:
        """Register with backend and wait for ack."""
        for attempt in range(4):
            try:
                register_msg = protocol.WorkerRegistration(
                    host=self._host,
                    port=self._port,
                ).get_reg_dict()
                send_tcp(self._backend_host, 
                         self._backend_tcp_port, 
                         register_msg
                )
            except Exception as e:
                logger.warning("Registration attempt %d failed: %s", attempt, e)
                continue

            if self._registered.wait(timeout=10.0):
                logger.info("Registered as worker %d", self._worker_id)
                return True

        return False

    def _process_jobs(self) -> None:
        """Main job processing loop."""
        while not self._shutdown.is_set():
            try:
                msg = self._job_queue.get(timeout=1.0)
            except Empty:
                continue

            if msg.get("type") == "new_batch":
                self._handle_new_batch(msg)
                continue

            if msg.get("type") != "new_job":
                continue

            if msg.get("batch_id") != self._batch_id:
                continue

            self._process_single_job(msg)

    def _process_single_job(self, msg: dict[str, Any]) -> None:
        """Process a single conversion job."""
        job_id = int(msg.get("job_id", -1))
        batch_id = self._batch_id

        logger.info("Processing job %d", job_id)

        out_dir = self._output_dir / str(job_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            options_dict = msg.get("options", {})
            file_options = protocol.parse_file_options(options_dict)

            worker_job = protocol.WorkerJob(
                input_file=msg.get("saved_path"),
                out_path=str(out_dir),
                job_id=job_id,
                options=file_options,
            )

            conversion = ConversionJob(
                worker_job,
                new_batch_event=self._new_batch,
                shutdown_event=self._shutdown,
            )
            result = conversion.run()

            if self._new_batch.is_set() or self._shutdown.is_set():
                return

            zip_path = self._output_dir / f"result-{self._worker_id}-{job_id}.zip"
            shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=str(out_dir))

            images_ready = protocol.SendFiles.img_ready_msg(
                batch_id, job_id, self._worker_id, zip_path
            )

            send_file_tcp(self._backend_host, self._backend_tcp_port, images_ready)

            logger.info("Job %d complete: %d files", job_id, len(result.output_files))

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error("Job %d failed: %s", job_id, error_msg)

            try:
                error_msg = protocol.JobError(
                    batch_id=batch_id,
                    job_id=job_id,
                    w_id=self._worker_id,
                    error=error_msg,
                    traceback=traceback.format_exc(),
                ).error_dict()

                send_tcp(self._backend_host, self._backend_tcp_port, error_msg)
            except protocol.ProtocolError as e:
                logger.error(f"Protocol error {e}")
            
            except Exception:
                pass

    def _handle_new_batch(self, msg: dict[str, Any]) -> None:
        """Handle new batch notification."""
        with self._lock:
            self._batch_id = int(msg.get("batch_id", -1))

        self._new_batch.set()

        if self._output_dir.exists():
            shutil.rmtree(self._output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        while not self._job_queue.empty():
            try:
                self._job_queue.get_nowait()
            except Empty:
                break

        self._new_batch.clear()
        logger.info("Switched to batch %d", self._batch_id)

    def _handle_message(self, msg: dict[str, Any]) -> None:
        """Handle TCP message."""
        msg_type = msg.get("type")

        if msg_type == "shutdown":
            self._shutdown.set()
        elif msg_type == "ack":
            self._worker_id = msg.get("id")
            self._registered.set()
        elif msg_type == "new_batch":
            with self._lock:
                self._batch_id = int(msg.get("batch_id", -1))
            self._job_queue.put(msg)
        elif msg_type == "new_job":
            if msg.get("batch_id") == self._batch_id:
                self._job_queue.put(msg)
