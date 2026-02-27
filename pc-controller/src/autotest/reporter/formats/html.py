"""HTML report generator with embedded SVG charts."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

from autotest.core.types import TestResult, TestStatus


class HtmlReporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def generate(
        self, results: list[TestResult], perf_data: dict[str, Any] | None = None
    ) -> Path:
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
        total_duration = sum(r.duration_ms for r in results)
        pass_rate = (passed / total * 100) if total > 0 else 0

        perf_section = ""
        if perf_data:
            from autotest.performance.analyzer import PerfAnalyzer
            from autotest.performance.visualizer import PerfVisualizer

            analysis = PerfAnalyzer().analyze(perf_data)
            charts = []
            cpu_chart = PerfVisualizer.generate_cpu_chart(analysis)
            if cpu_chart:
                charts.append(cpu_chart)
            mem_chart = PerfVisualizer.generate_memory_chart(analysis)
            if mem_chart:
                charts.append(mem_chart)
            fps_chart = PerfVisualizer.generate_fps_chart(analysis)
            if fps_chart:
                charts.append(fps_chart)

            if charts:
                perf_section = f"""
                <div class="section">
                    <h2>Performance Metrics</h2>
                    <div class="charts">{''.join(charts)}</div>
                </div>"""

        rows = []
        for r in results:
            status_class = {
                TestStatus.PASSED: "passed", TestStatus.FAILED: "failed",
                TestStatus.ERROR: "error", TestStatus.SKIPPED: "skipped",
            }.get(r.status, "")
            error_cell = f'<td class="error-msg">{html.escape(r.error_message or "")}</td>' if r.error_message else '<td>-</td>'
            rows.append(
                f'<tr class="{status_class}">'
                f'<td>{html.escape(r.name)}</td>'
                f'<td>{r.device_serial}</td>'
                f'<td><span class="badge {status_class}">{r.status.value.upper()}</span></td>'
                f'<td>{r.duration_ms:.0f}ms</td>'
                f'{error_cell}'
                f'</tr>'
            )

        report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoTest Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; padding: 24px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 4px; }}
.timestamp {{ color: #999; font-size: 13px; margin-bottom: 24px; }}
.summary {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
.stat-card {{ background: #fff; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 140px; }}
.stat-card .value {{ font-size: 28px; font-weight: 700; }}
.stat-card .label {{ font-size: 12px; color: #999; text-transform: uppercase; }}
.stat-card.passed .value {{ color: #4CAF50; }}
.stat-card.failed .value {{ color: #f44336; }}
.stat-card.rate .value {{ color: #2196F3; }}
.section {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.section h2 {{ font-size: 18px; margin-bottom: 16px; }}
.charts {{ display: flex; flex-wrap: wrap; gap: 16px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #eee; font-size: 12px; text-transform: uppercase; color: #999; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.badge.passed {{ background: #e8f5e9; color: #2e7d32; }}
.badge.failed {{ background: #ffebee; color: #c62828; }}
.badge.error {{ background: #fff3e0; color: #e65100; }}
.badge.skipped {{ background: #fff8e1; color: #f57f17; }}
tr.failed td, tr.error td {{ background: #fffafa; }}
.error-msg {{ font-family: monospace; font-size: 12px; color: #c62828; max-width: 400px; word-break: break-all; }}
</style>
</head>
<body>
<div class="container">
  <h1>AutoTest Report</h1>
  <div class="timestamp">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>

  <div class="summary">
    <div class="stat-card"><div class="value">{total}</div><div class="label">Total</div></div>
    <div class="stat-card passed"><div class="value">{passed}</div><div class="label">Passed</div></div>
    <div class="stat-card failed"><div class="value">{failed + errors}</div><div class="label">Failed</div></div>
    <div class="stat-card"><div class="value">{skipped}</div><div class="label">Skipped</div></div>
    <div class="stat-card rate"><div class="value">{pass_rate:.0f}%</div><div class="label">Pass Rate</div></div>
    <div class="stat-card"><div class="value">{total_duration / 1000:.1f}s</div><div class="label">Duration</div></div>
  </div>

  {perf_section}

  <div class="section">
    <h2>Test Results</h2>
    <table>
      <thead><tr><th>Test</th><th>Device</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</div>
</body>
</html>"""

        path = self.output_dir / "report.html"
        path.write_text(report_html, encoding="utf-8")
        return path
