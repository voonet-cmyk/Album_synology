"""Indexation des photos de l'espace partagé et gestion du cache local."""
from __future__ import annotations
import datetime
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from auth import SynologySession


CACHE_FILE = Path(__file__).parent / "cache" / "index.json"


def load_cache() -> list[dict[str, Any]]:
    """Charge l'index local. Retourne une liste vide si le cache n'existe pas encore."""
    if not CACHE_FILE.exists():
        return []
    with CACHE_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("photos", [])


def save_cache(photos: list[dict[str, Any]]) -> None:
    """Sauvegarde l'index des photos avec la date de création du cache."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.date.today().isoformat(),
        "count": len(photos),
        "photos": photos,
    }
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def is_cache_stale(refresh_day: str) -> bool:
    """Retourne True si aujourd'hui est le jour de régénération hebdomadaire."""
    # TODO

def fetch_all_photos(session: "SynologySession") -> list[dict[str, Any]]:
    """Interroge l'API SYNO.FotoTeam pour récupérer toutes les photos de l'espace partagé."""
    # TODO

def get_photos(
    session: "SynologySession",
    refresh_day: str = "monday",
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """
    Retourne la liste des photos disponibles.
    Utilise le cache sauf si force_refresh=True ou si le cache est périmé.
    """
    # TODO
