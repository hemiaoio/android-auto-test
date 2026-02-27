"""Report generation engine that dispatches to format-specific generators."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from autotest.core.types import TestResult

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates test reports in multiple formats."""

    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        results: list[TestResult],
        formats: list[str] | None = None,
        perf_data: dict[str, Any] | None = None,
    ) -> list[str]:
        """Generate reports in specified formats. Returns list of file paths."""
        formats = formats or ["html", "json"]
        generated = []

        for fmt in formats:
            try:
                path = self._generate_format(fmt, results, perf_data)
                if path:
                    generated.append(str(path))
                    logger.info("Generated %s report: %s", fmt, path)
            except Exception as e:
                logger.error("Failed to generate %s report: %s", fmt, e)

        return generated

    def _generate_format(
        self, fmt: str, results: list[TestResult], perf_data: dict[str, Any] | None
    ) -> Path | None:
        if fmt == "html":
            from autotest.reporter.formats.html import HtmlReporter
            return HtmlReporter(self.output_dir).generate(results, perf_data)
        elif fmt == "json":
            from autotest.reporter.formats.json_report import JsonReporter
            return JsonReporter(self.output_dir).generate(results, perf_data)
        elif fmt == "junit_xml":
            from autotest.reporter.formats.junit_xml import JunitXmlReporter
            return JunitXmlReporter(self.output_dir).generate(results)
        elif fmt == "allure":
            from autotest.reporter.formats.allure import AllureReporter
            return AllureReporter(self.output_dir).generate(results)
        else:
            logger.warning("Unknown report format: %s", fmt)
            return None
