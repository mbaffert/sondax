#!/usr/bin/env python3
"""Génère une page HTML par sondage dans site/sondages/<id>.html.

Données sources :
- data/sondages.json
- data/candidats.json
- data/derived/series-t1.json  (écart à la moyenne)
- scripts/bios.json (slugs avec page dédiée)
"""

import json
import math
import pathlib
import html as html_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SITE = ROOT / "site"

import sys
sys.path.insert(0, str(SCRIPTS))
from site_template import render_page
from instituts import charger_referentiel, lien_institut

referentiel = charger_referentiel()

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

# ---------- chargement ----------

sondages = json.loads((ROOT / "data" / "sondages.json").read_text(encoding="utf-8"))
candidats = json.loads((ROOT / "data" / "candidats.json").read_text(encoding="utf-8"))
bios = json.loads((SCRIPTS / "bios.json").read_text(encoding="utf-8"))

series_path = ROOT / "data" / "derived" / "series-t1.json"
series_data = json.loads(series_path.read_text(encoding="utf-8")) if series_path.exists() else {}

# Ensemble des slugs ayant une page dédiée
slugs_avec_page = set(bios.keys())


# ---------- index prev/next par institut ----------

sondages_by_institut: dict[str, list] = {}
for s in sorted(sondages, key=lambda s: s["terrain_fin"]):
    inst = s["institut"]
    sondages_by_institut.setdefault(inst, []).append(s)


def prev_next(sondage):
    """Retourne (prev_sondage, next_sondage) du même institut, ou (None, None)."""
    inst = sondage["institut"]
    lst = sondages_by_institut.get(inst, [])
    idx = next((i for i, s in enumerate(lst) if s["id"] == sondage["id"]), -1)
    if idx < 0:
        return None, None
    prev_s = lst[idx - 1] if idx > 0 else None
    next_s = lst[idx + 1] if idx < len(lst) - 1 else None
    return prev_s, next_s


# ---------- moyenne pondérée à une date ----------

def moyenne_a_date(cid, date_iso):
    """Retourne la valeur de la série lissée pour `cid` à `date_iso`, ou None."""
    pts = series_data.get("series", {}).get(cid, [])
    val = None
    for p in pts:
        if p["d"] > date_iso:
            break
        if p["v"] is not None:
            val = p["v"]
    return val


# ---------- helpers ----------

def candidate_full_name(cid):
    c = candidats.get(cid)
    if not c:
        return cid
    prenom = c.get("prenom", "")
    nom = c.get("nom", "")
    parts = [p for p in (prenom, nom) if p]
    return " ".join(parts) if parts else cid


