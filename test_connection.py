"""
Script de test de connexion ET d'indexation.
Lance ce script pour vérifier que tout fonctionne avant de déployer sur le NAS.

Usage :
    python test_connection.py              # connexion + index (utilise le cache si frais)
    python test_connection.py --rebuild    # force la reconstruction de l'index
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config_loader import load_config
from logger import setup_logger
from photo_index import PhotoIndex
from synology_client import AuthenticationError, SynologyAPIError, SynologyPhotosClient


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--rebuild", action="store_true",
        help="Force la reconstruction complète de l'index des photos",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        print(f"\nERREUR de configuration : {exc}")
        return 1

    setup_logger(level=config["logs"]["level"], retention_days=config["logs"]["retention_days"])

    print()
    print("=" * 55)
    print("  TEST — Synology Photos (DRY-RUN)")
    print("=" * 55)
    print(f"  NAS    : {config['synology']['host']}")
    print(f"  Compte : {config['synology']['username']}")
    print("=" * 55)

    try:
        with SynologyPhotosClient(config, dry_run=True) as client:

            # ── Étape 1 : connexion de base ───────────────────────────────
            print("\n[1/3] Comptage rapide des photos…")
            total = client.count_items()
            print(f"      → {total} photo(s) dans l'espace partagé")

            print("\n[2/3] Dossiers racine…")
            folders = client.list_folders()
            if not folders:
                print("      → Aucun dossier trouvé")
            else:
                print(f"      → {len(folders)} dossier(s), voici les 3 premiers :")
                for f in folders[:3]:
                    print(f"         • [{f.get('id', '?'):>6}]  {f.get('name', '(sans nom)')}")

            # ── Étape 2 : index ───────────────────────────────────────────
            print("\n[3/3] Index des photos…")
            if args.rebuild:
                print("      (reconstruction forcée — peut prendre plusieurs minutes)")
            else:
                print("      (utilise le cache si disponible et frais)")

            index = PhotoIndex.from_config(config)
            index.load(client, force_rebuild=args.rebuild)

            print(f"\n      → {index.count} photos dans l'index")

            # Quelques stats rapides sur les saisons
            for season, label in [
                ("spring", "Printemps"), ("summer", "Été"),
                ("autumn", "Automne"),  ("winter", "Hiver"),
            ]:
                n = len(index.filter_by_season(season))
                print(f"         {label:<12} {n:>6} photos")

            # Exemple : photos du jour/mois d'aujourd'hui (toutes années)
            import datetime
            today = datetime.date.today()
            anniversaire = index.filter_by_date(month=today.month, day=today.day)
            print(f"\n      → Thème anniversaire (aujourd'hui {today:%d/%m}) : "
                  f"{len(anniversaire)} photo(s) disponible(s)")

            sample = index.random_sample(5, pool=anniversaire or None)
            if sample:
                print("        Exemple de sélection (5 aléatoires) :")
                for p in sample:
                    ts   = p.get("date_taken", 0)
                    date = datetime.date.fromtimestamp(ts).isoformat() if ts else "?"
                    print(f"          [{p.get('id'):>6}]  {p.get('name', '?'):<35}  {date}")

    except AuthenticationError as exc:
        print(f"\nERREUR d'authentification : {exc}")
        return 1
    except SynologyAPIError as exc:
        print(f"\nERREUR API Synology : {exc}")
        print("Consulte logs/album.log pour le détail")
        return 1
    except Exception as exc:
        print(f"\nERREUR inattendue : {exc}")
        import traceback; traceback.print_exc()
        return 1

    print()
    print("=" * 55)
    print("  TOUT EST OK — prêt pour la phase suivante")
    print("=" * 55)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
