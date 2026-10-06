"""Génère site/assets/header-data.js et le balisage statique du bandeau.

Sans argument : écrit site/assets/header-data.js (dates de l'élection,
statistiques agrégées), lu par assets/header.js.

Avec --injecter (en fin de build, une fois toutes les pages générées) :
écrit le bandeau complet dans le <div id="site-header" class="sh"> de chaque
page HTML de site/, comme build_dates.py le fait pour le pied de page. Le
balisage reproduit celui que header.js produisait côté client, pour que la
navigation soit présente dans le HTML servi. header.js ne fait plus
qu'améliorer ce bandeau (compte à rebours recalculé, barre compacte, menu).
"""

import datetime
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "assets" / "header-data.js"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Repères factuels — textes en dur, regroupés ici (un seul endroit).
# Ces textes sont datés et devront être révisés :
# - à la publication du décret de convocation des électeurs ;
# - à la clôture des parrainages (12 mars 2027) ;
# - le jour du premier tour (18 avril 2027).
# Le booléen `officielles` de config.json ne sert plus à distinguer
# l'hypothèse du fait (les dates sont confirmées) mais à basculer la
# formulation si elles devaient changer.
# ---------------------------------------------------------------------------

REPERES_T1 = (
    'Le premier tour de l\u2019élection présidentielle se tient le dimanche '
    '<time datetime="2027-04-18">18\u00a0avril\u00a02027</time>. Les deux candidats arrivés en tête s\u2019affrontent '
    'au second tour, sauf si l\u2019un obtient la majorité absolue des suffrages '
    'exprimés dès le premier tour \u2014 ce qui n\u2019est jamais arrivé sous la '
    'V\u1d49\u00a0République. La liste officielle des candidats ne sera connue '
    'qu\u2019après la clôture des parrainages, le <time datetime="2027-03-12">12\u00a0mars\u00a02027</time>\u00a0: '
    'les instituts testent d\u2019ici là des hypothèses de candidatures, qui '
    'varient d\u2019un sondage à l\u2019autre.'
)

REPERES_T2 = (
    'Le second tour se tient le dimanche <time datetime="2027-05-02">2\u00a0mai\u00a02027</time>. Est élu le '
    'candidat qui obtient le plus de voix parmi les suffrages exprimés, les '
    'votes blancs et nuls étant décomptés à part et sans effet sur le résultat.'
)

JSONLD_T1 = {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Élection présidentielle française 2027 \u2014 premier tour",
    "startDate": "2027-04-18",
    "location": {"@type": "Country", "name": "France"},
}

JSONLD_T2 = {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Élection présidentielle française 2027 \u2014 second tour",
    "startDate": "2027-05-02",
    "location": {"@type": "Country", "name": "France"},
}


def select_hypothesis(sondage, candidats):
    """Sélectionne l'hypothèse T1 principale (SPEC §4).

    Utilise le champ "principale": true posé par principale.py.
    Fallback sur la première hypothèse T1 si aucune n'est marquée.
    """
    t1 = [h for h in sondage["hypotheses"] if h.get("tour") == 1]
    if not t1:
        return None

    # Chercher l'hypothèse marquée principale
    for h in t1:
        if h.get("principale"):
            return h

    # Fallback : première hypothèse T1
    return t1[0]


def format_date_fr(iso_date):
    """'2026-09-03' → '3 septembre 2026'"""
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    y, m, d = iso_date.split("-")
    return f"{int(d)} {mois[int(m) - 1]} {y}"


def format_date_mobile(iso_date):
    """'2026-09-03' → '3 septembre'"""
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    _, m, d = iso_date.split("-")
    return f"{int(d)} {mois[int(m) - 1]}"


def candidate_full_name(cid, candidats):
    """Nom complet (prénom + nom) du candidat depuis le référentiel."""
    c = candidats.get(cid, {})
    prenom = c.get("prenom", "")
    nom = c.get("nom", cid)
    if prenom:
        return f"{prenom} {nom}"
    return nom


def build_hyp_distinctive_label(hyp, all_t1, candidats):
    """Construit le libellé distinctif pour le lien 'Voir le détail'.

    Identifie les candidats qui distinguent cette hypothèse des autres T1
    du même sondage. S'il n'y a qu'une hypothèse, retourne None.
    """
    if len(all_t1) <= 1:
        return None

    # Candidats communs à toutes les hypothèses T1
    sets = [set(h.get("scores", {}).keys()) - {"autre"} for h in all_t1]
    common = set(sets[0])
    for s in sets[1:]:
        common &= s

    # Candidats distinctifs de cette hypothèse (présents ici, pas partout)
    mine = set(hyp.get("scores", {}).keys()) - {"autre"}
    distinctive = mine - common

    if not distinctive:
        return None

    # Trier par score décroissant, noms courts
    scores = hyp.get("scores", {})
    sorted_dist = sorted(distinctive, key=lambda c: -scores.get(c, 0))
    names = [candidats.get(cid, {}).get("nom", cid) for cid in sorted_dist]
    return " / ".join(names)


