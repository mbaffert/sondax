"""Injecte le contenu statique du premier tour dans site/index.html.

Lit data/derived/series-t1.json, data/sondages.json et data/candidats.json.
Génère le chapeau, le bloc « Dernier sondage publié » et le tableau des
derniers sondages agrégés, et les remplace entre leurs marqueurs respectifs.

Tout le contenu est rendu au build et présent dans le HTML servi.
"""

import json, pathlib, sys, html as html_mod
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "site" / "index.html"
SERIES_PATH = ROOT / "data" / "derived" / "series-t1.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"

sys.path.insert(0, str(ROOT / "scripts"))
from build_header import (
    select_hypothesis, select_latest_sondage, candidate_full_name, load_all_sondages,
    REPERES_T1, JSONLD_T1,
)

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

PT_BEGIN = "<!-- BEGIN:premier-tour -->"
PT_END = "<!-- END:premier-tour -->"
META_BEGIN = "<!-- BEGIN:dernier-sondage -->"
META_END = "<!-- END:dernier-sondage -->"
SCORES_BEGIN = "<!-- BEGIN:fiche-scores -->"
SCORES_END = "<!-- END:fiche-scores -->"
DS_BEGIN = "<!-- BEGIN:derniers-sondages -->"
DS_END = "<!-- END:derniers-sondages -->"
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


def generate_chapeau(series_data, sondages, candidats):
    """Trois phrases : leader, volume, delta 3 mois.

    Seuls les candidats ayant au moins une mesure dans la fenêtre glissante
    de 30 jours (§4 SPEC) sont retenus.
    """
    series = series_data.get("series", {})
    date_fin = series_data.get("date_fin", "")
    fenetre = series_data.get("fenetre_jours", 30)

    # Candidats testés dans la fenêtre de 30 jours
    cands_actifs = candidates_in_window(series_data, fenetre)

    # Dernière valeur de tendance pour chaque candidat actif
    latest = {}
    for cid in cands_actifs:
        pts = series.get(cid, [])
        for p in reversed(pts):
            if p["v"] is not None:
                latest[cid] = p["v"]
                break

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
    debut_fenetre = (fin - timedelta(days=fenetre)).isoformat()
    sondages_fenetre = [s for s in sondages if s["terrain_fin"] >= debut_fenetre]
    n_sondages = len(sondages_fenetre)
    instituts = sorted(set(s["institut"] for s in sondages_fenetre))

    debut_date_lettres = date_lettres(debut_fenetre)
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
# Tableau d'hypothèse (même présentation que les pages sondage ; le JS
# de index.html produit le même balisage quand on change de sélection)
# ---------------------------------------------------------------------------

BIOS_PATH = ROOT / "scripts" / "bios.json"


def _moyenne_a_date(series_data, cid, date_iso):
    val = None
    for p in series_data.get("series", {}).get(cid, []):
        if p["d"] > date_iso:
            break
        if p["v"] is not None:
            val = p["v"]
    return val


