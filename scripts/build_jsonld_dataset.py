#!/usr/bin/env python3
"""Injecte le balisage JSON-LD schema.org/Dataset dans index.html et sondages.html."""

import json, pathlib, datetime

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
        "url": "https://sondax.fr/",
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
                "contentUrl": "https://sondax.fr/data/sondages.json",
                "encodingFormat": "application/json",
                "name": "Sondages (JSON)",
            },
            {
                "@type": "DataDownload",
                "contentUrl": "https://sondax.fr/data/polymarket.json",
                "encodingFormat": "application/json",
                "name": "Cotes Polymarket (JSON)",
            },
        ],
    }


def main():
    dataset = compute_dataset()
    script_tag = f'<script type="application/ld+json">{json.dumps(dataset, ensure_ascii=False)}</script>'

    import re
    count = 0
    for name in ["index.html", "sondages.html"]:
        path = SITE / name
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        modified = False
        if MARKER in content:
            content = content.replace(MARKER, script_tag)
            modified = True
        else:
            # Remplacer un tag existant (re-build)
            pattern = r'<script type="application/ld\+json">\{"@context":"https://schema\.org","@type":"Dataset".*?</script>'
            if re.search(pattern, content):
                content = re.sub(pattern, script_tag, content)
                modified = True
        if modified:
            path.write_text(content, encoding="utf-8")
            count += 1
            print(f"  OK  {name}")

    print(f"JSON-LD Dataset injecté dans {count} pages")


if __name__ == "__main__":
    main()
