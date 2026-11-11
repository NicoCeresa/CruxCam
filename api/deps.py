"""Shared service instances, provided to routes via FastAPI Depends.

Each getter is cached, so the app uses one instance of each. Tests replace them with
`app.dependency_overrides[get_x] = ...`.
"""
import threading
import time
from collections import defaultdict
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import lru_cache
from typing import Dict, List

import redis as redis_lib
from fastapi import HTTPException

from .config import Settings, load_settings
from .jobs import JobStore
from .previews import PreviewStore


class RateLimiter:
    """Per-IP sliding one-minute window. Thread-safe (shared by request threads)."""

    def __init__(self, limit: int):
        self._limit = limit
        self._times: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, ip: str) -> None:
        now = time.time()
        with self._lock:
            self._times[ip] = [t for t in self._times[ip] if now - t < 60]
            if len(self._times[ip]) >= self._limit:
                raise HTTPException(status_code=429, detail="Too many requests — try again in a minute")
            self._times[ip].append(now)

    def prune(self) -> None:
        now = time.time()
        with self._lock:
            for ip in list(self._times):
                self._times[ip] = [t for t in self._times[ip] if now - t < 60]
                if not self._times[ip]:
                    del self._times[ip]


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_job_store() -> JobStore:
    s = get_settings()
    return JobStore(redis_lib.Redis.from_url(s.redis_url, decode_responses=True), s.file_ttl)


@lru_cache
def get_executor() -> Executor:
    return ThreadPoolExecutor(max_workers=2)


@lru_cache
def get_preview_store() -> PreviewStore:
    s = get_settings()
    return PreviewStore(s.tmp, s.file_ttl)


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().rate_limit)
