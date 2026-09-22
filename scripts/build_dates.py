#!/usr/bin/env python3
"""Injecte les dates de build dans le HTML de toutes les pages.

Remplace les marqueurs :
- <!-- BUILD:footer-dates --> dans le footer de toutes les pages

Données :
- Dernier sondage intégré : terrain_fin max de sondages.json
- Revid Wikipédia : revid max de sondages.json
- Date de vérification : date du build (aujourd'hui)
"""

import json, pathlib, datetime, glob as glob_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def date_lettres(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def compute_dates():
    sondages = json.loads((ROOT / "data" / "sondages.json").read_text())

    # Dernier sondage
    last_sondage = max(sondages, key=lambda s: s["terrain_fin"])
    last_date = last_sondage["terrain_fin"]

    # Dernier revid
    revids = [s.get("revid") for s in sondages if s.get("revid")]
    last_revid = max(revids) if revids else None

    # Date du build
    build_date = datetime.date.today().isoformat()

    return last_date, last_revid, build_date


def footer_html(last_date, last_revid, build_date):
    parts = [f"Dernier sondage intégré\u00a0: {date_lettres(last_date)}"]
    parts.append(f"Données vérifiées le {date_lettres(build_date)}")
    if last_revid:
        parts.append(
            f'revid\u00a0: <a href="https://fr.wikipedia.org/w/index.php?oldid={last_revid}" '
            f'target="_blank" style="color:inherit">{last_revid}</a>'
        )
    return " · ".join(parts)


def inject_into_footer(html_content, footer_text):
    """Injecte les dates dans le div#footer-run de chaque page."""
    import re
    replacement = f'<div id="footer-run">{footer_text}</div>'
    # Remplacer le div vide ou déjà rempli
    return re.sub(r'<div id="footer-run">.*?</div>', replacement, html_content)



def main():
    last_date, last_revid, build_date = compute_dates()
    footer_text = footer_html(last_date, last_revid, build_date)

    # Injecter dans toutes les pages HTML du site
    count = 0
    for html_path in sorted(SITE.rglob("*.html")):
        content = html_path.read_text(encoding="utf-8")
        new_content = inject_into_footer(content, footer_text)
        if new_content != content:
            html_path.write_text(new_content, encoding="utf-8")
            count += 1

    print(f"Dates injectées dans {count} pages")


if __name__ == "__main__":
    main()
