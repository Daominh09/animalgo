import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies.auth import get_current_user_id
from app.services import species, storage, vision

router = APIRouter(prefix="/captures", tags=["captures"])

# Owner: Person A — Capture & Species ID
# Single capture flow: the client POSTs the photo to the backend, which
# identifies the species (Gemini) and then stores the photo in R2. The backend
# needs the raw bytes for vision anyway, so a direct upload is simpler than the
# old presigned-URL + fetch-back flow (which has been removed).
# Week 2: write the Capture row + confidence-threshold branching + rarity.

# App-level guard so a huge upload can't exhaust backend memory or waste a
# Gemini/R2 call. A reverse-proxy body-size limit is the real DoS defense.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/detect-and-store")
async def detect_and_store(
    file: UploadFile = File(...),
    lat: float | None = None,
    lng: float | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """Identify the animal in a photo, store the photo, and score how rare it is.

    Upload a photo (max 10 MB). Returns the species, the stored image URL, and a
    `rarity` object with the tier and coin value.

    Auth: get a token from **POST /auth/token**, then click **Authorize** and paste it
    (the anon key will not work). `rarity` is `null` when rarity could not be determined — that means
    *unknown*, not zero and not "common". Full details in `backend/docs/capture-flow.md`.
    """
    # read() with a cap so an oversized upload never fully lands in memory.
    image_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    result = await vision.identify_species(
        image_bytes, mime_type=file.content_type or "image/jpeg"
    )
    object_key = f"{user_id}/{uuid.uuid4()}.jpg"
    image_url = storage.upload_bytes(object_key, image_bytes)

    # Hand-off to Person B's rarity engine: the identified species triggers the
    # GBIF + IUCN lookup automatically (both Redis-cached). `rarity` is None when the
    # species could not be resolved -- that means "unknown", NOT a rarity of zero, so
    # don't fall back to a tier here. See app/services/species.py.
    rarity_result = await species.resolve_species_rarity(
        scientific_name=result.get("scientific_name"),
        common_name=result.get("species"),
    )

    return {
        **result,
        "image_url": image_url,
        "object_key": object_key,
        "rarity": rarity_result,
    }
