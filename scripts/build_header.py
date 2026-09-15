"""Génère site/assets/header-data.js à partir des données de sondages.

Utilisé au build pour fournir au bandeau d'en-tête les données du dernier
sondage, de l'hypothèse sélectionnée et des statistiques agrégées.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "assets" / "header-data.js"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def select_hypothesis(sondage, candidats):
    """Sélectionne la meilleure hypothèse T1 selon la règle du bandeau (SPEC §4).

    1. Plus de candidats déclarés (declare_le <= terrain_fin)
    2. Échantillon le plus grand
    3. Première dans l'ordre du fichier
    """
    terrain_fin = sondage["terrain_fin"]
    t1 = [h for h in sondage["hypotheses"] if h.get("tour") == 1]
    if not t1:
        return None

    def count_declared(hyp):
        count = 0
        for cid in hyp.get("candidats", list(hyp.get("scores", {}).keys())):
            c = candidats.get(cid)
            if not c:
                continue
            dl = c.get("declare_le")
            if dl and dl <= terrain_fin:
                count += 1
        return count

    def echantillon(hyp):
        e = hyp.get("echantillon")
        if e is not None:
            return e
        return sondage.get("echantillon") or 0

    def sort_key(hyp):
        return (-count_declared(hyp), -echantillon(hyp))

    t1.sort(key=sort_key)
    return t1[0]


def format_date_fr(iso_date):
    """'2026-09-03' → 'terrain 3 septembre 2026'"""
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    y, m, d = iso_date.split("-")
    return f"terrain {int(d)} {mois[int(m) - 1]} {y}"


def format_date_mobile(iso_date):
    """'2026-09-03' → '3 septembre'"""
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    _, m, d = iso_date.split("-")
    return f"{int(d)} {mois[int(m) - 1]}"


def candidate_full_name(cid, candidats):
    """Nom complet (prénom + nom) du candidat depuis le référentiel."""
    c = candidats.get(cid, {})
    prenom = c.get("prenom", "")
    nom = c.get("nom", cid)
    if prenom:
        return f"{prenom} {nom}"
    return nom


def build_hyp_label(hyp, candidats):
    """Construit le libellé 'hyp. Attal / Le Pen / Glucksmann' pour le h2.

    Utilise les noms courts (nom seul) pour la lisibilité du titre.
    """
    scores = hyp.get("scores", {})
    sorted_cands = sorted(
        ((cid, s) for cid, s in scores.items() if cid != "autre"),
        key=lambda x: -x[1],
    )
    names = [candidats.get(cid, {}).get("nom", cid) for cid, _ in sorted_cands[:3]]
    return " / ".join(names)


def main():
    candidats = load_json(DATA / "candidats.json")
    sondages = load_json(DATA / "sondages.json")

    # Charger les sondages manuels s'ils existent
    manuels_path = DATA / "sondages_manuels.json"
    if manuels_path.exists():
        sondages_manuels = load_json(manuels_path)
        sondages = sondages + sondages_manuels

    if not sondages:
        print("Aucun sondage trouvé.")
        return

    # Sondage le plus récent par terrain_fin
    latest = max(sondages, key=lambda s: s["terrain_fin"])

    # Sélection de l'hypothèse
    hyp = select_hypothesis(latest, candidats)
    if not hyp:
        print(f"Pas d'hypothèse T1 pour {latest['id']}")
        return

    # Top 4 candidats, ordre décroissant, "autre" exclu
    scores = hyp.get("scores", {})
    top4 = sorted(
        ((cid, s) for cid, s in scores.items() if cid != "autre"),
        key=lambda x: -x[1],
    )[:4]

    # Formater les scores
    candidates_data = []
    for cid, score in top4:
        formatted = f"{score:.1f}".replace(".", ",")
        # Séparer partie entière et décimale pour l'affichage
        candidates_data.append({
            "name": candidate_full_name(cid, candidats),
            "score": formatted,
        })

    # Statistiques
    poll_count = len(sondages)
    institutes = set(s["institut"] for s in sondages)
    institute_count = len(institutes)

    # Libellé de l'hypothèse
    hyp_label = build_hyp_label(hyp, candidats)

    # Données pour le bandeau
    header_data = {
        "institut": latest["institut"],
        "terrainFin": latest["terrain_fin"],
        "terrainLabel": format_date_fr(latest["terrain_fin"]),
        "terrainLabelMobile": format_date_mobile(latest["terrain_fin"]),
        "hypLabel": hyp_label,
        "sondageId": latest["id"],
        "candidates": candidates_data,
        "pollCount": poll_count,
        "instituteCount": institute_count,
    }

    # Écrire le fichier JS
    js = "// Généré par scripts/build_header.py — ne pas modifier à la main\n"
    js += "window.HEADER_DATA = " + json.dumps(header_data, ensure_ascii=False, indent=2) + ";\n"

    os.makedirs(OUT.parent, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"header-data.js écrit : {latest['institut']} {latest['terrain_fin']}, "
          f"{poll_count} sondages, {institute_count} instituts")


if __name__ == "__main__":
    main()