def date_lettres(iso):
    """'2026-08-25' → '25 août 2026'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def fmt_ech(n):
    return f"{round(n):,}".replace(",", "\u202f")


def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",") + "\u202f%"


def marge_erreur(score, n):
    p = score / 100.0
    if n <= 0 or p <= 0 or p >= 1:
        return None
    return 1.96 * math.sqrt(p * (1 - p) / n) * 100


def candidate_link(cid, nom_complet):
    esc = html_mod.escape(nom_complet)
    if cid in slugs_avec_page:
        return f'<a href="../{html_mod.escape(cid)}.html">{esc}</a>'
    return esc


def is_type_parti(cid):
    return candidats.get(cid, {}).get("type") == "parti"


# ---------- construction d'une hypothèse ----------

def build_hypothesis_html(hyp, sondage_echantillon, is_principale, terrain_fin, label=""):
    tour = hyp.get("tour", "?")
    hyp_ech = hyp.get("echantillon")
    scores = hyp.get("scores", {})

    sorted_scores = sorted(
        ((cid, v) for cid, v in scores.items() if cid != "autre"),
        key=lambda kv: kv[1], reverse=True,
    )

    # Header
    parts = []
    if label:
        parts.append(label)
    if is_principale:
        parts.append('<span class="badge badge-principale">Principale</span>')
    if hyp_ech:
        parts.append(f'<span class="hyp-detail">{fmt_ech(hyp_ech)}\u202fpersonnes</span>')

    # Note marge approximative
    approx_me = not hyp_ech and sondage_echantillon
    n_for_me = hyp_ech if hyp_ech else sondage_echantillon

    # Colonnes : candidat, score, marge, (écart si principale T1)
    show_ecart = is_principale and tour == 1

    # En-tête de tableau
    cols_th = '<th>Candidat</th><th class="col-score">Score</th><th class="col-me">Marge</th>'
    if show_ecart:
        cols_th += '<th class="col-ecart">Écart / moy.</th>'

    rows = []
    for cid, score in sorted_scores:
        nom = candidate_full_name(cid)
        link = candidate_link(cid, nom)
        parti_cls = ' class="type-parti"' if is_type_parti(cid) else ""

        me = marge_erreur(score, n_for_me) if n_for_me else None
        me_str = f"±\u202f{me:.1f}\u202f%" if me is not None else "\u2014"
        if me is not None and approx_me:
            me_str += ' <span class="me-approx">(approx.)</span>'

        ecart_cell = ""
        if show_ecart:
            moy = moyenne_a_date(cid, terrain_fin)
            if moy is not None:
                delta = round(score - moy, 1)
                sign = "+" if delta > 0 else ""
                ecart_cell = f'<td class="col-ecart">{sign}{delta:.1f}'.replace(".", ",") + "\u202fpt</td>"
            else:
                ecart_cell = '<td class="col-ecart">\u2014</td>'

        couleur = candidats.get(cid, {}).get("couleur", "#888")
        bar_w = min(max(score, 0), 60)

        rows.append(
            f'    <tr{parti_cls}>'
            f'<td class="cand-name">{link}</td>'
            f'<td class="col-score"><span class="bar" style="width:{bar_w:.0f}%;background:{couleur}"></span>'
            f'{fmt_pct(score)}</td>'
            f'<td class="col-me">{me_str}</td>'
            f'{ecart_cell}'
            f'</tr>'
        )

    header_html = " ".join(parts)
    rows_html = "\n".join(rows)

    note = ""
    if approx_me:
        note = '<p class="note-approx">Marge approximative, calculée sur l\u2019échantillon total.</p>'

    return f"""<div class="hypothese{' hyp-principale' if is_principale else ''}">
  <div class="hyp-header">{header_html}</div>
  <table class="scores-table">
    <thead><tr>{cols_th}</tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
  {note}
</div>"""


def build_duel_html(hyp, sondage_echantillon):
    """Construit un bloc pour un duel de second tour."""
    scores = hyp.get("scores", {})
    hyp_ech = hyp.get("echantillon")
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if len(sorted_scores) != 2:
        return ""

    (cid_a, score_a), (cid_b, score_b) = sorted_scores
    nom_a = candidate_link(cid_a, candidate_full_name(cid_a))
    nom_b = candidate_link(cid_b, candidate_full_name(cid_b))
    couleur_a = candidats.get(cid_a, {}).get("couleur", "#888")
    couleur_b = candidats.get(cid_b, {}).get("couleur", "#888")

    n_for_me = hyp_ech if hyp_ech else sondage_echantillon
    me_a = marge_erreur(score_a, n_for_me) if n_for_me else None
    me_b = marge_erreur(score_b, n_for_me) if n_for_me else None
    me_a_str = f"±\u202f{me_a:.1f}\u202f%" if me_a else ""
    me_b_str = f"±\u202f{me_b:.1f}\u202f%" if me_b else ""

    return f"""<div class="duel">
  <div class="duel-bar">
    <span class="duel-part" style="width:{score_a:.1f}%;background:{couleur_a}"></span>
    <span class="duel-part" style="width:{score_b:.1f}%;background:{couleur_b}"></span>
  </div>
  <div class="duel-labels">
    <span class="duel-cand">{nom_a} <strong>{fmt_pct(score_a)}</strong> <span class="duel-me">{me_a_str}</span></span>
    <span class="duel-cand duel-cand-right">{nom_b} <strong>{fmt_pct(score_b)}</strong> <span class="duel-me">{me_b_str}</span></span>
  </div>
