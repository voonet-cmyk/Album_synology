#!/usr/bin/env bash
# =============================================================================
# install_on_dsm.sh — Installe "Album du jour" sur un NAS Synology (DSM 7+)
#
# Usage :
#   bash scripts/install_on_dsm.sh                     # installe dans le répertoire par défaut
#   bash scripts/install_on_dsm.sh /volume2/scripts/album  # chemin personnalisé
#
# Ce script doit être lancé DEPUIS LE RÉPERTOIRE RACINE DU PROJET :
#   cd /volume1/homes/YOUR_USER/download/AlbumPhotoAuto
#   bash scripts/install_on_dsm.sh
#
# Note sur les chemins : DSM File Station affiche "home/download/AlbumPhotoAuto"
# mais SSH utilise le chemin complet "/volume1/homes/YOUR_USER/download/AlbumPhotoAuto".
# =============================================================================

set -euo pipefail

# ── Paramètres ────────────────────────────────────────────────────────────────

DEST="${1:-/volume1/homes/${USER:-YOUR_USER}/Job/AlbumPhotoAuto}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON=""

# ── Couleurs pour le terminal ─────────────────────────────────────────────────

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"   # reset

ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
warn() { echo -e "${YELLOW}  ! $*${NC}"; }
err()  { echo -e "${RED}  ✗ $*${NC}"; exit 1; }

# ── Bannière ──────────────────────────────────────────────────────────────────

echo ""
echo "=================================================="
echo "  Installation — Album du jour (Synology Photos)"
echo "=================================================="
echo "  Source      : $PROJECT_DIR"
echo "  Destination : $DEST"
echo ""

# ── 1. Trouver Python 3 ───────────────────────────────────────────────────────

echo "[ 1/6 ] Recherche de Python 3..."

for candidate in python3 /usr/local/bin/python3 /var/packages/Python3/target/bin/python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" --version 2>&1)
        PYTHON="$candidate"
        ok "Python trouvé : $candidate ($version)"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3 introuvable. Installe-le depuis le Centre de paquets DSM (paquet 'Python 3')."
fi

# ── 2. Créer les répertoires ──────────────────────────────────────────────────

echo ""
echo "[ 2/6 ] Création des répertoires..."

mkdir -p "$DEST"
mkdir -p "$DEST/logs"
mkdir -p "$DEST/cache"
ok "Répertoires créés dans $DEST"

# ── 3. Copier les fichiers source ─────────────────────────────────────────────

echo ""
echo "[ 3/6 ] Copie des fichiers source..."

SOURCE_FILES=(
    album.py
    config_loader.py
    logger.py
    main.py
    photo_index.py
    synology_client.py
    themes.py
    requirements.txt
    config.example.yml
)

for f in "${SOURCE_FILES[@]}"; do
    src="$PROJECT_DIR/$f"
    if [ -f "$src" ]; then
        cp "$src" "$DEST/$f"
        ok "Copié : $f"
    else
        warn "Fichier absent (ignoré) : $f"
    fi
done

# ── 4. Créer config.yml si absent ─────────────────────────────────────────────

echo ""
echo "[ 4/6 ] Vérification de config.yml..."

if [ -f "$DEST/config.yml" ]; then
    warn "config.yml déjà présent — non écrasé (tes réglages sont conservés)."
else
    cp "$PROJECT_DIR/config.example.yml" "$DEST/config.yml"
    chmod 600 "$DEST/config.yml"
    ok "config.yml créé depuis config.example.yml"
    echo ""
    warn "IMPORTANT : ouvre $DEST/config.yml et remplis :"
    warn "  synology.host     → l'adresse IP de ton NAS"
    warn "  synology.username → le compte qui crée les albums (ex: script_user)"
    warn "  synology.password → son mot de passe"
fi

# ── 5. Créer l'environnement Python virtuel ───────────────────────────────────

echo ""
echo "[ 5/6 ] Création de l'environnement Python isolé..."

if [ -d "$DEST/.venv" ]; then
    warn "Environnement .venv déjà présent — réutilisé."
else
    "$PYTHON" -m venv "$DEST/.venv" || err "Impossible de créer le venv. Lance : $PYTHON -m ensurepip --upgrade"
    ok "Environnement créé : $DEST/.venv"
fi

echo ""
echo "[ 6/6 ] Installation des dépendances Python..."

"$DEST/.venv/bin/pip" install --quiet --upgrade pip
"$DEST/.venv/bin/pip" install --quiet requests
ok "Dépendances installées (requests)"

# ── Résumé ────────────────────────────────────────────────────────────────────

PYTHON_VENV="$DEST/.venv/bin/python"
MAIN="$DEST/main.py"
CONFIG="$DEST/config.yml"

echo ""
echo "=================================================="
echo -e "${GREEN}  Installation terminée !${NC}"
echo "=================================================="
echo ""
echo "  ÉTAPES SUIVANTES :"
echo ""
echo "  1. Remplis le fichier de configuration :"
echo "       nano $CONFIG"
echo ""
echo "  2. Teste sans rien modifier sur le NAS :"
echo "       $PYTHON_VENV $MAIN --dry-run --debug"
echo ""
echo "  3. Premier vrai lancement (crée les albums) :"
echo "       $PYTHON_VENV $MAIN --debug"
echo ""
echo "  4. Commande à coller dans le Planificateur DSM :"
echo "       $PYTHON_VENV $MAIN --config $CONFIG"
echo ""
echo "  5. Configure le partage des albums dans Synology Photos"
echo "     (une seule fois, manuellement)"
echo ""
