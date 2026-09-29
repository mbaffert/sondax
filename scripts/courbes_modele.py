"""Courbes des chances d'être au second tour, en SVG rendu au build (§14.14.5).

Les chances ne changent qu'à l'entrée d'un sondage : la courbe est tracée en
marches, sans interpolation. Le JavaScript de la page ne fait que masquer ou
afficher des courbes et changer de période.
"""

import datetime, html

e = html.escape
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
               "sept.", "oct.", "nov.", "déc."]

L, H = 720, 250                 # viewBox
MG, MD, MH, MB = 34, 12, 10, 26  # marges gauche, droite, haut, bas


def _date(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def points_candidat(historique, slug, debut, fin):
    """[(instant, valeur)] en marches entre debut et fin ; la valeur en vigueur
    au début de la fenêtre est reprise à `debut`."""
    pts, avant = [], None
    for h in historique:
        t = _date(h["date"])
        v = h["qualification"].get(slug)
        if t < debut:
            avant = v
            continue
        if t > fin:
            break
        pts.append((t, v))
    if avant is not None and (not pts or pts[0][0] > debut):
        pts.insert(0, (debut, avant))
    if pts:
        pts.append((fin, pts[-1][1]))
    return pts


def svg(historique, candidats, slugs, maintenant, jours=None, visibles=None,
        classe="mo-courbe", hauteur=H):
    """SVG des chances de `slugs`. `jours` : fenêtre (None = depuis le début).
    `visibles` : slugs affichés par défaut (les autres ont la classe « cache »)."""
    if not historique:
        return ""
    fin = maintenant
    debut = fin - datetime.timedelta(days=jours) if jours else _date(historique[0]["date"])
    duree = max((fin - debut).total_seconds(), 1)
    h_util = hauteur - MH - MB

    def x(t):
        return MG + (L - MG - MD) * (t - debut).total_seconds() / duree

    def y(v):
        return MH + h_util * (1 - v / 100)

    morceaux = []
    for v in (0, 25, 50, 75, 100):
        morceaux.append(f'<line x1="{MG}" x2="{L - MD}" y1="{y(v):.1f}" y2="{y(v):.1f}" '
                        f'class="grille{" mi" if v == 50 else ""}"/>'
                        f'<text x="{MG - 6}" y="{y(v) + 4:.1f}" class="axe" text-anchor="end">{v}</text>')

    # Graduations : quelques dates régulières
    nb = 4 if jours and jours <= 7 else 5
    for k in range(nb + 1):
        t = debut + (fin - debut) * k / nb
        ancre = "start" if k == 0 else "end" if k == nb else "middle"
        morceaux.append(f'<text x="{x(t):.1f}" y="{hauteur - 6}" class="axe" text-anchor="{ancre}">'
                        f'{t.day} {MOIS_COURTS[t.month - 1]}</text>')

    for slug in slugs:
        pts = points_candidat(historique, slug, debut, fin)
        if not pts:
            continue
        d, prec = [], None
        for t, v in pts:
            if v is None:
                prec = None
                continue
            if prec is None:
                d.append(f"M{x(t):.1f},{y(v):.1f}")
            else:
                d.append(f"H{x(t):.1f}V{y(v):.1f}")
            prec = v
        cache = "" if visibles is None or slug in visibles else " cache"
        couleur = candidats[slug]["couleur"]
        morceaux.append(f'<path d="{"".join(d)}" data-c="{slug}" class="ligne{cache}" '
                        f'stroke="{couleur}"/>')

    return (f'<svg class="{classe}" viewBox="0 0 {L} {hauteur}" role="img" '
            f'aria-label="Évolution des chances d’être au second tour, sur 100">'
            f'{"".join(morceaux)}</svg>')


CSS = '''
  .mo-courbe { width: 100%; height: auto; display: block; }
  .mo-courbe .grille { stroke: #EDEEEA; stroke-width: 1; }
  .mo-courbe .grille.mi { stroke: #C9CDD2; stroke-dasharray: 4 4; }
  .mo-courbe .axe { font-size: 11px; fill: #8A929C; font-family: var(--corps, sans-serif); }
  .mo-courbe .ligne { fill: none; stroke-width: 2.5; stroke-linejoin: round; }
  .mo-courbe .ligne.cache { display: none; }
'''
