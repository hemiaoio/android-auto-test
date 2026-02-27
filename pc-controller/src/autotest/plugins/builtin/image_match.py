"""Image matching plugin for template-based element detection.

Finds a small template image within a larger screenshot using
pixel-level comparison. Useful for finding icons, buttons with
images, or custom-rendered UI elements.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autotest.core.types import Rect
from autotest.plugins.base import Plugin, PluginContext, PluginInfo

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    bounds: Rect
    confidence: float
    center_x: int
    center_y: int


class ImageMatchPlugin(Plugin):
    """Template-based image matching for UI elements."""

    def __init__(self) -> None:
        self._context: PluginContext | None = None
        self._template_cache: dict[str, Any] = {}

    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.image_match",
            name="Image Template Matching",
            version="1.0.0",
            description="Find UI elements by matching template images in screenshots",
        )

    async def on_init(self, context: PluginContext) -> None:
        self._context = context

    async def find_template(
        self,
        screenshot: bytes,
        template: bytes | str | Path,
        threshold: float = 0.85,
        scale_range: tuple[float, float] = (0.8, 1.2),
    ) -> list[MatchResult]:
        """Find template image within screenshot.

        Args:
            screenshot: Screenshot image bytes (PNG/JPEG)
            template: Template image as bytes or file path
            threshold: Minimum match confidence (0-1)
            scale_range: Range of scales to try for multi-scale matching
        """
        try:
            from PIL import Image

            screen_img = Image.open(io.BytesIO(screenshot)).convert("RGB")
            screen_w, screen_h = screen_img.size

            if isinstance(template, (str, Path)):
                tmpl_img = Image.open(str(template)).convert("RGB")
            else:
                tmpl_img = Image.open(io.BytesIO(template)).convert("RGB")

            tmpl_w, tmpl_h = tmpl_img.size
            results: list[MatchResult] = []

            # Simple sliding window template matching
            # In production, use OpenCV's matchTemplate for GPU-accelerated matching
            best_score = 0.0
            best_pos = (0, 0)

            screen_pixels = list(screen_img.getdata())
            tmpl_pixels = list(tmpl_img.getdata())

            step = max(1, min(tmpl_w, tmpl_h) // 4)  # Coarse grid first

            for y in range(0, screen_h - tmpl_h, step):
                for x in range(0, screen_w - tmpl_w, step):
                    score = self._quick_match(
                        screen_pixels, screen_w, tmpl_pixels, tmpl_w, tmpl_h, x, y
                    )
                    if score > best_score:
                        best_score = score
                        best_pos = (x, y)

            if best_score >= threshold:
                bx, by = best_pos
                results.append(MatchResult(
                    bounds=Rect(left=bx, top=by, right=bx + tmpl_w, bottom=by + tmpl_h),
                    confidence=best_score,
                    center_x=bx + tmpl_w // 2,
                    center_y=by + tmpl_h // 2,
                ))

            return results

        except ImportError:
            logger.warning("PIL not available. Install pillow for image matching.")
            return []

    @staticmethod
    def _quick_match(
        screen: list[tuple[int, ...]],
        screen_w: int,
        template: list[tuple[int, ...]],
        tmpl_w: int,
        tmpl_h: int,
        ox: int,
        oy: int,
    ) -> float:
        """Quick approximate match using sampled pixels."""
        matches = 0
        total = 0
        sample_step = max(1, tmpl_w * tmpl_h // 100)  # Sample ~100 pixels

        for i in range(0, len(template), sample_step):
            tx = i % tmpl_w
            ty = i // tmpl_w
            if ty >= tmpl_h:
                break

            sx = ox + tx
            sy = oy + ty
            si = sy * screen_w + sx

            if si < len(screen):
                sp = screen[si]
                tp = template[i]
                diff = sum(abs(a - b) for a, b in zip(sp[:3], tp[:3]))
                if diff < 60:  # ~8% tolerance per channel
                    matches += 1
                total += 1

        return matches / total if total > 0 else 0
