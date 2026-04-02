"""Gestion centralisée du rate limit Spotify — v2 (stop total + file d'attente)."""

import asyncio
import re
import time

from spotipy.exceptions import SpotifyException

from bot.config import RATE_LIMIT_PING_INTERVAL, QUEUE_REQUEST_DELAY
from bot.utils.logger import log


# ─── ÉTAT GLOBAL ───────────────────────────────────────────────────────────────
_rate_limit_until: float = 0.0
_timer_task: asyncio.Task | None = None
_ping_task: asyncio.Task | None = None
_bot_ref = None  # référence au bot, injectée par activate_rate_limit


# ─── FONCTIONS PUBLIQUES ──────────────────────────────────────────────────────


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


def extract_retry_after(exc: SpotifyException) -> int:
    """
    Extrait le délai Retry-After d'une SpotifyException.
    Ordre :
      0. Attribut _captured_retry_after injecté depuis stdout
      1. Header HTTP Retry-After
      2. Regex dans le message d'erreur
      3. Fallback 3600s
    """
    captured = getattr(exc, "_captured_retry_after", None)
    if captured is not None:
        log.debug(f"Retry-After extrait depuis stdout spotipy : {captured}s")
        return captured

    if exc.headers:
        raw = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
        if raw is not None:
            try:
                value = int(raw)
                log.debug(f"Retry-After extrait du header : {value}s")
                return value
            except (ValueError, TypeError):
                pass

    pattern = r"Retry will occur after:\s*(\d+)"
    for source in (exc.msg, exc.reason, str(exc)):
        if source:
            match = re.search(pattern, str(source))
            if match:
                value = int(match.group(1))
                log.debug(f"Retry-After extrait du message : {value}s")
                return value

    log.warning("Retry-After introuvable dans l'exception, fallback à 3600s")
    log.debug(f"  exc.headers = {exc.headers}")
    log.debug(f"  exc.msg     = {exc.msg}")
    log.debug(f"  exc.reason  = {exc.reason}")
    log.debug(f"  str(exc)    = {str(exc)}")
    return 3600


def activate_rate_limit(retry_after: int, bot):
    """
    Déclenche le mode rate limit :
    1. Stoppe le cycle horaire de vérification
    2. Démarre le timer d'expiration
    3. Démarre la boucle de ping dans les logs
    """
    global _rate_limit_until, _timer_task, _ping_task, _bot_ref
    _bot_ref = bot
    _rate_limit_until = time.monotonic() + retry_after

    check_releases = getattr(bot, "_check_releases_task", None)
    if check_releases and check_releases.is_running():
        check_releases.cancel()
        log.warning(f"⛔ Cycle horaire stoppé — rate limit activé pour {format_remaining()}")
    else:
        log.warning(f"⛔ Rate limit activé pour {format_remaining()} (cycle déjà inactif)")

    if _timer_task and not _timer_task.done():
        _timer_task.cancel()
    if _ping_task and not _ping_task.done():
        _ping_task.cancel()

    _timer_task = asyncio.create_task(_expiration_timer())
    _ping_task = asyncio.create_task(_ping_loop())


# ─── TÂCHES INTERNES ──────────────────────────────────────────────────────────


async def _ping_loop():
    """Log le temps restant périodiquement — ne bloque rien."""
    log.info(f"⏸️ Rate limit Spotify — pause de {format_remaining()}...")

    while is_rate_limited():
        wait = min(remaining_seconds(), RATE_LIMIT_PING_INTERVAL)
        if wait < 1:
            break
        await asyncio.sleep(wait)
        if is_rate_limited():
            remaining = remaining_seconds()
            if remaining < 1:
                break
            log.info(f"⏳ Rate limit Spotify — encore {format_remaining()} avant reprise")

    log.info("✅ Rate limit Spotify — fin du ping loop")


async def _expiration_timer():
    """Attend l'expiration du rate limit, traite la file, puis relance le cycle."""
    delay = remaining_seconds()
    if delay > 0:
        await asyncio.sleep(delay)

    log.info("✅ Rate limit expiré")

    await _process_queue()

    if _bot_ref:
        check_releases = getattr(_bot_ref, "_check_releases_task", None)
        if check_releases and not check_releases.is_running():
            check_releases.start()
            log.info("🔄 Cycle horaire relancé")


async def _process_queue():
    """Traite la file d'attente après expiration du rate limit."""
    from bot.data.pending import get_all_pending, remove_entry
    from bot.spotify.api import get_artist_from_url, get_latest_release
    from bot.data import storage

    pending = await get_all_pending()

    if not pending:
        log.info("📭 File d'attente vide, rien à traiter")
        return

    log.info(f"📋 Traitement de la file d'attente ({len(pending)} requête(s))...")

    for entry in pending:
        entry_id = entry["id"]
        guild_id = entry["guild_id"]
        user_id = entry["user_id"]
        url = entry["url"]

        try:
            artist = await get_artist_from_url(url)
            if not artist:
                log.warning(f"File — artiste introuvable : {url}")
                await remove_entry(entry_id)
                await asyncio.sleep(QUEUE_REQUEST_DELAY)
                continue

            release = None
            try:
                release = await get_latest_release(artist["id"])
            except SpotifyException as e:
                if e.http_status == 429:
                    retry_after = extract_retry_after(e)
                    log.warning(f"🔁 Nouveau 429 pendant traitement file — re-timer {retry_after}s")
                    activate_rate_limit(retry_after, _bot_ref)
                    return
                log.warning(f"File — erreur récup. dernière sortie de '{artist['name']}' : {e}")
            except Exception as e:
                log.warning(f"File — erreur récup. dernière sortie de '{artist['name']}' : {e}")

            await storage.add_artist(guild_id, artist, release)
            await storage.add_subscriber(guild_id, artist["id"], user_id)
            log.info(f"File — ✅ {artist['name']} ajouté (guild={guild_id}, user={user_id})")
            await remove_entry(entry_id)

        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = extract_retry_after(e)
                log.warning(f"🔁 Nouveau 429 pendant traitement file — re-timer {retry_after}s")
                activate_rate_limit(retry_after, _bot_ref)
                return
            log.warning(f"File — erreur pour {url} : {e}")
            await remove_entry(entry_id)

        except Exception as e:
            log.error(f"File — erreur inattendue pour {url} : {type(e).__name__}: {e}")
            await remove_entry(entry_id)

        await asyncio.sleep(QUEUE_REQUEST_DELAY)

    log.info("📋 File d'attente entièrement traitée")