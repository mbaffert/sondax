"""Génère les pages statiques de second tour et le sitemap.

Lit data/sondages.json et data/candidats.json, produit :
- site/second-tour/index.html         page d'entrée listant tous les duels
- site/second-tour/{slug}.html        une page par duel ≥ 5 mesures
- site/second-tour/{slug-inv}.html    redirection vers le slug canonique
- site/sitemap.xml                    sitemap couvrant tout le site
"""

import json, pathlib, sys, html as html_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
DEFAULT_OUT = ROOT / "site" / "second-tour"
SITEMAP_PATH = ROOT / "site" / "sitemap.xml"

SEUIL = 5
BASE_URL = "https://sondax.fr"

sys.path.insert(0, str(ROOT / "scripts"))
from instituts import charger_referentiel, lien_institut

# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------

def load_duels():
    sondages = json.loads(SONDAGES_PATH.read_text())
    candidats = json.loads(CANDIDATS_PATH.read_text())

    duels = {}  # "a-b" → [{"institut", "terrain_fin", "terrain_debut", "echantillon", "url_source", "scores"}]
    for s in sondages:
        for h in s["hypotheses"]:
            if h["tour"] != 2 or len(h["scores"]) != 2:
                continue
            pair = sorted(h["scores"].keys())
            slug = "-".join(pair)
            entry = {
                "institut": s["institut"],
                "terrain_debut": s["terrain_debut"],
                "terrain_fin": s["terrain_fin"],
                "echantillon": s["echantillon"],
                "url_source": s.get("url_source"),
                "scores": h["scores"],
            }
            duels.setdefault(slug, []).append(entry)

    # Trier chaque duel par date décroissante
    for entries in duels.values():
        entries.sort(key=lambda e: e["terrain_fin"], reverse=True)

    return duels, candidats


def nom_court(cid, candidats):
    c = candidats.get(cid)
    return c["nom"] if c else cid


def couleur(cid, candidats):
    c = candidats.get(cid)
    return c["couleur"] if c and "couleur" in c else "#888"


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",") + "\u00a0%"


# ---------------------------------------------------------------------------
# Templates HTML
# ---------------------------------------------------------------------------

def header(title_text, depth=1):
    prefix = "../" * depth
    return f"""\
<div id="site-header" class="sh"></div>
<script src="{prefix}assets/header-data.js"></script>
<script src="{prefix}assets/header.js"></script>"""


def footer(depth=1):
    prefix = "../" * depth
    return f"""\
<footer class="site-footer">
  <div class="footer-inner">
    <div>
      <div style="margin-bottom:10px;">
        <img src="{prefix}assets/logo-sondax-blanc.svg" alt="Sondax" style="height:22px;">
      </div>
      <p class="disclaimer">Marque indépendante. Le bleu et le rouge ne représentent aucun camp politique.</p>
    </div>
    <div>
      <div class="footer-col-title">Données</div>
      <div style="display:flex;flex-direction:column;gap:5px;">
        <a href="https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027" target="_blank">Sondages · Wikipédia (CC BY-SA 4.0)</a>
        Cotes · Polymarket
      </div>
    </div>
    <div>
      <div class="footer-col-title">Le site</div>
      <div style="display:flex;flex-direction:column;gap:5px;">
        <a href="{prefix}methodologie.html">Méthodologie</a>
        <a href="{prefix}sondages.html">Tous les sondages</a>
        <a href="{prefix}donnees.html">Données</a>
        <a href="{prefix}a-propos.html">À propos</a>
      </div>
    </div>
    <div>
      <div id="footer-run"></div>
      <div><a href="mailto:contact@sondax.fr">Contact</a></div>
      <div>Hébergeur · <a href="https://pages.github.com" target="_blank">GitHub Pages</a></div>
    </div>
  </div>
</footer>"""


