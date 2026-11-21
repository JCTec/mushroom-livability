"""Test doubles shared by the test modules. No network, ever."""

from __future__ import annotations

from src.domain import Location

VANCOUVER = Location("vancouver", "Vancouver", "Canada", "Canada", 49.2827, -123.1207)


class FakeHttp:
    """Answers requests from a list of (url_fragment, payload) routes.

    `payload` may be a callable taking (url, params) for dynamic answers.
    Every call is recorded in `.calls` so tests can assert on parameters.
    """

    def __init__(self, routes):
        self.routes = list(routes)
        self.calls = []

    def _answer(self, method, url, params):
        self.calls.append((method, url, dict(params or {})))
        for fragment, payload in self.routes:
            if fragment in url:
                return payload(url, params or {}) if callable(payload) else payload
        raise AssertionError(f"Unexpected request: {method} {url}")

    def get_json(self, url, params=None, *, cache_if=None):
        return self._answer("GET", url, params)

    def post_json(self, url, data, *, cache_if=None):
        return self._answer("POST", url, data)
