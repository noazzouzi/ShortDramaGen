"""Event bus of the interface: numbered events, a replay buffer, bounded subscribers.

The server publishes what happens (jobs, progress, episodes, library,
settings, health) and ``/api/events`` streams it as Server-Sent Events. A
client that reconnects sends ``Last-Event-ID``: the missed events are
replayed if they are still in the buffer, otherwise it gets a fresh
snapshot. ``progress`` events are never buffered: only the latest value
counts, and the snapshot already carries it.
"""

from __future__ import annotations

import json
import queue
import threading
from collections import deque
from dataclasses import dataclass

BUFFER_SIZE = 1000
SUBSCRIBER_QUEUE = 1000


@dataclass(frozen=True)
class Event:
    id: int | None  # None for events that are not replayable (progress, ping)
    type: str
    data: dict

    def encode(self) -> bytes:
        """SSE wire format."""
        lines = []
        if self.id is not None:
            lines.append(f"id: {self.id}")
        lines.append(f"event: {self.type}")
        payload = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        lines += [f"data: {line}" for line in payload.splitlines() or [""]]
        return ("\n".join(lines) + "\n\n").encode("utf-8")


class Subscription:
    def __init__(self, bus: "EventBus"):
        self._bus = bus
        self._queue: queue.Queue[Event | None] = queue.Queue(SUBSCRIBER_QUEUE)
        self.overflowed = False

    def put(self, event: Event) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:  # a client too slow to follow: it will reconnect and get a snapshot
            self.overflowed = True
            self.close()

    def get(self, timeout: float) -> Event | None:
        """Next event, or None after ``timeout`` seconds (time for a ping)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        self._bus._unsubscribe(self)
        try:
            self._queue.put_nowait(None)  # wakes the reader
        except queue.Full:
            pass

    @property
    def closed(self) -> bool:
        return self not in self._bus._subscribers


class EventBus:
    def __init__(self, buffer_size: int = BUFFER_SIZE):
        self._lock = threading.Lock()
        self._buffer: deque[Event] = deque(maxlen=buffer_size)
        self._subscribers: set[Subscription] = set()
        self._seq = 0

    @property
    def last_id(self) -> int:
        return self._seq

    def publish(self, type_: str, data: dict, replay: bool = True) -> Event:
        with self._lock:
            if replay:
                self._seq += 1
                event = Event(self._seq, type_, data)
                self._buffer.append(event)
            else:
                event = Event(None, type_, data)
            subscribers = list(self._subscribers)
        for sub in subscribers:
            sub.put(event)
        return event

    def subscribe(self, last_id: int | None = None) -> tuple[Subscription, list[Event] | None]:
        """A new subscriber and the events it missed since ``last_id``.

        The missed list is None when the caller must send a snapshot instead
        (no id, or events already dropped from the buffer).
        """
        sub = Subscription(self)
        with self._lock:
            self._subscribers.add(sub)
            missed = None
            if last_id is not None and 0 <= last_id <= self._seq:
                oldest = self._buffer[0].id if self._buffer else self._seq + 1
                if last_id >= oldest - 1:
                    missed = [e for e in self._buffer if e.id > last_id]
        return sub, missed

    def _unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
