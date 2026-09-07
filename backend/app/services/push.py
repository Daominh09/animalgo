import logging
import re
from dataclasses import dataclass, field
from typing import Sequence

import httpx

logger = logging.getLogger(__name__)

# Owner: Person C — Battle System
#
# Outbound Expo push notifications. The only two things the app pushes are battle events:
# "someone challenged you" and "your battle was decided". Person D owns the other half of
# this (registering the device token in app/routers/devices.py); this module is the
# sending side.
#
# No API key: Expo's push service accepts unauthenticated sends to tokens it issued,
# which is the whole point of the ExponentPushToken indirection -- knowing a token lets
# you push to that device and nothing more.
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# Expo's own token shape. Checked before sending so a null/garbage/stale-format column
# value costs nothing instead of a network round trip that is certain to be rejected.
_TOKEN_RE = re.compile(r"^Expo(nent)?PushToken\[[^\]]+\]$")

# Kept short deliberately. This runs inside the request that resolves a battle, so the
# player is looking at a spinner while it happens. A slow push service must not hold up
# their result screen -- a notification that arrives late is worth less than a battle
# that resolves promptly, and the result is in the DB either way.
PUSH_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class PushMessage:
    """One notification. `token` may be None -- a player who never granted notification
    permission, or is on web, has no token, and that is an ordinary case rather than an
    error. Such messages are dropped before the request is built."""

    token: str | None
    title: str
    body: str
    # What the app reads on tap to know where to navigate. Battle pushes carry
    # {"type": "battle", "battle_id": ...}; see mobile/src/notifications/.
    data: dict = field(default_factory=dict)


def is_sendable(token: str | None) -> bool:
    return bool(token) and bool(_TOKEN_RE.match(token))


async def send_push(messages: Sequence[PushMessage]) -> int:
    """Sends notifications, best effort. Returns how many were handed to Expo.

    Never raises. Every caller is in the middle of something that already succeeded --
    a challenge has been created, or a battle has been resolved and paid out -- and
    failing that operation because a notification could not be delivered would be a bad
    trade: the player would see an error for something that actually worked, and their
    retry would create a second challenge.

    Sent as one batched request; Expo accepts up to 100 messages per call and we send at
    most two (challenger and opponent).
    """
    payload = [
        {
            "to": m.token,
            "title": m.title,
            "body": m.body,
            "data": m.data,
            "sound": "default",
        }
        for m in messages
        if is_sendable(m.token)
    ]
    if not payload:
        return 0

    try:
        async with httpx.AsyncClient(timeout=PUSH_TIMEOUT_SECONDS) as client:
            response = await client.post(EXPO_PUSH_URL, json=payload)
            response.raise_for_status()
    except Exception:  # noqa: BLE001
        # Logged without the tokens: a push token identifies a specific device, so it
        # does not belong in logs that get shipped somewhere.
        logger.warning("expo push send failed for %d message(s)", len(payload), exc_info=True)
        return 0

    # A 200 does not mean every message was delivered -- Expo returns per-message tickets,
    # and a "DeviceNotRegistered" ticket means the token is dead and should be cleared.
    # KNOWN GAP, Week 4: acting on tickets needs the receipts endpoint polled a few
    # minutes later, which needs a background worker (Celery/Redis) that does not exist
    # yet. Until then a stale token just fails silently forever, which costs one wasted
    # HTTP call per battle and nothing else.
    return len(payload)
