#!/usr/bin/env python3
"""Injecte les dates de build dans le HTML de toutes les pages.

Remplace :
- le contenu de <div id="footer-run"> dans le footer de toutes les pages
- le contenu de <p id="compteur-sondages"> sous le H1 de l'accueil
- dans sondages.html : <title>, meta description, og:title, og:description et
  h1#titre-sondages, qui portent le nombre de sondages

Données :
- Nombre de sondages : entrées de sondages.json
- Nombre d'instituts : clés distinctes du référentiel (alias regroupés)
- Dernier sondage intégré : terrain_fin max de sondages.json
- Revid Wikipédia : revid max de sondages.json
- Date de vérification : date du build (aujourd'hui)
"""

import json, pathlib, datetime, re

from instituts import charger_referentiel, compter_instituts
from balise_time import time_tag

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

    return {
        "n_sondages": len(sondages),
        "n_instituts": compter_instituts(sondages, charger_referentiel()),
        "last_date": last_date,
        "last_revid": last_revid,
        "build_date": build_date,
    }


def compteur_html(n_sondages, n_instituts, build_date, **_):
    date = date_lettres(build_date).replace(" ", "\u00a0")  # pas de « 2026 » seul à la ligne
    return (f"{n_sondages}\u00a0sondages · {n_instituts}\u00a0instituts · "
            f"mis à jour le {time_tag(build_date, date)}")


def footer_html(n_sondages, last_date, last_revid, build_date, **_):
    parts = [f"{n_sondages}\u00a0sondages agrégés"]
    parts.append(f"Dernier sondage intégré\u00a0: {time_tag(last_date, date_lettres(last_date))}")
    parts.append(f"Données vérifiées le {time_tag(build_date, date_lettres(build_date))}")
    if last_revid:
        parts.append(
            f'revid\u00a0: <a href="https://fr.wikipedia.org/w/index.php?oldid={last_revid}" '
            f'target="_blank" style="color:inherit">{last_revid}</a>'
        )
    return " · ".join(parts)


def sondages_page_textes(n_sondages, **_):
    """Textes de sondages.html qui portent le nombre de sondages."""
    titre = f"Les {n_sondages} sondages de la présidentielle 2027, par institut et par date"
    description = (f"Les {n_sondages} sondages de la présidentielle 2027, listés par institut "
                   f"et par date, avec le détail de chaque sondage : scores, marges "
                   f"d’erreur et configurations testées.")
    return {
        r'<title>.*?</title>': f'<title>{titre} — Sondax</title>',
        r'<meta name="description" content="[^"]*">': f'<meta name="description" content="{description}">',
        r'<meta property="og:title" content="[^"]*">': f'<meta property="og:title" content="{titre}">',
        r'<meta property="og:description" content="[^"]*">': f'<meta property="og:description" content="{description}">',
        r'<h1 id="titre-sondages">.*?</h1>': (f'<h1 id="titre-sondages">Les {n_sondages}\u00a0sondages '
                                              f'de la présidentielle 2027, un par un</h1>'),
    }


def inject_sondages_page(html_content, textes):
    for motif, remplacement in textes.items():
        html_content, n = re.subn(motif, lambda _: remplacement, html_content)
        if n != 1:
            raise ValueError(f"sondages.html : {motif} trouvé {n} fois (1 attendu)")
    return html_content


def inject_into_footer(html_content, footer_text):
    """Injecte les dates dans le div#footer-run de chaque page."""
    replacement = f'<div id="footer-run">{footer_text}</div>'
    # Remplacer le div vide ou déjà rempli
    return re.sub(r'<div id="footer-run">.*?</div>', replacement, html_content)


def inject_compteur(html_content, compteur_text):
    """Injecte le compteur dans le p#compteur-sondages (accueil)."""
    replacement = f'<p id="compteur-sondages">{compteur_text}</p>'
    return re.sub(r'<p id="compteur-sondages">.*?</p>', replacement, html_content)


def main():
    stats = compute_dates()
    footer_text = footer_html(**stats)
    compteur_text = compteur_html(**stats)
    textes_sondages = sondages_page_textes(**stats)

    # Injecter dans toutes les pages HTML du site
    count = 0
    for html_path in sorted(SITE.rglob("*.html")):
        content = html_path.read_text(encoding="utf-8")
        new_content = inject_compteur(inject_into_footer(content, footer_text), compteur_text)
        if html_path == SITE / "sondages.html":
            new_content = inject_sondages_page(new_content, textes_sondages)
        if new_content != content:
            html_path.write_text(new_content, encoding="utf-8")
            count += 1

    print(f"Dates injectées dans {count} pages "
          f"({stats['n_sondages']} sondages, {stats['n_instituts']} instituts)")


if __name__ == "__main__":
    main()
