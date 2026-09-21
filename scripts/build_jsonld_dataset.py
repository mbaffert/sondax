#!/usr/bin/env python3
"""Injecte le balisage JSON-LD schema.org/Dataset dans donnees.html."""

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


def main():
    """Le balisage Dataset vit sur la seule page Données.

    Les anciennes versions l'injectaient aussi dans index.html et sondages.html,
    où il restait figé (la regex de remplacement ne correspondait pas). On l'y retire.
    """
    dataset = compute_dataset()
    script_tag = f'<script type="application/ld+json">{json.dumps(dataset, ensure_ascii=False)}</script>'
    pattern = re.compile(
        r'<script type="application/ld\+json">\{"@context":\s*"https://schema\.org",'
        r'\s*"@type":\s*"Dataset".*?</script>\n?', re.S)

    for name in ["index.html", "sondages.html"]:
        path = SITE / name
        if path.exists():
            content = path.read_text(encoding="utf-8")
            nouveau = pattern.sub("", content).replace(MARKER + "\n", "").replace(MARKER, "")
            if nouveau != content:
                path.write_text(nouveau, encoding="utf-8")
                print(f"  retiré  {name}")

    path = SITE / "donnees.html"
    content = path.read_text(encoding="utf-8")
    if MARKER in content:
        content = content.replace(MARKER, script_tag)
    else:
        content = pattern.sub(script_tag + "\n", content)
    path.write_text(content, encoding="utf-8")
    print("JSON-LD Dataset injecté dans donnees.html")


if __name__ == "__main__":
    main()
