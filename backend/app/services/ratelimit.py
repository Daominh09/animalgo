import logging

from app.services.cache import r

logger = logging.getLogger(__name__)

# Owner: Person B — shared infra, added with the auth endpoints.
#
# WHY THIS EXISTS
# Supabase rate-limits sign-in attempts per source IP. Now that the app signs in through
# our API instead of calling Supabase directly, every attempt from every user arrives
# from ONE IP -- our server's. That turns Supabase's per-user protection into a single
# shared bucket: one attacker can spend the whole quota and lock everyone out, and
# password guessing costs an attacker nothing per attempt.
#
# So we count attempts ourselves, per email address, and stop replaying them upstream.
#
# FAILS OPEN, DELIBERATELY. If Redis is unreachable the limiter allows the attempt and
# logs it. Failing closed would mean a Redis outage locks every player out of the game
# entirely, which is a bigger and more likely harm than the brute-force window it would
# close. This is the opposite of the rarity engine's fail-safe rule, because the cost of
# being wrong points the other way -- worth noticing rather than assuming one rule fits
# everywhere.


async def check_and_count(action: str, key: str, limit: int, window_seconds: int) -> bool:
    """Record an attempt and report whether it is still within the allowance.

    Returns False once more than ``limit`` attempts for ``key`` occur inside a rolling
    ``window_seconds``. The counter's TTL is set on first write only, so the window runs
    from the first attempt rather than sliding forward with each one -- otherwise an
    attacker could hold the key alive indefinitely by keeping up a steady rate.
    """
    redis_key = f"ratelimit:{action}:{key}"
    try:
        count = await r.incr(redis_key)
        if count == 1:
            await r.expire(redis_key, window_seconds)
        return count <= limit
    except Exception:  # noqa: BLE001
        logger.exception("rate limit check failed for %s; allowing the attempt", action)
        return True


async def reset(action: str, key: str) -> None:
    """Clear the counter, called after a successful sign-in so a legitimate user who
    mistyped a few times isn't left throttled."""
    try:
        await r.delete(f"ratelimit:{action}:{key}")
    except Exception:  # noqa: BLE001
        logger.exception("rate limit reset failed for %s", action)