CSS = """\
  :root {
    --bleu-vif: #0C6CF2;
    --bleu-nuit: #0B2E6F;
    --fond: #F7F8F5;
    --texte: #202632;
    --gris: #66707D;
    --titre: 'Space Grotesk', system-ui, sans-serif;
    --corps: 'IBM Plex Sans', system-ui, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: var(--corps); background: var(--fond); color: var(--texte); font-size: 15px; line-height: 1.5; }
  a { color: var(--bleu-vif); text-decoration: none; }
  a:hover { color: var(--bleu-nuit); text-decoration: underline; }

  main { max-width: 1180px; margin: 0 auto; padding: 26px 28px 40px; }

  footer.site-footer { background: var(--bleu-nuit); color: rgba(255,255,255,0.72); padding: 34px 28px 26px; font-size: 13px; }
  footer.site-footer .footer-inner { max-width: 1180px; margin: 0 auto; display: grid;
    grid-template-columns: 1.2fr 1fr 1fr 1fr; gap: 16px 32px; }
  footer.site-footer .footer-col-title { color: #fff; font-weight: 600; margin-bottom: 9px; font-size: 12.5px; }
  footer.site-footer a { color: rgba(255,255,255,0.72); text-decoration: none; }
  footer.site-footer a:hover { color: #fff; text-decoration: none; }
  footer.site-footer .disclaimer { font-size: 12.5px; line-height: 1.6; }
  @media (max-width: 900px) {
    footer.site-footer { padding: 24px 16px; }
    footer.site-footer .footer-inner { grid-template-columns: 1fr; gap: 20px; }
  }

  h1 { font-family: var(--titre); font-size: 1.8em; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0.3em; }
  h2 { font-family: var(--titre); font-size: 1.3em; font-weight: 700; margin: 1.5em 0 0.5em; }
  .subtitle { font-size: 14px; color: var(--gris); margin-bottom: 1.5em; }

  .chart-wrap { position: relative; width: 100%; height: 420px; margin-bottom: 1.5em; }

  .t2-table { border-collapse: collapse; width: 100%; font-size: 0.85em; margin-top: 0.5em; margin-bottom: 1.5em; }
  .t2-table th, .t2-table td { border: 1px solid #e2e4e0; padding: 0.4em 0.6em; text-align: left; }
  .t2-table th { background: #f5f5f3; font-weight: 600; }
  .t2-table a { color: var(--bleu-vif); }

  .duel-card { display: block; background: #fff; border: 1px solid #E3E5E0; border-radius: 12px;
    padding: 18px 22px; margin-bottom: 10px; text-decoration: none; color: var(--texte);
    transition: box-shadow 0.15s; }
  .duel-card:hover { box-shadow: 0 2px 8px rgba(32,38,50,0.1); text-decoration: none; }
  .duel-card .duel-noms { font-family: var(--titre); font-size: 1.1em; font-weight: 600; }
  .duel-card .duel-count { font-size: 13px; color: var(--gris); margin-top: 2px; }

  @media (max-width: 600px) {
    main { padding: 14px 12px 30px; }
    .chart-wrap { height: 300px; }
  }"""


HEAD_COMMON = """\
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="{prefix}assets/logo-sondax.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}assets/header.css">
<script data-goatcounter="https://sondax.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>"""


# ---------------------------------------------------------------------------
# Génération des pages de duel
# ---------------------------------------------------------------------------

def render_table_html(entries, cid_a, cid_b, candidats):
    referentiel = charger_referentiel()
    rows = []
    for e in entries:
        ech = f'{round(e["echantillon"]):,}'.replace(",", "\u202f") if e["echantillon"] else "—"
        source = f'<a href="{html_mod.escape(e["url_source"])}" target="_blank">Notice</a>' if e["url_source"] else "—"
        rows.append(
            f"<tr><td>{lien_institut(e['institut'], referentiel, '../')}</td>"
            f"<td>{fmt_date(e['terrain_debut'])} → {fmt_date(e['terrain_fin'])}</td>"
            f"<td>{ech}</td>"
            f"<td>{fmt_pct(e['scores'][cid_a])}</td>"
            f"<td>{fmt_pct(e['scores'][cid_b])}</td>"
            f"<td>{source}</td></tr>"
        )
    nom_a = html_mod.escape(nom_court(cid_a, candidats))
    nom_b = html_mod.escape(nom_court(cid_b, candidats))
    return (
        f'<table class="t2-table"><tr><th>Institut</th><th>Terrain</th>'
        f"<th>Échantillon</th><th>{nom_a}</th><th>{nom_b}</th><th>Source</th></tr>\n"
        + "\n".join(rows)
        + "\n</table>"
    )


