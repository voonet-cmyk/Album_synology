"""Tests unitaires pour la logique de cache et de filtrage des photos."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import photos as photos_module


def test_load_cache_retourne_liste_vide_si_absent(tmp_path):
    """Pas de crash si le fichier cache n'existe pas encore."""
    photos_module.CACHE_FILE = tmp_path / "index.json"
    assert photos_module.load_cache() == []


def test_save_puis_load_cache(tmp_path):
    """Les données sauvegardées doivent être identiques à celles chargées."""
    photos_module.CACHE_FILE = tmp_path / "index.json"
    donnees = [{"item_id": 1, "filename": "test.jpg"}]
    photos_module.save_cache(donnees)
    assert photos_module.load_cache() == donnees


# TODO : ajouter des tests de filtrage par date/saison une fois photos.py complété
