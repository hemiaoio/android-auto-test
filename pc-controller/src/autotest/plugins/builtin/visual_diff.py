"""Visual regression testing plugin.

Compares screenshots pixel-by-pixel to detect UI changes.
Generates diff images highlighting differences.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autotest.plugins.base import Plugin, PluginContext, PluginInfo

logger = logging.getLogger(__name__)


@dataclass
class DiffResult:
    is_match: bool
    diff_percentage: float
    diff_pixel_count: int
    total_pixels: int
    diff_image: bytes | None = None  # PNG bytes of diff visualization
    diff_regions: list[dict[str, int]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.diff_regions is None:
            self.diff_regions = []


class VisualDiffPlugin(Plugin):
    """Pixel-level visual regression comparison."""

    def __init__(self) -> None:
        self._context: PluginContext | None = None
        self._baseline_dir: Path = Path("./baselines")

    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.visual_diff",
            name="Visual Regression Testing",
            version="1.0.0",
            description="Compare screenshots to detect UI regressions",
        )

    async def on_init(self, context: PluginContext) -> None:
        self._context = context
        self._baseline_dir = Path(context.data_dir) / "baselines"
        self._baseline_dir.mkdir(parents=True, exist_ok=True)

    async def compare(
        self,
        actual: bytes,
        expected: bytes,
        threshold: float = 0.01,
        ignore_regions: list[dict[str, int]] | None = None,
    ) -> DiffResult:
        """Compare two screenshots pixel-by-pixel.

        Args:
            actual: Current screenshot (PNG bytes)
            expected: Baseline screenshot (PNG bytes)
            threshold: Max allowed diff percentage (0-1)
            ignore_regions: Regions to ignore [{"left":, "top":, "right":, "bottom":}]
        """
        try:
            from PIL import Image

            img_actual = Image.open(io.BytesIO(actual)).convert("RGB")
            img_expected = Image.open(io.BytesIO(expected)).convert("RGB")

            if img_actual.size != img_expected.size:
                return DiffResult(
                    is_match=False,
                    diff_percentage=100.0,
                    diff_pixel_count=img_actual.size[0] * img_actual.size[1],
                    total_pixels=img_actual.size[0] * img_actual.size[1],
                )

            width, height = img_actual.size
            total = width * height
            pixels_a = list(img_actual.getdata())
            pixels_e = list(img_expected.getdata())

            diff_count = 0
            diff_pixels: list[int] = []

            ignore = ignore_regions or []

            for i in range(total):
                x = i % width
                y = i // width

                # Check ignore regions
                skip = False
                for region in ignore:
                    if (region["left"] <= x <= region["right"] and
                            region["top"] <= y <= region["bottom"]):
                        skip = True
                        break
                if skip:
                    diff_pixels.append(0)
                    continue

                pa = pixels_a[i]
                pe = pixels_e[i]
                channel_diff = sum(abs(a - b) for a, b in zip(pa[:3], pe[:3]))

                if channel_diff > 30:  # ~4% per channel tolerance
                    diff_count += 1
                    diff_pixels.append(1)
                else:
                    diff_pixels.append(0)

            diff_pct = diff_count / total * 100 if total > 0 else 0
            is_match = diff_pct <= threshold * 100

            # Generate diff image
            diff_image_bytes = None
            if diff_count > 0:
                diff_img = Image.new("RGB", (width, height))
                diff_data = []
                for i, is_diff in enumerate(diff_pixels):
                    if is_diff:
                        diff_data.append((255, 0, 0))  # Red for differences
                    else:
                        # Dim the original
                        r, g, b = pixels_a[i][:3]
                        diff_data.append((r // 3, g // 3, b // 3))
                diff_img.putdata(diff_data)
                buf = io.BytesIO()
                diff_img.save(buf, format="PNG")
                diff_image_bytes = buf.getvalue()

            return DiffResult(
                is_match=is_match,
                diff_percentage=diff_pct,
                diff_pixel_count=diff_count,
                total_pixels=total,
                diff_image=diff_image_bytes,
            )

        except ImportError:
            logger.warning("PIL not available. Install pillow for visual diff.")
            return DiffResult(
                is_match=False, diff_percentage=100, diff_pixel_count=0, total_pixels=0
            )

    async def save_baseline(self, name: str, screenshot: bytes) -> Path:
        """Save a screenshot as a baseline for future comparisons."""
        path = self._baseline_dir / f"{name}.png"
        path.write_bytes(screenshot)
        logger.info("Saved baseline: %s", path)
        return path

    async def load_baseline(self, name: str) -> bytes | None:
        """Load a previously saved baseline."""
        path = self._baseline_dir / f"{name}.png"
        if path.exists():
            return path.read_bytes()
        return None

    async def compare_with_baseline(
        self, name: str, actual: bytes, threshold: float = 0.01
    ) -> DiffResult:
        """Compare a screenshot against a saved baseline."""
        baseline = await self.load_baseline(name)
        if baseline is None:
            # First run: save as baseline
            await self.save_baseline(name, actual)
            return DiffResult(
                is_match=True, diff_percentage=0, diff_pixel_count=0,
                total_pixels=0
            )
        return await self.compare(actual, baseline, threshold)
