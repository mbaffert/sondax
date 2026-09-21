#!/usr/bin/env python3
"""Génère une page HTML par sondage dans site/sondages/<id>.html.

Données sources :
- data/sondages.json
- data/candidats.json
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

# ---------- chargement ----------

sondages = json.loads((ROOT / "data" / "sondages.json").read_text(encoding="utf-8"))
candidats = json.loads((ROOT / "data" / "candidats.json").read_text(encoding="utf-8"))
bios = json.loads((SCRIPTS / "bios.json").read_text(encoding="utf-8"))

# Ensemble des slugs ayant une page dédiée
slugs_avec_page = set(bios.keys())


# ---------- helpers ----------

def candidate_full_name(cid, candidats):
    """Retourne prénom + nom depuis candidats.json, ou l'identifiant en fallback."""
    c = candidats.get(cid)
    if not c:
        return cid
    prenom = c.get("prenom", "")
    nom = c.get("nom", "")
    parts = [p for p in (prenom, nom) if p]
    return " ".join(parts) if parts else cid


def fmt_date(iso):
    """Formate une date ISO YYYY-MM-DD en JJ/MM/AAAA."""
    try:
        y, m, d = iso.split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return iso


def fmt_ech(n):
    """Formate un nombre avec espace fine comme séparateur de milliers."""
    return f"{round(n):,}".replace(",", "\u202f")


def marge_erreur(score, n):
    """Calcule la marge d'erreur à 95 % (1,96 × sqrt(p(1-p)/n))."""
    p = score / 100.0
    if n <= 0 or p <= 0 or p >= 1:
        return None
    return 1.96 * math.sqrt(p * (1 - p) / n)


def candidate_link(cid, nom_complet):
    """Retourne un lien HTML vers la page du candidat si elle existe, sinon le nom brut."""
    esc = html_mod.escape(nom_complet)
    if cid in slugs_avec_page:
        return f'<a href="../{html_mod.escape(cid)}.html">{esc}</a>'
    return esc


def build_hypothesis_html(hyp, sondage_echantillon, is_principale):
    """Construit le bloc HTML pour une hypothèse."""
    tour = hyp.get("tour", "?")
    hyp_ech = hyp.get("echantillon")
    scores = hyp.get("scores", {})

    # Tri des scores décroissant
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    # Badge principale
    badge = ' <span class="badge-principale">Principale</span>' if is_principale else ""

    # Label tour
    tour_label = f"Tour {tour}"

    # Échantillon de l'hypothèse
    if hyp_ech:
        ech_label = f"Échantillon&nbsp;: {fmt_ech(hyp_ech)}"
        ech_note = ""
    else:
        ech_label = ""
        ech_note = ""

    # En-tête hypothèse
    header_parts = [f'<span class="hyp-tour">{html_mod.escape(str(tour_label))}</span>{badge}']
    if ech_label:
        header_parts.append(f'<span class="hyp-ech">{ech_label}</span>')

    rows_html = []
    for cid, score in sorted_scores:
        nom = candidate_full_name(cid, candidats)
        link_html = candidate_link(cid, nom)

        # Calcul marge d'erreur
        n_for_me = hyp_ech if hyp_ech else sondage_echantillon
        me = marge_erreur(score, n_for_me) if n_for_me else None

        if me is not None:
            me_str = f"±\u202f{me:.1f}\u202f%"
            if not hyp_ech and sondage_echantillon:
                me_str += ' <span class="me-approx" title="Calculée sur l\'échantillon total du sondage">(approx.)</span>'
        else:
            me_str = "\u2014"

        # Barre de progression
        bar_width = min(max(score, 0), 100)

        rows_html.append(f"""    <tr>
      <td class="cand-name">{link_html}</td>
      <td class="cand-score">
        <span class="score-val">{score:.1f}\u202f%</span>
        <span class="score-bar-wrap"><span class="score-bar" style="width:{bar_width:.1f}%"></span></span>
      </td>
      <td class="cand-me">{me_str}</td>
    </tr>""")

    rows_joined = "\n".join(rows_html)

    # Note marge approximative si applicable
    note_me = ""
    if not hyp_ech and sondage_echantillon:
        note_me = (
            '<p class="note-me">La marge d\u2019erreur est approximative\u202f: '
            'calculée sur l\u2019\u00e9chantillon total du sondage, '
            'faute d\u2019\u00e9chantillon propre à cette hypothèse.</p>'
        )

    header_html = " \u2014 ".join(header_parts)

    return f"""<div class="hypothese{'  hypothese-principale' if is_principale else ''}">
  <div class="hyp-header">{header_html}</div>
  <table class="scores-table">
    <thead><tr>
      <th>Candidat·e</th>
      <th>Score</th>
      <th>Marge d\u2019erreur (95\u202f%)</th>
    </tr></thead>
    <tbody>
{rows_joined}
    </tbody>
  </table>
  {note_me}
</div>"""


