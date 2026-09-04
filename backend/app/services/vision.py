import base64
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Owner: Person A — Capture & Species ID
# Species ID runs against a vision model. Gemini (gemini-2.5-flash) is the primary;
# OpenRouter (free Gemma vision model) is the fallback, used when Gemini has no API key
# configured or its call fails. DeepSeek was the original plan but its API rejects image
# input.
#
# Both providers are asked for the same JSON shape and return the same dict, so callers
# never need to know which one answered.
#
# scientific_name is required by the rarity engine (Person B): GBIF and the IUCN Red
# List are keyed on scientific names, and common names do not resolve against them --
# "Red Fox" matches a Fox Sparrow, "Grey Squirrel" matches a flea, and "House Sparrow"
# does not match at all. See app/services/species.py.

SPECIES_ID_PROMPT = (
    "Identify the animal species in this photo. If there is no animal, use "
    '"none" for both names. Give the scientific name as a binomial (genus and '
    "species, e.g. Passer domesticus) — not a family or genus alone. "
    "Respond with a JSON object: "
    '{"species": "<common name or none>", '
    '"scientific_name": "<binomial scientific name or none>", '
    '"confidence": <0-1 float>}'
)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.gemini_model}:generateContent"
)

_TIMEOUT = 30


def _parse(text: str) -> dict:
    """Both providers are asked for raw JSON; parse into our canonical shape."""
    parsed = json.loads(text)
    return {
        "species": parsed.get("species"),
        "scientific_name": parsed.get("scientific_name"),
        "confidence": float(parsed.get("confidence", 0)),
    }


async def _identify_gemini(image_bytes: bytes, mime_type: str) -> dict:
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SPECIES_ID_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode(),
                        }
                    },
                ]
            }
        ],
        # Force raw JSON — otherwise Gemini sometimes wraps the object in
        # ```json ... ``` markdown fences and json.loads() chokes.
        "generationConfig": {"responseMimeType": "application/json"},
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            GEMINI_URL,
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=payload,
        )
        response.raise_for_status()

    return _parse(response.json()["candidates"][0]["content"]["parts"][0]["text"])


async def _identify_openrouter(image_bytes: bytes, mime_type: str) -> dict:
    """OpenRouter exposes an OpenAI-compatible chat API; images go in as data URLs."""
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
    payload = {
        "model": settings.open_router_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SPECIES_ID_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{settings.open_router_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.open_router_api_key}"},
            json=payload,
        )
        response.raise_for_status()

    return _parse(response.json()["choices"][0]["message"]["content"])


async def identify_species(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Identify the species in a photo, trying each configured provider in order.

    Returns {"species", "scientific_name", "confidence"}. Raises if every configured
    provider fails, so the caller can surface a real error rather than a bogus ID.
    """
    providers = []
    if settings.gemini_api_key:
        providers.append(("gemini", _identify_gemini))
    if settings.open_router_api_key:
        providers.append(("openrouter", _identify_openrouter))

    if not providers:
        raise RuntimeError(
            "No vision provider configured — set GEMINI_API_KEY or OPEN_ROUTER_API_KEY"
        )

    last_error: Exception | None = None
    for name, provider in providers:
        try:
            return await provider(image_bytes, mime_type)
        except Exception as exc:  # noqa: BLE001 — try the next provider on any failure
            # Covers auth errors, rate limits (the free tier is easy to exhaust),
            # timeouts and malformed JSON alike.
            logger.warning("vision provider %s failed: %s", name, exc)
            last_error = exc

    raise RuntimeError("All vision providers failed") from last_error
