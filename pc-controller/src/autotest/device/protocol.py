"""Protocol message encoding/decoding matching the Kotlin agent protocol."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "request"
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    timestamp: int = 0

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            import time
            self.timestamp = int(time.time() * 1000)

    def to_json(self) -> str:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> Message:
        data = json.loads(text)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def request(
        cls,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Message:
        metadata = {"timeout": int(timeout * 1000)} if timeout else None
        return cls(type="request", method=method, params=params, metadata=metadata)

    @classmethod
    def cancel(cls, request_id: str) -> Message:
        return cls(id=request_id, type="cancel")

    @property
    def is_success(self) -> bool:
        return self.type == "response" and self.error is None

    @property
    def error_message(self) -> str:
        if self.error:
            return self.error.get("message", "Unknown error")
        return ""

    @property
    def error_code(self) -> int:
        if self.error:
            return self.error.get("code", 0)
        return 0
