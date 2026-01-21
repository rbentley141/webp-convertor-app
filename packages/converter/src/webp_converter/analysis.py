"""
Image analysis utilities for quality optimization.

Analyzes images to provide factors that can strengthen
hardcoded parameters decided by user input.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

def edge_density(gray: np.ndarray) -> float:
    """
    Calculate the edge density of a grayscale image.

    Returns Edge density in range [0.0, 1.0]
    """
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, threshold1=100, threshold2=200, L2gradient=True)
    edge_pixels = np.count_nonzero(edges)
    total_pixels = edges.size
    return edge_pixels / total_pixels if total_pixels > 0 else 0.0


def center_background_contrast(gray: np.ndarray) -> float:
    """
    Calculate contrast between image center and edges.

    Returns: Absolute difference in mean brightness [0.0, 255.0]
    """
    h, w = gray.shape
    cx0, cx1 = int(w * 0.30), int(w * 0.70)
    cy0, cy1 = int(h * 0.30), int(h * 0.70)

    center = gray[cy0:cy1, cx0:cx1]
    border = gray.copy()
    border[cy0:cy1, cx0:cx1] = 0
    border_vals = border[border > 0]

    if border_vals.size == 0:
        return 0.0

    return float(abs(center.mean() - border_vals.mean()))


def analyze_image(image_path: Path) -> Tuple[float, float]:
    """
    Analyze an image and return quality hints.

    Returns Tuple of (edge_density, center_contrast)

    Raises ValueError: If image is multi-frame
    """
    img = Image.open(image_path)

    n_frames = getattr(img, "n_frames", 1)
    if n_frames != 1:
        raise ValueError(f"Multi-frame image not supported: {image_path}")

    img = ImageOps.exif_transpose(img)

    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )

    if has_alpha:
        img = img.convert("RGBA")
        rgba = np.array(img, dtype=np.uint8)
        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
    else:
        img = img.convert("RGB")
        rgb = np.array(img, dtype=np.uint8)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    bgr = np.ascontiguousarray(bgr)

    h, w = bgr.shape[:2]
    max_dim = max(h, w)
    if max_dim > 512:
        scale = 512 / max_dim
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    ed = edge_density(gray)
    cc = center_background_contrast(gray)

    logger.debug("Analysis for %s: edge_density=%.3f, contrast=%.1f", image_path.name, ed, cc)
    return ed, cc