def select_latest_sondage(sondages):
    """Sélectionne le dernier sondage publié.

    Règle de départage (SPEC §4) :
    1. terrain_fin la plus récente
    2. en cas d'égalité, le plus grand echantillon total
    3. en cas d'égalité encore, l'ordre d'apparition dans sondages.json
    """
    if not sondages:
        return None
    # enumerate pour conserver l'ordre du fichier comme critère final
    return max(
        enumerate(sondages),
        key=lambda t: (t[1]["terrain_fin"], t[1].get("echantillon") or 0, -t[0]),
    )[1]


def load_all_sondages():
    """Charge sondages.json (contient déjà les manuels, fusionnés par le collecteur)."""
    return load_json(DATA / "sondages.json")


# ---------------------------------------------------------------------------
# Bandeau statique — reproduit à l'identique le rendu de assets/header.js
# (mêmes classes, même ordre, mêmes libellés). Toute modification de la
# navigation se fait ici ; header.js ne la reconstruit qu'en filet de sécurité.
# ---------------------------------------------------------------------------

SITE = ROOT / "site"

LOGO_SVG = (
    '<svg viewBox="0 0 44 24" aria-hidden="true">'
    '<path d="M4 7 C 12 7, 14 17, 22 17 C 30 17, 32 7, 40 7" fill="none" stroke="#0C6CF2" stroke-width="5.5" stroke-linecap="round"/>'
    '<path d="M4 17 C 12 17, 14 7, 22 7 C 30 7, 32 17, 40 17" fill="none" stroke="#F23D5B" stroke-width="5.5" stroke-linecap="round"/>'
    '</svg>'
)

CANDIDATS_PAGES = [
    ("le-pen", "Marine Le Pen"),
    ("philippe", "Édouard Philippe"),
    ("melenchon", "Jean-Luc Mélenchon"),
    ("glucksmann", "Raphaël Glucksmann"),
    ("hollande", "François Hollande"),
    ("attal", "Gabriel Attal"),
    ("retailleau", "Bruno Retailleau"),
    ("tondelier", "Marine Tondelier"),
    ("zemmour", "Éric Zemmour"),
    ("roussel", "Fabien Roussel"),
]

# (libellé, href, pages qui l'activent, préfixe qui l'active) ;
# None à la place du href : menu déroulant des candidats.
NAV_ITEMS = [
    ("Accueil", "/", ["index.html", ""], None),
    ("Candidats", None, [], None),
    ("Tous les sondages", "sondages.html", ["sondages.html"], None),
    ("Modèle Sondax", "modele-sondax.html", ["modele-sondax.html"], None),
    ("Instituts", "instituts.html", ["instituts.html"], None),
    ("Élections passées", "precedentes-elections.html", ["precedentes-elections.html"], "presidentielle-"),
    ("Méthode", "methodologie.html", ["methodologie.html"], None),
    ("Données", "donnees.html", ["donnees.html"], None),
]

SOUS_DOSSIERS = ("second-tour", "sondages", "instituts", "candidats", "partage")
RUBRIQUES = {"sondages": "Tous les sondages", "instituts": "Instituts"}


def compte_a_rebours(premier_tour, second_tour, aujourd_hui):
    """(gros chiffre, date longue, date courte), ou None après le second tour.

    Même calcul que header.js, qui le refait au chargement de la page.
    """
    d1 = (datetime.date.fromisoformat(premier_tour) - aujourd_hui).days
    d2 = (datetime.date.fromisoformat(second_tour) - aujourd_hui).days
    if d1 > 0:
        return f"J\u2212{d1}", "1<sup>er</sup> tour · 18 avril 2027", "18 avril"
    if d1 == 0:
        return "J0", "1<sup>er</sup> tour · aujourd\u2019hui", "aujourd\u2019hui"
    if d2 > 0:
        return f"J\u2212{d2}", "2<sup>d</sup> tour · 2 mai 2027", "2 mai"
    if d2 == 0:
        return "J0", "2<sup>d</sup> tour · aujourd\u2019hui", "aujourd\u2019hui"
    return None


