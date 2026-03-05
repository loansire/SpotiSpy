"""Throttle proactif pour l'API Spotify — débit constant par fenêtre glissante."""

import asyncio
import time
from collections import deque

from bot.config import THROTTLE_WINDOW_S, THROTTLE_MAX_REQUESTS, THROTTLE_RESERVED_SLOTS
from bot.utils.logger import log


class SpotifyThrottle:
    """
    Régulateur de débit à flux constant.

    Deux comportements selon la priorité :
    - priority=False (checker, queue) → delay fixe entre chaque requête
      delay = THROTTLE_WINDOW_S / (MAX_REQUESTS - RESERVED_SLOTS)
    - priority=True  (/spy) → passe immédiatement tant que le bucket
      a de la place (< MAX_REQUESTS), sinon attend un slot libre

    La deque de timestamps sert de compteur réel pour le bucket.
    """

    def __init__(self):
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._last_normal: float = 0.0

        # Delay pré-calculé pour les requêtes normales
        max_normal = THROTTLE_MAX_REQUESTS - THROTTLE_RESERVED_SLOTS
        self._delay_normal = THROTTLE_WINDOW_S / max_normal

        log.info(
            f"Throttle initialisé : {THROTTLE_WINDOW_S}s / "
            f"{max_normal} req = {self._delay_normal:.2f}s entre chaque requête (checker) | "
            f"{THROTTLE_RESERVED_SLOTS} slots réservés (/spy = immédiat)"
        )

    def _purge(self):
        """Retire les timestamps hors de la fenêtre glissante."""
        cutoff = time.monotonic() - THROTTLE_WINDOW_S
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def get_usage(self) -> tuple[int, int, float]:
        """Retourne (count, max, pourcentage) — pour debug/logging."""
        self._purge()
        count = len(self._timestamps)
        pct = count / THROTTLE_MAX_REQUESTS if THROTTLE_MAX_REQUESTS > 0 else 0.0
        return count, THROTTLE_MAX_REQUESTS, pct

    async def _acquire_priority(self):
        """Requête prioritaire (/spy) : passe immédiatement si le bucket a de la place."""
        self._purge()

        if len(self._timestamps) < THROTTLE_MAX_REQUESTS:
            self._timestamps.append(time.monotonic())
            log.debug(f"🟢 Throttle [prioritaire] : pass direct ({len(self._timestamps)}/{THROTTLE_MAX_REQUESTS})")
            return

        # Bucket plein → attendre le plus ancien slot
        oldest = self._timestamps[0]
        wait = oldest + THROTTLE_WINDOW_S - time.monotonic()
        if wait > 0:
            log.warning(
                f"🔴 Throttle [prioritaire] : bucket plein "
                f"({THROTTLE_MAX_REQUESTS}/{THROTTLE_MAX_REQUESTS}), pause {wait:.1f}s"
            )
            self._lock.release()
            try:
                await asyncio.sleep(wait)
            finally:
                await self._lock.acquire()
            self._purge()

        self._timestamps.append(time.monotonic())

    async def _acquire_normal(self):
        """Requête normale (checker, queue) : delay fixe entre chaque requête."""
        # ── Espacement fixe depuis la dernière requête normale ──────
        now = time.monotonic()
        elapsed = now - self._last_normal
        wait = self._delay_normal - elapsed

        if wait > 0:
            log.debug(f"🟡 Throttle [normal] : attente {wait:.2f}s")
            self._lock.release()
            try:
                await asyncio.sleep(wait)
            finally:
                await self._lock.acquire()

        # ── Sécurité : vérifier le bucket réel ─────────────────────
        self._purge()
        effective_max = THROTTLE_MAX_REQUESTS - THROTTLE_RESERVED_SLOTS

        if len(self._timestamps) >= effective_max:
            oldest = self._timestamps[0]
            safety_wait = oldest + THROTTLE_WINDOW_S - time.monotonic()
            if safety_wait > 0:
                log.warning(
                    f"🔴 Throttle [normal] : sécurité activée, bucket plein "
                    f"({len(self._timestamps)}/{effective_max}), pause {safety_wait:.1f}s"
                )
                self._lock.release()
                try:
                    await asyncio.sleep(safety_wait)
                finally:
                    await self._lock.acquire()
                self._purge()

        # ── Enregistrer et passer ──────────────────────────────────
        self._last_normal = time.monotonic()
        self._timestamps.append(self._last_normal)

    async def acquire(self, priority: bool = False):
        """
        Point d'entrée unique. Attend si nécessaire avant d'autoriser un appel API.

        Args:
            priority: True pour les commandes utilisateur (/spy),
                      False pour le checker et le traitement de la file.
        """
        async with self._lock:
            if priority:
                await self._acquire_priority()
            else:
                await self._acquire_normal()


# Instance unique, importable partout
throttle = SpotifyThrottle()