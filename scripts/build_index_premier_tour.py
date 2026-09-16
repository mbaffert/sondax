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
)

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

PT_BEGIN = "<!-- BEGIN:premier-tour -->"
PT_END = "<!-- END:premier-tour -->"
FICHE_BEGIN = "<!-- BEGIN:dernier-sondage -->"
FICHE_END = "<!-- END:dernier-sondage -->"
DS_BEGIN = "<!-- BEGIN:derniers-sondages -->"
DS_END = "<!-- END:derniers-sondages -->"


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

def generate_chapeau(series_data, sondages, candidats):
    """Trois phrases : leader, volume, delta 3 mois."""
    series = series_data.get("series", {})
    date_fin = series_data.get("date_fin", "")

    # Dernière valeur non-null par candidat
    latest = {}
    for cid, pts in series.items():
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
    # type: parti → pas de "arrive en tête"
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

    # Phrase 2 : volume et instituts
    # Fenêtre de 6 mois (période par défaut)
    fin = date.fromisoformat(date_fin)
    debut_6m = (fin - timedelta(days=180)).isoformat()
    sondages_fenetre = [s for s in sondages if s["terrain_fin"] >= debut_6m]
    n_sondages = len(sondages_fenetre)
    instituts = sorted(set(s["institut"] for s in sondages_fenetre))

    debut_date_lettres = date_lettres(debut_6m)
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

    # Phrase 3 : delta 3 mois du leader (optionnel)
    phrase3 = ""
    debut_3m = (fin - timedelta(days=90)).isoformat()
    leader_pts = series.get(leader_cid, [])
    v_3m_ago = None
    for p in leader_pts:
        if p["d"] <= debut_3m and p["v"] is not None:
            v_3m_ago = p["v"]
    if v_3m_ago is not None:
        delta = leader_v - v_3m_ago
        nom_court = candidats.get(leader_cid, {}).get("nom", leader_cid)
        if abs(delta) >= 0.1:
            delta_fmt = f"{abs(delta):.1f}".replace(".", ",")
            pts = "point" if abs(delta) < 1.5 else "points"
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
# Bloc « Dernier sondage publié »
# ---------------------------------------------------------------------------

def generate_dernier_sondage(sondages, candidats):
    """Génère le bloc du dernier sondage publié."""
    latest = select_latest_sondage(sondages)
    if not latest:
        return ""

    hyp = select_hypothesis(latest, candidats)
    if not hyp:
        return ""

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

    # Scores de l'hypothèse, tri décroissant, "autre" exclu
    scores = hyp.get("scores", {})
    sorted_scores = sorted(
        ((cid, s) for cid, s in scores.items() if cid != "autre"),
        key=lambda x: -x[1],
    )

    score_lines = []
    for cid, score in sorted_scores:
        nom = html_mod.escape(candidate_full_name(cid, candidats))
        score_lines.append(
            f'        <tr><td>{nom}</td>'
            f'<td style="text-align:right;font-variant-numeric:tabular-nums;">'
            f'{fmt_pct(score)}</td></tr>'
        )

    meta_parts = [f"{source_label}, {dates_str}"]
    if ech_str:
        meta_parts.append(ech_str)

    return (
        '    <div class="dernier-sondage" id="dernier-sondage">\n'
        '      <h3 style="font-family:var(--titre);font-size:18px;font-weight:600;'
        'margin:14px 0 6px;">Dernier sondage publié</h3>\n'
        f'      <p class="subtitle" style="margin-bottom:8px;">'
        f'{" · ".join(meta_parts)}. '
        f'<a href="sondages.html" style="font-weight:500;">Voir la fiche</a></p>\n'
        f'      <table class="t2-table" style="max-width:420px;">\n'
        + "\n".join(score_lines) + "\n"
        f'      </table>\n'
        '    </div>'
    )


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

    # 1. Chapeau seul dans la section premier tour
    chapeau = generate_chapeau(series_data, sondages, candidats)
    content = inject(content, PT_BEGIN, PT_END, f"    {chapeau}")

    # 2. Fiche du dernier sondage dans la section Explorer
    dernier = generate_dernier_sondage(sondages, candidats)
    content = inject(content, FICHE_BEGIN, FICHE_END, dernier)

    # 3. Derniers sondages agrégés
    ds_html = generate_derniers_sondages(sondages)
    content = inject(content, DS_BEGIN, DS_END, ds_html)

    INDEX_PATH.write_text(content, encoding="utf-8")
    print("Premier tour injecté dans index.html")


if __name__ == "__main__":
    main()
