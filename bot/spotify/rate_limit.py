"""Gestion centralisée du rate limit Spotify."""

import asyncio
import re
import time

from spotipy.exceptions import SpotifyException

from bot.utils.logger import log

_DEFAULT_RETRY = 3600
_RETRY_PATTERN = re.compile(r"Retry will occur after:\s*(\d+)")


def extract_retry_after(exc: SpotifyException) -> int:
    """Extrait le délai Retry-After depuis les headers ou le message d'erreur Spotify."""
    # 1. Header HTTP standard
    if exc.headers:
        raw = exc.headers.get("Retry-After")
        if raw is not None:
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass

    # 2. Parsing du message d'erreur spotipy (ex: "Retry will occur after: 45010 s")
    for source in (getattr(exc, "msg", ""), getattr(exc, "reason", ""), str(exc)):
        if not source:
            continue
        match = _RETRY_PATTERN.search(source)
        if match:
            return int(match.group(1))

    # 3. Fallback
    log.warning(f"Retry-After introuvable dans l'exception, fallback {_DEFAULT_RETRY}s")
    return _DEFAULT_RETRY

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
        wait = remaining_seconds()
        if wait <= 0:
            break
        await asyncio.sleep(min(wait, _PING_INTERVAL))
        if is_rate_limited() and remaining_seconds() > 0:
            log.info(f"⏳ Rate limit Spotify — encore {format_remaining()} avant reprise")

    log.info("✅ Rate limit expiré, reprise au prochain cycle")