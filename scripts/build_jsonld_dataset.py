#!/usr/bin/env python3
"""Injecte le balisage JSON-LD schema.org/Dataset : sondages sur donnees.html, cotes sur index.html."""

import json, pathlib, datetime, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

MARKER = "<!-- BUILD:jsonld-dataset -->"


def compute_dataset():
    sondages = json.loads((ROOT / "data" / "sondages.json").read_text())
    dates = [s["terrain_fin"] for s in sondages]
    first = min(dates)
    last = max(dates)
    today = datetime.date.today().isoformat()

    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "Sondages de l\u2019\u00e9lection pr\u00e9sidentielle fran\u00e7aise 2027",
        "description": "Agr\u00e9gation des sondages d\u2019intention de vote pour la pr\u00e9sidentielle 2027, "
                        "premier et second tour, collect\u00e9s automatiquement depuis Wikip\u00e9dia.",
        "url": "https://sondax.fr/donnees.html",
        "license": "https://creativecommons.org/licenses/by-sa/4.0/",
        "isBasedOn": {
            "@type": "CreativeWork",
            "name": "Liste de sondages sur l\u2019\u00e9lection pr\u00e9sidentielle fran\u00e7aise de 2027",
            "url": "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027",
        },
        "creator": {
            "@type": "Organization",
            "name": "Sondax",
            "url": "https://sondax.fr",
        },
        "temporalCoverage": f"{first}/{last}",
        "dateModified": today,
        "distribution": [
            {
                "@type": "DataDownload",
                "contentUrl": "https://sondax.fr/donnees/sondages-presidentielle-2027.csv",
                "encodingFormat": "text/csv",
                "name": "Sondages présidentielle 2027 (CSV)",
            },
        ],
    }


def compute_dataset_polymarket():
    """Second jeu de données, distinct : cotes Polymarket.

    Pas de propriété license : les cotes relèvent des conditions d'utilisation de
    Polymarket, pas de la CC BY-SA des sondages. Ne jamais les fusionner avec
    le jeu de données des sondages.
    """
    pm = json.loads((ROOT / "data" / "polymarket.json").read_text())
    dates = [h["d"] for m in pm["marches"].values()
             for c in m["candidats"].values() for h in c.get("historique", [])]
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "Cotes Polymarket de l\u2019\u00e9lection pr\u00e9sidentielle fran\u00e7aise 2027",
        "description": "Probabilit\u00e9s implicites issues des march\u00e9s de pr\u00e9diction Polymarket "
                       "pour la pr\u00e9sidentielle 2027 : victoire et acc\u00e8s au second tour, "
                       "par candidat, historique quotidien. Ce sont des prix de march\u00e9, "
                       "pas des intentions de vote.",
        "url": "https://sondax.fr/#bloc-polymarket",
        "isBasedOn": {
            "@type": "CreativeWork",
            "name": "Polymarket",
            "url": "https://polymarket.com",
        },
        "creator": {
            "@type": "Organization",
            "name": "Sondax",
            "url": "https://sondax.fr",
        },
        "temporalCoverage": f"{min(dates)}/{max(dates)}",
        "dateModified": pm["maj"][:10],
        "distribution": [
            {
                "@type": "DataDownload",
                "contentUrl": "https://sondax.fr/data/polymarket.json",
                "encodingFormat": "application/json",
                "name": "Cotes Polymarket (JSON)",
            },
        ],
    }


def main():
    """Deux jeux de données, deux pages.

    - Sondages (CC BY-SA) : sur donnees.html uniquement.
    - Cotes Polymarket (sans licence déclarée) : sur index.html, où elles s'affichent.
    Chaque balise porte un id, ce qui rend l'injection idempotente.
    """
    ancien = re.compile(  # balises sans id des versions précédentes
        r'<script type="application/ld\+json">\{"@context":\s*"https://schema\.org",'
        r'\s*"@type":\s*"Dataset".*?</script>\n?', re.S)

    def tag(ident, data):
        return (f'<script type="application/ld+json" id="{ident}">'
                f'{json.dumps(data, ensure_ascii=False)}</script>')

    def poser(name, ident, data):
        path = SITE / name
        content = path.read_text(encoding="utf-8")
        content = ancien.sub("", content).replace(MARKER + "\n", "").replace(MARKER, "")
        propre = re.compile(rf'<script type="application/ld\+json" id="{ident}">.*?</script>', re.S)
        if propre.search(content):
            content = propre.sub(lambda _: tag(ident, data), content)
        else:
            content = content.replace("</head>", tag(ident, data) + "\n</head>", 1)
        path.write_text(content, encoding="utf-8")
        print(f"  OK  {ident} -> {name}")

    # sondages.html ne porte plus de balisage Dataset
    path = SITE / "sondages.html"
    content = path.read_text(encoding="utf-8")
    nouveau = ancien.sub("", content).replace(MARKER + "\n", "").replace(MARKER, "")
    if nouveau != content:
        path.write_text(nouveau, encoding="utf-8")

    poser("donnees.html", "jsonld-dataset-sondages", compute_dataset())
    poser("index.html", "jsonld-dataset-polymarket", compute_dataset_polymarket())


if __name__ == "__main__":
    main()
