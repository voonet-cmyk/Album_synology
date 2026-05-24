"""
Index local des photos de l'espace partagé Synology.

Construit un cache JSON au premier lancement puis le réutilise.
Le cache est invalidé si son âge dépasse max_age_hours (défaut : 24 h)
ou si force_rebuild=True est passé à load().

Structure de chaque photo dans l'index :
    {
        "id":          int,   # identifiant Synology (item_id)
        "name":        str,   # nom du fichier (ex: IMG_1234.jpg)
        "date_taken":  int,   # timestamp Unix de la prise de vue (0 si inconnu)
        "folder_id":   int,   # identifiant du dossier parent
        "folder_path": str,   # chemin reconstitué (ex: "Vacances/2021/Été")
    }
"""
from __future__ import annotations

import datetime
import fnmatch
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from synology_client import SynologyPhotosClient

log = logging.getLogger("album")

CACHE_FILE          = Path(__file__).parent / "cache" / "index.json"
DEFAULT_MAX_AGE_H   = 24
_PAGE_SIZE          = 500   # photos par appel API

# Mois de chaque saison (hémisphère nord)
_SEASON_MONTHS: dict[str, frozenset[int]] = {
    "spring": frozenset([3, 4, 5]),
    "summer": frozenset([6, 7, 8]),
    "autumn": frozenset([9, 10, 11]),
    "winter": frozenset([12, 1, 2]),
}


