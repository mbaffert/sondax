#!/usr/bin/env python3
"""Publie les données Search Console sous forme de JSON servi par le site.

Lit les CSV produits par scripts/collecte_gsc.py et écrit site/donnees/gsc.json,
consommé par le relevé quotidien du tableau de bord « Sondax — audience et
référencement ». Voir claude/contrat-gsc-json.md dans le projet Claude.

Les CSV croisent toutes les dimensions avec la date. Ici, les journées passent
telles quelles ; requêtes, pages et appareils sont agrégés sur toute la période.

Aucune authentification : ce script ne lit que des fichiers déjà collectés.
"""

import csv, datetime, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "gsc"
SORTIE = ROOT / "site" / "donnees" / "gsc.json"

SITE_URL = "sc-domain:sondax.fr"
METRIQUES = ["clicks", "impressions", "ctr", "position"]


def erreur(message):
    print(f"Erreur build_gsc_public : {message}", file=sys.stderr)
    sys.exit(1)


def absent(message):
    """Sort sans rien écrire, et SANS faire échouer le build.

    Les CSV de collecte_gsc.py ne sont pas forcément présents dans la copie
    de travail. Dans ce cas le site est déployé sans gsc.json : le tableau de
    bord gardera ses chiffres précédents, et c'est le relevé quotidien qui
    signalera l'absence. Un déploiement ne doit jamais échouer pour ça.
    """
    print(f"  gsc.json : non publié — {message}")
    sys.exit(0)


def lire(nom, dimensions):
    """Lit un CSV de collecte_gsc.py et vérifie son entête."""
    chemin = SOURCE_DIR / nom
    if not chemin.exists():
        absent(f"{chemin.relative_to(ROOT)} absent")
    entete_attendue = dimensions + METRIQUES
    with chemin.open(newline="", encoding="utf-8") as f:
        lecteur = csv.reader(f)
        if next(lecteur, None) != entete_attendue:
            erreur(f"{nom} : entête inattendue, attendu {entete_attendue}")
        lignes = [l for l in lecteur if l]
    if not lignes:
        erreur(f"{nom} : aucune ligne")
    return lignes


def agreger(lignes, dimensions, cle_sortie):
    """Somme les clics et impressions par valeur de la 2e dimension.

    La position est une moyenne pondérée par les impressions. Ce n'est pas
    exactement le calcul de Google, qui repart de toutes les impressions
    individuelles, mais l'écart est négligeable et c'est la seule agrégation
    possible à partir de données déjà groupées par jour.
    """
    cumul = {}
    for l in lignes:
        valeur = l[1]
        clics, impressions = int(l[2]), int(l[3])
        position = float(l[5])
        e = cumul.setdefault(valeur, {"clics": 0, "impressions": 0, "pos_pond": 0.0})
        e["clics"] += clics
        e["impressions"] += impressions
        e["pos_pond"] += position * impressions
    sortie = []
    for valeur, e in cumul.items():
        impressions = e["impressions"]
        sortie.append({
            cle_sortie: valeur,
            "clics": e["clics"],
            "impressions": impressions,
            "position": round(e["pos_pond"] / impressions, 2) if impressions else 0.0,
        })
    sortie.sort(key=lambda r: -r["impressions"])
    return sortie


def main():
    jours = [
        {"date": l[0], "clics": int(l[1]), "impressions": int(l[2]),
         "position": round(float(l[4]), 2)}
        for l in lire("gsc-date.csv", ["date"])
    ]
    jours.sort(key=lambda r: r["date"])

    requetes = agreger(
        lire("gsc-date-query.csv", ["date", "query"]),
        ["date", "query"], "requete")
    pages = agreger(
        lire("gsc-date-page.csv", ["date", "page"]),
        ["date", "page"], "url")
    appareils = agreger(
        lire("gsc-date-device.csv", ["date", "device"]),
        ["date", "device"], "appareil")

    donnees = {
        "maj": datetime.date.today().isoformat(),
        "propriete": SITE_URL,
        "jours": jours,
        "requetes": requetes,
        "pages": pages,
        "appareils": appareils,
    }

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SORTIE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    tmp.replace(SORTIE)

    print(f"  gsc.json : {len(jours)} jours ({jours[0]['date']} → "
          f"{jours[-1]['date']}), {len(requetes)} requêtes, {len(pages)} pages, "
          f"{len(appareils)} appareils, {SORTIE.stat().st_size // 1024} Kio")


if __name__ == "__main__":
    main()
