import logging
import sys
from bot.config import LOG_FILE

def setup_logger(name: str = "spotispy", level: int = logging.DEBUG) -> logging.Logger:
    """Crée et configure un logger avec sortie console + fichier."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="[{asctime}] [{levelname:<8}] {name}.{funcName}: {message}",
        datefmt="%H:%M:%S %d-%m-%Y",
        style="{"
    )

    # ─── Console : INFO+ ──────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # ─── Fichier : DEBUG+ (tout) ──────────────────────────────────────
    file = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file.setLevel(logging.DEBUG)
    file.setFormatter(fmt)
    logger.addHandler(file)

    return logger

# Logger principal, importable partout
log = setup_logger()