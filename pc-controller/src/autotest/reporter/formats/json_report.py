"""JSON report generator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotest.core.types import TestResult, TestStatus


class JsonReporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def generate(
        self, results: list[TestResult], perf_data: dict[str, Any] | None = None
    ) -> Path:
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": total - passed - failed - errors,
                "pass_rate": (passed / total * 100) if total > 0 else 0,
                "duration_ms": sum(r.duration_ms for r in results),
            },
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "duration_ms": r.duration_ms,
                    "device": r.device_serial,
                    "error": r.error_message,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }

        if perf_data:
            report["performance"] = perf_data

        path = self.output_dir / "report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
