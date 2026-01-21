"""
Image conversion orchestration for WebP output.

This module handles the high-level conversion workflow:
1. Pre-process (crop, resize large images)
2. Choose quality/size variants based on image analysis
3. Run cwebp multiple times with different settings
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from webp_shared.protocol import FileOptions, WorkerJob

from .analysis import analyze_image
from .cwebp import CwebpError, convert_with_retry

logger = logging.getLogger(__name__)

SIZE_PRESETS: dict[str, list[int]] = {
    "banner": [1200, 1500, 1800],
    "content": [800, 1000, 1200, 1400],
    "thumbnail": [400, 500, 650, 800],
    "icon": [96, 128, 256],
    "default": [600, 800, 1000, 1200],
}

MAX_DIMENSION = 8000
MAX_PIXELS = 50_000_000


@dataclass
class ConversionResult:
    """Result of a conversion job."""
    output_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ConversionJob:
    """
    Orchestrates the conversion of a single image to WebP.

    The job generates multiple output variants at different sizes and
    quality levels based on the FileOptions.
    """

    def __init__(
        self,
        job: WorkerJob,
        new_batch_event: threading.Event | None = None,
        shutdown_event: threading.Event | None = None,
    ):
        self._new_batch = new_batch_event or threading.Event()
        self._shutdown = shutdown_event or threading.Event()

        if job.input_file is None:
            raise ValueError("WorkerJob.input_file is required")
        if job.out_path is None:
            raise ValueError("WorkerJob.out_path is required")

        self.input_file = Path(job.input_file)
        self.output_dir = Path(job.out_path)
        self.options: FileOptions = job.options or FileOptions()

        self._working_file: Path = self.input_file
        self._size_args: list[list[str]] = []
        self.quality_factor: float = 1.0
        self.sharpness: int = 4

        if self.options.has_text:
            self.sharpness = 1

        ext = self.input_file.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            raise ValueError(f"Unsupported input format: {ext}")

    def should_stop(self) -> bool:
        """Check if the job should be cancelled."""
        return self._new_batch.is_set() or self._shutdown.is_set()

    def run(self) -> ConversionResult:
        """Execute the conversion job."""
        result = ConversionResult()

        if self.should_stop():
            return result

        self._preprocess()
        if self.should_stop():
            return result

        self._choose_sizes()
        if self.should_stop():
            return result

        self.output_dir.mkdir(parents=True, exist_ok=True)
        variants = self._get_quality_variants()

        if not self._size_args:
            self._size_args = [[]]

        size0 = self._size_args[0]
        size1 = self._size_args[1] if len(self._size_args) >= 2 else size0

        for i in range(12):
            if self.should_stop():
                break

            size_args = size0 if i < 6 else size1
            variant_args = variants[i % 6]
            output_path = self.output_dir / f"{i}.webp"

            try:
                convert_with_retry(
                    self._working_file,
                    output_path,
                    size_args + variant_args,
                    max_retries=4,
                )
                if output_path.exists():
                    result.output_files.append(output_path)
            except CwebpError as e:
                result.errors.append(f"Variant {i}: {e}")
                logger.warning("Variant %d failed: %s", i, e)
            except Exception as e:
                result.errors.append(f"Variant {i}: {type(e).__name__}: {e}")

        if not result.output_files:
            raise RuntimeError(f"All variants failed. Errors: {result.errors}")

        logger.info("Conversion complete: %d files", len(result.output_files))
        return result

    def _preprocess(self) -> None:
        """Apply cropping and handle oversized images."""
        with Image.open(self.input_file) as img:
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            modified = False

            if self.options.has_crop():
                scale_x = width / self.options.crop_size_w
                scale_y = height / self.options.crop_size_h

                x = int(round(self.options.crop_top_x * scale_x))
                y = int(round(self.options.crop_top_y * scale_y))
                w = int(round(self.options.crop_w * scale_x))
                h = int(round(self.options.crop_h * scale_y))

                img = img.crop((x, y, x + w, y + h))
                width, height = w, h
                modified = True

            if max(width, height) >= MAX_DIMENSION or (width * height) >= MAX_PIXELS:
                while max(width, height) >= MAX_DIMENSION or (width * height) >= MAX_PIXELS:
                    width = int(width * 0.95)
                    height = int(height * 0.95)
                img = img.resize((width, height), Image.Resampling.LANCZOS)
                modified = True

            if modified:
                processed_path = self.input_file.with_name(
                    f"{self.input_file.stem}_processed{self.input_file.suffix}"
                )
                img.save(processed_path)
                self._working_file = processed_path

    def _choose_sizes(self) -> None:
        """Determine output sizes based on options and analysis."""
        if self.options.has_explicit_size():
            w = self.options.width or 0
            h = self.options.height or 0
            self._size_args = [["-resize", str(w), str(h)]]
            return

        size_key = self.options.size_type or "default"
        if size_key not in SIZE_PRESETS:
            size_key = "default"
        widths = SIZE_PRESETS[size_key]

        if self.options.type in ("product", "complex", "default"):
            ed, cc = analyze_image(self._working_file)

            if ed <= 0.05 and cc < 15:
                chosen = widths[:2]
                self.quality_factor = 1.06
            elif ed <= 0.08 and cc < 20:
                chosen = widths[1:3] if len(widths) >= 3 else widths[:2]
                self.quality_factor = 1.03
            else:
                chosen = widths[2:4] if len(widths) >= 4 else widths[-2:]

            if len(chosen) < 2:
                chosen = (widths + widths)[:2]

            self._size_args = [
                ["-resize", str(chosen[0]), "0"],
                ["-resize", str(chosen[1]), "0"],
            ]
            return

        if self.options.type == "graphic":
            self._size_args = [["-resize", "150", "0"], ["-resize", "250", "0"]]
            return

        self._size_args = [[]]

    def _get_quality_variants(self) -> list[list[str]]:
        """Get cwebp argument sets for quality variants."""
        q = lambda x: str(int(round(x * self.quality_factor)))

        if self.options.lossless:
            return [
                ["-lossless", "-m", "6", "-q", "100"],
                ["-lossless", "-z", "9"],
                ["-lossless", "-z", "6"],
                ["-near_lossless", "80"],
                ["-near_lossless", "60"],
                ["-near_lossless", "40"],
            ]

        if self.options.text_focus:
            return [
                ["-preset", "text", "-lossless", "-m", "6", "-q", "100", "-alpha_q", "100", "-exact"],
                ["-preset", "text", "-lossless", "-z", "6", "-alpha_q", "100", "-exact"],
                ["-preset", "text", "-lossless", "-z", "9", "-alpha_q", "100", "-exact"],
                ["-preset", "text", "-near_lossless", "90", "-m", "6", "-alpha_q", "100"],
                ["-preset", "text", "-near_lossless", "70", "-m", "6", "-alpha_q", "100"],
                ["-preset", "text", "-m", "6", "-q", "94", "-alpha_q", "100", "-alpha_filter", "best"],
            ]

        t = self.options.type

        if t == "product":
            s = str(self.sharpness)
            return [
                ["-m", "6", "-q", q(92), "-af", "-sharpness", s],
                ["-preset", "picture", "-m", "6", "-q", q(88), "-af"],
                ["-preset", "picture", "-m", "6", "-q", q(86), "-af"],
                ["-preset", "picture", "-m", "6", "-q", q(84), "-af"],
                ["-preset", "picture", "-m", "6", "-q", q(82), "-af"],
                ["-preset", "picture", "-m", "6", "-q", q(80), "-af"],
            ]

        if t == "complex":
            return [
                ["-preset", "photo", "-m", "6", "-q", "96", "-af"],
                ["-preset", "photo", "-m", "6", "-q", "94", "-af"],
                ["-preset", "photo", "-m", "6", "-q", "92", "-af"],
                ["-preset", "photo", "-m", "6", "-q", "90", "-af"],
                ["-preset", "photo", "-m", "6", "-q", "85", "-af"],
                ["-preset", "photo", "-m", "6", "-q", "82", "-af"],
            ]

        if t == "graphic":
            return [
                ["-preset", "drawing", "-lossless", "-m", "6", "-q", "100", "-alpha_q", "100", "-alpha_filter", "best", "-exact"],
                ["-preset", "drawing", "-lossless", "-z", "9", "-alpha_q", "100", "-alpha_filter", "best", "-exact"],
                ["-preset", "drawing", "-lossless", "-z", "6", "-alpha_q", "100", "-alpha_filter", "best", "-exact"],
                ["-preset", "drawing", "-near_lossless", "90", "-m", "6", "-alpha_q", "100"],
                ["-preset", "drawing", "-near_lossless", "75", "-m", "6", "-alpha_q", "100"],
                ["-preset", "drawing", "-near_lossless", "60", "-m", "6", "-alpha_q", "100"],
            ]

        return [
            ["-lossless", "-m", "6", "-q", "100"],
            ["-preset", "photo", "-m", "6", "-q", "96", "-af"],
            ["-preset", "picture", "-m", "6", "-q", q(90), "-af"],
            ["-preset", "photo", "-m", "6", "-q", q(90)],
            ["-m", "6", "-q", q(90), "-sns", "30", "-af"],
            ["-m", "6", "-q", q(90), "-sns", "40"],
        ]
