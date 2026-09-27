"""Is the network there? Measured, not guessed: the platforms' sites and sources are contacted.

A download that fails because the network is down must not count as a
failure: the job waits and starts again by itself when the connection is
back. This module gives the runner and the interface that information.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from .http import USER_AGENT
from .providers import registry

TIMEOUT = 6.0

Probe = Callable[[], tuple[bool, bool]]  # (an official site reachable, a source reachable)


def reachable(url: str, timeout: float = TIMEOUT) -> bool:
    """Any HTTP answer, even an error status, means the host is reachable."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, ValueError):
        return False


def default_probe() -> tuple[bool, bool]:
    """One answer is enough: the first reachable site ends each check."""
    official = any(reachable(p.home_url) for p in registry.PROVIDERS)
    source = any(reachable(url) for p in registry.PROVIDERS for url in p.source_urls)
    return official, source


class Connectivity:
    def __init__(self, probe: Probe | None = None):
        self._probe = probe or default_probe
        self._lock = threading.Lock()
        self.state = {"online": None, "official_reachable": None, "source_reachable": None, "checked_at": None}

    def check(self) -> bool:
        """Measure now; True if the online state changed."""
        official, source = self._probe()
        with self._lock:
            before = self.state["online"]
            self.state = {
                "online": official or source,
                "official_reachable": official,
                "source_reachable": source,
                "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            return before != self.state["online"]

    @property
    def online(self) -> bool | None:
        return self.state["online"]

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)