def render_hypothese(hyp, sondage, candidats, series_data):
    import math
    slugs = set(load_json(BIOS_PATH).keys())
    ech = sondage.get("echantillon")
    hyp_ech = hyp.get("echantillon")
    n = hyp_ech or ech
    approx = not hyp_ech and bool(ech)
    is_p = bool(hyp.get("principale"))

    head = []
    if is_p:
        head.append('<span class="badge badge-principale">Principale</span>')
    if hyp_ech:
        head.append(f'<span class="hyp-detail">{fmt_ech(hyp_ech)}\u202fpersonnes</span>')

    th = '<th>Candidat</th><th class="col-score">Score</th><th class="col-me">Marge</th>'
    if is_p:
        th += '<th class="col-ecart">Écart / moy.</th>'

    rows = []
    for cid, v in sorted(((c, x) for c, x in hyp.get("scores", {}).items() if c != "autre"),
                         key=lambda kv: -kv[1]):
        c = candidats.get(cid, {})
        nom = html_mod.escape(" ".join(x for x in (c.get("prenom"), c.get("nom")) if x) or cid)
        if cid in slugs:
            nom = f'<a href="{html_mod.escape(cid)}.html">{nom}</a>'
        parti = ' class="type-parti"' if c.get("type") == "parti" else ""
        p = v / 100
        me = "\u2014"
        if n and 0 < p < 1:
            me = f"±\u202f{1.96 * math.sqrt(p * (1 - p) / n) * 100:.1f}".replace(".", ",") + "\u202f%"
            if approx:
                me += ' <span class="me-approx">(approx.)</span>'
        ecart = ""
        if is_p:
            moy = _moyenne_a_date(series_data, cid, sondage["terrain_fin"])
            if moy is not None:
                d = round(v - moy, 1)
                ecart = f'<td class="col-ecart">{"+" if d > 0 else ""}{d:.1f}'.replace(".", ",") + "\u202fpt</td>"
            else:
                ecart = '<td class="col-ecart">\u2014</td>'
        w = min(max(v, 0), 60)
        rows.append(
            f'<tr{parti}><td class="cand-name">{nom}</td>'
            f'<td class="col-score"><span class="bar" style="--w:{w:.0f};background:{c.get("couleur", "#888")}"></span>{fmt_pct(v)}</td>'
            f'<td class="col-me">{me}</td>{ecart}</tr>'
        )

    out = f'<div class="hypothese{" hyp-principale" if is_p else ""}">'
    if head:
        out += f'<div class="hyp-header">{" ".join(head)}</div>'
    out += f'<table class="scores-table"><thead><tr>{th}</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
    if approx:
        out += '<p class="note-approx">Marge approximative, calculée sur l\u2019échantillon total.</p>'
    out += "</div>"
    return out

# ---------------------------------------------------------------------------
# Bloc « Dernier sondage publié »
# ---------------------------------------------------------------------------

def generate_dernier_sondage(sondages, candidats, series_data):
    """Génère la ligne de métadonnées et le tableau de scores du dernier sondage.

    Retourne (meta_html, scores_html).
    """
    latest = select_latest_sondage(sondages)
    if not latest:
        return "", ""

    hyp = select_hypothesis(latest, candidats)
    if not hyp:
        return "", ""

    # Institut + commanditaire
    institut = html_mod.escape(latest["institut"])
    commanditaire = latest.get("commanditaire")
    source_label = institut
    if commanditaire:
        source_label += f" pour {html_mod.escape(commanditaire)}"

    # Dates en toutes lettres
    td = date_lettres(latest["terrain_debut"])
    tf = date_lettres(latest["terrain_fin"])
    if latest["terrain_debut"] == latest["terrain_fin"]:
        dates_str = f"le {tf}"
    else:
        dates_str = f"du {td} au {tf}"

    # Échantillon
    ech = latest.get("echantillon")
    ech_str = f"{fmt_ech(ech)}\u00a0personnes" if ech else ""
    pop = latest.get("population")
    if pop and ech_str:
        ech_str += f" ({html_mod.escape(pop)})"

    meta_parts = [f"{source_label}, {dates_str}"]
    if ech_str:
        meta_parts.append(ech_str)

    meta_html = (
        f'    <p class="fiche-meta" id="fiche-meta">'
        f'{" · ".join(meta_parts)}'
        f' · <a href="sondages/{html_mod.escape(latest["id"])}.html" style="font-weight:500;">Voir la fiche</a></p>'
    )

    scores_html = render_hypothese(hyp, latest, candidats, series_data)
    return meta_html, scores_html


# ---------------------------------------------------------------------------
# Bloc « Dernier sondage » (nouveau bloc compact en haut de page)
# ---------------------------------------------------------------------------