def build_page(sondage):
    sid = sondage["id"]
    institut = sondage.get("institut", "")
    terrain_debut = sondage.get("terrain_debut", "")
    terrain_fin = sondage.get("terrain_fin", "")
    echantillon = sondage.get("echantillon")
    population = sondage.get("population")
    url_source = sondage.get("url_source", "")
    hypotheses = sondage.get("hypotheses", [])

    # Trier les hypothèses : principale d'abord
    def hyp_sort_key(h):
        return (0 if h.get("principale") else 1, h.get("tour", 99))

    sorted_hyps = sorted(hypotheses, key=hyp_sort_key)

    # Métadonnées sondage
    date_label = fmt_date(terrain_fin)
    title = f"{html_mod.escape(institut)} — {date_label} — Sondax"
    canonical = f"https://sondax.fr/sondages/{html_mod.escape(sid)}.html"
    meta_desc = (
        f"Résultats du sondage {html_mod.escape(institut)} du {date_label} "
        f"pour l\u2019\u00e9lection pr\u00e9sidentielle 2027."
    )

    # Breadcrumb
    breadcrumb = (
        f'<nav class="breadcrumb" aria-label="Fil d\u2019Ariane">'
        f'<a href="../index.html">Sondax</a>'
        f' \u203a <a href="../sondages.html">Sondages</a>'
        f' \u203a <span>{html_mod.escape(institut)} {date_label}</span>'
        f'</nav>'
    )

    # Fiche sondage
    meta_items = []
    meta_items.append(f'<dt>Institut</dt><dd>{html_mod.escape(institut)}</dd>')
    if terrain_debut:
        meta_items.append(f'<dt>Terrain</dt><dd>{fmt_date(terrain_debut)}\u202f\u2013\u202f{fmt_date(terrain_fin)}</dd>')
    else:
        meta_items.append(f'<dt>Date de terrain</dt><dd>{fmt_date(terrain_fin)}</dd>')
    if echantillon:
        meta_items.append(f'<dt>\u00c9chantillon</dt><dd>{fmt_ech(echantillon)}\u202fpersonnes</dd>')
    if population:
        meta_items.append(f'<dt>Population</dt><dd>{html_mod.escape(str(population))}</dd>')
    if url_source:
        esc_url = html_mod.escape(url_source)
        meta_items.append(
            f'<dt>Source</dt>'
            f'<dd><a href="{esc_url}" target="_blank" rel="noopener">Notice (Commission des sondages)</a></dd>'
        )

    meta_html = '<dl class="sondage-meta">\n  ' + "\n  ".join(meta_items) + "\n</dl>"

    # Hypothèses
    hyps_html_parts = []
    for hyp in sorted_hyps:
        is_principale = bool(hyp.get("principale"))
        hyps_html_parts.append(build_hypothesis_html(hyp, echantillon, is_principale))

    hyps_html = "\n".join(hyps_html_parts)

    # Nombre d'hypothèses dans le titre de section
    n_hyp = len(sorted_hyps)
    hyps_section_title = (
        f"{n_hyp}\u202fhypoth\u00e8se" if n_hyp == 1
        else f"{n_hyp}\u202fhypoth\u00e8ses"
    )

    body = f"""<main class="sondage-page">
  <div class="sondage-inner">
    {breadcrumb}

    <h1 class="sondage-title">
      {html_mod.escape(institut)}
      <span class="sondage-date">{fmt_date(terrain_debut)}\u202f\u2013\u202f{fmt_date(terrain_fin)}</span>
    </h1>

    {meta_html}

    <section class="hypotheses-section">
      <h2>{hyps_section_title}</h2>
      {hyps_html}
    </section>
  </div>
</main>"""

    extra_css = """<style>
.sondage-page { padding: 24px 16px 60px; }
.sondage-inner { max-width: 860px; margin: 0 auto; }

.breadcrumb { font-size: 13px; color: var(--gris); margin-bottom: 18px; }
.breadcrumb a { color: var(--gris); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }

.sondage-title {
  font-family: var(--titre);
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 700;
  color: var(--bleu-nuit);
  margin-bottom: 18px;
  line-height: 1.2;
}
.sondage-date {
  display: inline-block;
  font-size: 0.65em;
  font-weight: 500;
  color: var(--gris);
  margin-left: 10px;
}

.sondage-meta {
  background: var(--carte);
  border: 1px solid var(--bord);
  border-radius: 10px;
  padding: 16px 20px;
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 16px;
  font-size: 14px;
  margin-bottom: 32px;
}
.sondage-meta dt { color: var(--gris); font-weight: 500; }
.sondage-meta dd { margin: 0; }

.hypotheses-section h2 {
  font-family: var(--titre);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--bleu-nuit);
  margin-bottom: 18px;
}

.hypothese {
  background: var(--carte);
  border: 1px solid var(--bord);
  border-radius: 10px;
  padding: 18px 20px 14px;
  margin-bottom: 18px;
}
.hypothese-principale {
  border-color: var(--bleu-vif);
  border-width: 2px;
}

.hyp-header {
  font-size: 14px;
  font-weight: 600;
  color: var(--bleu-nuit);
  margin-bottom: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.hyp-tour { font-size: 15px; }
.hyp-ech { font-weight: 400; color: var(--gris); font-size: 13px; }

.badge-principale {
  background: var(--bleu-vif);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  letter-spacing: 0.03em;
}

.scores-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.scores-table th {
  text-align: left;
  color: var(--gris);
  font-weight: 500;
  font-size: 12px;
  padding: 0 8px 8px 0;
  border-bottom: 1px solid var(--bord);
}
.scores-table td {
  padding: 7px 8px 7px 0;
  border-bottom: 1px solid var(--bord);
  vertical-align: middle;
}
.scores-table tr:last-child td { border-bottom: none; }

.cand-name { min-width: 160px; font-weight: 500; }
.cand-score { min-width: 180px; }
.score-val { font-family: var(--mono); font-size: 13.5px; margin-right: 8px; }
.score-bar-wrap {
  display: inline-block;
  width: 100px;
  height: 8px;
  background: #e8eaf0;
  border-radius: 4px;
  vertical-align: middle;
}
.score-bar {
  display: block;
  height: 100%;
  background: var(--bleu-vif);
  border-radius: 4px;
}
.cand-me { font-family: var(--mono); font-size: 12.5px; color: var(--gris); white-space: nowrap; }

.me-approx { color: #aaa; font-family: var(--corps); font-size: 11px; }
.note-me {
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--gris);
  font-style: italic;
}

@media (max-width: 600px) {
  .score-bar-wrap { display: none; }
  .scores-table th:last-child,
  .scores-table td:last-child { display: none; }
}
</style>"""

    return render_page(
        title=title,
        meta_description=meta_desc,
        canonical=canonical,
        body_content=body,
        extra_head=extra_css,
        depth=1,
    )


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
    print(f"  OK  sondages/{sid}.html")

print(f"\n{count} pages sondage générées dans site/sondages/")
