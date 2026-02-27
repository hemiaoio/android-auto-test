"""Test distribution planner for multi-device parallel execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autotest.automation.decorators import TestCaseInfo

logger = logging.getLogger(__name__)


@dataclass
class ExecutionPlan:
    """Maps tests to devices for parallel execution."""
    assignments: dict[str, list[TestCaseInfo]] = field(default_factory=dict)
    unassigned: list[TestCaseInfo] = field(default_factory=list)

    @property
    def total_tests(self) -> int:
        return sum(len(t) for t in self.assignments.values()) + len(self.unassigned)

    @property
    def device_count(self) -> int:
        return len(self.assignments)


class TestPlanner:
    """Distributes tests across available devices using various strategies."""

    def plan(
        self,
        tests: list[TestCaseInfo],
        device_serials: list[str],
        strategy: str = "round_robin",
        device_capabilities: dict[str, dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        if not device_serials:
            return ExecutionPlan(unassigned=tests)

        if strategy == "round_robin":
            return self._round_robin(tests, device_serials)
        elif strategy == "capability_match":
            return self._capability_match(tests, device_serials, device_capabilities or {})
        elif strategy == "single_device":
            return self._single_device(tests, device_serials)
        elif strategy == "duplicate":
            return self._duplicate_all(tests, device_serials)
        else:
            return self._round_robin(tests, device_serials)

    def _round_robin(
        self, tests: list[TestCaseInfo], devices: list[str]
    ) -> ExecutionPlan:
        """Distribute tests evenly across devices in round-robin order."""
        assignments: dict[str, list[TestCaseInfo]] = {d: [] for d in devices}
        sorted_tests = sorted(tests, key=lambda t: t.priority, reverse=True)

        for i, test in enumerate(sorted_tests):
            device = devices[i % len(devices)]
            assignments[device].append(test)

        logger.info(
            "Round-robin plan: %d tests across %d devices",
            len(tests), len(devices),
        )
        return ExecutionPlan(assignments=assignments)

    def _capability_match(
        self,
        tests: list[TestCaseInfo],
        devices: list[str],
        capabilities: dict[str, dict[str, Any]],
    ) -> ExecutionPlan:
        """Assign tests to devices based on required tags/capabilities."""
        assignments: dict[str, list[TestCaseInfo]] = {d: [] for d in devices}
        unassigned: list[TestCaseInfo] = []

        for test in tests:
            if test.devices:
                # Test specifies required devices
                matched = [d for d in devices if d in test.devices]
                if matched:
                    # Assign to least-loaded matching device
                    target = min(matched, key=lambda d: len(assignments[d]))
                    assignments[target].append(test)
                else:
                    unassigned.append(test)
            else:
                # Assign to least-loaded device
                target = min(devices, key=lambda d: len(assignments[d]))
                assignments[target].append(test)

        return ExecutionPlan(assignments=assignments, unassigned=unassigned)

    def _single_device(
        self, tests: list[TestCaseInfo], devices: list[str]
    ) -> ExecutionPlan:
        """Run all tests on the first device."""
        return ExecutionPlan(assignments={devices[0]: list(tests)})

    def _duplicate_all(
        self, tests: list[TestCaseInfo], devices: list[str]
    ) -> ExecutionPlan:
        """Run all tests on every device (compatibility testing)."""
        return ExecutionPlan(
            assignments={d: list(tests) for d in devices}
        )
