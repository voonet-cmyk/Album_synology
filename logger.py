"""Configuration centralisée des logs avec rotation automatique."""
from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path


LOG_FILE = Path(__file__).parent / "logs" / "album.log"


def setup_logger(level: str = "INFO", retention_days: int = 30) -> logging.Logger:
    """
    Configure et retourne le logger principal.
    Rotation quotidienne à minuit, conservation sur `retention_days` jours.
    Les messages s'affichent aussi dans le terminal pour les tests manuels.
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("album")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",
        backupCount=retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    logger.addHandler(console_handler)

    return logger