def header_html(rel_path, cd):
    """Contenu de <div id="site-header"> pour la page site/<rel_path>."""
    parts = rel_path.split("/")
    page = parts[-1]
    sous_dossier = parts[0] if len(parts) > 1 and parts[0] in SOUS_DOSSIERS else None
    base = "../" if sous_dossier else ""

    def actif(label, match, prefixe):
        if sous_dossier:
            return RUBRIQUES.get(sous_dossier) == label
        return page in match or bool(prefixe and page.startswith(prefixe))

    def liens():
        h = ""
        for label, href, match, prefixe in NAV_ITEMS:
            if href is not None and not href.startswith("/"):
                href = base + href
            if href is None:
                h += (f'<div class="menu-candidats">'
                      f'<a href="{base}candidats/" class="menu-candidats-label">Candidats</a>'
                      f'<div class="menu-panneau">')
                h += "".join(f'<a href="{base}{slug}.html">{nom}</a>' for slug, nom in CANDIDATS_PAGES)
                h += "</div></div>"
            elif actif(label, match, prefixe):
                h += f'<a href="{href}" class="is-active" aria-current="page">{label}</a>'
            else:
                h += f'<a href="{href}">{label}</a>'
        return h

    cd_html = ""
    if cd:
        big, longue, courte = cd
        cd_html = ('<div class="sh-cd">'
                   f'<span class="sh-cd-big">{big}</span>'
                   f'<span class="sh-cd-date sh-cd-date-longue">{longue}</span>'
                   f'<span class="sh-cd-date sh-cd-date-courte">{courte}</span>'
                   '</div>')

    return ('<div class="sh-inner">'
            '<a class="sh-logo" href="/" aria-label="Sondax — accueil">'
            + LOGO_SVG
            + '<span class="sh-wordmark">sondax</span>'
            '</a>'
            f'<nav class="sh-nav" aria-label="Navigation principale">{liens()}</nav>'
            '<div class="sh-sub-slot"></div>'
            + cd_html
            + '<button type="button" class="sh-menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="sh-panel">'
            '<span class="sh-menu-bars" aria-hidden="true"><span></span><span></span><span></span></span>'
            '<span class="sh-menu-txt" aria-hidden="true">Menu</span>'
            '</button>'
            '</div>'
            f'<nav class="sh-panel" id="sh-panel" aria-label="Navigation principale">{liens()}</nav>')


OUVRANT = '<div id="site-header" class="sh">'
BALISE_DIV = re.compile(r"<div\b|</div>")


def inject_header(content, inner):
    """Remplace le contenu du div#site-header (vide ou déjà rempli).

    La fin du div est trouvée en comptant les <div> imbriqués, pour que
    l'injection soit idempotente d'un build à l'autre.
    """
    debut = content.find(OUVRANT)
    if debut < 0:
        return content
    i = debut + len(OUVRANT)
    profondeur = 1
    for m in BALISE_DIV.finditer(content, i):
        profondeur += 1 if m.group() != "</div>" else -1
        if profondeur == 0:
            return content[:i] + inner + content[m.start():]
    raise ValueError("div#site-header non fermé")


def injecter():
    config_path = DATA / "config.json"
    config = load_json(config_path) if config_path.exists() else {}
    election = config.get("election", {})
    # Jour courant à Paris, comme header.js (le build tourne chaque jour)
    aujourd_hui = datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    cd = compte_a_rebours(election.get("premier_tour", "2027-04-18"),
                          election.get("second_tour", "2027-05-02"), aujourd_hui)

    count = 0
    for html_path in sorted(SITE.rglob("*.html")):
        content = html_path.read_text(encoding="utf-8")
        if OUVRANT not in content:
            continue
        new_content = inject_header(content, header_html(html_path.relative_to(SITE).as_posix(), cd))
        if new_content != content:
            html_path.write_text(new_content, encoding="utf-8")
        count += 1
    print(f"Bandeau statique injecté dans {count} pages ({cd[0] if cd else 'sans compte à rebours'})")


def main():
    if "--injecter" in sys.argv[1:]:
        injecter()
        return

    sondages = load_all_sondages()

    if not sondages:
        print("Aucun sondage trouvé.")
        return

    # Statistiques
    poll_count = len(sondages)
    institutes = set(s["institut"] for s in sondages)
    institute_count = len(institutes)

    # Dates de l'élection depuis config.json
    config_path = DATA / "config.json"
    config = load_json(config_path) if config_path.exists() else {}
    election = config.get("election", {})

    # Données pour le bandeau
    header_data = {
        "pollCount": poll_count,
        "instituteCount": institute_count,
        "electionDates": {
            "premierTour": election.get("premier_tour", "2027-04-18"),
            "secondTour": election.get("second_tour", "2027-05-02"),
        },
    }

    # Pages institut : nom court (champ `institut`) → slug du référentiel
    sys.path.insert(0, str(ROOT / "scripts"))
    from instituts import charger_referentiel, slug_institut
    referentiel = charger_referentiel()
    header_data["instituts"] = {
        nom: slug for nom in sorted(institutes)
        if (slug := slug_institut(nom, referentiel))
    }

    # Écrire le fichier JS
    js = "// Généré par scripts/build_header.py — ne pas modifier à la main\n"
    js += "window.HEADER_DATA = " + json.dumps(header_data, ensure_ascii=False, indent=2) + ";\n"

    os.makedirs(OUT.parent, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"header-data.js écrit : {poll_count} sondages, {institute_count} instituts")


if __name__ == "__main__":
    main()
