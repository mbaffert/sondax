#!/usr/bin/env python3
"""Intègre au build les petites feuilles de style dans un <style> de chaque page.

Les feuilles de INLINE (moins de 3 Kio chacune) bloquaient l'affichage par une
requête chacune. Ce script, lancé après toutes les étapes qui écrivent des
pages, remplace dans chaque site/**/*.html

    <link rel="stylesheet" href="…assets/bloc-chart.css?v=1">

par <style data-inline="bloc-chart.css">…</style> (le contenu du fichier). Le
<style> est placé dans le <head> (là où se trouvait le lien, ou en fin de <head>
quand le lien était dans le <body>, comme celui du bloc de partage). Idempotent :
un <style data-inline="…"> déjà présent est simplement rafraîchi, donc modifier
la feuille dans site/assets/ suffit, la page est mise à jour au build suivant.

header.css (≈ 10 Kio, commune à toutes les pages donc mise en cache) et
historique.css (≈ 15 Kio) restent des fichiers liés.

Usage : python scripts/inline_css.py
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ASSETS = SITE / "assets"

INLINE = ("bloc-chart.css", "bloc-retro.css", "partage-premier-tour.css")


def _bloc(nom):
    css = (ASSETS / nom).read_text(encoding="utf-8").strip()
    return f'<style data-inline="{nom}">\n{css}\n</style>\n'


def inliner(html):
    """Renvoie la page avec les feuilles de INLINE intégrées (ou rafraîchies)."""
    for nom in INLINE:
        bloc = _bloc(nom)
        deja = re.compile(rf'<style data-inline="{re.escape(nom)}">.*?</style>\n?', re.S)
        lien = re.compile(rf'<link rel="stylesheet" href="(?:\.\./)*assets/{re.escape(nom)}(?:\?v=\d+)?">\n?')
        if deja.search(html):
            html = deja.sub(lambda m: bloc, html, count=1)
        else:
            m = lien.search(html)
            if not m:
                continue
            if m.start() < html.find("</head>"):
                html = html[:m.start()] + bloc + html[m.end():]
            else:                              # lien dans le <body> : on le remonte
                html = html.replace("</head>", bloc + "</head>", 1)
        html = lien.sub("", html)              # liens restants (bloc de partage réécrit au build)
    return html


def main():
    for nom in INLINE:
        taille = (ASSETS / nom).stat().st_size
        if taille > 3 * 1024:
            sys.exit(f"ERREUR {nom} : {taille} octets, trop gros pour être intégré (> 3 Kio)")
    n = 0
    for page in sorted(SITE.rglob("*.html")):
        html = page.read_text(encoding="utf-8")
        nouveau = inliner(html)
        if nouveau != html:
            page.write_text(nouveau, encoding="utf-8")
            n += 1
    print(f"CSS intégrée ({', '.join(INLINE)}) dans {n} pages")


if __name__ == "__main__":
    main()
