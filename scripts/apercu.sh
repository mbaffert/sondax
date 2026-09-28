#!/usr/bin/env bash
# Aperçu local du site, sans toucher aux fichiers du dépôt.
#
# Copie le dépôt dans un dossier temporaire, y exécute les mêmes étapes de build
# que .github/workflows/pages.yml, assemble le site comme au déploiement et le
# sert sur http://localhost:8000 (port modifiable : scripts/apercu.sh 8080).
#
# Prérequis : Python 3.10+ ; numpy pour recalculer le modèle Sondax.
set -euo pipefail

PORT="${1:-8000}"
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Copie du dépôt dans $TMP"
tar -C "$RACINE" --exclude=.git --exclude=_site -cf - . | tar -C "$TMP" -xf -
cd "$TMP"

# Étapes de build, lues dans le workflow de déploiement
grep -E '^[[:space:]]+python scripts/[a-z_]+\.py[[:space:]]*$' .github/workflows/pages.yml | sed 's/^ *//' |
while read -r etape; do
  echo "→ $etape"
  ${etape/python /python3 } > /dev/null
done

# Modèle Sondax (phase A, hors déploiement) : nécessite numpy
if python3 -c "import numpy" 2>/dev/null; then
  for etape in calibration modele build_modele build_sitemap; do
    echo "→ python scripts/$etape.py"
    python3 "scripts/$etape.py" > /dev/null
  done
else
  echo "numpy absent (pip install -r requirements.txt) : modèle Sondax non recalculé"
fi

mkdir -p _site/data/derived
cp -r site/* _site/
cp data/*.json _site/data/
cp data/derived/*.json _site/data/derived/
rm -f _site/data/historique.json

echo
echo "Site servi sur http://localhost:$PORT/instituts.html  (Ctrl+C pour arrêter)"
cd _site && python3 -m http.server "$PORT"
