"""Upload and file serving routes."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from webp_shared.files import extract_files

logger = logging.getLogger(__name__)

uploads_bp = Blueprint("uploads", __name__, url_prefix="/api")


@uploads_bp.post("/upload-zip")
def upload_zip():
    """Upload a ZIP archive or single image for processing."""
    job_service = current_app.config["job_service"]
    extract_dir = current_app.config["extract_dir"]
    upload_dir = current_app.config["upload_dir"]

    batch_id = job_service.new_batch()

    f = request.files.get("file")
    if f is None:
        abort(400, description="Missing file field 'file'")

    filename = secure_filename(f.filename or "")
    if not filename:
        abort(400, description="Invalid filename")

    ext = Path(filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".zip"}:
        abort(400, description="File must be .png, .jpg, .jpeg, or .zip")

    temp_path = upload_dir / f"{batch_id}{ext}"
    f.save(temp_path)

    dest_dir = extract_dir / str(batch_id)
    raw_images = extract_files(temp_path, dest_dir)

    if not raw_images:
        abort(400, description="No valid images found")

    manifest = {}
    images = []

    for job_id, raw_path_str in enumerate(raw_images):
        raw_path = Path(raw_path_str)
        new_name = f"{job_id}{raw_path.suffix}"
        new_path = dest_dir / new_name

        if raw_path != new_path:
            raw_path.rename(new_path)

        logger.info(f"File exists at {new_path}: {new_path.exists()}")
        manifest[job_id] = {
            "original_name": raw_path.name,
            "original_ext": raw_path.suffix.lower(),
        }
        images.append({
            "job_id": job_id,
            "url": f"/api/files/{batch_id}/input/{job_id}",
            "original_name": raw_path.name,
        })

    (dest_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    job_service.set_job_count(len(images))

    return jsonify({"batch_id": batch_id, "images": images})


@uploads_bp.get("/files/<int:batch_id>/input/<int:image_id>")
def serve_input_image(batch_id: int, image_id: int):
    """Serve an extracted input image for preview."""
    extract_dir: Path = current_app.config["extract_dir"]
    batch_dir = extract_dir / str(batch_id)
    
    logger.info(f"extract_dir config: {extract_dir}")
    logger.info(f"batch_dir: {batch_dir}")
    logger.info(f"batch_dir exists: {batch_dir.exists()}")
    
    if batch_dir.exists():
        logger.info(f"Contents: {list(batch_dir.iterdir())}")
    if not batch_dir.exists():
        abort(404, description="Batch not found")

    for ext in (".png", ".jpg", ".jpeg"):
        candidate = batch_dir / f"{image_id}{ext}"
        logger.info(f"Checking: {candidate} - exists: {candidate.exists()}")
        if candidate.exists():
            mimetype = "image/jpeg" if ext == ".jpg" else f"image/{ext[1:]}"
            return send_from_directory(batch_dir, candidate.name, mimetype=mimetype)

    abort(404, description="Image not found")


@uploads_bp.get("/files/<int:batch_id>/output/<int:job_id>/<path:filename>")
def serve_output_webp(batch_id: int, job_id: int, filename: str):
    """Serve a converted WebP file."""
    results_dir: Path = current_app.config["results_dir"]

    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        abort(400, description="Invalid filename")

    job_dir = results_dir / str(batch_id) / str(job_id)
    if not job_dir.exists():
        abort(404, description="Job not found")

    file_path = job_dir / safe_name
    if not file_path.exists():
        abort(404, description="File not found")

    return send_from_directory(job_dir, safe_name, mimetype="image/webp")
