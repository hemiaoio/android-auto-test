"""Event bus for decoupled component communication."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
import time


@dataclass
class Event:
    type: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus supporting typed event subscriptions."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []

    def on(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to events of a specific type. Returns an unsubscribe function."""
        self._handlers[event_type].append(handler)
        return lambda: self._handlers[event_type].remove(handler)

    def on_all(self, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to all events."""
        self._wildcard_handlers.append(handler)
        return lambda: self._wildcard_handlers.remove(handler)

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribed handlers."""
        handlers = list(self._handlers.get(event.type, []))
        handlers.extend(self._wildcard_handlers)

        tasks = [self._safe_call(handler, event) for handler in handlers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception:
            pass  # Handlers should not break the bus

    def clear(self, event_type: str | None = None) -> None:
        """Remove all handlers, optionally for a specific event type."""
        if event_type:
            self._handlers.pop(event_type, None)
        else:
            self._handlers.clear()
            self._wildcard_handlers.clear()
