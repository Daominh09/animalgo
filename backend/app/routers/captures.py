import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies.auth import get_current_user_id
from app.services import storage, vision

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


@router.post("/detect")
async def detect_and_store(
    file: UploadFile = File(...),
    lat: float | None = None,
    lng: float | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """Identify the animal first, then push the photo to R2.

    Week 1 slice: no DB write, no rarity scoring yet — just species ID +
    storage so the capture pipeline can be exercised end to end.
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
    return {**result, "image_url": image_url, "object_key": object_key}
