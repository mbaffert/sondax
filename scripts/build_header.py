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


# ---------------------------------------------------------------------------
# Repères factuels — textes en dur, regroupés ici (un seul endroit).
# Ces textes sont datés et devront être révisés :
# - à la publication du décret de convocation des électeurs ;
# - à la clôture des parrainages (12 mars 2027) ;
# - le jour du premier tour (18 avril 2027).
# Le booléen `officielles` de config.json ne sert plus à distinguer
# l'hypothèse du fait (les dates sont confirmées) mais à basculer la
# formulation si elles devaient changer.
# ---------------------------------------------------------------------------

REPERES_T1 = (
    'Le premier tour de l\u2019élection présidentielle se tient le dimanche '
    '18\u00a0avril\u00a02027. Les deux candidats arrivés en tête s\u2019affrontent '
    'au second tour, sauf si l\u2019un obtient la majorité absolue des suffrages '
    'exprimés dès le premier tour \u2014 ce qui n\u2019est jamais arrivé sous la '
    'V\u1d49\u00a0République. La liste officielle des candidats ne sera connue '
    'qu\u2019après la clôture des parrainages, le 12\u00a0mars\u00a02027\u00a0: '
    'les instituts testent d\u2019ici là des hypothèses de candidatures, qui '
    'varient d\u2019un sondage à l\u2019autre.'
)

REPERES_T2 = (
    'Le second tour se tient le dimanche 2\u00a0mai\u00a02027. Est élu le '
    'candidat qui obtient le plus de voix parmi les suffrages exprimés, les '
    'votes blancs et nuls étant décomptés à part et sans effet sur le résultat.'
)

JSONLD_T1 = {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Élection présidentielle française 2027 \u2014 premier tour",
    "startDate": "2027-04-18",
    "location": {"@type": "Country", "name": "France"},
}

JSONLD_T2 = {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Élection présidentielle française 2027 \u2014 second tour",
    "startDate": "2027-05-02",
    "location": {"@type": "Country", "name": "France"},
}


def select_hypothesis(sondage, candidats):
    """Sélectionne l'hypothèse T1 principale (SPEC §4).

    Utilise le champ "principale": true posé par principale.py.
    Fallback sur la première hypothèse T1 si aucune n'est marquée.
    """
    t1 = [h for h in sondage["hypotheses"] if h.get("tour") == 1]
    if not t1:
        return None

    # Chercher l'hypothèse marquée principale
    for h in t1:
        if h.get("principale"):
            return h

    # Fallback : première hypothèse T1
    return t1[0]


def format_date_fr(iso_date):
    """'2026-09-03' → '3 septembre 2026'"""
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    y, m, d = iso_date.split("-")
    return f"{int(d)} {mois[int(m) - 1]} {y}"


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


def build_hyp_distinctive_label(hyp, all_t1, candidats):
    """Construit le libellé distinctif pour le lien 'Voir le détail'.

    Identifie les candidats qui distinguent cette hypothèse des autres T1
    du même sondage. S'il n'y a qu'une hypothèse, retourne None.
    """
    if len(all_t1) <= 1:
        return None

    # Candidats communs à toutes les hypothèses T1
    sets = [set(h.get("scores", {}).keys()) - {"autre"} for h in all_t1]
    common = set(sets[0])
    for s in sets[1:]:
        common &= s

    # Candidats distinctifs de cette hypothèse (présents ici, pas partout)
    mine = set(hyp.get("scores", {}).keys()) - {"autre"}
    distinctive = mine - common

    if not distinctive:
        return None

    # Trier par score décroissant, noms courts
    scores = hyp.get("scores", {})
    sorted_dist = sorted(distinctive, key=lambda c: -scores.get(c, 0))
    names = [candidats.get(cid, {}).get("nom", cid) for cid in sorted_dist]
    return " / ".join(names)


def select_latest_sondage(sondages):
    """Sélectionne le dernier sondage publié.

    Règle de départage (SPEC §4) :
    1. terrain_fin la plus récente
    2. en cas d'égalité, le plus grand echantillon total
    3. en cas d'égalité encore, l'ordre d'apparition dans sondages.json
    """
    if not sondages:
        return None
    # enumerate pour conserver l'ordre du fichier comme critère final
    return max(
        enumerate(sondages),
        key=lambda t: (t[1]["terrain_fin"], t[1].get("echantillon") or 0, -t[0]),
    )[1]


def load_all_sondages():
    """Charge sondages.json (contient déjà les manuels, fusionnés par le collecteur)."""
    return load_json(DATA / "sondages.json")


def main():
    sondages = load_all_sondages()

    if not sondages:
        print("Aucun sondage trouvé.")
        return

    # Statistiques
    poll_count = len(sondages)
    institutes = set(s["institut"] for s in sondages)
    institute_count = len(institutes)

    # Dates de l'élection depuis config.json
    config_path = DATA / "config.json"
    config = load_json(config_path) if config_path.exists() else {}
    election = config.get("election", {})

    # Données pour le bandeau
    header_data = {
        "pollCount": poll_count,
        "instituteCount": institute_count,
        "electionDates": {
            "premierTour": election.get("premier_tour", "2027-04-18"),
            "secondTour": election.get("second_tour", "2027-05-02"),
        },
    }

    # Écrire le fichier JS
    js = "// Généré par scripts/build_header.py — ne pas modifier à la main\n"
    js += "window.HEADER_DATA = " + json.dumps(header_data, ensure_ascii=False, indent=2) + ";\n"

    os.makedirs(OUT.parent, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"header-data.js écrit : {poll_count} sondages, {institute_count} instituts")


if __name__ == "__main__":
    main()
