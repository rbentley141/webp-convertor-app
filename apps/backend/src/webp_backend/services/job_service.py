"""
Job Orchestration for the WebP backend.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from webp_shared.tcp import send_file_tcp, send_tcp, tcp_server
from webp_shared.udp import udp_server
from webp_shared import protocol

from ..config import Config

logger = logging.getLogger(__name__)

@dataclass
class WorkerState:
    """Tracks the state of a registered worker."""
    host: str
    port: int
    last_heartbeat: float = field(default_factory=time.time)
    status: str = "alive"
    active_jobs: list[int] = field(default_factory=list)


@dataclass
class JobState:
    """Tracks the state of a dispatched job."""
    job_id: int
    batch_id: int
    job_dict: dict[str, Any] = field(default_factory=dict)
    worker: int | None = None
    status: str = "pending"
    error: str | None = None


class JobService:
    """Manages job dispatch and worker coordination."""
    def __init__(self, config: Config):
        self._config = config
        self.results_dir = config.results_dir

        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

        self._workers: dict[int, WorkerState] = {}
        self._next_worker_id = 0

        self._batch_id = 0
        self._next_job_id = 0
        self._jobs: dict[int, JobState] = {}
        self._total_jobs = 0
        self._completed_jobs = 0
        self._results: Queue[dict[str, Any]] = Queue()

        self._tcp_thread = threading.Thread(
            target=tcp_server,
            args=(config.tcp_host, config.tcp_port, self.results_dir,
                  self._shutdown_event, self._handle_tcp_message),
            daemon=True,
        )
        self._tcp_thread.start()

        self._udp_thread = threading.Thread(
            target=udp_server,
            args=(config.tcp_host, config.udp_port,
                  self._shutdown_event, self._handle_heartbeat),
            daemon=True,
        )
        self._udp_thread.start()

        self._monitor_thread = threading.Thread(
            target=self._monitor_heartbeats,
            daemon=True,
        )
        self._monitor_thread.start()

        logger.info("JobService started on %s:%d", config.tcp_host, config.tcp_port)


    def shutdown(self) -> None:
        self._shutdown_event.set()
        with self._lock:
            workers = [
                (w.host, w.port) for w in self._workers.values()
            ]
        try:
            msg = protocol.Shutdown(
                host=self._config.tcp_host,
                port=self._config.tcp_port
            ).shutdown_dict()
        except protocol.ProtocolError as e:
            logger.error(e)
        for host, port in workers:
            try:
                send_tcp(host, port, msg)
            except Exception:
                pass
    

    def new_batch(self) -> int:
        """Start a new batch, clearing previous state."""
        with self._lock:
            self._batch_id += 1
            batch_id = self._batch_id
            self._jobs.clear()
            self._next_job_id = 0
            self._total_jobs = 0
            self._completed_jobs = 0
            self._results = Queue()
            workers = [
                (w.host, w.port) for w in self._workers.values()
            ]
            try:
                new_batch_msg = protocol.NewBatch(batch_id=self._batch_id).new_batch_dict()
            except protocol.ProtocolError as e:
                logger.error(e)
        for host, port in workers:
            try:
                send_tcp(host, port, new_batch_msg)
            except Exception as e:
                logger.warning("Failed to notify worker: %s", e)

        return batch_id
    
    def set_job_count(self, count: int) -> None:
        with self._lock:
            self._total_jobs = count

    def is_batch_complete(self) -> bool:
        with self._lock:
            return self._total_jobs > 0 and self._completed_jobs >= self._total_jobs

    def start_job(self, job_data: dict[str, Any]) -> bool:
        """Dispatch a job to an available worker."""
        with self._lock:
            job_id = job_data.get("job_id")
            if job_id is None:
                job_id = self._next_job_id
                self._next_job_id += 1
            job_data["job_id"] = job_id
            job_data["batch_id"] = self._batch_id

            alive = [(len(w.active_jobs), w_id) for w_id, w in self._workers.items()
                     if w.status == "alive"]
            if not alive:
                return False

            alive.sort(key=lambda x: x[0])
            _, id = alive[0]
            host = self._workers[id].host
            port = self._workers[id].port

            input_path = Path(job_data["input_file"])
            job_data["filename"] = f"job-{job_id}{input_path.suffix}"

            self._workers[id].active_jobs.append(job_id)
            self._jobs[job_id] = JobState(
                job_id=job_id,
                batch_id=self._batch_id,
                job_dict=dict(job_data),
                worker=(host, port),
                status="running",
            )

        try:
            file_data = protocol.SendFiles.start_job(
                job_data["batch_id"], job_data["job_id"],
                job_data["input_file"], job_data["filename"],
                job_data["options"]
            )
            send_file_tcp(host, port, file_data)
            return True
        except Exception as e:
            logger.error("Failed to dispatch job %d: %s", job_id, e)
            return False

    def get_next_result(self, timeout: float = 3.0) -> dict[str, Any] | None:
        """Get the next completed job result."""
        if self.is_batch_complete():
            return None
        try:
            result = self._results.get(timeout=timeout)
            with self._lock:
                self._completed_jobs += 1
            return result
        except Empty:
            return None

    def _handle_tcp_message(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("type")

        if msg_type == "shutdown":
            self._shutdown_event.set()
        elif msg_type == "new_convertor":
            self._register_worker(msg)
        elif msg_type == "images_ready":
            self._handle_job_complete(msg)
        elif msg_type == "job_error":
            self._handle_job_error(msg)

    def _register_worker(self, msg: dict[str, Any]) -> None:
        host = str(msg.get("host", ""))
        port = int(msg.get("port", 0))
        if not host or not port:
            return
        
        with self._lock:
            for w in self._workers.values():
                if w.host == host and w.port == port:
                    return
            
            key = self._next_worker_id
            self._next_worker_id += 1
            self._workers[key] = WorkerState(
                host=host,
                port=port,
            )

        logger.info("Registered worker %d at %s:%d", key, host, port)
        try:
            send_tcp(host, port, {"type": "ack", "id": key})
        except Exception as e:
            logger.error("Failed to ack worker: %s", e)

    def _handle_job_complete(self, msg: dict[str, Any]) -> None:
        batch_id = int(msg.get("batch_id", -1))
        job_id = int(msg.get("job_id", -1))
        worker_id = int(msg.get("worker_id", -1))

        with self._lock:
            if batch_id != self._batch_id:
                return
            if worker_id == -1 or worker_id not in self._workers:
                return
            worker = self._workers.get(worker_id)
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"

            w_host, w_port = worker.host, worker.port
            if w_host and w_port:
                if worker and job_id in worker.active_jobs:
                    worker.active_jobs.remove(job_id)

        paths = msg.get("paths", [])
        urls = [f"/api/files/{batch_id}/output/{job_id}/{Path(p).name}" for p in paths]

        self._results.put({
            "type": "images",
            "batch_id": batch_id,
            "job_id": job_id,
            "urls": urls,
        })

    def _handle_job_error(self, msg: dict[str, Any]) -> None:
        job_id = int(msg.get("job_id", -1))
        batch_id = int(msg.get("batch_id", -1))

        with self._lock:
            if batch_id != self._batch_id:
                return
            job = self._jobs.get(job_id)
            if job:
                job.status = "error"
                job.error = msg.get("error")

        self._results.put({
            "type": "job_error",
            "batch_id": batch_id,
            "job_id": job_id,
            "error": msg.get("error"),
            "traceback": msg.get("traceback"),
        })

    def _handle_heartbeat(self, msg: dict[str, Any]) -> None:
        if msg.get("type") != "heartbeat":
            return
        worker_id = msg.get("worker_id")
        if worker_id is None:
            return

        with self._lock:
            worker = self._workers.get(worker_id)
            if worker and worker.status == "alive":
                worker.last_heartbeat = float(msg["time"])

    def _monitor_heartbeats(self) -> None:
        """Detect dead workers and reassign their jobs."""
        while not self._shutdown_event.is_set():
            time.sleep(2.0)
            now = time.time()
            jobs_to_reassign = []

            with self._lock:
                for worker in self._workers.values():
                    if worker.status == "dead":
                        continue
                    if now - worker.last_heartbeat >= self._config.heartbeat_timeout:
                        logger.warning("Worker %s:%d is dead. Last recorded time: %d", worker.host, worker.port, worker.last_heartbeat)
                        worker.status = "dead"
                        for job_id in worker.active_jobs:
                            job = self._jobs.get(job_id)
                            if job and job.status == "running":
                                jobs_to_reassign.append(job.job_dict)
                        worker.active_jobs.clear()

            for job_dict in jobs_to_reassign:
                self.start_job(job_dict)

