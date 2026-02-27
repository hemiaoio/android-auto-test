"""Allure report data generator."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from autotest.core.types import TestResult, TestStatus


class AllureReporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir / "allure-results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, results: list[TestResult]) -> Path:
        for result in results:
            allure_result = {
                "uuid": str(uuid.uuid4()),
                "historyId": result.name,
                "name": result.name,
                "status": self._map_status(result.status),
                "stage": "finished",
                "start": int(datetime.now().timestamp() * 1000 - result.duration_ms),
                "stop": int(datetime.now().timestamp() * 1000),
                "labels": [
                    {"name": "suite", "value": "AutoTest"},
                    {"name": "host", "value": result.device_serial or "unknown"},
                    {"name": "framework", "value": "autotest"},
                ],
                "parameters": [],
            }

            if result.error_message:
                allure_result["statusDetails"] = {
                    "message": result.error_message,
                    "trace": result.error_message,
                }

            if result.screenshots:
                allure_result["attachments"] = [
                    {"name": f"screenshot_{i}", "source": path, "type": "image/png"}
                    for i, path in enumerate(result.screenshots)
                ]

            file_path = self.output_dir / f"{allure_result['uuid']}-result.json"
            file_path.write_text(
                json.dumps(allure_result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return self.output_dir

    @staticmethod
    def _map_status(status: TestStatus) -> str:
        return {
            TestStatus.PASSED: "passed",
            TestStatus.FAILED: "failed",
            TestStatus.ERROR: "broken",
            TestStatus.SKIPPED: "skipped",
            TestStatus.PENDING: "unknown",
            TestStatus.RUNNING: "unknown",
        }.get(status, "unknown")
