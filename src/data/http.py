"""HTTP access: one small interface, a polite client and a caching decorator.

Sources depend on the `JsonHttp` protocol only (dependency inversion), so
tests inject a fake and never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Protocol
from urllib.parse import urlparse

CacheIf = Optional[Callable[[Any], bool]]


class HttpError(RuntimeError):
    """A request failed after all retries."""


class JsonHttp(Protocol):
    """What a data source needs from the outside world."""

    def get_json(self, url: str, params: Optional[dict] = None, *, cache_if: CacheIf = None) -> Any: ...

    def post_json(self, url: str, data: dict, *, cache_if: CacheIf = None) -> Any: ...


class PoliteHttpClient:
    """`requests`-based client with per-host throttling and retries.

    - identifies itself with a descriptive User-Agent (API etiquette);
    - waits at least `host_min_interval_s[host]` between calls to one host;
    - retries 429 and 5xx responses with exponential backoff.
    """

    RETRY_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, user_agent: str, host_min_interval_s: dict, timeout_s: float, max_retries: int,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        import requests  # imported lazily so offline tests need no network stack

        self._session = requests.Session()
        contact = os.environ.get("MUSHROOM_CONTACT")
        if contact:
            user_agent = user_agent.replace(
                "set MUSHROOM_CONTACT env var to add a contact address", f"contact: {contact}"
            )
        self._session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self._intervals = dict(host_min_interval_s)
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_call: dict = {}

    def get_json(self, url: str, params: Optional[dict] = None, *, cache_if: CacheIf = None) -> Any:
        return self._request("GET", url, params=params)

    def post_json(self, url: str, data: dict, *, cache_if: CacheIf = None) -> Any:
        return self._request("POST", url, data=data)

    def _throttle(self, host: str) -> None:
        interval = self._intervals.get(host, 0.5)
        last = self._last_call.get(host)
        if last is not None:
            wait = interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_call[host] = self._clock()

    def _request(self, method: str, url: str, **kwargs) -> Any:
        host = urlparse(url).netloc
        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            self._throttle(host)
            try:
                response = self._session.request(method, url, timeout=self._timeout, **kwargs)
            except Exception as exc:  # network-level failure
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise HttpError(f"{method} {url}: response is not JSON ({exc})") from exc
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                if response.status_code not in self.RETRY_STATUS:
                    break
            if attempt < self._max_retries:
                self._sleep(min(60.0, 2.0 ** (attempt + 1)))
        raise HttpError(f"{method} {url} failed: {last_error}")


class CachedJsonHttp:
    """Decorator adding a transparent on-disk cache to any `JsonHttp`.

    Each cache file stores the payload *and* its provenance (method, URL,
    parameters, retrieval time), so `data/cache/` doubles as the complete
    record of how every number was obtained.

    It also remembers the retrieval time of every response it hands out
    (cached or new), so a run from cache reports when the data was really
    fetched, not when the results file was built.
    """

    def __init__(self, inner: JsonHttp, cache_dir: Path):
        self._inner = inner
        self._dir = Path(cache_dir)
        self._fetched_at: list = []

    def retrieval_window(self) -> Optional[dict]:
        """{"first", "last"} ISO timestamps of the responses served so far, or None."""
        if not self._fetched_at:
            return None
        return {"first": min(self._fetched_at), "last": max(self._fetched_at)}

    def get_json(self, url: str, params: Optional[dict] = None, *, cache_if: CacheIf = None) -> Any:
        return self._cached("GET", url, params or {}, cache_if, lambda: self._inner.get_json(url, params))

    def post_json(self, url: str, data: dict, *, cache_if: CacheIf = None) -> Any:
        return self._cached("POST", url, data, cache_if, lambda: self._inner.post_json(url, data))

    def _path(self, method: str, url: str, params: dict) -> Path:
        key = json.dumps([method, url, sorted((str(k), str(v)) for k, v in params.items())])
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self._dir / urlparse(url).netloc / f"{digest}.json"

    def _cached(self, method: str, url: str, params: dict, cache_if: CacheIf, fetch: Callable[[], Any]) -> Any:
        path = self._path(method, url, params)
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                record = json.load(handle)
            if record.get("fetched_at"):
                self._fetched_at.append(record["fetched_at"])
            return record["payload"]
        payload = fetch()
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._fetched_at.append(fetched_at)
        if cache_if is None or cache_if(payload):
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "method": method,
                "url": url,
                "params": {str(k): str(v) for k, v in params.items()},
                "fetched_at": fetched_at,
                "payload": payload,
            }
            tmp = path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(record, handle)
            tmp.replace(path)
        return payload
