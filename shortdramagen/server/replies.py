"""Reply types shared by the routes and the HTTP handler."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Reply:
    status: int
    body: bytes = b""
    headers: dict = field(default_factory=dict)


@dataclass
class StreamReply:
    """A response written progressively (Server-Sent Events): ``stream(write)`` returns when done."""

    status: int
    headers: dict
    stream: Callable[[Callable[[bytes], None]], None]


class ApiError(Exception):
    """A refused request: HTTP status, stable code, message for the user, details."""

    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details or {}


def json_reply(data, status: int = 200, headers: dict | None = None) -> Reply:
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Reply(status, body, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", **(headers or {})})


def error_reply(status: int, code: str, message: str, details: dict | None = None) -> Reply:
    """The API error format: {"error": {"code", "message", "details"}}."""
    return json_reply({"error": {"code": code, "message": message, "details": details or {}}}, status)