def chart_js(entries, cid_a, cid_b, candidats):
    """JS pour dessiner le graphique Chart.js du duel (même rendu que l'accueil :
    points bruts pâles, courbe de tendance, nom et score au bout de la courbe)."""
    sorted_entries = sorted(entries, key=lambda e: e["terrain_fin"])
    pts = json.dumps([
        {"d": e["terrain_fin"], "a": e["scores"][cid_a], "b": e["scores"][cid_b],
         "i": e.get("institut", "")}
        for e in sorted_entries
    ], ensure_ascii=False)
    nom_a = json.dumps(nom_court(cid_a, candidats), ensure_ascii=False)
    nom_b = json.dumps(nom_court(cid_b, candidats), ensure_ascii=False)
    col_a = json.dumps(couleur(cid_a, candidats))
    col_b = json.dumps(couleur(cid_b, candidats))

    ecart = max(abs(v - 50) for e in sorted_entries for v in (e["scores"][cid_a], e["scores"][cid_b]))
    demi = max(5, -(-int(ecart + 1) // 5) * 5)

    js = """\
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/date-fns@3/locale/fr/cdn.min.js"></script>
<script src="../assets/end-labels.js?v=1"></script>
<script>
(function() {
  var PTS = __PTS__;
  var mobile = window.innerWidth < 600;
  function parseD(s) { var p = s.split('-').map(Number); return new Date(p[0], p[1]-1, p[2]); }
  function pct(v) { return v.toFixed(1).replace('.', ',') + '\\u00a0%'; }
  function brut(k) { return PTS.map(function(p) { return { x: parseD(p.d), y: p[k], i: p.i, d: p.d }; }); }
  // Tendance : moyenne des mesures des 30 jours précédents (au moins les 3 dernières)
  function tendance(pts) {
    var F = 30 * 86400000, out = [], vues = {};
    pts.forEach(function(p) {
      var t = +p.x; if (vues[t]) return; vues[t] = 1;
      var avant = pts.filter(function(q) { return +q.x <= t; });
      var fen = avant.filter(function(q) { return +q.x > t - F; });
      if (fen.length < 3) fen = avant.slice(-3);
      var m = fen.reduce(function(s, q) { return s + q.y; }, 0) / fen.length;
      out.push({ x: t, y: Math.round(m * 10) / 10 });
    });
    return out;
  }
  function courbe(nom, col, pts) {
    var d = tendance(pts);
    return { label: nom, data: d, borderColor: col, borderWidth: mobile ? 2.8 : 2.5,
      pointRadius: 0, pointHoverRadius: 0, tension: 0.35, cubicInterpolationMode: 'monotone',
      fill: false, _label: nom + ' ' + pct(d[d.length - 1].y) };
  }
  function points(nom, col, pts) {
    return { label: nom, data: pts, showLine: false, backgroundColor: col + '55',
      borderWidth: 0, pointRadius: mobile ? 2.5 : 3, pointHoverRadius: 5, _isBrut: true };
  }
  var A = brut('a'), B = brut('b');
  var ligne50 = {
    id: 'ligne50',
    beforeDatasetsDraw: function(chart) {
      var y = chart.scales.y.getPixelForValue(50), ctx = chart.ctx, a = chart.chartArea;
      ctx.save(); ctx.strokeStyle = 'rgba(32,38,50,0.35)'; ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y);
      ctx.stroke(); ctx.restore();
    }
  };
  var tickCol = mobile ? '#b0b5bc' : '#9aa2ac', gridCol = mobile ? '#f0f1ed' : '#edeee9';
  var locale = window.dateFns && window.dateFns.locale && window.dateFns.locale.fr;
  new Chart(document.getElementById('chart-duel'), {
    type: 'line',
    data: { datasets: [
      points(__NOM_A__, __COL_A__, A), points(__NOM_B__, __COL_B__, B),
      courbe(__NOM_A__, __COL_A__, A), courbe(__NOM_B__, __COL_B__, B)
    ] },
    plugins: [ligne50, SondaxEndLabels.plugin],
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: SondaxEndLabels.padding({ top: 4 }) },
      interaction: { mode: 'nearest', intersect: true },
      scales: {
        x: { type: 'time', time: { unit: 'month', displayFormats: { month: 'MMM yyyy' }, tooltipFormat: 'd MMMM yyyy' },
             adapters: { date: { locale: locale } },
             ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: mobile ? 5 : 9, color: tickCol, font: { size: mobile ? 10 : 11 } },
             grid: { color: gridCol } },
        y: { min: __YMIN__, max: __YMAX__, border: { display: false },
             ticks: { stepSize: 5, callback: function(v) { return v + '\\u00a0%'; }, color: tickCol, font: { size: mobile ? 10 : 11 } },
             grid: { color: gridCol } }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: function(item) { return item.dataset._isBrut; },
          callbacks: {
            title: function(items) { var r = items[0].raw, d = r.d.split('-'); return r.i + ' \\u00b7 ' + d[2] + '/' + d[1] + '/' + d[0]; },
            label: function(ctx) { return ctx.dataset.label + '\\u00a0: ' + pct(ctx.parsed.y); }
          }
        }
      }
    }
  });
})();
</script>"""
    return (js.replace("__PTS__", pts)
              .replace("__NOM_A__", nom_a).replace("__NOM_B__", nom_b)
              .replace("__COL_A__", col_a).replace("__COL_B__", col_b)
              .replace("__YMIN__", str(50 - demi)).replace("__YMAX__", str(50 + demi)))


def generate_duel_page(slug, entries, candidats, out_dir):
    pair = slug.split("-", 1)
    # Re-split properly: the slug is two candidate keys joined by '-', but keys themselves
    # can contain '-' (e.g. le-pen, dupont-aignan). We need to find the split point.
    cid_a, cid_b = find_pair_from_slug(slug, candidats)

    nom_a = nom_court(cid_a, candidats)
    nom_b = nom_court(cid_b, candidats)
    title = f"Sondages second tour 2027 : {nom_a} – {nom_b}"
    description = f"Tous les sondages du duel {nom_a} – {nom_b} pour le second tour de la présidentielle 2027. Courbe et tableau."
    canonical = f"{BASE_URL}/second-tour/{slug}.html"
    prefix = "../"

    # Graphique seulement si >= SEUIL mesures (SPEC §5)
    if len(entries) >= SEUIL:
        chart_section = (
            f'  <div class="chart-wrap"><canvas id="chart-duel"></canvas></div>\n'
            f'  <h2>Tous les sondages</h2>\n'
        )
        chart_script = chart_js(entries, cid_a, cid_b, candidats)
    else:
        chart_section = ""
        chart_script = ""

    page = f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
{HEAD_COMMON.format(prefix=prefix)}
<title>{html_mod.escape(title)} — Sondax</title>
<meta name="description" content="{html_mod.escape(description)}">
<link rel="canonical" href="{canonical}">
<style>
{CSS}
</style>
</head>
<body>

{header("Second tour 2027", depth=1)}

<main>
  <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--gris);padding:0 0 18px;">
    <a href="../" style="color:inherit">Sondax</a> › <a href="./" style="color:inherit">Second tour</a> › {html_mod.escape(nom_a)} – {html_mod.escape(nom_b)}
  </div>
  <h1>{html_mod.escape(title)}</h1>
  <p class="subtitle">{len(entries)} sondage{"s" if len(entries) > 1 else ""} · Dernier : {fmt_date(entries[0]["terrain_fin"])}</p>

{chart_section}
  {render_table_html(entries, cid_a, cid_b, candidats)}
</main>

{footer(depth=1)}

{chart_script}

</body>
</html>
"""
    (out_dir / f"{slug}.html").write_text(page, encoding="utf-8")

    # Redirection pour le slug inversé
    slug_inv = f"{cid_b}-{cid_a}"
    if slug_inv != slug:
        redir = f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Redirection</title>
<link rel="canonical" href="{canonical}">
<meta http-equiv="refresh" content="0;url={slug}.html">
</head>
<body>
<p>Redirection vers <a href="{slug}.html">{html_mod.escape(title)}</a>.</p>
</body>
</html>
"""
        (out_dir / f"{slug_inv}.html").write_text(redir, encoding="utf-8")


def find_pair_from_slug(slug, candidats):
    """Retrouve la paire (cid_a, cid_b) à partir du slug canonique."""
    # Les clés candidats peuvent contenir des tirets, on teste toutes les coupures
    for i in range(1, len(slug)):
        if slug[i - 1] == "-":
            continue
        if slug[i] != "-":
            continue
        a, b = slug[:i], slug[i + 1:]
        if a in candidats and b in candidats:
            return a, b
    raise ValueError(f"Impossible de découper le slug '{slug}' en deux candidats")


# ---------------------------------------------------------------------------
# Page d'entrée
# ---------------------------------------------------------------------------

def generate_index_page(duels, candidats, out_dir):
    prefix = "../"
    above = []  # (slug, entries) — ≥ SEUIL mesures
    below = []  # (slug, entries) — < SEUIL mesures

    for slug in sorted(duels, key=lambda s: -len(duels[s])):
        if len(duels[slug]) >= SEUIL:
            above.append((slug, duels[slug]))
        else:
            below.append((slug, duels[slug]))

    # Cartes des duels avec pages dédiées
    cards_html = ""
    for slug, entries in above:
        cid_a, cid_b = find_pair_from_slug(slug, candidats)
        nom_a = html_mod.escape(nom_court(cid_a, candidats))
        nom_b = html_mod.escape(nom_court(cid_b, candidats))
        n = len(entries)
        cards_html += (
            f'  <a class="duel-card" href="{slug}.html">\n'
            f'    <div class="duel-noms">{nom_a} – {nom_b}</div>\n'
            f'    <div class="duel-count">{n} sondage{"s" if n > 1 else ""} · '
            f'Dernier : {fmt_date(entries[0]["terrain_fin"])}</div>\n'
            f'  </a>\n'
        )

    # Tableaux des duels sous le seuil
    tables_html = ""
    for slug, entries in below:
        cid_a, cid_b = find_pair_from_slug(slug, candidats)
        nom_a = html_mod.escape(nom_court(cid_a, candidats))
        nom_b = html_mod.escape(nom_court(cid_b, candidats))
        n = len(entries)
        tables_html += f'<h2>{nom_a} – {nom_b} ({n} sondage{"s" if n > 1 else ""})</h2>\n'
        tables_html += render_table_html(entries, cid_a, cid_b, candidats) + "\n"

    canonical = f"{BASE_URL}/second-tour/"

    page = f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
{HEAD_COMMON.format(prefix=prefix)}
<title>Second tour — Sondax</title>
<meta name="description" content="Tous les duels de second tour testés pour la présidentielle 2027 : courbes, tableaux et sources.">
<link rel="canonical" href="{canonical}">
<style>
{CSS}
</style>
</head>
<body>

{header("Second tour 2027", depth=1)}

<main>
  <h1>Sondages de second tour</h1>
  <p class="subtitle">Tous les duels testés pour la présidentielle 2027.</p>

{cards_html}
{f'<h2>Autres duels testés</h2>' if tables_html else ''}
{tables_html}
</main>

{footer(depth=1)}

</body>
</html>
"""
    (out_dir / "index.html").write_text(page, encoding="utf-8")


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

STATIC_PAGES = [
    "",
    "sondages.html",
    "methodologie.html",
    "precedentes-elections.html",
    "presidentielle-2002.html",
    "presidentielle-2007.html",
    "presidentielle-2012.html",
    "presidentielle-2017.html",
    "presidentielle-2022.html",
    "second-tour/",
]


def generate_sitemap():
    urls = []
    for page in STATIC_PAGES:
        urls.append(f"  <url><loc>{BASE_URL}/{page}</loc></url>")

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    SITEMAP_PATH.write_text(sitemap, encoding="utf-8")
    print(f"Sitemap écrit : {SITEMAP_PATH.name} ({len(urls)} URLs)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    out_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    # Nettoyer les pages précédemment générées
    for f in out_dir.glob("*.html"):
        f.unlink()

    duels, candidats = load_duels()

    print(f"{len(duels)} duels trouvés")

    generate_index_page(duels, candidats, out_dir)
    print(f"Page d'entrée : {out_dir / 'index.html'}")

    # Pages de duel individuelles
    n_pages = 0
    for slug, entries in duels.items():
        generate_duel_page(slug, entries, candidats, out_dir)
        n_pages += 1

    print(f"{len(duels)} duels, {n_pages} pages générées")


if __name__ == "__main__":
    main()
