"""Test execution engine."""

from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any

from autotest.automation.decorators import TestCaseInfo, get_registered_tests
from autotest.automation.dsl import Device
from autotest.core.events import Event, EventBus
from autotest.core.types import TestResult, TestStatus
from autotest.device.client import DeviceClient

logger = logging.getLogger(__name__)


class TestRunner:
    """Discovers, filters, and executes test cases."""

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self.results: list[TestResult] = []

    def discover(self, paths: list[str | Path]) -> list[TestCaseInfo]:
        """Discover test cases from Python files."""
        for path in paths:
            path = Path(path)
            if path.is_file() and path.suffix == ".py":
                self._load_module(path)
            elif path.is_dir():
                for py_file in path.rglob("test_*.py"):
                    self._load_module(py_file)

        tests = list(get_registered_tests().values())
        logger.info("Discovered %d test cases", len(tests))
        return tests

    @staticmethod
    def _load_module(path: Path) -> None:
        """Dynamically import a Python file to trigger @test_case registration."""
        import sys
        module_name = path.stem
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

    def filter_tests(
        self,
        tests: list[TestCaseInfo],
        tags: list[str] | None = None,
        names: list[str] | None = None,
    ) -> list[TestCaseInfo]:
        """Filter tests by tags or names."""
        filtered = tests
        if tags:
            filtered = [t for t in filtered if any(tag in t.tags for tag in tags)]
        if names:
            filtered = [t for t in filtered if t.name in names]
        # Sort by priority (higher first)
        filtered.sort(key=lambda t: t.priority, reverse=True)
        return filtered

    async def run(
        self,
        tests: list[TestCaseInfo],
        client: DeviceClient,
    ) -> list[TestResult]:
        """Execute a list of tests on a single device."""
        device = Device(client)
        results: list[TestResult] = []

        await self.event_bus.emit(Event(
            type="run.started",
            source="runner",
            data={"total": len(tests), "device": client.serial},
        ))

        for i, test in enumerate(tests):
            logger.info("Running [%d/%d]: %s", i + 1, len(tests), test.name)

            await self.event_bus.emit(Event(
                type="test.started",
                source="runner",
                data={"name": test.name, "index": i},
            ))

            result = await self._run_single(test, device, client.serial)
            results.append(result)

            await self.event_bus.emit(Event(
                type="test.completed",
                source="runner",
                data={"name": test.name, "status": result.status.value, "duration": result.duration_ms},
            ))

        self.results.extend(results)

        await self.event_bus.emit(Event(
            type="run.completed",
            source="runner",
            data={
                "total": len(results),
                "passed": sum(1 for r in results if r.status == TestStatus.PASSED),
                "failed": sum(1 for r in results if r.status == TestStatus.FAILED),
                "error": sum(1 for r in results if r.status == TestStatus.ERROR),
            },
        ))

        return results

    async def _run_single(
        self, test: TestCaseInfo, device: Device, serial: str
    ) -> TestResult:
        """Run a single test with retry support."""
        last_result: TestResult | None = None

        for attempt in range(test.retry + 1):
            if attempt > 0:
                logger.info("Retry %d for: %s", attempt, test.name)

            try:
                result = await asyncio.wait_for(
                    test.func(device),
                    timeout=test.timeout,
                )
                # If func returns TestResult (wrapped by decorator), use it
                if isinstance(result, TestResult):
                    last_result = result
                    last_result.device_serial = serial
                else:
                    last_result = TestResult(
                        name=test.name,
                        status=TestStatus.PASSED,
                        device_serial=serial,
                    )
            except asyncio.TimeoutError:
                last_result = TestResult(
                    name=test.name,
                    status=TestStatus.ERROR,
                    device_serial=serial,
                    error_message=f"Test timed out after {test.timeout}s",
                )
            except Exception as e:
                last_result = TestResult(
                    name=test.name,
                    status=TestStatus.ERROR,
                    device_serial=serial,
                    error_message=f"{type(e).__name__}: {e}",
                )

            if last_result and last_result.status == TestStatus.PASSED:
                break

        return last_result or TestResult(
            name=test.name, status=TestStatus.ERROR, device_serial=serial,
            error_message="Unknown error"
        )
