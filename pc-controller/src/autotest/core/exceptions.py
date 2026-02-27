"""Exception hierarchy for the AutoTest framework."""

from __future__ import annotations


class AutoTestError(Exception):
    """Base exception for all AutoTest errors."""

    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


# Transport errors (1000-1999)
class ConnectionError(AutoTestError):
    pass


class AuthenticationError(AutoTestError):
    pass


class TimeoutError(AutoTestError):
    pass


# Device errors (2000-2999)
class DeviceOfflineError(AutoTestError):
    pass


class RootRequiredError(AutoTestError):
    pass


class AccessibilityRequiredError(AutoTestError):
    pass


# App errors (3000-3999)
class AppNotInstalledError(AutoTestError):
    pass


class AppCrashedError(AutoTestError):
    pass


class InstallFailedError(AutoTestError):
    pass


# UI errors (4000-4999)
class ElementNotFoundError(AutoTestError):
    pass


class ElementNotVisibleError(AutoTestError):
    pass


class ElementNotClickableError(AutoTestError):
    pass


# Performance errors (5000-5999)
class PerfSessionError(AutoTestError):
    pass


# Plugin errors (7000-7999)
class PluginError(AutoTestError):
    pass
