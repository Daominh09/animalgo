import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Capture, User
from app.services import rarity, storage, vision
from app.services.gbif_iucn import get_gbif_occurrence_count, get_iucn_status

router = APIRouter(prefix="/captures", tags=["captures"])

# Owner: Person A — Capture & Species ID
# Capture flow (one request): client POSTs a photo → Gemini identifies the
# species → photo stored in R2 → rarity scored via Person B's engine (GBIF/IUCN,
# Redis-cached) → a Capture row is saved. The backend needs the raw bytes for
# vision anyway, so a direct upload (not a presigned URL) keeps it to one call.

# App-level guard so a huge upload can't exhaust backend memory or waste a
# Gemini/R2 call. A reverse-proxy body-size limit is the real DoS defense.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/detect")
async def detect_and_store(
    file: UploadFile = File(...),
    lat: float | None = None,
    lng: float | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Identify the animal, store the photo, score rarity, and save the capture."""
    image_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    # 1. Species ID (Gemini). scientific_name is what the rarity engine needs —
    #    GBIF keys on Latin names, not common names like "cat".
    result = await vision.identify_species(
        image_bytes, mime_type=file.content_type or "image/jpeg"
    )
    species = result.get("species")
    scientific_name = result.get("scientific_name")
    confidence = result.get("confidence")

    # No animal found → don't store a photo or a junk capture row.
    if not species or species.lower() == "none":
        return {"detected": False, "species": "none", "message": "No animal detected."}

    # 2. Store the photo in R2.
    object_key = f"{user_id}/{uuid.uuid4()}.jpg"
    image_url = storage.upload_bytes(object_key, image_bytes)

    # 3. Rarity via Person B's cached GBIF/IUCN engine (keyed on the scientific
    #    name). A rarity/GBIF failure must NOT fail the capture — save it
    #    unscored (rarity_tier=None) and let it be backfilled later.
    rarity_tier: str | None = None
    iucn_status = "NE"
    if scientific_name and scientific_name.lower() != "none":
        try:
            occurrence = await get_gbif_occurrence_count(scientific_name)
            iucn_status = await get_iucn_status(scientific_name)
            rarity_tier, _coins = rarity.score_rarity(occurrence, iucn_status)
        except Exception:
            rarity_tier = None  # leave unscored for backfill

    # 4. Geoprivacy: withhold coordinates for threatened species.
    safe_lat, safe_lng = rarity.fuzz_coordinates(lat, lng, iucn_status)

    # 5. Persist. The user's own `users` row may not exist yet (there's no
    #    auth→public.users trigger — see wallet.py), so create it first to
    #    satisfy the captures.owner_id foreign key. flush() forces the users
    #    insert ahead of the captures insert (no ORM relationship to auto-order).
    owner_id = uuid.UUID(user_id)
    if await db.get(User, owner_id) is None:
        db.add(User(id=owner_id))
        await db.flush()

    capture = Capture(
        owner_id=owner_id,
        species_id=scientific_name or species,
        image_url=image_url,
        rarity_tier=rarity_tier,
        confidence_score=confidence,
        lat=safe_lat,
        lng=safe_lng,
    )
    db.add(capture)
    await db.commit()
    await db.refresh(capture)

    return {
        "detected": True,
        "capture_id": str(capture.id),
        "species": species,
        "scientific_name": scientific_name,
        "confidence": confidence,
        "rarity_tier": rarity_tier,
        "image_url": image_url,
        "object_key": object_key,
    }
