import json

import httpx

from app.config import settings

# Owner: Person A — Capture & Species ID
# Species ID runs against Google Gemini vision (free tier: gemini-2.5-flash).
# DeepSeek was the original plan but its API rejects image input; Gemini was
# the fallback, verified against ~5 sample images (species-level, including
# hard small birds like house sparrow).
# Week 2: wire confidence threshold branching in app/routers/captures.py

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.gemini_model}:generateContent"
)

SPECIES_ID_PROMPT = (
    "Identify the animal species in this photo. If there is no animal, use "
    '"none" as the species. Respond with a JSON object: '
    '{"species": "<common name or none>", "confidence": <0-1 float>}'
)


async def identify_species(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    import base64

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

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GEMINI_URL,
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=payload,
        )
        response.raise_for_status()

    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    return {
        "species": parsed.get("species"),
        "confidence": float(parsed.get("confidence", 0)),
    }
