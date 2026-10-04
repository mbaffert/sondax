#!/usr/bin/env python3
"""Injecte le balisage JSON-LD de navigation (SPEC §13.5).

- WebSite et Organization sur index.html (invisible).
- BreadcrumbList sur chaque page qui affiche un fil d'Ariane (élément de
  classe « fil ») : mêmes étapes que le fil visible, dans le même ordre. Une
  étape liée prend l'URL absolue de son lien ; la dernière étape, non liée, est
  la page elle-même (son canonical). Un fil d'une seule étape n'est pas balisé.

Chaque balise porte un id, ce qui rend l'injection idempotente. À lancer après
la génération de toutes les pages.
"""

import html as html_mod
import json
import pathlib
import re
import sys
from urllib.parse import urljoin

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://sondax.fr/"

# Étapes intermédiaires affichées sans lien : URL de la page correspondante
ETAPES_SANS_LIEN = {"Candidats": urljoin(BASE, "candidats/")}

FIL = re.compile(r'<(nav|div|p) class="fil"[^>]*>(.*?)</\1>', re.S)
LIEN = re.compile(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S)
CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)">')

WEBSITE = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "WebSite",
            "name": "Sondax",
            "alternateName": "Sondax — sondages présidentielle 2027",
            "url": BASE,
            "inLanguage": "fr-FR",
        },
        {
            "@type": "Organization",
            "name": "Sondax",
            "url": BASE,
            "logo": urljoin(BASE, "assets/logo-sondax.svg"),
            "sameAs": [
                "https://www.data.gouv.fr/organizations/sondax/",
                "https://github.com/mbaffert/sondax",
            ],
        },
    ],
}


def texte(fragment):
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def etapes_fil(contenu, canonical, chemin):
    """[(nom, url)] du fil d'Ariane de la page, ou [] s'il n'y en a pas."""
    m = FIL.search(contenu)
    if not m:
        return []
    morceaux = [p for p in m.group(2).split("›") if p.strip()]
    etapes = []
    for i, morceau in enumerate(morceaux):
        lien = LIEN.search(morceau)
        nom = texte(lien.group(2) if lien else morceau)
        if lien:
            url = urljoin(canonical, lien.group(1))
        elif i == len(morceaux) - 1:
            url = canonical
        elif nom in ETAPES_SANS_LIEN:
            url = ETAPES_SANS_LIEN[nom]
        else:
            sys.exit(f"build_jsonld_navigation : étape « {nom} » sans lien dans le fil "
                     f"de {chemin} (à ajouter à ETAPES_SANS_LIEN)")
        etapes.append((nom, url))
    return etapes


def breadcrumb(etapes):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": nom, "item": url}
            for i, (nom, url) in enumerate(etapes, 1)
        ],
    }


def poser(contenu, ident, data):
    balise = (f'<script type="application/ld+json" id="{ident}">'
              f'{json.dumps(data, ensure_ascii=False)}</script>')
    existante = re.compile(rf'<script type="application/ld\+json" id="{ident}">.*?</script>', re.S)
    if existante.search(contenu):
        return existante.sub(lambda _: balise, contenu)
    return contenu.replace("</head>", balise + "\n</head>", 1)


def main():
    index = SITE / "index.html"
    index.write_text(poser(index.read_text(encoding="utf-8"), "jsonld-website", WEBSITE),
                     encoding="utf-8")
    print("  OK  jsonld-website -> index.html")

    n = 0
    for chemin in sorted(SITE.rglob("*.html")):
        contenu = chemin.read_text(encoding="utf-8")
        m = CANONICAL.search(contenu)
        if not m or 'http-equiv="refresh"' in contenu:
            continue
        etapes = etapes_fil(contenu, m.group(1), chemin.relative_to(SITE))
        if len(etapes) < 2:
            continue
        nouveau = poser(contenu, "jsonld-breadcrumb", breadcrumb(etapes))
        if nouveau != contenu:
            chemin.write_text(nouveau, encoding="utf-8")
        n += 1
    print(f"  OK  jsonld-breadcrumb -> {n} pages")


if __name__ == "__main__":
    main()
