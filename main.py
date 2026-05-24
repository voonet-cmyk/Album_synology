"""
Point d'entree principal - lance chaque matin par le planificateur DSM.

Usage :
    python main.py                        # mode normal
    python main.py --dry-run --debug      # simulation sans rien creer
    python main.py --theme random         # force le theme aleatoire
    python main.py --rebuild-index        # reconstruit le cache des photos
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

# Permet d'importer les modules du projet depuis n'importe quel repertoire courant
sys.path.insert(0, str(Path(__file__).parent))

from album import build_daily_album
from config_loader import load_config
from logger import setup_logger
from photo_history import PhotoHistory
from photo_index import PhotoIndex
from synology_client import AuthenticationError, SynologyAPIError, SynologyPhotosClient
from themes import current_theme, select_for_day

# Libelles francais des themes pour le resume
_THEME_LABELS_FR = {
    "anniversary": "Anniversaire",
    "season":      "Saison / Mois courant",
    "random":      "Aleatoire",
}


# ── Ligne de commande ─────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cree l'album photo quotidien sur Synology Photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--config", default="config.yml", metavar="FICHIER",
        help="Chemin vers la configuration (defaut : config.yml)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Simule toutes les actions sans rien ecrire sur le NAS",
    )
    p.add_argument(
        "--rebuild-index", action="store_true",
        help="Reconstruit l'index des photos meme si le cache est frais",
    )
    p.add_argument(
        "--theme", choices=["anniversary", "season", "random"], metavar="NOM",
        help="Force un theme specifique (anniversary | season | random)",
    )
    p.add_argument(
        "--debug", action="store_true",
        help="Active les logs detailles (niveau DEBUG)",
    )
    return p.parse_args()


# ── Point d'entree ────────────────────────────────────────────────────────────
def main() -> int:
    args   = _parse_args()
    today  = datetime.date.today()

    # ── 1. Configuration ──────────────────────────────────────────────────────
    try:
        config = load_config(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        print(f"\nERREUR de configuration : {exc}", file=sys.stderr)
        return 1

    # ── 2. Logger ─────────────────────────────────────────────────────────────
    log_level = "DEBUG" if args.debug else config["logs"]["level"]
    log = setup_logger(level=log_level, retention_days=config["logs"]["retention_days"])

    log.info("=" * 50)
    log.info("Lancement - %s", today.strftime("%A %d %B %Y"))
    if args.dry_run:
        log.info("MODE DRY-RUN - aucune modification sur le NAS")

    # ── 3. Client Synology ────────────────────────────────────────────────────
    try:
        with SynologyPhotosClient(config, dry_run=args.dry_run) as client:

            # ── 4. Index des photos ───────────────────────────────────────────
            index = PhotoIndex.from_config(config)
            index.load(client, force_rebuild=args.rebuild_index)

            if index.count == 0:
                log.error("L'index est vide - aucune photo dans l'espace partage.")
                return 1

            log.info("Index pret : %d photos disponibles", index.count)

            # ── 5. Historique et exclusions ───────────────────────────────────
            history     = PhotoHistory()
            chosen      = current_theme(config, today, force=args.theme)
            no_repeat   = _no_repeat_days(config, chosen)
            exclude_ids = history.recent_ids(chosen, no_repeat)

            if exclude_ids:
                log.info(
                    "Non-repetition (%s) : %d photo(s) ecartee(s) (deja partagees dans les %d derniers jours)",
                    chosen, len(exclude_ids), no_repeat,
                )

            # ── 6. Selection du theme ─────────────────────────────────────────
            theme_result = select_for_day(
                index, config, today=today, force_theme=args.theme,
                exclude_ids=exclude_ids,
            )

            if theme_result.is_empty():
                log.error(
                    "Aucune photo selectionnee - verifiez la bibliotheque et la config."
                )
                return 1

            # ── 7. Mise a jour de l'album ─────────────────────────────────────
            album_name = build_daily_album(client, theme_result, config)

            # ── 8. Enregistrement dans l'historique ───────────────────────────
            if not args.dry_run:
                history.record(theme_result.theme_name, today, theme_result.item_ids)
                history.save(max_days=_max_no_repeat_days(config))
                log.info(
                    "Historique mis a jour : %d photo(s) enregistrees pour '%s'",
                    len(theme_result.item_ids), theme_result.theme_name,
                )

    except AuthenticationError as exc:
        log.error("Erreur d'authentification : %s", exc)
        return 1
    except SynologyAPIError as exc:
        log.error("Erreur API Synology : %s", exc)
        return 1
    except Exception as exc:
        log.exception("Erreur inattendue : %s", exc)
        return 1

    # ── 7. Resume final ───────────────────────────────────────────────────────
    _print_summary(config, theme_result, album_name, today, dry_run=args.dry_run)
    return 0


def _print_summary(config, theme_result, album_name, today, dry_run):
    """Affiche le recapitulatif final."""
    label_fr = _THEME_LABELS_FR.get(theme_result.theme_name, theme_result.theme_name)
    n_photos = len(theme_result.photos)

    sep = "=" * 54
    print(f"\n{sep}")
    if dry_run:
        print("  SIMULATION TERMINEE  (aucune modification sur le NAS)")
    else:
        print("  ALBUM MIS A JOUR")
    print(sep)
    print(f"  Album    : {album_name}")
    print(f"  Theme    : {label_fr}")
    if "repli" in theme_result.label:
        print("  /!\\ Repli automatique (theme original sans resultat)")
    if dry_run:
        print(f"  Photos   : {n_photos} selectionnees (non publiees)")
    else:
        print(f"  Photos   : {n_photos}")
    print(sep)
    print()


def _no_repeat_days(config: dict, theme: str) -> int:
    """Retourne la fenêtre de non-répétition (en jours) pour le thème donné."""
    themes_cfg = config.get("themes", {})
    return int(themes_cfg.get(f"no_repeat_days_{theme}", 30))


def _max_no_repeat_days(config: dict) -> int:
    """Retourne la plus grande fenêtre configurée (pour dimensionner la purge)."""
    themes_cfg = config.get("themes", {})
    values = [
        int(themes_cfg.get(f"no_repeat_days_{t}", 30))
        for t in ("anniversary", "season", "random")
    ]
    return max(values)


if __name__ == "__main__":
    sys.exit(main())
