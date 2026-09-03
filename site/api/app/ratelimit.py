"""Minimal in-memory per-IP rate limiter.

Placeholder for production use -- the implementation plan calls for a shared store
(Upstash Redis or similar) once this runs on more than one process/instance, since an
in-memory counter resets per-process and doesn't coordinate across replicas.
"""
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 20

_hits: dict[str, deque] = defaultdict(deque)


def allow(client_id: str) -> bool:
    now = time.time()
    q = _hits[client_id]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= MAX_REQUESTS_PER_WINDOW:
        return False
    q.append(now)
    return True
