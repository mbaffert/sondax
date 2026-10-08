"""Lecture de data/sondages.json : point d'entrée unique pour les consommateurs.

data/sondages.json est la référence de Sondax. Un sondage n'en est jamais
supprimé automatiquement : une suppression volontaire passe par le champ
`retire` (avec `retire_motif` et `retire_le`). Une entrée retirée reste dans le
fichier mais est exclue de tous les calculs et de toutes les pages.
"""

import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SONDAGES_PATH = ROOT / "data" / "sondages.json"


def est_retire(sondage):
    return bool(sondage.get("retire"))


def actifs(sondages):
    """Sondages non retirés, dans l'ordre d'origine."""
    return [s for s in sondages if not est_retire(s)]


def charger_tous(path=SONDAGES_PATH):
    """Contenu brut du fichier, retirés compris (collecte, validation)."""
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def charger(path=SONDAGES_PATH):
    """Sondages actifs : à utiliser pour tout calcul ou page."""
    return actifs(charger_tous(path))
