"""JUnit XML report generator for CI/CD integration."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from autotest.core.types import TestResult, TestStatus


class JunitXmlReporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def generate(self, results: list[TestResult]) -> Path:
        total = len(results)
        failures = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
        total_time = sum(r.duration_ms for r in results) / 1000

        testsuite = ET.Element("testsuite", {
            "name": "AutoTest",
            "tests": str(total),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
            "time": f"{total_time:.3f}",
            "timestamp": datetime.now().isoformat(),
        })

        for r in results:
            testcase = ET.SubElement(testsuite, "testcase", {
                "name": r.name,
                "classname": f"autotest.{r.device_serial}",
                "time": f"{r.duration_ms / 1000:.3f}",
            })

            if r.status == TestStatus.FAILED:
                failure = ET.SubElement(testcase, "failure", {
                    "message": r.error_message or "Test failed",
                    "type": "AssertionError",
                })
                failure.text = r.error_message or ""
            elif r.status == TestStatus.ERROR:
                error = ET.SubElement(testcase, "error", {
                    "message": r.error_message or "Test error",
                    "type": "Exception",
                })
                error.text = r.error_message or ""
            elif r.status == TestStatus.SKIPPED:
                ET.SubElement(testcase, "skipped")

        tree = ET.ElementTree(testsuite)
        path = self.output_dir / "junit-results.xml"
        ET.indent(tree, space="  ")
        tree.write(str(path), encoding="unicode", xml_declaration=True)
        return path
