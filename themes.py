"""
Moteur de thèmes : sélectionne N photos selon la stratégie du jour.

Trois stratégies :
  AnniversaryTheme  — photos prises autour de la même date les années passées
  SeasonTheme       — photos prises dans le même mois (toutes années)
  RandomTheme       — tirage uniforme dans toute la bibliothèque

La stratégie du jour est choisie par rotation déterministe basée sur le
numéro du jour dans l'année. Si elle ne trouve pas assez de photos, le
sélecteur repli automatiquement sur RandomTheme.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from photo_index import PhotoIndex

log = logging.getLogger("album")

# Fenêtres d'élargissement successives pour AnniversaryTheme (en jours de chaque côté)
_WINDOWS = [1, 3, 7]

_FR_MONTHS = {
    1: "janvier",  2: "février",   3: "mars",      4: "avril",
    5: "mai",      6: "juin",      7: "juillet",   8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}
_SEASON_OF_MONTH: dict[int, str] = {
    1: "winter", 2: "winter",  3: "spring", 4: "spring",
    5: "spring", 6: "summer",  7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn", 12: "winter",
}
_SEASON_LABELS: dict[str, str] = {
    "spring": "Printemps", "summer": "Été",
    "autumn": "Automne",   "winter": "Hiver",
}


# ── Résultat ──────────────────────────────────────────────────────────────────
@dataclass
class ThemeResult:
    """Ce que renvoie chaque stratégie."""
    theme_name: str        # "anniversary" | "season" | "random"
    label:      str        # libellé humain pour le nom de l'album
    photos:     list[dict] # photos sélectionnées (dicts issus de PhotoIndex)

    @property
    def item_ids(self) -> list[int]:
        """IDs Synology prêts à passer à add_items_to_album()."""
        return [p["id"] for p in self.photos if p.get("id") is not None]

    def is_empty(self) -> bool:
        return len(self.photos) == 0


# ── AnniversaryTheme ──────────────────────────────────────────────────────────
class AnniversaryTheme:
    """Photos prises à la même date (± fenêtre) dans les années précédentes."""
    name = "anniversary"

    def select(
        self,
        index: "PhotoIndex",
        today: datetime.date,
        count: int,
        years_back: list[int],
        exclude_ids: Optional[frozenset[int]] = None,
    ) -> ThemeResult:
        """
        Cherche dans les fenêtres ±1 j → ±3 j → ±7 j.
        Abandonne (retourne vide) si 0 photo trouvée avec ±7 j.
        """
        pool: list[dict[str, Any]] = []

        for window in _WINDOWS:
            pool = self._collect(index, today, years_back, window)
            if pool:
                if window > _WINDOWS[0]:
                    log.info(
                        "AnniversaryTheme : fenêtre élargie à ±%d j → %d photo(s)",
                        window, len(pool),
                    )
                break
            if window < _WINDOWS[-1]:
                log.info(
                    "AnniversaryTheme : ±%d j → 0 photo, élargissement…", window,
                )

        if not pool:
            log.warning(
                "AnniversaryTheme : aucune photo autour du %02d/%02d"
                " même avec ±%d j sur %d an(s) — abandon",
                today.day, today.month, _WINDOWS[-1], len(years_back),
            )
            return ThemeResult(self.name, "", [])

        # Tri chronologique pour mélanger les années naturellement
        pool.sort(key=lambda p: p.get("date_taken", 0))
        selected = index.random_sample(count, pool=pool, exclude_ids=exclude_ids)
        selected.sort(key=lambda p: p.get("date_taken", 0))

        years_found = sorted({
            datetime.date.fromtimestamp(p["date_taken"]).year
            for p in selected if p.get("date_taken")
        })

        if len(years_found) == 1:
            delta = today.year - years_found[0]
            label = f"Il y a {delta} an{'s' if delta > 1 else ''} aujourd'hui"
        else:
            label = f"Souvenirs du {today.day} {_FR_MONTHS[today.month]}"

        log.info(
            "AnniversaryTheme : %d photo(s) depuis %s",
            len(selected), ", ".join(str(y) for y in years_found),
        )
        return ThemeResult(self.name, label, selected)

    def _collect(
        self,
        index: "PhotoIndex",
        today: datetime.date,
        years_back: list[int],
        window: int,
    ) -> list[dict[str, Any]]:
        """Un seul parcours de l'index pour trouver les photos dans tous les intervalles."""
        intervals: list[tuple[datetime.date, datetime.date]] = []
        for y in years_back:
            try:
                center = datetime.date(today.year - y, today.month, today.day)
            except ValueError:
                # 29 février dans une année non bissextile → 28 février
                center = datetime.date(today.year - y, today.month, 28)
            intervals.append((
                center - datetime.timedelta(days=window),
                center + datetime.timedelta(days=window),
            ))

        seen: set = set()
        results: list[dict[str, Any]] = []
        for photo in index.all_photos:
            ts = photo.get("date_taken", 0)
            if not ts:
                continue
            try:
                d = datetime.date.fromtimestamp(ts)
            except (OSError, OverflowError, ValueError):
                continue
            pid = photo.get("id")
            if pid in seen:
                continue
            for lo, hi in intervals:
                if lo <= d <= hi:
                    seen.add(pid)
                    results.append(photo)
                    break

        return results


