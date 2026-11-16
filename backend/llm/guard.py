"""Protection for the public LLM endpoints (/api/analyze, /api/safety-insights).

The API key only ever lives in the server's environment (LLM_API_KEY): it is never sent
to the browser or committed. On a public site the endpoints themselves are still open,
so these guards keep other sites and scripts from spending the key:

- Origin check: requests must come from this site (same host as the request, a
  localhost page during development, or an origin listed in LLM_ALLOWED_ORIGINS).
- Rate limits: per client IP per minute and per day, plus a cap per server instance
  per minute. Limits are kept in memory, so each serverless instance counts on its
  own; pair them with a platform rule (e.g. Vercel Firewall) for a hard ceiling.

Everything is on by default when running on Vercel (VERCEL is set) and off for local
development. Each setting can be overridden with the environment variables below.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlsplit


def _int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return max(0, int(value))
    except ValueError:
        raise ValueError(f"{name} must be a whole number, got '{value}'.") from None


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be true or false, got '{value}'.")


def _origin(value: str | None) -> str | None:
    """Normalise an Origin or Referer header to scheme://host[:port], lower-case."""
    if not value:
        return None
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


@dataclass(frozen=True)
class GuardSettings:
    allowed_origins: tuple[str, ...] = ()  # extra allowed origins, e.g. a custom domain
    require_origin: bool = False           # reject requests that carry no Origin/Referer
    per_client_per_minute: int = 0         # 0 disables a limit
    per_client_per_day: int = 0
    global_per_minute: int = 0

    @property
    def active(self) -> bool:
        return bool(self.require_origin or self.allowed_origins or self.per_client_per_minute
                    or self.per_client_per_day or self.global_per_minute)

    @classmethod
    def from_env(cls) -> "GuardSettings":
        public = bool(os.getenv("VERCEL"))
        origins = tuple(o for o in (_origin(x) for x in os.getenv("LLM_ALLOWED_ORIGINS", "").split(",")) if o)
        return cls(
            allowed_origins=origins,
            require_origin=_bool("LLM_REQUIRE_ORIGIN", public),
            per_client_per_minute=_int("LLM_RATE_LIMIT_PER_MINUTE", 6 if public else 0),
            per_client_per_day=_int("LLM_RATE_LIMIT_PER_DAY", 100 if public else 0),
            global_per_minute=_int("LLM_GLOBAL_LIMIT_PER_MINUTE", 30 if public else 0),
        )


def origin_allowed(settings: GuardSettings, origin: str | None, referer: str | None, host: str | None) -> bool:
    """True when the request comes from this site (or an allowed origin)."""
    source = _origin(origin) or _origin(referer)
    if source is None:
        return not settings.require_origin
    if source in settings.allowed_origins:
        return True
    netloc = urlsplit(source).netloc
    if host and netloc == host.strip().lower():
        return True  # same site: covers the production domain and every preview URL
    hostname = urlsplit(source).hostname or ""
    return hostname in ("localhost", "127.0.0.1") and not settings.require_origin


class RateLimiter:
    """Sliding-window limits per client and per instance, kept in memory."""

    MINUTE = 60.0
    DAY = 86_400.0
    MAX_CLIENTS = 10_000

    def __init__(self, settings: GuardSettings, clock=time.monotonic) -> None:
        self.settings = settings
        self.clock = clock
        self.lock = threading.Lock()
        self.clients: dict[str, tuple[deque, deque]] = {}
        self.everyone: deque = deque()

    @staticmethod
    def _prune(times: deque, now: float, window: float) -> None:
        while times and now - times[0] >= window:
            times.popleft()

    def check(self, client: str) -> int | None:
        """Record a request. Returns None if allowed, else seconds to wait."""
        s = self.settings
        now = self.clock()
        with self.lock:
            if s.global_per_minute:
                self._prune(self.everyone, now, self.MINUTE)
                if len(self.everyone) >= s.global_per_minute:
                    return max(1, int(self.MINUTE - (now - self.everyone[0])) + 1)
            minute, day = self.clients.get(client) or (deque(), deque())
            self._prune(minute, now, self.MINUTE)
            self._prune(day, now, self.DAY)
            if s.per_client_per_minute and len(minute) >= s.per_client_per_minute:
                return max(1, int(self.MINUTE - (now - minute[0])) + 1)
            if s.per_client_per_day and len(day) >= s.per_client_per_day:
                return max(1, int(self.DAY - (now - day[0])) + 1)
            minute.append(now)
            day.append(now)
            self.everyone.append(now)
            if client not in self.clients and len(self.clients) >= self.MAX_CLIENTS:
                # Drop the client whose newest request is oldest.
                stale = min(self.clients, key=lambda c: self.clients[c][1][-1] if self.clients[c][1] else 0)
                self.clients.pop(stale, None)
            self.clients[client] = (minute, day)
            return None


def client_id(headers, remote_addr: str | None) -> str:
    """Client IP. On Vercel, x-real-ip / x-forwarded-for are set by the platform."""
    real = (headers.get("X-Real-IP") or "").strip()
    if real:
        return real
    forwarded = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or remote_addr or "unknown"
