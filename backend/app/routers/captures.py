import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Capture, User
from app.routers.wallet import credit_wallet
from app.services import geoprivacy, species, storage, vision

logger = logging.getLogger(__name__)

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
    db: AsyncSession = Depends(get_db),
):
    """Identify the animal in a photo, store the photo, score how rare it is, and
    persist the capture.

    Upload a photo (max 10 MB). Returns the species, the stored image URL, and a
    `rarity` object with the tier and coin value.

    Auth: click **Authorize** and paste the `access_token` from signing in (the anon key
    will not work). `rarity` is `null` when rarity could not be determined — that means
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
    species_common_name = result.get("species")

    # No animal found → don't store a photo or a junk capture row.
    if not species_common_name or species_common_name.lower() == "none":
        return {"detected": False, "species": "none", "message": "No animal detected."}

    object_key = f"{user_id}/{uuid.uuid4()}.jpg"
    image_url = storage.upload_bytes(object_key, image_bytes)

    # Hand-off to Person B's rarity engine: the identified species triggers the
    # GBIF + IUCN lookup automatically (both Redis-cached). `rarity` is None when the
    # species could not be resolved -- that means "unknown", NOT a rarity of zero, so
    # don't fall back to a tier here. See app/services/species.py.
    rarity_result = await species.resolve_species_rarity(
        scientific_name=result.get("scientific_name"),
        common_name=species_common_name,
    )

    # Geoprivacy: every capture is fuzzed to a ~11 km grid cell, so no capture can lead
    # anyone to a specific nest or den. This MUST stay above the Capture row write --
    # once a raw coordinate is in Postgres it is queryable, joinable, and in every
    # backup from then on. `location` is the only coordinate anything downstream (the
    # DB write, the response, the Map screen) may use. Do not persist or return the raw
    # lat/lng, and do not log them.
    location = geoprivacy.fuzz_coordinates(lat, lng)

    # Hand-off out to Person D: pay the player. Only a scored capture pays -- unknown
    # rarity has no coin value, and inventing one would mint currency out of a failed
    # lookup. credit_wallet is called directly rather than over HTTP, deliberately: it
    # has no route, so a player cannot call it themselves.
    #
    # Failures here are logged and swallowed rather than raised. The photo is already in
    # R2 by this point, so a 500 would leave the player with a stored capture, no coins,
    # and an error screen -- and their retry would re-run vision and re-upload. Better to
    # return the capture and report coins_awarded: null, which is true and visible.
    coins_awarded = None
    if rarity_result is not None:
        try:
            await credit_wallet(
                db,
                uuid.UUID(user_id),
                rarity_result["coin_value"],
                f"capture:{rarity_result['rarity_tier']}",
            )
            coins_awarded = rarity_result["coin_value"]
        except Exception:  # noqa: BLE001
            logger.exception("wallet credit failed for user %s", user_id)

    # Persist the capture. The user's own `users` row may not exist yet -- neither
    # Supabase sign-in nor app/routers/auth.py creates it, see wallet.py's own
    # get-or-create -- so create it first to satisfy the captures.owner_id foreign key.
    # flush() forces the users insert ahead of the captures insert (no ORM relationship
    # to auto-order them).
    owner_id = uuid.UUID(user_id)
    if await db.get(User, owner_id) is None:
        db.add(User(id=owner_id))
        await db.flush()

    capture = Capture(
        owner_id=owner_id,
        species_id=result.get("scientific_name"),
        common_name=species_common_name,
        image_url=image_url,
        rarity_tier=rarity_result["rarity_tier"] if rarity_result else None,
        confidence_score=result.get("confidence"),
        lat=location["lat"],
        lng=location["lng"],
    )
    db.add(capture)
    await db.commit()
    await db.refresh(capture)

    # KNOWN GAP, for Person A: this endpoint is not idempotent. Once the offline queue
    # and upload retry land, the same photo re-POSTed pays out again and creates a
    # second capture row -- there is nothing yet to deduplicate against. The fix
    # belongs here: a client-supplied idempotency key, or a unique constraint on
    # (owner, image hash).
    return {
        **result,
        "capture_id": str(capture.id),
        "image_url": image_url,
        "object_key": object_key,
        "rarity": rarity_result,
        "location": location,
        "coins_awarded": coins_awarded,
    }
