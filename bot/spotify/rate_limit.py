"""Gestion centralisée du rate limit Spotify."""

import asyncio
import time
from bot.utils.logger import log

# ─── ÉTAT GLOBAL ───────────────────────────────────────────────────────────────
_rate_limit_until: float = 0.0
_PING_INTERVAL = 600  # log toutes les 10 minutes
_ping_task: asyncio.Task | None = None


def is_rate_limited() -> bool:
    return time.monotonic() < _rate_limit_until


def remaining_seconds() -> int:
    return max(0, int(_rate_limit_until - time.monotonic()))


def format_remaining() -> str:
    secs = remaining_seconds()
    if secs <= 0:
        return "0s"
    h, remainder = divmod(secs, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}h{m:02d}min"
    if m > 0:
        return f"{m}min{s:02d}s"
    return f"{s}s"


def set_rate_limit(retry_after: int):
    global _rate_limit_until, _ping_task
    _rate_limit_until = time.monotonic() + retry_after
    log.warning(f"Rate limit activé pour {retry_after}s (~{format_remaining()})")

    if _ping_task is None or _ping_task.done():
        _ping_task = asyncio.create_task(_ping_loop())


async def _ping_loop():
    """Log le temps restant toutes les 10 minutes — ne bloque rien."""
    log.info(f"⏸️ Rate limit Spotify — pause de {format_remaining()}...")

    while is_rate_limited():
        await asyncio.sleep(min(remaining_seconds(), _PING_INTERVAL))
        if is_rate_limited():
            log.info(f"⏳ Rate limit Spotify — encore {format_remaining()} avant reprise")

    log.info("✅ Rate limit expiré, reprise au prochain cycle")