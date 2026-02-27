"""Performance chart generation using SVG (no external dependencies)."""

from __future__ import annotations

from autotest.performance.analyzer import PerfAnalysisResult


class PerfVisualizer:
    """Generates inline SVG charts for performance reports."""

    @staticmethod
    def generate_cpu_chart(analysis: PerfAnalysisResult, width: int = 600, height: int = 200) -> str:
        if not analysis.cpu or not analysis.cpu.samples:
            return ""
        return _line_chart(
            analysis.cpu.samples, width, height,
            title="CPU Usage (%)", color="#e74c3c", y_max=100,
            threshold=analysis.cpu.avg, threshold_label=f"avg: {analysis.cpu.avg:.1f}%"
        )

    @staticmethod
    def generate_memory_chart(analysis: PerfAnalysisResult, width: int = 600, height: int = 200) -> str:
        if not analysis.memory or not analysis.memory.samples:
            return ""
        samples_mb = [s / 1024 for s in analysis.memory.samples]
        return _line_chart(
            samples_mb, width, height,
            title="Memory PSS (MB)", color="#3498db",
            threshold=analysis.memory.avg_pss_kb / 1024,
            threshold_label=f"avg: {analysis.memory.avg_pss_kb / 1024:.1f}MB"
        )

    @staticmethod
    def generate_fps_chart(analysis: PerfAnalysisResult, width: int = 600, height: int = 200) -> str:
        if not analysis.fps or not analysis.fps.samples:
            return ""
        return _line_chart(
            analysis.fps.samples, width, height,
            title="FPS", color="#2ecc71", y_max=70,
            threshold=60, threshold_label="target: 60fps"
        )


def _line_chart(
    data: list[float], width: int, height: int,
    title: str, color: str, y_max: float | None = None,
    threshold: float | None = None, threshold_label: str = ""
) -> str:
    if not data:
        return ""

    pad_top, pad_bottom, pad_left, pad_right = 30, 25, 50, 20
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    data_max = y_max or max(data) * 1.1
    if data_max == 0:
        data_max = 1

    x_step = chart_w / max(len(data) - 1, 1)
    points = []
    for i, val in enumerate(data):
        x = pad_left + i * x_step
        y = pad_top + chart_h - (val / data_max * chart_h)
        points.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(points)

    # Area fill
    area_points = f"{pad_left},{pad_top + chart_h} {polyline} {pad_left + (len(data) - 1) * x_step},{pad_top + chart_h}"

    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="#fafafa" rx="4"/>',
        # Title
        f'<text x="{pad_left}" y="18" font-size="13" font-family="sans-serif" fill="#333">{title}</text>',
        # Grid lines
    ]

    # Y-axis grid
    for i in range(5):
        y = pad_top + chart_h * i / 4
        val = data_max * (4 - i) / 4
        svg_parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" '
            f'stroke="#eee" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{pad_left - 5}" y="{y + 4:.1f}" font-size="10" '
            f'font-family="sans-serif" fill="#999" text-anchor="end">{val:.0f}</text>'
        )

    # Threshold line
    if threshold is not None and threshold > 0:
        ty = pad_top + chart_h - (threshold / data_max * chart_h)
        svg_parts.append(
            f'<line x1="{pad_left}" y1="{ty:.1f}" x2="{width - pad_right}" y2="{ty:.1f}" '
            f'stroke="#ff9800" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        svg_parts.append(
            f'<text x="{width - pad_right}" y="{ty - 3:.1f}" font-size="9" '
            f'font-family="sans-serif" fill="#ff9800" text-anchor="end">{threshold_label}</text>'
        )

    # Area + Line
    svg_parts.extend([
        f'<polygon points="{area_points}" fill="{color}" opacity="0.1"/>',
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5"/>',
    ])

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
