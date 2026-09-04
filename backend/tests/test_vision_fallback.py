import asyncio

import pytest

from app.services import vision

# Owner: Person A — Capture & Species ID (fallback wiring added with Person B's rarity
# hand-off, since rarity depends on getting a scientific name back).
# Provider selection and failover, with both HTTP providers faked — no network.

IMG = b"fake-image-bytes"


def _use_providers(monkeypatch, gemini_key="", openrouter_key=""):
    monkeypatch.setattr(vision.settings, "gemini_api_key", gemini_key)
    monkeypatch.setattr(vision.settings, "open_router_api_key", openrouter_key)


def _stub(monkeypatch, name, result=None, error=None, calls=None):
    async def impl(image_bytes, mime_type):
        if calls is not None:
            calls.append(name)
        if error:
            raise error
        return result

    monkeypatch.setattr(vision, f"_identify_{name}", impl)


def test_gemini_used_when_configured(monkeypatch):
    _use_providers(monkeypatch, gemini_key="g", openrouter_key="o")
    calls = []
    _stub(monkeypatch, "gemini", result={"species": "House Sparrow"}, calls=calls)
    _stub(monkeypatch, "openrouter", result={"species": "wrong"}, calls=calls)

    out = asyncio.run(vision.identify_species(IMG))

    assert out["species"] == "House Sparrow"
    assert calls == ["gemini"]  # fallback not touched when the primary works


def test_falls_back_to_openrouter_when_gemini_fails(monkeypatch):
    _use_providers(monkeypatch, gemini_key="g", openrouter_key="o")
    calls = []
    _stub(monkeypatch, "gemini", error=RuntimeError("429 rate limited"), calls=calls)
    _stub(monkeypatch, "openrouter", result={"species": "Red Fox"}, calls=calls)

    out = asyncio.run(vision.identify_species(IMG))

    assert out["species"] == "Red Fox"
    assert calls == ["gemini", "openrouter"]  # tried primary first, then fell back


def test_openrouter_used_alone_when_gemini_key_missing(monkeypatch):
    # This is the current .env state: no Gemini key, OpenRouter key present.
    _use_providers(monkeypatch, gemini_key="", openrouter_key="o")
    calls = []
    _stub(monkeypatch, "gemini", result={"species": "should not run"}, calls=calls)
    _stub(monkeypatch, "openrouter", result={"species": "Monarch Butterfly"}, calls=calls)

    out = asyncio.run(vision.identify_species(IMG))

    assert out["species"] == "Monarch Butterfly"
    assert calls == ["openrouter"]  # unconfigured provider is skipped, not attempted


def test_raises_when_all_providers_fail(monkeypatch):
    _use_providers(monkeypatch, gemini_key="g", openrouter_key="o")
    _stub(monkeypatch, "gemini", error=RuntimeError("gemini down"))
    _stub(monkeypatch, "openrouter", error=RuntimeError("openrouter down"))

    # Better to surface a real error than return a bogus identification.
    with pytest.raises(RuntimeError, match="All vision providers failed"):
        asyncio.run(vision.identify_species(IMG))


def test_raises_when_no_provider_configured(monkeypatch):
    _use_providers(monkeypatch, gemini_key="", openrouter_key="")

    with pytest.raises(RuntimeError, match="No vision provider configured"):
        asyncio.run(vision.identify_species(IMG))


def test_parse_normalises_provider_payload():
    out = vision._parse('{"species": "Tiger", "scientific_name": "Panthera tigris", "confidence": 0.9}')
    assert out == {"species": "Tiger", "scientific_name": "Panthera tigris", "confidence": 0.9}


def test_parse_defaults_missing_confidence():
    # A provider that omits confidence must not blow up the capture path.
    out = vision._parse('{"species": "Tiger", "scientific_name": "Panthera tigris"}')
    assert out["confidence"] == 0.0
