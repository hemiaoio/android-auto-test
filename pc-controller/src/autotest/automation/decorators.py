"""Test case decorators for the automation framework."""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from autotest.core.types import TestResult, TestStatus

# Global test registry
_test_registry: dict[str, TestCaseInfo] = {}


@dataclass
class TestCaseInfo:
    name: str
    func: Callable[..., Coroutine[Any, Any, None]]
    tags: list[str] = field(default_factory=list)
    devices: list[str] | None = None  # None means any device
    timeout: float = 300.0  # 5 minutes default
    retry: int = 0
    priority: int = 0
    description: str = ""


def test_case(
    name: str | None = None,
    tags: list[str] | None = None,
    devices: list[str] | None = None,
    timeout: float = 300.0,
    retry: int = 0,
    priority: int = 0,
    description: str = "",
) -> Callable[..., Callable[..., Coroutine[Any, Any, TestResult]]]:
    """Decorator to register a function as a test case.

    Usage:
        @test_case(name="Login Test", tags=["smoke"])
        async def test_login(device: Device):
            await device.app("com.example").launch()
            ...
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, None]]) -> Callable[..., Coroutine[Any, Any, TestResult]]:
        test_name = name or func.__name__
        info = TestCaseInfo(
            name=test_name,
            func=func,
            tags=tags or [],
            devices=devices,
            timeout=timeout,
            retry=retry,
            priority=priority,
            description=description or func.__doc__ or "",
        )
        _test_registry[test_name] = info

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> TestResult:
            start = time.monotonic()
            try:
                await func(*args, **kwargs)
                duration = (time.monotonic() - start) * 1000
                return TestResult(
                    name=test_name,
                    status=TestStatus.PASSED,
                    duration_ms=duration,
                )
            except AssertionError as e:
                duration = (time.monotonic() - start) * 1000
                return TestResult(
                    name=test_name,
                    status=TestStatus.FAILED,
                    duration_ms=duration,
                    error_message=str(e),
                )
            except Exception as e:
                duration = (time.monotonic() - start) * 1000
                return TestResult(
                    name=test_name,
                    status=TestStatus.ERROR,
                    duration_ms=duration,
                    error_message=f"{type(e).__name__}: {e}",
                )

        wrapper._test_info = info  # type: ignore[attr-defined]
        return wrapper

    return decorator


def get_registered_tests() -> dict[str, TestCaseInfo]:
    """Return all registered test cases."""
    return dict(_test_registry)


def get_tests_by_tags(tags: list[str]) -> list[TestCaseInfo]:
    """Filter tests by tags (OR logic)."""
    return [t for t in _test_registry.values() if any(tag in t.tags for tag in tags)]


def clear_registry() -> None:
    """Clear the test registry (used in testing)."""
    _test_registry.clear()
