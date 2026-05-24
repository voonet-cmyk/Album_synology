"""
Chargeur de config.yml minimal — aucune dépendance externe (pas de PyYAML).
Supporte uniquement le sous-ensemble YAML utilisé dans ce projet :
  - 2 niveaux d'imbrication (section: puis   clé: valeur)
  - Valeurs scalaires : chaînes (avec ou sans guillemets), entiers, booléens
  - Commentaires sur ligne entière (# ...) — pas de commentaires en fin de ligne
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CONFIG_FILE = Path(__file__).parent / "config.yml"


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    """
    Charge config.yml et retourne un dict Python.
    Lève FileNotFoundError si le fichier n'existe pas.
    Lève ValueError si un champ obligatoire est absent.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier de configuration introuvable : {path}\n"
            "Copie config.example.yml en config.yml et remplis tes identifiants."
        )

    data: dict[str, Any] = {}
    section: str | None  = None

    with path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip()
            stripped = line.lstrip()

            # Ligne vide ou commentaire
            if not stripped or stripped.startswith("#"):
                continue

            if not line[0].isspace():
                # En-tête de section  ex: "synology:"
                section = stripped.rstrip(":")
                data[section] = {}
            elif section is not None:
                # Clé-valeur indentée  ex: "  host: \"valeur\""
                if ":" not in stripped:
                    continue
                key, _, raw_val = stripped.partition(":")
                key = key.strip()
                val: Any = raw_val.strip()

                # Retirer les guillemets simples ou doubles
                if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
                    val = val[1:-1]
                elif val == "":
                    continue
                else:
                    # Supprimer les commentaires en fin de ligne pour les valeurs non quotées
                    # ex: "24  # texte" → "24"  (ne touche pas aux valeurs entre guillemets)
                    for marker in ("  #", " #", "\t#"):
                        pos = val.find(marker)
                        if pos > 0:
                            val = val[:pos].strip()
                            break

                # Conversion de type
                if isinstance(val, str):
                    if val.lstrip("-").isdigit():
                        val = int(val)
                    elif val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False

                data[section][key] = val

    _validate(data, path)
    return data


def _validate(cfg: dict, path: Path) -> None:
    """Vérifie que les champs obligatoires sont présents et non vides."""
    required = {
        "synology": ["host", "username", "password", "port"],
        "album":    ["name_prefix", "photo_count"],
        "logs":     ["retention_days", "level"],
        "cache":    ["max_age_hours", "force_refresh"],
        "themes":   ["rotation"],
    }
    placeholders = {"TON_LOGIN", "TON_MOT_DE_PASSE", "ton_login", "ton_mot_de_passe"}

    for section, keys in required.items():
        if section not in cfg:
            raise ValueError(f"[{path.name}] Section manquante : [{section}]")
        for key in keys:
            if key not in cfg[section]:
                raise ValueError(f"[{path.name}] Clé manquante : {section}.{key}")
            val = cfg[section][key]
            if isinstance(val, str) and val in placeholders:
                raise ValueError(
                    f"[{path.name}] La valeur de {section}.{key} n'a pas été remplie.\n"
                    "Ouvre config.yml et remplace les valeurs exemple par tes vrais identifiants."
                )
