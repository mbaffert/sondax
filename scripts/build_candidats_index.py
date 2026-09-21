#!/usr/bin/env python3
"""Génère site/candidats/index.html — index de tous les candidats.

Liste les candidats avec leur nom, parti, dernier score (hypothèse principale
du sondage le plus récent où ils apparaissent) et la date de ce sondage.
Triés par score décroissant.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

sys.path.insert(0, str(ROOT / "scripts"))
from site_template import render_page

# ---------- chargement ----------

candidats = json.loads((ROOT / "data" / "candidats.json").read_text(encoding="utf-8"))
series_data = json.loads((ROOT / "data" / "derived" / "series-t1.json").read_text(encoding="utf-8"))
sondages = json.loads((ROOT / "data" / "sondages.json").read_text(encoding="utf-8"))
bios = json.loads((ROOT / "scripts" / "bios.json").read_text(encoding="utf-8"))

# ---------- helpers ----------

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def date_lettres(iso):
    """'2026-09-10' → '10 septembre 2026'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",") + "\u00a0%"


def candidate_display_name(slug, cand):
    """Retourne le nom d'affichage du candidat."""
    if cand.get("type") == "parti":
        return cand.get("label", cand.get("nom", slug))
    prenom = cand.get("prenom", "")
    nom = cand.get("nom", slug)
    if prenom:
        return f"{prenom} {nom}"
    return nom


def candidate_parti(slug, cand):
    """Retourne le parti du candidat."""
    return cand.get("parti", "")


# ---------- calcul du dernier score par candidat ----------
# Pour chaque candidat, cherche le sondage le plus récent (terrain_fin)
# contenant une hypothèse principale de T1 avec ce candidat.

sondages_sorted = sorted(sondages, key=lambda s: s["terrain_fin"], reverse=True)

rows = []
for slug, cand in candidats.items():
    last_score = None
    last_date = None

    for s in sondages_sorted:
        for h in s["hypotheses"]:
            if h.get("tour") != 1:
                continue
            if not h.get("principale"):
                continue
            scores = h.get("scores", {})
            if slug not in scores:
                continue
            last_score = scores[slug]
            last_date = s["terrain_fin"]
            break
        if last_score is not None:
            break

    if last_score is None:
        # Candidat sans mesure dans une hypothèse principale : on l'inclut quand même
        # avec score None (sera affiché en bas)
        pass

    display_name = candidate_display_name(slug, cand)
    parti = candidate_parti(slug, cand)
    has_page = slug in bios

    rows.append({
        "slug": slug,
        "display_name": display_name,
        "parti": parti,
        "score": last_score,
        "date": last_date,
        "has_page": has_page,
    })

# Tri : score décroissant (None en bas)
rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))

# ---------- construction du HTML ----------

table_rows = []
for r in rows:
    slug = r["slug"]
    display_name = r["display_name"]
    parti = r["parti"]
    score = r["score"]
    date_iso = r["date"]
    has_page = r["has_page"]

    if has_page:
        name_cell = f'<a href="../{slug}.html">{display_name}</a>'
    else:
        name_cell = display_name

    score_cell = fmt_pct(score) if score is not None else "\u2014"
    date_cell = date_lettres(date_iso) if date_iso else "\u2014"

    table_rows.append(
        f"      <tr>"
        f"<td>{name_cell}</td>"
        f"<td>{parti}</td>"
        f"<td style=\"text-align:right;font-variant-numeric:tabular-nums;\">{score_cell}</td>"
        f"<td>{date_cell}</td>"
        f"</tr>"
    )

table_html = (
    "    <table>\n"
    "      <tr>"
    "<th>Candidat</th>"
    "<th>Parti</th>"
    "<th style=\"text-align:right;\">Score</th>"
    "<th>Dernière mesure</th>"
    "</tr>\n"
    + "\n".join(table_rows) + "\n"
    "    </table>"
)

body_content = f"""<main>
  <p class="fil"><a href="../">Sondax</a> › Candidats</p>
  <h1>Candidats</h1>
{table_html}
</main>"""

html = render_page(
    title="Candidats — Sondax",
    meta_description=(
        "Liste de tous les candidats à l'élection présidentielle française de 2027 "
        "avec leurs derniers scores dans les sondages du premier tour."
    ),
    canonical="https://sondax.fr/candidats/",
    body_content=body_content,
    depth=1,
)

# ---------- écriture ----------

out_dir = SITE / "candidats"
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "index.html"
out_file.write_text(html, encoding="utf-8")
print(f"  OK  {out_file.relative_to(ROOT)}")