</div>"""


# ---------- page complète ----------

def build_page(sondage):
    sid = sondage["id"]
    institut = sondage.get("institut", "")
    terrain_debut = sondage.get("terrain_debut", "")
    terrain_fin = sondage.get("terrain_fin", "")
    echantillon = sondage.get("echantillon")
    population = sondage.get("population")
    url_source = sondage.get("url_source", "")
    hypotheses = sondage.get("hypotheses", [])

    # Titre et SEO
    date_titre = date_lettres(terrain_fin)
    title = f"Sondage {html_mod.escape(institut)} du {date_titre} \u2013 présidentielle 2027"
    canonical = f"https://sondax.fr/sondages/{html_mod.escape(sid)}.html"
    meta_desc = (
        f"Résultats du sondage {html_mod.escape(institut)} du {date_titre} "
        f"pour l\u2019élection présidentielle 2027 : scores, marges d\u2019erreur"
        f"{', duels de second tour' if any(h['tour'] == 2 for h in hypotheses) else ''}."
    )

    # Breadcrumb
    breadcrumb = (
        '<nav class="fil" aria-label="Fil d\u2019Ariane">'
        '<a href="../">Sondax</a> \u203a '
        '<a href="../sondages.html">Sondages</a>'
        '</nav>'
    )

    # En-tête sondage : date en lettres
    if terrain_debut and terrain_debut != terrain_fin:
        date_display = f"{date_lettres(terrain_debut)} \u2013 {date_lettres(terrain_fin)}"
    else:
        date_display = date_lettres(terrain_fin)

    # Métadonnées compactes
    meta_parts = [lien_institut(institut, referentiel, "../")]
    if echantillon:
        meta_parts.append(f"{fmt_ech(echantillon)}\u202fpersonnes")
    if population:
        meta_parts.append(html_mod.escape(str(population)))
    if url_source:
        esc = html_mod.escape(url_source)
        meta_parts.append(f'<a href="{esc}" target="_blank" rel="noopener">Notice</a>')

    meta_line = " · ".join(meta_parts)

    # Hypothèses T1 et T2
    t1 = [h for h in hypotheses if h.get("tour") == 1]
    t2 = [h for h in hypotheses if h.get("tour") == 2]

    # Tri T1 : principale d'abord, puis par nombre de candidats décroissant
    t1.sort(key=lambda h: (0 if h.get("principale") else 1, -len(h.get("scores", {}))))

    # Hypothèses T1 avec sous-titres numérotés
    hyps_html = []
    for i, hyp in enumerate(t1, 1):
        is_p = bool(hyp.get("principale"))
        label = f"Hypothèse\u00a0{i}" if len(t1) > 1 else ""
        hyps_html.append(build_hypothesis_html(hyp, echantillon, is_p, terrain_fin, label))

    # Duels T2
    duels_html = []
    for hyp in t2:
        duels_html.append(build_duel_html(hyp, echantillon))

    # Prev / next par institut
    prev_s, next_s = prev_next(sondage)
    nav_parts = []
    if prev_s:
        nav_parts.append(
            f'<a href="{html_mod.escape(prev_s["id"])}.html" class="nav-prev">'
            f'\u2190 {html_mod.escape(prev_s["institut"])} {fmt_date(prev_s["terrain_fin"])}</a>'
        )
    else:
        nav_parts.append('<span></span>')
    if next_s:
        nav_parts.append(
            f'<a href="{html_mod.escape(next_s["id"])}.html" class="nav-next">'
            f'{html_mod.escape(next_s["institut"])} {fmt_date(next_s["terrain_fin"])} \u2192</a>'
        )
    else:
        nav_parts.append('<span></span>')

    nav_html = f'<nav class="sondage-nav">{"".join(nav_parts)}</nav>'

    # Assemblage
    sections = []
    if hyps_html:
        sections.append(
            '<h2>Premier tour</h2>\n'
            + "\n".join(hyps_html)
        )
    if duels_html:
        sections.append(
            '<div class="section-sep"></div>'
            '<h2>Second tour</h2>\n'
            + "\n".join(duels_html)
        )

    body = f"""<main class="sondage-page">
  <div class="sondage-inner">
    {breadcrumb}
    <h1>{html_mod.escape(institut)}</h1>
    <p class="sondage-date">{date_display}</p>
    <p class="sondage-meta-line">{meta_line}</p>

    <div class="section-sep"></div>
    {chr(10).join(sections)}

    {nav_html}
  </div>
