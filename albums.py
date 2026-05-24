"""Création d'un album partagé Synology et ajout des photos par référence (item_id)."""
from __future__ import annotations
import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from auth import SynologySession

BATCH_SIZE = 100  # nombre max de photos par appel API


def build_album_name(prefix: str, theme: str, today: datetime.date) -> str:
    """Construit le nom de l'album, ex : 'Album du jour — Anniversaire — 2026-05-15'."""
    labels = {
        "anniversary": "Anniversaire",
        "seasonal": "Saison",
        "random": "Aléatoire",
    }
    return f"{prefix} — {labels.get(theme, theme)} — {today.isoformat()}"


def create_album(session: "SynologySession", name: str) -> int:
    """
    Crée un album partagé vide via SYNO.FotoTeam.Album.
    Retourne l'album_id assigné par Synology.
    """
    # TODO

def add_photos_to_album(
    session: "SynologySession",
    album_id: int,
    photos: list[dict[str, Any]],
) -> None:
    """
    Ajoute les photos à l'album via leurs item_id (zéro copie physique).
    Procède par lots de BATCH_SIZE pour respecter les limites de l'API.
    """
    # TODO
