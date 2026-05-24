"""
Orchestration de la mise a jour de l'album quotidien sur Synology Photos.
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from synology_client import SynologyPhotosClient
    from themes import ThemeResult

log = logging.getLogger("album")

# Suffixe du nom d'album pour chaque theme — ces noms sont permanents
_ALBUM_SUFFIX = {
    "anniversary": "Anniversaires",
    "season":      "Saison",
    "random":      "Aleatoire",
}


def build_album_name(prefix: str, theme_name: str) -> str:
    """Construit le nom permanent de l'album : 'Album du jour — Anniversaires'."""
    suffix = _ALBUM_SUFFIX.get(theme_name, theme_name.capitalize())
    return f"{prefix} — {suffix}"


def build_daily_album(
    client: "SynologyPhotosClient",
    theme_result: "ThemeResult",
    config: dict[str, Any],
) -> str:
    """
    Met a jour l'album persistant du theme du jour sur Synology Photos.
    Retourne le nom de l'album.

    - Album introuvable → le cree (configurer le partage une fois dans Synology Photos)
    - Album existant    → vide les photos et les remplace par la nouvelle selection
    """
    prefix   = config["album"]["name_prefix"]
    name     = build_album_name(prefix, theme_result.theme_name)
    item_ids = theme_result.item_ids

    log.info("Preparation de l'album : << %s >>", name)
    log.info("Photos a ajouter : %d (theme : %s)", len(item_ids), theme_result.theme_name)

    album_id = client.find_album(name)
    if album_id is None:
        log.info("Album introuvable — creation de << %s >>", name)
        album_id = client.create_album(name)
    else:
        log.info("Album existant (id=%d) — remplacement des photos", album_id)
        client.clear_album(album_id)

    client.add_items_to_album(album_id, item_ids)
    log.info("Album << %s >> mis a jour", name)
    return name
