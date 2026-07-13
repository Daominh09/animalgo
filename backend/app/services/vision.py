import json

from openai import OpenAI

from app.config import settings

# Owner: Person A — Capture & Species ID
# Week 1: prototype this call against ~15-20 sample images, log accuracy
# Week 2: wire confidence threshold branching in app/routers/captures.py

client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)

SPECIES_ID_PROMPT = (
    "You are identifying an animal species from a photo. "
    'Respond with ONLY a JSON object, no other text: {"species": "<common name>", "confidence": <0-1 float>}'
)


async def identify_species(image_url: str) -> dict:
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SPECIES_ID_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    )
    raw = response.choices[0].message.content
    # TODO: parse defensively — DeepSeek may wrap JSON in prose depending on prompt/model behavior.
    # Verify at build time whether a strict JSON response mode is available.
    return json.loads(raw)
