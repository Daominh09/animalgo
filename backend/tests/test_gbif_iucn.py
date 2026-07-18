import asyncio

from app.services import cache, gbif_iucn

# Owner: Person B — Rarity Engine & Collection
# Unit tests for the get-or-fetch cache wrapper and the GBIF fetch functions.
# httpx and the Redis client are both faked, so no network and no running Redis are
# needed. Coroutines are driven with asyncio.run() to avoid a pytest-asyncio dependency.


class FakeRedis:
    """Just enough of redis.asyncio to back get_or_fetch. Real redis returns bytes."""

    def __init__(self):
        self.store: dict[str, bytes] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = str(value).encode()


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"x" if payload is not None else b""

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    """Async context-manager stand-in for httpx.AsyncClient. `responder` maps a request
    URL to a FakeResponse; every GET is recorded in `calls`."""

    def __init__(self, responder, calls):
        self._responder = responder
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        self._calls.append((url, params))
        return self._responder(url)


def _patch(monkeypatch, responder):
    """Give the wrapper a fresh FakeRedis and route GBIF HTTP through `responder`."""
    calls = []
    monkeypatch.setattr(cache, "r", FakeRedis())
    monkeypatch.setattr(gbif_iucn.httpx, "AsyncClient", lambda *a, **k: FakeClient(responder, calls))
    return calls


# --- the get-or-fetch wrapper itself -----------------------------------------------


def test_get_or_fetch_caches_and_reuses(monkeypatch):
    monkeypatch.setattr(cache, "r", FakeRedis())
    calls = {"n": 0}

    async def fetch():
        calls["n"] += 1
        return "42"

    async def run():
        return await cache.get_or_fetch("k", fetch), await cache.get_or_fetch("k", fetch)

    first, second = asyncio.run(run())
    assert first == "42"
    assert second == "42"
    assert calls["n"] == 1  # second call served from cache, fetch not re-run


def test_get_or_fetch_does_not_cache_on_error(monkeypatch):
    monkeypatch.setattr(cache, "r", FakeRedis())

    async def boom():
        raise RuntimeError("upstream down")

    async def run():
        try:
            await cache.get_or_fetch("k", boom)
        except RuntimeError:
            pass
        return await cache.r.get("k")  # must be unset — errors aren't cached

    assert asyncio.run(run()) is None


# --- GBIF occurrence count ----------------------------------------------------------


def test_gbif_count_parsed_and_cached(monkeypatch):
    calls = _patch(monkeypatch, lambda url: FakeResponse({"count": 134}))

    async def run():
        first = await gbif_iucn.get_gbif_occurrence_count("Panthera tigris", "US")
        second = await gbif_iucn.get_gbif_occurrence_count("Panthera tigris", "US")
        return first, second

    first, second = asyncio.run(run())
    assert first == 134
    assert second == 134
    assert len(calls) == 1  # second lookup served from Redis, no second HTTP hit


def test_gbif_regions_cached_independently(monkeypatch):
    calls = _patch(monkeypatch, lambda url: FakeResponse({"count": 23}))

    async def run():
        await gbif_iucn.get_gbif_occurrence_count("Panthera tigris", "US")
        await gbif_iucn.get_gbif_occurrence_count("Panthera tigris", "VN")

    asyncio.run(run())
    assert len(calls) == 2  # different regions are distinct cache keys


# --- IUCN status via GBIF -----------------------------------------------------------


def _iucn_responder(usage_key=None, code=None, category_status=200):
    def responder(url):
        if "/species/match" in url:
            return FakeResponse({"usageKey": usage_key} if usage_key else {})
        if "/iucnRedListCategory" in url:
            payload = {"code": code, "category": "ENDANGERED"} if code else None
            return FakeResponse(payload, status_code=category_status)
        raise AssertionError(f"unexpected url {url}")

    return responder


def test_iucn_status_from_gbif_parsed_and_cached(monkeypatch):
    calls = _patch(monkeypatch, _iucn_responder(usage_key=5219416, code="EN"))

    async def run():
        first = await gbif_iucn.get_iucn_status("Panthera tigris")
        second = await gbif_iucn.get_iucn_status("Panthera tigris")
        return first, second

    first, second = asyncio.run(run())
    assert first == "EN"
    assert second == "EN"
    assert len(calls) == 2  # first = match + category; second served from Redis


def test_iucn_no_name_match_is_ne_and_skips_category(monkeypatch):
    calls = _patch(monkeypatch, _iucn_responder(usage_key=None))
    assert asyncio.run(gbif_iucn.get_iucn_status("Not a species")) == "NE"
    assert len(calls) == 1  # only the match call; no usageKey → no category lookup


def test_iucn_no_assessment_is_ne(monkeypatch):
    # matched taxon, but GBIF has no Red List category for it (204/empty body)
    _patch(monkeypatch, _iucn_responder(usage_key=999, code=None, category_status=204))
    assert asyncio.run(gbif_iucn.get_iucn_status("Some plant")) == "NE"
