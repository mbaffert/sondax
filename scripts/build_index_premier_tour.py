"""Injecte le contenu statique du premier tour dans site/index.html.

Lit data/derived/series-t1.json, data/sondages.json et data/candidats.json.
Génère le chapeau et le bloc « Dernier sondage », et les remplace entre leurs
marqueurs respectifs. Le tableau des derniers sondages agrégés a été retiré de
l'accueil (lien « Voir tous les sondages » sous la carte, dans le gabarit).

Tout le contenu est rendu au build et présent dans le HTML servi.
"""

import json, pathlib, sys, html as html_mod
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "site" / "index.html"
SERIES_PATH = ROOT / "data" / "derived" / "series-t1.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"

sys.path.insert(0, str(ROOT / "scripts"))
from instituts import charger_referentiel, lien_institut
from balise_time import time_tag, time_periode
from build_header import (
    select_hypothesis, select_latest_sondage, candidate_full_name, load_all_sondages,
    REPERES_T1, JSONLD_T1, CANDIDATS_PAGES,
)

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

PT_BEGIN = "<!-- BEGIN:premier-tour -->"
PT_END = "<!-- END:premier-tour -->"
SRC_BEGIN = "<!-- BEGIN:source-premier-tour -->"
SRC_END = "<!-- END:source-premier-tour -->"
BLOC_DS_BEGIN = "<!-- BEGIN:bloc-dernier-sondage -->"
BLOC_DS_END = "<!-- END:bloc-dernier-sondage -->"


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def date_lettres(iso):
    """'2026-09-10' → '10 septembre 2026'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",") + "\u00a0%"


def fmt_ech(n):
    """Échantillon avec séparateur de milliers."""
    return f"{round(n):,}".replace(",", "\u202f")


def enumeration_fr(items):
    """['A', 'B', 'C'] → 'A, B et C'"""
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " et " + items[-1]


# ---------------------------------------------------------------------------
# Chapeau du premier tour
# ---------------------------------------------------------------------------

def candidates_in_window(series_data, fenetre_jours=30):
    """Retourne le set des candidats ayant au moins un point brut dans la fenêtre."""
    date_fin = series_data.get("date_fin", "")
    if not date_fin:
        return set()
    fin = date.fromisoformat(date_fin)
    debut = (fin - timedelta(days=fenetre_jours)).isoformat()
    cands = set()
    for pb in series_data.get("points_bruts", []):
        if pb["d"] >= debut:
            for cid in pb["scores"]:
                cands.add(cid)
    return cands


def derniers_scores(series_data):
    """{candidat: dernière valeur de tendance} des candidats ayant au moins une
    mesure dans la fenêtre glissante (§4 SPEC)."""
    series = series_data.get("series", {})
    latest = {}
    for cid in candidates_in_window(series_data, series_data.get("fenetre_jours", 30)):
        for p in reversed(series.get(cid, [])):
            if p["v"] is not None:
                latest[cid] = p["v"]
                break
    return latest


def sondages_dans_fenetre(series_data, sondages):
    """(début de la fenêtre ISO, sondages dont le terrain s'est achevé dedans) :
    ceux que pondère la moyenne affichée."""
    fin = date.fromisoformat(series_data["date_fin"])
    debut = (fin - timedelta(days=series_data.get("fenetre_jours", 30))).isoformat()
    return debut, [s for s in sondages if s["terrain_fin"] >= debut]


def generate_chapeau(series_data, sondages, candidats):
    """Trois phrases : leader, volume, delta 3 mois.

    Seuls les candidats ayant au moins une mesure dans la fenêtre glissante
    de 30 jours (§4 SPEC) sont retenus.
    """
    series = series_data.get("series", {})
    date_fin = series_data.get("date_fin", "")

    latest = derniers_scores(series_data)

    if not latest:
        return '<p class="subtitle">Aucune donnée de premier tour disponible.</p>'

    # Top 3 par score décroissant
    top = sorted(latest.items(), key=lambda x: -x[1])[:3]

    # Phrase 1 : leader
    leader_cid, leader_v = top[0]
    leader_nom = candidate_full_name(leader_cid, candidats)
    c = candidats.get(leader_cid, {})
    is_parti = c.get("type") == "parti"

    others = []
    for cid, v in top[1:]:
        others.append(f"{candidate_full_name(cid, candidats)} ({fmt_pct(v)})")

    if is_parti:
        phrase1 = (
            f"{leader_nom} est en tête des sondages du premier tour "
            f"avec {fmt_pct(leader_v)} des intentions de vote"
        )
    else:
        phrase1 = (
            f"{leader_nom} arrive en tête des sondages du premier tour "
            f"de la présidentielle 2027 avec {fmt_pct(leader_v)} des intentions de vote"
        )
    if others:
        phrase1 += f", devant {enumeration_fr(others)}"
    phrase1 += "."

    # Phrase 2 : volume et instituts dans la fenêtre de 30 jours
    fin = date.fromisoformat(date_fin)
    debut_fenetre, sondages_fenetre = sondages_dans_fenetre(series_data, sondages)
    n_sondages = len(sondages_fenetre)
    instituts = sorted(set(s["institut"] for s in sondages_fenetre))

    debut_date_lettres = time_tag(debut_fenetre, date_lettres(debut_fenetre))
    if n_sondages == 1:
        phrase2 = (
            f"Cette moyenne repose sur un seul sondage publié "
            f"par {enumeration_fr(instituts)}."
        )
    else:
        phrase2 = (
            f"Cette moyenne pondère les {n_sondages}\u00a0sondages publiés depuis "
            f"le {debut_date_lettres} par {len(instituts)}\u00a0instituts\u00a0: "
            f"{enumeration_fr(instituts)}."
        )

    # Phrase 3 : delta 3 mois du leader
    # Comparer la valeur actuelle à celle d'il y a 90 jours, mais seulement
    # si le leader avait des mesures à cette date (était dans la fenêtre).
    phrase3 = ""
    debut_3m = (fin - timedelta(days=90)).isoformat()
    leader_pts = series.get(leader_cid, [])

    # Vérifier que le leader était testé il y a 3 mois
    cands_3m = set()
    for pb in series_data.get("points_bruts", []):
        d = pb["d"]
        if d >= debut_3m and d <= (fin - timedelta(days=60)).isoformat():
            # Points dans la zone [J-90, J-60] : le leader avait des données
            if leader_cid in pb["scores"]:
                cands_3m.add(leader_cid)

    if leader_cid in cands_3m:
        # Trouver la valeur la plus proche de J-90
        v_3m_ago = None
        for p in leader_pts:
            if p["d"] <= debut_3m and p["v"] is not None:
                v_3m_ago = p["v"]
        if v_3m_ago is not None:
            delta = leader_v - v_3m_ago
            nom_court = candidats.get(leader_cid, {}).get("nom", leader_cid)
            if abs(delta) >= 0.1:
                delta_fmt = f"{abs(delta):.1f}".replace(".", ",")
                pts = "point" if abs(delta) < 2 else "points"
                if delta > 0:
                    phrase3 = f"{nom_court} gagne {delta_fmt}\u00a0{pts} en trois mois."
                else:
                    phrase3 = f"{nom_court} perd {delta_fmt}\u00a0{pts} en trois mois."
            else:
                phrase3 = f"{nom_court} est stable sur trois mois."

    parts = [phrase1, phrase2]
    if phrase3:
        parts.append(phrase3)
    return f'<p class="subtitle">{" ".join(parts)}</p>'



# ---------------------------------------------------------------------------
# Bloc « Dernier sondage » (nouveau bloc compact en haut de page)
# ---------------------------------------------------------------------------

MOIS_ABBREV = [
    "janv.", "fév.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]


def initiales(nom):
    """Première lettre de chaque mot du nom, deux au maximum : « Le Pen » → « LP »."""
    return "".join(m[0] for m in nom.split())[:2].upper()


def portrait(cid, nom, couleur, photos):
    """Portrait rond de 46 px cerclé de la couleur du candidat : photo de
    photos.json, à défaut monogramme."""
    c = f"--c:{couleur}"
    if cid in photos:
        fichier = html_mod.escape(photos[cid]["fichier"], quote=True)
        img = (f'<img class="ds-photo" style="{c}" src="{fichier}" alt="" '
               f'width="46" height="46" loading="lazy">')
    else:
        img = f'<span class="ds-photo ds-mono" style="{c}">{html_mod.escape(initiales(nom))}</span>'
    return f'<div class="ds-ph">{img}</div>'


def sondage_affiche(sondages, candidats):
    """(sondage, hypothèse principale) que montre le bloc « Dernier sondage »,
    ou None. Source unique : le <title> de l'accueil (build_dates.py) s'en sert
    pour ne jamais diverger du bloc."""
    latest = select_latest_sondage(sondages)
    if not latest:
        return None
    hyp = select_hypothesis(latest, candidats)
    return (latest, hyp) if hyp else None


def generate_bloc_dernier_sondage(sondages, candidats, series_data):
    """Génère le bloc compact « Dernier sondage » affiché en haut de page."""
    choix = sondage_affiche(sondages, candidats)
    if not choix:
        return ""
    latest, hyp = choix

    scores_raw = hyp.get("scores", {})
    # Tri décroissant, sans "autre"
    scores = sorted(
        ((cid, v) for cid, v in scores_raw.items() if cid != "autre"),
        key=lambda kv: -kv[1],
    )
    top4 = scores[:4]
    others = scores[4:]
    photos = json.loads(PHOTOS_PATH.read_text(encoding="utf-8"))
    # Pages candidat : liste de build_header, pas le disque (elles sont générées après ce script)
    pages = {slug for slug, _ in CANDIDATS_PAGES}

    institut = lien_institut(latest["institut"], charger_referentiel())

    # Dates
    td = latest["terrain_debut"]
    tf = latest["terrain_fin"]
    td_y, td_m, td_d = td.split("-")
    tf_y, tf_m, tf_d = tf.split("-")
    if td == tf:
        dates_str = time_tag(tf, f"{int(tf_d)} {MOIS[int(tf_m) - 1]} {tf_y}")
    elif td_m == tf_m and td_y == tf_y:
        dates_str = time_periode(td, tf, f"{int(td_d)}", f"{int(tf_d)} {MOIS[int(tf_m) - 1]} {tf_y}",
                                 "\u2013")
    else:
        dates_str = time_periode(td, tf, f"{int(td_d)} {MOIS_ABBREV[int(td_m) - 1]}",
                                 f"{int(tf_d)} {MOIS_ABBREV[int(tf_m) - 1]} {tf_y}", " \u2013 ")

    # Échantillon
    ech = latest.get("echantillon")
    ech_str = fmt_ech(ech) if ech else ""

    # Header
    lines = []
    lines.append('<div class="bloc" id="dernier-sondage" style="padding:22px 28px 20px;">')
    lines.append('  <div class="ds-header">')
    lines.append('    <div class="section-label">Dernier sondage</div>')
    lines.append(f'    <span class="ds-institut">{institut}</span>')
    meta_parts = [dates_str]
    if ech_str:
        meta_parts.append(f"{ech_str}\u00a0personnes")
    lines.append(f'    <span class="ds-meta">{" · ".join(meta_parts)}</span>')
    lines.append(
        f'    <a href="sondages/{html_mod.escape(latest["id"])}.html" class="ds-fiche">Voir la fiche \u2192</a>'
    )
    lines.append("  </div>")

    # Top 4
    max_score = top4[0][1] if top4 else 1
    lines.append('  <div class="ds-top4">')
    for cid, v in top4:
        c = candidats.get(cid, {})
        nom = html_mod.escape(c.get("nom", cid))
        couleur = c.get("couleur", "#888")
        pct = v / max_score * 100
        lines.append('    <div class="ds-cand">')
        corps = [portrait(cid, c.get("nom", cid), couleur, photos),
                 f'<div class="ds-cand-name">{nom}</div>',
                 f'<div class="ds-cand-score">{v:.1f}<span class="pct"> %</span></div>']
        if cid in pages:
            lines.append(f'      <a class="ds-lien" href="{cid}.html">')
            lines.extend(f"        {x}" for x in corps)
            lines.append("      </a>")
        else:
            lines.extend(f"      {x}" for x in corps)
        lines.append(
            f'      <div class="ds-bar-wrap"><div class="ds-bar" style="width:{pct:.0f}%;background:{couleur}"></div></div>'
        )
        lines.append("    </div>")
    lines.append("  </div>")

    # Others
    if others:
        lines.append('  <div class="ds-others">')
        for cid, v in others:
            c = candidats.get(cid, {})
            nom = html_mod.escape(c.get("nom", cid))
            couleur = c.get("couleur", "#888")
            contenu = (f'<span class="ds-other-dot" style="background:{couleur}"></span>'
                       f'{nom} <b>{v:.1f}\u00a0%</b>')
            if cid in pages:
                contenu = f'<a class="ds-lien" href="{cid}.html">{contenu}</a>'
            lines.append(f"    <span>{contenu}</span>")
        lines.append("  </div>")

    lines.append("</div>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

def inject(content, begin, end, html_bloc):
    try:
        i_begin = content.index(begin)
        i_end = content.index(end) + len(end)
    except ValueError:
        raise ValueError(f"Marqueurs {begin} / {end} introuvables dans index.html")
    return content[:i_begin] + begin + "\n" + html_bloc + "\n" + end + content[i_end:]


def generate_source_partage(sondages):
    """Ligne de source sous le graphique, avec le bloc « Partager / Reprendre ».
    En veille électorale, sans le bloc : la page de partage n'est alors pas produite."""
    import veille
    # import tardif : partage_premier_tour importe lui-même ce module
    import partage_premier_tour
    f = partage_premier_tour.faits()
    return partage_premier_tour.source_html(f, avec_partage=not veille.en_veille()) if f else ""


def main():
    series_data = load_json(SERIES_PATH)
    candidats = load_json(CANDIDATS_PATH)
    sondages = load_all_sondages()

    content = INDEX_PATH.read_text(encoding="utf-8")

    # 1. Chapeau + repères factuels T1
    chapeau = generate_chapeau(series_data, sondages, candidats)
    ld_t1 = json.dumps(JSONLD_T1, ensure_ascii=False)
    reperes_t1 = (
        f'    {chapeau}\n'
        f'    <p class="subtitle">{REPERES_T1}</p>\n'
        f'    <script type="application/ld+json">{ld_t1}</script>'
    )
    content = inject(content, PT_BEGIN, PT_END, reperes_t1)

    # 2. Bloc « Dernier sondage » (nouveau bloc compact)
    bloc_ds = generate_bloc_dernier_sondage(sondages, candidats, series_data)
    content = inject(content, BLOC_DS_BEGIN, BLOC_DS_END, bloc_ds)

    # 3. Ligne de source et bloc « Partager / Reprendre » sous le graphique
    content = inject(content, SRC_BEGIN, SRC_END, generate_source_partage(sondages))

    INDEX_PATH.write_text(content, encoding="utf-8")
    print("Premier tour injecté dans index.html")


if __name__ == "__main__":
    main()
