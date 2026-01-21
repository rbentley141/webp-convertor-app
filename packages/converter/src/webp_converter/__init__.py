"""
WebP Conversion Engine.

This package is the core image-webp conversion logic.
It is used only by workers.

Deployment:
    pip install webp-convertor

This package has no networking dependencies. It's pure image processing.

"""

from .analysis import analyze_image, center_background_contrast, edge_density
from .convert import ConversionJob, ConversionResult
from .cwebp import CwebpError, convert_with_retry, run_cwebp

__all__ = [
    "edge_density",
    "center_background_contrast",
    "analyze_image",
    "CwebpError",
    "run_cwebp",
    "convert_with_retry",
    "ConversionJob",
    "ConversionResult",
]