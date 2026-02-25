"""Gestion centralisée du rate limit Spotify."""

import asyncio
import time
from bot.utils.logger import log

# ─── ÉTAT GLOBAL ───────────────────────────────────────────────────────────────
_rate_limit_until: float = 0.0  # timestamp UNIX jusqu'auquel on est bloqué
_PING_INTERVAL = 600            # log un ping toutes les 10 minutes pendant le sleep
_ping_task: asyncio.Task | None = None


def is_rate_limited() -> bool:
    """Retourne True si on est actuellement rate-limité."""
    return time.time() < _rate_limit_until


def remaining_seconds() -> int:
    """Secondes restantes avant la fin du rate limit."""
    return max(0, int(_rate_limit_until - time.time()))


def format_remaining() -> str:
    """Formate le temps restant en heures/minutes lisible."""
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
    """Enregistre un rate limit et lance immédiatement la task de ping."""
    global _rate_limit_until, _ping_task
    _rate_limit_until = time.time() + retry_after
    log.warning(f"Rate limit activé pour {retry_after}s (~{format_remaining()})")

    # Lancer la task de ping si pas déjà en cours
    if _ping_task is None or _ping_task.done():
        _ping_task = asyncio.create_task(_ping_loop())


def clear_rate_limit():
    """Annule le rate limit."""
    global _rate_limit_until
    _rate_limit_until = 0.0


async def _ping_loop():
    """Task autonome qui log le temps restant à intervalle régulier."""
    log.info(f"⏸️ Rate limit Spotify — pause de {format_remaining()}...")

    while is_rate_limited():
        remaining = remaining_seconds()
        sleep_time = min(remaining, _PING_INTERVAL)
        await asyncio.sleep(sleep_time)

        if is_rate_limited():
            log.info(f"⏳ Rate limit Spotify — encore {format_remaining()} avant reprise")

    clear_rate_limit()
    log.info("✅ Rate limit expiré, reprise des opérations")


async def wait_for_rate_limit():
    """
    Attend la fin du rate limit si actif.
    Si la ping_loop tourne déjà, attend simplement qu'elle finisse.
    """
    global _ping_task

    if not is_rate_limited():
        return

    # Si la task tourne déjà, on attend sa fin
    if _ping_task and not _ping_task.done():
        await _ping_task
    # Sinon on attend directement (cas improbable)
    elif is_rate_limited():
        _ping_task = asyncio.create_task(_ping_loop())
        await _ping_task