</main>"""

    return render_page(
        title=title,
        meta_description=meta_desc,
        canonical=canonical,
        body_content=body,
        extra_head=EXTRA_CSS,
        depth=1,
    )


EXTRA_CSS = """<style>
.sondage-page { padding: 24px 16px 40px; }
.sondage-inner { max-width: 780px; margin: 0 auto; }

.sondage-date {
  font-size: 15px; color: var(--gris); margin: -12px 0 4px;
}
.sondage-meta-line {
  font-size: 13.5px; color: var(--gris); margin-bottom: 0;
}
.sondage-meta-line a { font-weight: 500; }

.section-sep {
  border-top: 1px solid var(--bord); margin: 20px 0;
}

/* Hypothèses */
.hypothese { margin-bottom: 18px; }
.hyp-principale { border-left: 3px solid var(--bleu-vif); padding-left: 16px; }
.hyp-header {
  font-size: 14px; font-weight: 600; color: var(--bleu-nuit);
  margin-bottom: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.hyp-detail { font-weight: 400; color: var(--gris); font-size: 13px; }

.scores-table { font-size: 14px; }
.scores-table th { font-size: 11px; padding: 0 8px 6px 0; }
.scores-table td { padding: 5px 8px 5px 0; }
.scores-table tr:last-child td { border-bottom: none; }

.cand-name { min-width: 140px; font-weight: 500; }
.cand-name a { color: var(--texte); }
.cand-name a:hover { color: var(--bleu-vif); }
tr.type-parti .cand-name { font-style: italic; }

.col-score { white-space: nowrap; min-width: 130px; position: relative; }
.bar {
  display: inline-block; height: 6px; border-radius: 3px;
  vertical-align: middle; margin-right: 8px; min-width: 2px;
}
.col-me { font-size: 12.5px; color: var(--gris); white-space: nowrap; }
.me-approx { font-size: 10.5px; color: #aaa; }
.col-ecart { font-size: 12.5px; color: var(--gris); white-space: nowrap; text-align: right; }
.note-approx { font-size: 12px; color: var(--gris); font-style: italic; margin-top: 8px; }

/* Duels T2 */
.duels-section { margin-bottom: 18px; }
.duel { margin-bottom: 14px; }
.duel-bar {
  display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 6px;
}
.duel-part { display: block; height: 100%; }
.duel-labels {
  display: flex; justify-content: space-between; font-size: 14px;
}
.duel-cand strong { font-weight: 600; }
.duel-cand-right { text-align: right; }
.duel-me { font-size: 12px; color: var(--gris); }

/* Navigation prev/next */
.sondage-nav {
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 20px; border-top: 1px solid var(--bord); margin-top: 24px;
  font-size: 13.5px;
}
.nav-prev, .nav-next { color: var(--gris); }
.nav-prev:hover, .nav-next:hover { color: var(--bleu-vif); text-decoration: none; }

@media (max-width: 600px) {
  .col-ecart { display: none; }
  .col-me { font-size: 11.5px; }
  .bar { display: none; }
}
</style>"""


# ---------- génération ----------

out_dir = SITE / "sondages"
out_dir.mkdir(parents=True, exist_ok=True)

count = 0
for sondage in sondages:
    sid = sondage.get("id")
    if not sid:
        print(f"  skip  (sondage sans id)")
        continue

    html_out = out_dir / f"{sid}.html"
    html_content = build_page(sondage)
    html_out.write_text(html_content, encoding="utf-8")
    count += 1

print(f"\n{count} pages sondage générées dans site/sondages/")
