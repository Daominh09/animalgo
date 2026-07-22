import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.auth import get_current_user_id
from app.services import storage, vision

router = APIRouter(prefix="/captures", tags=["captures"])

# Owner: Person A — Capture & Species ID
# Week 1: /captures returns a mock species so Person B can build against it
# Week 2: wire to real vision.identify_species() + confidence threshold branching + rarity + geoprivacy


@router.post("/upload-url")
async def get_upload_url(filename: str, user_id: str = Depends(get_current_user_id)):
    key = f"{user_id}/{filename}"
    return {"upload_url": storage.generate_presigned_upload_url(key), "object_key": key}


@router.post("")
async def create_capture(object_key: str, lat: float, lng: float, user_id: str = Depends(get_current_user_id)):
    # TODO Week 2: call vision.identify_species(), branch on confidence,
    # call rarity.score_rarity() + rarity.fuzz_coordinates(), write to captures table
    return {
        "species": "mock species",
        "confidence": 0.42,
        "rarity_tier": "common",
        "coins_awarded": 5,
    }


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
    image_bytes = await file.read()
    result = await vision.identify_species(
        image_bytes, mime_type=file.content_type or "image/jpeg"
    )
    object_key = f"{user_id}/{uuid.uuid4()}.jpg"
    image_url = storage.upload_bytes(object_key, image_bytes)
    return {**result, "image_url": image_url, "object_key": object_key}
