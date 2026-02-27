"""Core type definitions for the AutoTest framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    UNAUTHORIZED = "unauthorized"


class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class DeviceInfo:
    serial: str
    model: str
    manufacturer: str
    sdk_version: int
    android_version: str
    screen_width: int
    screen_height: int
    is_rooted: bool
    is_accessibility_enabled: bool
    abi: str = ""
    brand: str = ""
    density: float = 0.0


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center_x(self) -> int:
        return (self.left + self.right) // 2

    @property
    def center_y(self) -> int:
        return (self.top + self.bottom) // 2


@dataclass
class UiElement:
    id: str
    class_name: str
    bounds: Rect
    resource_id: str | None = None
    text: str | None = None
    content_description: str | None = None
    package_name: str | None = None
    is_clickable: bool = False
    is_enabled: bool = True
    is_scrollable: bool = False
    is_visible: bool = True
    children: list[UiElement] = field(default_factory=list)


@dataclass
class ShellResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class TestResult:
    name: str
    status: TestStatus
    duration_ms: float = 0
    device_serial: str = ""
    error_message: str | None = None
    screenshots: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
