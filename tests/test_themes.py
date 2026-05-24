"""Tests unitaires pour le moteur de thèmes — aucun appel réseau."""
import datetime
import sys
from pathlib import Path

import pytest
from freezegun import freeze_time

sys.path.insert(0, str(Path(__file__).parent.parent))

from photo_index import PhotoIndex
from themes import (
    AnniversaryTheme, SeasonTheme, RandomTheme,
    ThemeResult, theme_of_day, select_for_day,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _photo(id: int, year: int, month: int, day: int) -> dict:
    """Crée un dict photo avec un timestamp à midi pour éviter les décalages de fuseau."""
    ts = int(datetime.datetime(year, month, day, 12, 0).timestamp())
    return {
        "id": id, "name": f"photo_{id:04d}.jpg",
        "date_taken": ts, "folder_id": 1, "folder_path": "test",
    }


def _index(*photos: dict) -> PhotoIndex:
    """Crée un PhotoIndex en mémoire (pas d'accès disque ni réseau)."""
    idx = PhotoIndex()
    idx._photos = list(photos)
    return idx


def _config(rotation="anniversary,season,random", years_back="1,2,3,5,10", count=30):
    return {
        "album":  {"photo_count": count},
        "themes": {"rotation": rotation, "anniversary_years_back": years_back},
    }


# ── AnniversaryTheme ──────────────────────────────────────────────────────────
@freeze_time("2026-05-15")
def test_anniversary_trouve_photos_annees_passees():
    idx = _index(
        _photo(1, 2025, 5, 15),  # 1 an avant → doit être sélectionné
        _photo(2, 2024, 5, 15),  # 2 ans avant → doit être sélectionné
        _photo(3, 2020, 1,  1),  # mauvaise date → ne doit pas apparaître
    )
    result = AnniversaryTheme().select(
        idx, datetime.date.today(), count=30, years_back=[1, 2]
    )
    ids = {p["id"] for p in result.photos}
    assert 1 in ids,  "Photo d'il y a 1 an manquante"
    assert 2 in ids,  "Photo d'il y a 2 ans manquante"
    assert 3 not in ids, "Photo du 1er janvier ne devrait pas apparaître"


@freeze_time("2026-05-15")
def test_anniversary_elargit_fenetre():
    # Photos uniquement le 13 mai 2025 (±2 j de May 15 → hors ±1 j mais dans ±3 j)
    idx = _index(*[_photo(i, 2025, 5, 13) for i in range(10)])
    result = AnniversaryTheme().select(
        idx, datetime.date.today(), count=5, years_back=[1]
    )
    assert not result.is_empty(), "Doit trouver des photos après élargissement à ±3 j"


@freeze_time("2026-05-15")
def test_anniversary_vide_si_aucune_photo_correspondante():
    idx = _index(_photo(1, 2020, 1, 1))  # rien autour du 15 mai
    result = AnniversaryTheme().select(
        idx, datetime.date.today(), count=30, years_back=[1]
    )
    assert result.is_empty(), "Doit retourner vide si aucune correspondance"


@freeze_time("2026-05-15")
def test_anniversary_label_une_seule_annee():
    idx = _index(*[_photo(i, 2025, 5, 15) for i in range(15)])
    result = AnniversaryTheme().select(
        idx, datetime.date.today(), count=10, years_back=[1]
    )
    assert not result.is_empty()
    assert "il y a" in result.label.lower()
    assert "1 an" in result.label.lower()


@freeze_time("2026-05-15")
def test_anniversary_label_plusieurs_annees():
    idx = _index(
        *[_photo(i,    2025, 5, 15) for i in range(10)],
        *[_photo(i+10, 2023, 5, 15) for i in range(10)],
    )
    result = AnniversaryTheme().select(
        idx, datetime.date.today(), count=20, years_back=[1, 3]
    )
    assert not result.is_empty()
    # Avec plusieurs années le label mentionne la date
    label = result.label.lower()
    assert "mai" in label or "souvenirs" in label


@freeze_time("2026-05-15")
def test_anniversary_photos_triees_par_date():
    idx = _index(
        _photo(1, 2025, 5, 15),
        _photo(2, 2023, 5, 15),
        _photo(3, 2021, 5, 15),
    )
    result = AnniversaryTheme().select(
        idx, datetime.date.today(), count=30, years_back=[1, 3, 5]
    )
    dates = [p["date_taken"] for p in result.photos]
    assert dates == sorted(dates), "Les photos doivent être triées par date"


# ── SeasonTheme ───────────────────────────────────────────────────────────────
@freeze_time("2026-05-15")  # mai → Printemps
def test_season_filtre_par_mois_courant():
    idx = _index(
        _photo(1, 2024, 5, 10),  # mai → inclus
        _photo(2, 2023, 5, 20),  # mai → inclus
        _photo(3, 2024, 8,  1),  # août → exclus
    )
    result = SeasonTheme().select(idx, datetime.date.today(), count=30)
    ids = {p["id"] for p in result.photos}
    assert 1 in ids and 2 in ids, "Les photos de mai doivent être incluses"
    assert 3 not in ids, "Les photos d'août ne doivent pas apparaître"


@freeze_time("2026-07-01")  # juillet → Été
def test_season_label_ete():
    idx = _index(*[_photo(i, 2024, 7, i % 28 + 1) for i in range(30)])
    result = SeasonTheme().select(idx, datetime.date.today(), count=30)
    assert result.label == "Été"


@freeze_time("2026-12-21")  # décembre → Hiver
def test_season_label_hiver():
    idx = _index(*[_photo(i, 2024, 12, i % 28 + 1) for i in range(30)])
    result = SeasonTheme().select(idx, datetime.date.today(), count=30)
    assert result.label == "Hiver"


# ── RandomTheme ───────────────────────────────────────────────────────────────
def test_random_renvoie_exactement_n_photos():
    idx = _index(*[_photo(i, 2024, 1, 1) for i in range(100)])
    result = RandomTheme().select(idx, count=30)
    assert len(result.photos) == 30


def test_random_ne_depasse_pas_le_stock():
    idx = _index(*[_photo(i, 2024, 1, 1) for i in range(10)])
    result = RandomTheme().select(idx, count=30)
    assert len(result.photos) == 10


def test_random_label():
    idx = _index(*[_photo(i, 2024, 1, 1) for i in range(5)])
    result = RandomTheme().select(idx, count=5)
    assert result.label == "Sélection du jour"


# ── Rotation ──────────────────────────────────────────────────────────────────
def test_rotation_deterministe():
    rotation = ["anniversary", "season", "random"]
    d = datetime.date(2026, 5, 15)
    assert theme_of_day(d, rotation) == theme_of_day(d, rotation)


def test_rotation_couvre_tous_les_themes():
    rotation = ["anniversary", "season", "random"]
    vus = set()
    for offset in range(3):
        d = datetime.date(2026, 1, 1) + datetime.timedelta(days=offset)
        vus.add(theme_of_day(d, rotation))
    assert vus == set(rotation), "Chaque thème doit apparaître exactement une fois sur 3 jours"


def test_rotation_jour_connu():
    rotation = ["anniversary", "season", "random"]
    # 15 mai 2026 = jour 135 → 135 % 3 = 0 → "anniversary"
    d = datetime.date(2026, 5, 15)
    assert d.timetuple().tm_yday == 135
    assert theme_of_day(d, rotation) == "anniversary"


# ── Fallback RandomTheme ──────────────────────────────────────────────────────
def test_select_for_day_repli_sur_random_si_vide():
    """
    Si le thème principal (anniversary) ne trouve rien,
    select_for_day doit utiliser RandomTheme et le signaler dans le label.
    """
    rotation = ["anniversary", "season", "random"]
    # Trouver le premier jour 2026 où le thème est "anniversary"
    anniv_day = next(
        datetime.date(2026, 1, 1) + datetime.timedelta(days=i)
        for i in range(365)
        if theme_of_day(
            datetime.date(2026, 1, 1) + datetime.timedelta(days=i), rotation
        ) == "anniversary"
    )
    # Index : 30 photos en juin uniquement → aucun anniversaire en janvier
    idx = _index(*[_photo(i, 2025, 6, 15) for i in range(30)])
    cfg = _config(rotation="anniversary,season,random", years_back="1,2")

    result = select_for_day(idx, cfg, today=anniv_day)

    assert not result.is_empty(), "Le repli sur random doit produire des photos"
    assert "repli" in result.label.lower(), "Le label doit signaler le repli automatique"
    assert result.theme_name == "random"
