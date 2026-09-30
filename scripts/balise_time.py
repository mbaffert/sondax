"""Balise <time datetime> autour d'une date affichée (SPEC §13.5).

La balise n'ajoute aucun style : le texte affiché reste identique, seule la
date lisible par les machines est ajoutée.
"""

import re


def time_tag(iso, texte):
    """'2026-09-24', '24 septembre 2026' → <time datetime="2026-09-24">24 septembre 2026</time>"""
    return f'<time datetime="{iso}">{texte}</time>'


def time_periode(debut, fin, texte_debut, texte_fin, sep):
    """Période de terrain : deux balises, une par borne ; une seule si debut == fin."""
    if not debut or debut == fin:
        return time_tag(fin, texte_fin)
    return f"{time_tag(debut, texte_debut)}{sep}{time_tag(fin, texte_fin)}"


MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
_ESP = r"(?:[  ]|&nbsp;)"
_DATE_PROSE = re.compile(
    rf"\b(?:(?P<jour>1er|[0-9]{{1,2}}){_ESP})?(?P<mois>{'|'.join(MOIS)}){_ESP}(?P<annee>[0-9]{{4}})\b")


# Hors texte : balises, scripts, styles et dates déjà balisées
_HORS_TEXTE = re.compile(r"(<(script|style|time)\b.*?</\2>|<[^>]+>)", re.S)


def baliser_dates(fragment):
    """Balise les dates d'un texte rédigé (brut ou HTML) : « 22 mai 2026 » →
    2026-05-22, « décembre 2024 » → 2024-12. Les balises, scripts, styles et
    dates déjà balisées sont laissés tels quels."""
    def remplacer(m):
        iso = f"{m['annee']}-{MOIS.index(m['mois']) + 1:02d}"
        if m["jour"]:
            iso += f"-{int(m['jour'].replace('er', '')):02d}"
        return time_tag(iso, m.group(0))
    morceaux, debut = [], 0
    for m in _HORS_TEXTE.finditer(fragment):
        morceaux.append(_DATE_PROSE.sub(remplacer, fragment[debut:m.start()]))
        morceaux.append(m.group(0))
        debut = m.end()
    morceaux.append(_DATE_PROSE.sub(remplacer, fragment[debut:]))
    return "".join(morceaux)
