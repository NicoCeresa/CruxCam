"""Client address used for rate limiting, behind zero or more reverse proxies."""
import dataclasses
import logging

import pytest
from starlette.requests import Request

import api.routes as routes
from api.config import load_settings


def _request(client_host="10.0.0.5", xff=None):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers,
                    "client": (client_host, 1234), "query_string": b""})


def _settings(hops):
    return dataclasses.replace(load_settings(), proxy_hops=hops)


@pytest.fixture(autouse=True)
def reset_warning(monkeypatch):
    monkeypatch.setattr(routes, "_warned_unused_xff", False)


def test_no_proxy_uses_direct_address():
    assert routes._client_ip(_request(), _settings(0)) == "10.0.0.5"


def test_one_proxy_uses_address_it_appended():
    assert routes._client_ip(_request(xff="203.0.113.7"), _settings(1)) == "203.0.113.7"


def test_spoofed_entries_are_ignored():
    # Client sends a fake X-Forwarded-For; the proxy appends the real address on the right.
    req = _request(xff="1.2.3.4, 5.6.7.8, 203.0.113.7")
    assert routes._client_ip(req, _settings(1)) == "203.0.113.7"


def test_two_proxies():
    req = _request(xff="1.2.3.4, 203.0.113.7, 100.64.0.2")
    assert routes._client_ip(req, _settings(2)) == "203.0.113.7"


def test_missing_header_falls_back_to_direct_address():
    assert routes._client_ip(_request(), _settings(1)) == "10.0.0.5"


def test_unused_header_logs_one_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="api.routes"):
        routes._client_ip(_request(xff="203.0.113.7"), _settings(0))
        routes._client_ip(_request(xff="203.0.113.8"), _settings(0))
    warnings = [r for r in caplog.records if "CRUXCAM_PROXY_HOPS" in r.getMessage()]
    assert len(warnings) == 1
    assert "203.0.113.7" in warnings[0].getMessage() and "10.0.0.5" in warnings[0].getMessage()