# ── SeasonTheme ───────────────────────────────────────────────────────────────
class SeasonTheme:
    """Photos prises dans le même mois que aujourd'hui, toutes années confondues."""
    name = "season"

    def select(
        self,
        index: "PhotoIndex",
        today: datetime.date,
        count: int,
        exclude_ids: Optional[frozenset[int]] = None,
    ) -> ThemeResult:
        pool     = index.filter_by_date(month=today.month)
        selected = index.random_sample(count, pool=pool, exclude_ids=exclude_ids)
        label    = _SEASON_LABELS[_SEASON_OF_MONTH[today.month]]
        log.info(
            "SeasonTheme : mois %d → %d/%d photo(s) (%s)",
            today.month, len(selected), len(pool), label,
        )
        return ThemeResult(self.name, label, selected)


# ── RandomTheme ───────────────────────────────────────────────────────────────
class RandomTheme:
    """Tirage uniforme dans toute la bibliothèque."""
    name = "random"

    def select(
        self,
        index: "PhotoIndex",
        count: int,
        exclude_ids: Optional[frozenset[int]] = None,
    ) -> ThemeResult:
        selected = index.random_sample(count, exclude_ids=exclude_ids)
        log.info("RandomTheme : %d photo(s) sélectionnée(s)", len(selected))
        return ThemeResult(self.name, "Sélection du jour", selected)


# ── Sélecteur du jour ─────────────────────────────────────────────────────────
_REGISTRY = {
    "anniversary": AnniversaryTheme,
    "season":      SeasonTheme,
    "random":      RandomTheme,
}


def theme_of_day(today: datetime.date, rotation: list[str]) -> str:
    """Retourne le nom du thème pour `today` par rotation déterministe."""
    return rotation[today.timetuple().tm_yday % len(rotation)]


def current_theme(
    config: dict[str, Any],
    today: datetime.date,
    force: Optional[str] = None,
) -> str:
    """Retourne le nom du thème pour aujourd'hui (ou force si fourni)."""
    if force:
        return force
    return theme_of_day(today, _parse_list(config["themes"]["rotation"]))


def select_for_day(
    index: "PhotoIndex",
    config: dict[str, Any],
    today: Optional[datetime.date] = None,
    force_theme: Optional[str] = None,
    exclude_ids: Optional[frozenset[int]] = None,
) -> ThemeResult:
    """
    Point d'entrée principal.
    Choisit le thème du jour (ou force_theme si fourni), repli sur RandomTheme si vide.
    exclude_ids : IDs à écarter pour le thème choisi (non appliqué au repli).
    """
    if today is None:
        today = datetime.date.today()

    count      = int(config["album"]["photo_count"])
    rotation   = _parse_list(config["themes"]["rotation"])
    years_back = _parse_int_list(
        config["themes"].get("anniversary_years_back", "1,2,3,5,10")
    )

    if force_theme:
        chosen = force_theme
        log.info("Thème forcé : %s", chosen)
    else:
        chosen = theme_of_day(today, rotation)
        log.info(
            "Thème du jour : %s  (jour %d, rotation %s)",
            chosen, today.timetuple().tm_yday, rotation,
        )

    result = _run_theme(chosen, index, today, count, years_back, exclude_ids=exclude_ids)

    if result.is_empty():
        log.warning(
            "Thème '%s' sans résultat → repli automatique sur RandomTheme", chosen,
        )
        result = RandomTheme().select(index, count)
        result.label += " (repli automatique)"

    return result


def _run_theme(
    name: str,
    index: "PhotoIndex",
    today: datetime.date,
    count: int,
    years_back: list[int],
    exclude_ids: Optional[frozenset[int]] = None,
) -> ThemeResult:
    cls = _REGISTRY.get(name)
    if cls is None:
        log.error("Thème inconnu : '%s' — repli sur random", name)
        return ThemeResult("random", "Sélection du jour", [])
    if name == "anniversary":
        return cls().select(index, today, count, years_back, exclude_ids=exclude_ids)
    if name == "season":
        return cls().select(index, today, count, exclude_ids=exclude_ids)
    return cls().select(index, count, exclude_ids=exclude_ids)  # random


# ── Utilitaires ───────────────────────────────────────────────────────────────
def _parse_list(value: Any) -> list[str]:
    return [x.strip() for x in str(value).split(",") if x.strip()]


def _parse_int_list(value: Any) -> list[int]:
    return [int(x.strip()) for x in str(value).split(",") if x.strip()]