class PhotoIndex:
    """
    Index en mémoire de toutes les photos de l'espace partagé.

    Usage typique :
        index = PhotoIndex.from_config(config)
        index.load(client, force_rebuild=args.rebuild_index)
        pool  = index.filter_by_date(month=5, day=15)
        picks = index.random_sample(30, pool=pool)
    """

    def __init__(
        self,
        cache_file: Path = CACHE_FILE,
        max_age_hours: float = DEFAULT_MAX_AGE_H,
        exclude_paths: Optional[list[str]] = None,
    ) -> None:
        self._cache_file    = cache_file
        self._max_age_hours = max_age_hours
        self._exclude_paths: frozenset[str] = frozenset(exclude_paths or [])
        self._photos: list[dict[str, Any]] = []

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "PhotoIndex":
        """Construit un PhotoIndex depuis la configuration applicative."""
        max_age = float(config.get("cache", {}).get("max_age_hours", DEFAULT_MAX_AGE_H))
        raw_excl = config.get("themes", {}).get("exclude_paths", "")
        exclude  = [p.strip() for p in str(raw_excl).split(",") if p.strip()]
        if exclude:
            log.info("Chemins exclus de l'index : %s", exclude)
        return cls(cache_file=CACHE_FILE, max_age_hours=max_age, exclude_paths=exclude)

    # ── Chargement / reconstruction ──────────────────────────────────────────

    def load(
        self,
        client: "SynologyPhotosClient",
        force_rebuild: bool = False,
    ) -> None:
        """
        Point d'entrée principal.
        Charge le cache si récent, sinon reconstruit depuis l'API Synology.
        force_rebuild=True → reconstruit toujours, même si le cache est frais.
        """
        if force_rebuild:
            log.info("Reconstruction forcée de l'index (--rebuild-index)")
            self._rebuild(client)
            return

        if self._is_stale():
            log.info("Cache absent ou périmé — reconstruction de l'index")
            self._rebuild(client)
        else:
            self._load_from_cache()

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _is_stale(self) -> bool:
        if not self._cache_file.exists():
            return True
        try:
            meta = json.loads(self._cache_file.read_text(encoding="utf-8"))
            age_h = (time.time() - float(meta.get("generated_at_ts", 0))) / 3600
            if age_h > self._max_age_hours:
                log.debug("Cache périmé (%.1fh > %.1fh max)", age_h, self._max_age_hours)
                return True
            log.debug("Cache valide (âge : %.1fh)", age_h)
            return False
        except Exception as exc:
            log.warning("Cache illisible (%s) — reconstruction", exc)
            return True

    def _load_from_cache(self) -> None:
        raw = json.loads(self._cache_file.read_text(encoding="utf-8"))
        self._photos = raw.get("photos", [])
        log.info(
            "Index chargé depuis le cache : %d photos (généré le %s)",
            len(self._photos),
            raw.get("generated_at", "?"),
        )

    def _save_cache(self) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now()
        payload = {
            "generated_at":    now.isoformat(timespec="seconds"),
            "generated_at_ts": now.timestamp(),
            "count":           len(self._photos),
            "photos":          self._photos,
        }
        self._cache_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Cache sauvegardé → %s (%d photos)", self._cache_file, len(self._photos))

    # ── Reconstruction depuis l'API ───────────────────────────────────────────

    def _rebuild(self, client: "SynologyPhotosClient") -> None:
        """Parcourt tous les dossiers de l'espace partagé et indexe les photos."""
        log.info("Reconstruction de l'index en cours…")

        folder_map = self._fetch_folder_map(client)
        log.info("%d dossier(s) trouvé(s)", len(folder_map))

        photos: list[dict[str, Any]] = []
        for folder_id, folder_path in folder_map.items():
            batch = self._fetch_folder_items(client, folder_id, folder_path)
            photos.extend(batch)
            if batch:
                log.info(
                    "  %-45s  %4d photo(s)  [cumul : %d]",
                    (folder_path or "/")[:45],
                    len(batch),
                    len(photos),
                )

        self._photos = photos
        self._save_cache()
        log.info("Index terminé : %d photos indexées", len(photos))

    def _fetch_folder_map(
        self,
        client: "SynologyPhotosClient",
    ) -> dict[int, str]:
        """
        Retourne un dict {folder_id: chemin_complet} pour tous les dossiers.
        Parcours récursif en largeur (BFS) pour éviter les débordements de pile.
        """
        folder_map: dict[int, str] = {}
        # File d'attente : (parent_id, chemin_parent)
        queue: list[tuple[Optional[int], str]] = [(None, "")]

        while queue:
            parent_id, parent_path = queue.pop(0)
            try:
                children = client.list_folders(parent_id=parent_id, limit=500)
            except Exception as exc:
                log.warning("Impossible de lister les sous-dossiers de id=%s : %s", parent_id, exc)
                continue

            for f in children:
                fid = f.get("id")
                if fid is None:
                    continue
                name = f.get("name", "")
                path = f"{parent_path}/{name}".lstrip("/")
                if self._is_excluded(path):
                    log.info("Dossier exclu (config) : %s", path)
                    continue
                folder_map[fid] = path
                queue.append((fid, path))

        return folder_map

    def _is_excluded(self, path: str) -> bool:
        """
        Retourne True si le chemin doit être ignoré selon exclude_paths.

        Deux règles selon la forme du pattern :
        - Sans '/'  (ex: "19*", "VHS*") → match sur chaque segment du chemin
        - Avec '/'  (ex: "Famille/19*") → match glob sur le chemin complet
        """
        segments = path.split("/")
        for pattern in self._exclude_paths:
            if "/" in pattern:
                if fnmatch.fnmatch(path, pattern):
                    return True
            else:
                if any(fnmatch.fnmatch(seg, pattern) for seg in segments):
                    return True
        return False

    def _fetch_folder_items(
        self,
        client: "SynologyPhotosClient",
        folder_id: int,
        folder_path: str,
    ) -> list[dict[str, Any]]:
        """Récupère toutes les photos d'un dossier, page par page."""
        photos: list[dict[str, Any]] = []
        offset = 0

        while True:
            try:
                batch = client.list_items(
                    folder_id=folder_id,
                    limit=_PAGE_SIZE,
                    offset=offset,
                )
            except Exception as exc:
                log.warning("Erreur lors de la lecture de '%s' : %s", folder_path, exc)
                break

            for item in batch:
                photos.append({
                    "id":          item.get("id"),
                    "name":        item.get("filename", ""),
                    "date_taken":  item.get("time", 0),
                    "folder_id":   item.get("folder_id", folder_id),
                    "folder_path": folder_path,
                })

            offset += len(batch)
            if len(batch) < _PAGE_SIZE:
                break   # dernière page atteinte

        return photos

    # ── Filtres ───────────────────────────────────────────────────────────────

    def filter_by_date(
        self,
        month: Optional[int] = None,
        day: Optional[int] = None,
        year: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Filtre les photos par date de prise de vue.
        Les critères non fournis sont ignorés (filtre cumulatif).

        Exemples :
            filter_by_date(month=5, day=15)  → photos du 15 mai, toutes années
            filter_by_date(month=12)         → photos prises en décembre
            filter_by_date(year=2019)        → photos de 2019
            filter_by_date(month=7, year=2022) → photos de juillet 2022
        """
        result = []
        for p in self._photos:
            ts = p.get("date_taken", 0)
            if not ts:
                continue
            try:
                d = datetime.date.fromtimestamp(ts)
            except (OSError, OverflowError, ValueError):
                continue
            if month is not None and d.month != month:
                continue
            if day   is not None and d.day   != day:
                continue
            if year  is not None and d.year  != year:
                continue
            result.append(p)
        return result

    def filter_by_season(self, season: str) -> list[dict[str, Any]]:
        """
        Filtre les photos par saison, toutes années confondues.
        season : "spring" | "summer" | "autumn" | "winter"
        Lève ValueError pour une valeur inconnue.
        """
        key = season.lower().strip()
        months = _SEASON_MONTHS.get(key)
        if months is None:
            raise ValueError(
                f"Saison inconnue : '{season}'. "
                f"Valeurs acceptées : {sorted(_SEASON_MONTHS)}"
            )
        result = []
        for p in self._photos:
            ts = p.get("date_taken", 0)
            if not ts:
                continue
            try:
                if datetime.date.fromtimestamp(ts).month in months:
                    result.append(p)
            except (OSError, OverflowError, ValueError):
                continue
        return result

    def random_sample(
        self,
        n: int,
        pool: Optional[list[dict[str, Any]]] = None,
        exclude_ids: Optional[frozenset[int]] = None,
    ) -> list[dict[str, Any]]:
        """
        Retourne n photos tirées au hasard.
        pool=None       → tire depuis l'intégralité de l'index.
        exclude_ids     → écarte les photos déjà partagées récemment.
        Si le pool est épuisé après exclusion, ignore l'historique pour cette sélection.
        Si le pool contient moins de n photos, retourne tout le pool.
        """
        source = pool if pool is not None else self._photos
        if exclude_ids:
            filtered = [p for p in source if p.get("id") not in exclude_ids]
            if filtered:
                excluded_count = len(source) - len(filtered)
                if excluded_count:
                    log.debug(
                        "Non-répétition : %d/%d photo(s) écartée(s) (déjà partagées)",
                        excluded_count, len(source),
                    )
                source = filtered
            else:
                log.warning(
                    "Toutes les photos du pool (%d) sont dans l'historique "
                    "— fenêtre de non-répétition ignorée pour cette sélection",
                    len(source),
                )
        return random.sample(source, min(n, len(source)))

    # ── Propriétés ────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Nombre total de photos dans l'index."""
        return len(self._photos)

    @property
    def all_photos(self) -> list[dict[str, Any]]:
        """Liste complète des photos indexées."""
        return self._photos