MOIS_ABBREV = [
    "janv.", "fév.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]


def generate_bloc_dernier_sondage(sondages, candidats, series_data):
    """Génère le bloc compact « Dernier sondage » affiché en haut de page."""
    latest = select_latest_sondage(sondages)
    if not latest:
        return ""

    hyp = select_hypothesis(latest, candidats)
    if not hyp:
        return ""

    scores_raw = hyp.get("scores", {})
    # Tri décroissant, sans "autre"
    scores = sorted(
        ((cid, v) for cid, v in scores_raw.items() if cid != "autre"),
        key=lambda kv: -kv[1],
    )
    top4 = scores[:4]
    others = scores[4:]

    institut = html_mod.escape(latest["institut"])

    # Dates
    td = latest["terrain_debut"]
    tf = latest["terrain_fin"]
    td_y, td_m, td_d = td.split("-")
    tf_y, tf_m, tf_d = tf.split("-")
    if td == tf:
        dates_str = f"{int(tf_d)} {MOIS[int(tf_m) - 1]} {tf_y}"
    elif td_m == tf_m and td_y == tf_y:
        dates_str = f"{int(td_d)}\u2013{int(tf_d)} {MOIS[int(tf_m) - 1]} {tf_y}"
    else:
        dates_str = (
            f"{int(td_d)} {MOIS_ABBREV[int(td_m) - 1]} \u2013 "
            f"{int(tf_d)} {MOIS_ABBREV[int(tf_m) - 1]} {tf_y}"
        )

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
        lines.append(f'      <div class="ds-cand-name">{nom}</div>')
        lines.append(f'      <div class="ds-cand-score">{v:.1f}<span class="pct"> %</span></div>')
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
            lines.append(
                f'    <span><span class="ds-other-dot" style="background:{couleur}"></span>'
                f'{nom} <b>{v:.1f}\u00a0%</b></span>'
            )
        lines.append("  </div>")

    lines.append("</div>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tableau des derniers sondages agrégés
# ---------------------------------------------------------------------------

def generate_derniers_sondages(sondages):
    """Table HTML des 5 derniers sondages."""
    sorted_s = sorted(sondages, key=lambda s: s["terrain_fin"], reverse=True)[:5]

    rows = ['    <tr><th>Institut</th><th>Date</th><th>Échantillon</th><th>Source</th></tr>']
    for s in sorted_s:
        institut = html_mod.escape(s["institut"])
        d = s["terrain_fin"].split("-")
        date_str = f"{d[2]}/{d[1]}/{d[0]}"
        ech = fmt_ech(s["echantillon"]) if s.get("echantillon") else "\u2014"
        source = (
            f'<a href="{html_mod.escape(s["url_source"])}" target="_blank">Notice</a>'
            if s.get("url_source") else "\u2014"
        )
        rows.append(f'    <tr><td>{institut}</td><td>{date_str}</td><td>{ech}</td><td>{source}</td></tr>')

    return (
        '  <div class="bloc" id="bloc-derniers">\n'
        '    <div class="section-label">Traçabilité</div>\n'
        '    <h2>Derniers sondages agrégés</h2>\n'
        '    <table class="sondages-table" id="table-derniers">\n'
        + "\n".join(rows) + "\n"
        '    </table>\n'
        '    <a href="sondages.html" class="voir-tous">Voir tous les sondages</a>\n'
        '  </div>'
    )


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

    # 3. Fiche du dernier sondage : meta + scores
    meta_html, scores_html = generate_dernier_sondage(sondages, candidats, series_data)
    content = inject(content, META_BEGIN, META_END, meta_html)
    content = inject(content, SCORES_BEGIN, SCORES_END, scores_html)

    # 4. Derniers sondages agrégés
    ds_html = generate_derniers_sondages(sondages)
    content = inject(content, DS_BEGIN, DS_END, ds_html)

    INDEX_PATH.write_text(content, encoding="utf-8")
    print("Premier tour injecté dans index.html")


if __name__ == "__main__":
    main()
