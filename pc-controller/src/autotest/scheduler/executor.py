"""Parallel test executor that runs tests across multiple devices concurrently."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from autotest.automation.decorators import TestCaseInfo
from autotest.automation.runner import TestRunner
from autotest.core.events import Event, EventBus
from autotest.core.types import TestResult, TestStatus
from autotest.device.client import DeviceClient
from autotest.device.manager import DeviceManager
from autotest.scheduler.planner import ExecutionPlan, TestPlanner

logger = logging.getLogger(__name__)


class ParallelExecutor:
    """Execute tests across multiple devices in parallel.

    Uses a producer-consumer pattern with bounded concurrency:
    - Each device runs its assigned tests sequentially
    - Multiple devices run in parallel (bounded by max_workers)
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        event_bus: EventBus | None = None,
        max_workers: int = 8,
    ):
        self.device_manager = device_manager
        self.event_bus = event_bus or EventBus()
        self.max_workers = max_workers
        self._results: list[TestResult] = []
        self._start_time: float = 0

    async def execute(
        self,
        tests: list[TestCaseInfo],
        strategy: str = "round_robin",
    ) -> ExecutionResult:
        """Execute tests according to the planned distribution."""
        self._start_time = time.monotonic()
        self._results = []

        # Connect to all devices
        clients = await self.device_manager.connect_all()
        if not clients:
            return ExecutionResult(
                results=[], duration_ms=0, device_count=0, error="No devices available"
            )

        device_serials = [c.serial for c in clients]

        # Plan test distribution
        planner = TestPlanner()
        plan = planner.plan(tests, device_serials, strategy=strategy)

        await self.event_bus.emit(Event(
            type="execution.started",
            source="executor",
            data={
                "total_tests": plan.total_tests,
                "device_count": plan.device_count,
                "strategy": strategy,
            },
        ))

        # Execute in parallel with bounded concurrency
        semaphore = asyncio.Semaphore(self.max_workers)
        tasks = []

        for serial, test_list in plan.assignments.items():
            if not test_list:
                continue
            client = self.device_manager.get_client(serial)
            if client:
                tasks.append(
                    self._run_device_worker(client, test_list, semaphore)
                )

        if tasks:
            all_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in all_results:
                if isinstance(result, list):
                    self._results.extend(result)
                elif isinstance(result, Exception):
                    logger.error("Device worker failed: %s", result)

        duration = (time.monotonic() - self._start_time) * 1000

        await self.event_bus.emit(Event(
            type="execution.completed",
            source="executor",
            data={
                "total": len(self._results),
                "passed": sum(1 for r in self._results if r.status == TestStatus.PASSED),
                "failed": sum(1 for r in self._results if r.status == TestStatus.FAILED),
                "duration_ms": duration,
            },
        ))

        return ExecutionResult(
            results=self._results,
            duration_ms=duration,
            device_count=len(clients),
            plan=plan,
        )

    async def _run_device_worker(
        self,
        client: DeviceClient,
        tests: list[TestCaseInfo],
        semaphore: asyncio.Semaphore,
    ) -> list[TestResult]:
        """Run tests sequentially on a single device."""
        async with semaphore:
            runner = TestRunner(self.event_bus)
            logger.info(
                "Starting %d tests on device %s", len(tests), client.serial
            )

            try:
                results = await runner.run(tests, client)
                logger.info(
                    "Device %s completed: %d/%d passed",
                    client.serial,
                    sum(1 for r in results if r.status == TestStatus.PASSED),
                    len(results),
                )
                return results
            except Exception as e:
                logger.error("Device %s worker error: %s", client.serial, e)
                return [
                    TestResult(
                        name=t.name,
                        status=TestStatus.ERROR,
                        device_serial=client.serial,
                        error_message=f"Worker error: {e}",
                    )
                    for t in tests
                ]


class ExecutionResult:
    """Result of a parallel execution."""

    def __init__(
        self,
        results: list[TestResult],
        duration_ms: float,
        device_count: int,
        plan: ExecutionPlan | None = None,
        error: str | None = None,
    ):
        self.results = results
        self.duration_ms = duration_ms
        self.device_count = device_count
        self.plan = plan
        self.error = error

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAILED)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0

    @property
    def is_success(self) -> bool:
        return self.failed == 0 and self.error is None
