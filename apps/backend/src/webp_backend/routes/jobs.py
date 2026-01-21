"""Job submission and polling routes."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request

from webp_shared.protocol import FileOptions, StartJob

logger = logging.getLogger(__name__)

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api")


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_str(value: str | None) -> str | None:
    return None if value is None or value == "" else value


@jobs_bp.post("/submit-job")
def submit_job():
    """Submit a single image for conversion."""
    job_service = current_app.config["job_service"]
    extract_dir: Path = current_app.config["extract_dir"]

    batch_id = _parse_int(request.form.get("batch_id"))
    job_id = _parse_int(request.form.get("image_id"))

    if batch_id is None or job_id is None:
        abort(400, description="batch_id and image_id are required")

    batch_dir = extract_dir / str(batch_id)
    input_file = None
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = batch_dir / f"{job_id}{ext}"
        if candidate.exists():
            input_file = candidate
            break

    if input_file is None:
        abort(400, description=f"Image {job_id} not found in batch {batch_id}")

    options = FileOptions(
        width=_parse_int(request.form.get("width")),
        height=_parse_int(request.form.get("height")),
        size_type=_parse_str(request.form.get("size_type")) if not (
            _parse_int(request.form.get("width")) or _parse_int(request.form.get("height"))
        ) else None,
        crop_size_w=_parse_int(request.form.get("crop_size_w")),
        crop_size_h=_parse_int(request.form.get("crop_size_h")),
        crop_top_x=_parse_int(request.form.get("crop_top_x")),
        crop_top_y=_parse_int(request.form.get("crop_top_y")),
        crop_w=_parse_int(request.form.get("crop_w")),
        crop_h=_parse_int(request.form.get("crop_h")),
        lossless="lossless" in request.form,
        text_focus="text_focus" in request.form,
        has_text="has_text" in request.form,
        type=request.form.get("type", "default"),
    )

    job = {
        "job_id": job_id,
        "input_file": Path(input_file),
        "options": options,
    }

    if not job_service.start_job(job):
        return jsonify({"type": "no_worker"}), 503

    return "", 200


@jobs_bp.get("/get-next-job")
def get_next_job():
    """Poll for the next completed job result."""
    job_service = current_app.config["job_service"]

    if job_service.is_batch_complete():
        return jsonify({"type": "jobs_done"})

    result = job_service.get_next_result(timeout=3.0)

    if result is None:
        return jsonify({"type": "processing"})

    return jsonify(result)
