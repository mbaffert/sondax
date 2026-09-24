#!/usr/bin/env python3
"""Génère site/sitemap.xml au build, listant toutes les pages publiques.

Parcourt site/ pour les pages statiques, puis ajoute les pages générées
(candidats, sondages, duels, instituts) à partir des données.
"""

import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://sondax.fr"


def collect_urls():
    """Collecte toutes les URLs publiques du site."""
    urls = []

    # Pages statiques à la racine de site/
    for f in sorted(SITE.glob("*.html")):
        name = f.name
        # Exclure les pages candidat générées (elles seront ajoutées depuis bios.json)
        # On les détecte car elles n'ont pas de marqueur statique
        urls.append(f"{BASE}/{name}" if name != "index.html" else f"{BASE}/")

    # Pages dans second-tour/ (exclure les redirections)
    st_index = SITE / "second-tour" / "index.html"
    if st_index.exists():
        urls.append(f"{BASE}/second-tour/")
    for f in sorted((SITE / "second-tour").glob("*.html")):
        if f.name == "index.html":
            continue
        # Exclure les pages de redirection (< 500 octets, contiennent "Redirection")
        content = f.read_text(encoding="utf-8")
        if len(content) < 500 and "Redirection" in content:
            continue
        urls.append(f"{BASE}/second-tour/{f.name}")

    # Pages dans candidats/
    cand_index = SITE / "candidats" / "index.html"
    if cand_index.exists():
        urls.append(f"{BASE}/candidats/")

    # Pages dans sondages/
    for f in sorted((SITE / "sondages").glob("*.html")):
        if f.name != "index.html":
            urls.append(f"{BASE}/sondages/{f.name}")

    # Pages dans instituts/ (instituts.html est couvert par la racine)
    for f in sorted((SITE / "instituts").glob("*.html")):
        urls.append(f"{BASE}/instituts/{f.name}")

    return urls


def generate_sitemap(urls):
    today = datetime.date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url in urls:
        lines.append(f"  <url><loc>{url}</loc><lastmod>{today}</lastmod></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main():
    urls = collect_urls()
    xml = generate_sitemap(urls)
    out = SITE / "sitemap.xml"
    out.write_text(xml, encoding="utf-8")
    print(f"sitemap.xml : {len(urls)} URLs")


if __name__ == "__main__":
    main()
