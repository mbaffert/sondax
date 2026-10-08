"""Injecte le contenu statique de site/sondages.html.

- Module « Explorer les sondages » (#bloc-fiche) : ligne de métadonnées et
  tableau de l'hypothèse principale du dernier sondage publié. Le script
  assets/explorer-sondages.js produit le même balisage quand on change de
  sélection.
- Tableau complet des sondages. Le JavaScript garde le filtrage ; le HTML
  statique contient toutes les données pour l'indexation.
"""

import json, math, pathlib, sys, html as html_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from instituts import charger_referentiel, lien_institut
from balise_time import time_tag
from build_header import select_hypothesis, select_latest_sondage
from sondages_io import charger as charger_sondages

SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
BIOS_PATH = ROOT / "scripts" / "bios.json"
SONDAGES_HTML = ROOT / "site" / "sondages.html"

BEGIN = "<!-- BEGIN:table-sondages -->"
END = "<!-- END:table-sondages -->"
META_BEGIN = "<!-- BEGIN:dernier-sondage -->"
META_END = "<!-- END:dernier-sondage -->"
SCORES_BEGIN = "<!-- BEGIN:fiche-scores -->"
SCORES_END = "<!-- END:fiche-scores -->"

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def fmt_ech(n):
    return f"{round(n):,}".replace(",", "\u202f")


def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",") + "\u00a0%"


def date_lettres(iso):
    """'2026-09-10' → '10 septembre 2026'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


# ---------------------------------------------------------------------------
# Module « Explorer les sondages » : état initial (dernier sondage publié,
# hypothèse principale)
# ---------------------------------------------------------------------------

def render_hypothese(hyp, sondage, candidats):
    slugs = set(json.loads(BIOS_PATH.read_text(encoding="utf-8")).keys())
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

    th = '<th>Candidat</th><th class="col-score">Score</th><th class="col-me">Marge d\u2019erreur</th>'

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
        w = min(max(v, 0), 60)
        rows.append(
            f'<tr{parti}><td class="cand-name">{nom}</td>'
            f'<td class="col-score"><span class="bar" style="--w:{w:.0f};background:{c.get("couleur", "#888")}"></span>{fmt_pct(v)}</td>'
            f'<td class="col-me">{me}</td></tr>'
        )

    out = f'<div class="hypothese{" hyp-principale" if is_p else ""}">'
    if head:
        out += f'<div class="hyp-header">{" ".join(head)}</div>'
    out += f'<table class="scores-table"><thead><tr>{th}</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
    if approx:
        out += '<p class="note-approx">Marge approximative, calculée sur l\u2019échantillon total.</p>'
    out += "</div>"
    return out


def generate_fiche(sondages, candidats, referentiel):
    """Ligne de métadonnées et tableau de scores du dernier sondage publié.

    Retourne (meta_html, scores_html).
    """
    latest = select_latest_sondage(sondages)
    if not latest:
        return "", ""

    hyp = select_hypothesis(latest, candidats)
    if not hyp:
        return "", ""

    # Institut + commanditaire
    source_label = lien_institut(latest["institut"], referentiel)
    commanditaire = latest.get("commanditaire")
    if commanditaire:
        source_label += f" pour {html_mod.escape(commanditaire)}"

    # Dates en toutes lettres
    td = time_tag(latest["terrain_debut"], date_lettres(latest["terrain_debut"]))
    tf = time_tag(latest["terrain_fin"], date_lettres(latest["terrain_fin"]))
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

    return meta_html, render_hypothese(hyp, latest, candidats)


def inject(content, begin, end, html_bloc):
    try:
        i_begin = content.index(begin)
        i_end = content.index(end) + len(end)
    except ValueError:
        raise ValueError(f"Marqueurs {begin} / {end} introuvables dans sondages.html")
    return content[:i_begin] + begin + "\n" + html_bloc + "\n" + end + content[i_end:]


def main():
    sondages = charger_sondages(SONDAGES_PATH)
    candidats = json.loads(CANDIDATS_PATH.read_text(encoding="utf-8"))
    referentiel = charger_referentiel()

    # sondages.json contient déjà les manuels (fusionnés par le collecteur)

    # Module « Explorer les sondages » (avant le tri : select_latest_sondage
    # départage en dernier ressort sur l'ordre du fichier)
    meta_html, scores_html = generate_fiche(sondages, candidats, referentiel)

    # Tri par terrain_fin décroissant
    sondages.sort(key=lambda s: s["terrain_fin"], reverse=True)

    rows = [
        '<tr><th>Institut</th><th>Date</th>'
        '<th>Échantillon</th><th style="width:3em;text-align:center">Hyp.</th></tr>'
    ]
    for s in sondages:
        sid = s.get("id", "")
        date_str = time_tag(s["terrain_fin"], fmt_date(s["terrain_fin"]))
        ech = fmt_ech(s["echantillon"]) if s.get("echantillon") else "\u2014"
        nhyp = len(s.get("hypotheses", []))
        # Institut → page de l'institut ; date → fiche du sondage
        inst_link = lien_institut(s["institut"], referentiel)
        date_link = f'<a href="sondages/{html_mod.escape(sid)}.html">{date_str}</a>' if sid else date_str
        # data-id : un clic sur la ligne charge le sondage dans le module
        rows.append(
            f'<tr data-id="{html_mod.escape(sid)}"><td>{inst_link}</td><td>{date_link}</td>'
            f'<td>{ech}</td><td style="text-align:center">{nhyp}</td></tr>'
        )

    table_html = (
        '  <table class="sondages-table" id="table-sondages">\n'
        + "\n".join(rows) + "\n"
        '  </table>'
    )

    content = SONDAGES_HTML.read_text(encoding="utf-8")
    content = inject(content, META_BEGIN, META_END, meta_html)
    content = inject(content, SCORES_BEGIN, SCORES_END, scores_html)
    content = inject(content, BEGIN, END, table_html)
    SONDAGES_HTML.write_text(content, encoding="utf-8")
    print(f"Module « Explorer les sondages » et table injectés : {len(sondages)} sondages")


if __name__ == "__main__":
    main()
