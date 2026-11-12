"""In-memory job store: round-trip, isolation from callers, expiry."""
from api.jobs import JobStore


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_round_trip_returns_a_copy():
    store = JobStore(ttl=60)
    store.set("j", {"status": "processing", "current": 1})
    got = store.get("j")
    got["current"] = 99
    assert store.get("j") == {"status": "processing", "current": 1}
    assert store.get("missing") is None


def test_entries_expire_after_last_update():
    clock = Clock()
    store = JobStore(ttl=60, clock=clock)
    store.set("j", {"status": "pending"})
    clock.now = 50
    store.set("j", {"status": "complete"})   # update restarts the TTL
    clock.now = 100
    assert store.get("j") == {"status": "complete"}
    clock.now = 111
    assert store.get("j") is None


def test_set_drops_expired_entries():
    clock = Clock()
    store = JobStore(ttl=10, clock=clock)
    store.set("old", {"status": "complete"})
    clock.now = 20
    store.set("new", {"status": "pending"})
    assert list(store._jobs) == ["new"]
