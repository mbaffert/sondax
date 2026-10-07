#!/usr/bin/env python3
"""Injecte les dates de build dans le HTML de toutes les pages.

Remplace :
- le contenu de <div id="footer-run"> dans le footer de toutes les pages
- le contenu de <p id="compteur-sondages"> sous le H1 de l'accueil
- dans sondages.html : <title>, meta description, og:title, og:description et
  h1#titre-sondages, qui portent le nombre de sondages, ainsi que le paragraphe
  d'introduction p#intro-sondages
- dans index.html : <title>, meta description, og:title et og:description, qui
  portent le dernier sondage (institut et date de fin de terrain). Le sondage est
  celui du bloc « Dernier sondage » (build_index_premier_tour.sondage_affiche) ;
  sans sondage, les textes écrits à la main sont laissés tels quels

Données :
- Nombre de sondages : entrées de sondages.json
- Nombre d'instituts : clés distinctes du référentiel (alias regroupés)
- Dernier sondage intégré : terrain_fin max de sondages.json
- Revid Wikipédia : revid max de sondages.json
- Date de vérification : date du build (aujourd'hui)
"""

import json, pathlib, datetime, re, html as html_mod

from instituts import charger_referentiel, compter_instituts, slug_institut
from balise_time import time_tag
from build_header import load_all_sondages
from build_index_premier_tour import sondage_affiche, load_json, CANDIDATS_PATH, MOIS_ABBREV

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


def sondages_page_textes(n_sondages, n_instituts, last_date, **_):
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
        r'<p id="intro-sondages"[^>]*>.*?</p>': (
            f'<p id="intro-sondages" style="font-size:14.5px;color:var(--gris);margin:0 0 18px;">Tous les sondages des présidentielles 2027, institut par '
            f'institut\u00a0: {n_sondages}\u00a0sondages publiés par {n_instituts}\u00a0instituts, le plus récent '
            f'terminé le {time_tag(last_date, date_lettres(last_date))}.</p>'),
    }


def inject_textes(html_content, textes, page):
    for motif, remplacement in textes.items():
        html_content, n = re.subn(motif, lambda _: remplacement, html_content)
        if n != 1:
            raise ValueError(f"{page} : {motif} trouvé {n} fois (1 attendu)")
    return html_content


def inject_sondages_page(html_content, textes):
    return inject_textes(html_content, textes, "sondages.html")


def inject_accueil(html_content, textes):
    return inject_textes(html_content, textes, "index.html")


TITRE_ACCUEIL_MAX = 65
DESCRIPTION_ACCUEIL = ("Tous les sondages de la présidentielle 2027 : premier tour, second tour "
                       "et cotes des marchés de prédiction. Mise à jour quotidienne et détail "
                       "du dernier sondage paru.")


def dates_courtes(iso):
    """Date de terrain de la plus longue à la plus courte : « 29 septembre »,
    « 29 sept. », « 29/09 »."""
    _, m, d = iso.split("-")
    jour = "1er" if int(d) == 1 else str(int(d))
    return [f"{jour} {MOIS[int(m) - 1]}", f"{jour} {MOIS_ABBREV[int(m) - 1]}",
            f"{int(d):02d}/{m}"]


def accueil_textes(sondages, candidats, referentiel):
    """Textes de index.html qui portent le dernier sondage, ou None sans sondage.

    Le sondage est celui du bloc « Dernier sondage ». La date est raccourcie
    plutôt que de perdre « Sondages présidentielle 2027 » ou de dépasser les
    longueurs visées.
    """
    choix = sondage_affiche(sondages, candidats)
    if not choix:
        return None
    sondage = choix[0]
    slug = slug_institut(sondage["institut"], referentiel)
    institut = referentiel[slug]["nom"] if slug else sondage["institut"]
    dates = dates_courtes(sondage["terrain_fin"])

    def premier_qui_tient(modele, maxi):
        for d in dates:
            texte = modele.format(dernier=f"{institut} du {d}")
            if len(texte) <= maxi:
                return texte
        return modele.format(dernier=f"{institut} du {dates[-1]}")

    titre = premier_qui_tient("Sondages présidentielle 2027 : dernier sondage {dernier}",
                              TITRE_ACCUEIL_MAX - len(" — Sondax"))
    description = DESCRIPTION_ACCUEIL
    titre, description = html_mod.escape(titre), html_mod.escape(description)
    return {
        r'<title>.*?</title>': f'<title>{titre} — Sondax</title>',
        r'<meta name="description" content="[^"]*">': f'<meta name="description" content="{description}">',
        r'<meta property="og:title" content="[^"]*">': f'<meta property="og:title" content="{titre}">',
        r'<meta property="og:description" content="[^"]*">': f'<meta property="og:description" content="{description}">',
    }


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
    textes_accueil = accueil_textes(load_all_sondages(), load_json(CANDIDATS_PATH),
                                    charger_referentiel())

    # Injecter dans toutes les pages HTML du site
    count = 0
    for html_path in sorted(SITE.rglob("*.html")):
        content = html_path.read_text(encoding="utf-8")
        new_content = inject_compteur(inject_into_footer(content, footer_text), compteur_text)
        if html_path == SITE / "sondages.html":
            new_content = inject_sondages_page(new_content, textes_sondages)
        if html_path == SITE / "index.html" and textes_accueil:
            new_content = inject_accueil(new_content, textes_accueil)
        if new_content != content:
            html_path.write_text(new_content, encoding="utf-8")
            count += 1

    print(f"Dates injectées dans {count} pages "
          f"({stats['n_sondages']} sondages, {stats['n_instituts']} instituts)")


if __name__ == "__main__":
    main()
