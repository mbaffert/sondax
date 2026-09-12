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

COUNTDOWN_JS = """\
<script>
(function(){var el=document.getElementById('countdown');if(!el)return;
var T1=new Date(2027,3,18),T2=new Date(2027,4,2);
var p=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
var today=new Date(p+'T00:00:00');
var d1=Math.round((T1-today)/864e5),d2=Math.round((T2-today)/864e5);
window._joursAvantT1_2027=d1;
if(d2<0){el.style.display='none';return}
var b,s;
if(d1>0){b='J\\u2011'+d1;s='Premier tour le dimanche 18 avril 2027'}
else if(d1===0){b='J0';s='Premier tour aujourd\\u2019hui'}
else if(d2>0){b='J\\u2011'+d2;s='Second tour le dimanche 2 mai 2027'}
else{b='J0';s='Second tour aujourd\\u2019hui'}
el.innerHTML='<div class="cd-big">'+b+'</div><div class="cd-small">'+s+'</div>';
})();
</script>"""


def header(title_text, depth=1):
    prefix = "../" * depth
    return f"""\
<header>
  <div class="header-inner">
    <div>
      <a href="{prefix}index.html"><img src="{prefix}assets/logo-sondax-blanc.svg" alt="Sondax"></a>
      <p class="header-title">{html_mod.escape(title_text)}</p>
    </div>
    <div id="countdown" class="countdown"></div>
  </div>
</header>
{COUNTDOWN_JS}

<nav class="section-nav">
  <div class="nav-inner">
    <a href="{prefix}index.html">Présidentielle 2027</a>
    <a href="{prefix}second-tour/" class="active">Second tour</a>
    <span class="nav-sep"></span>
    <a href="{prefix}sondages.html">Tous les sondages</a>
    <a href="{prefix}methodologie.html">Méthodologie</a>
    <a href="{prefix}precedentes-elections.html">Précédentes élections</a>
  </div>
</nav>"""


def footer(depth=1):
    prefix = "../" * depth
    return f"""\
<footer>
  <div class="footer-inner">
    <p>Données sondages\u00a0: <a href="https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027" target="_blank">Wikipédia</a>,
    licence <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.fr" target="_blank">CC BY-SA 4.0</a> ·
    Cotes\u00a0: <a href="https://polymarket.com" target="_blank">Polymarket</a> ·
    <a href="{prefix}methodologie.html">Méthodologie</a></p>
    <p><a href="mailto:contact@sondax.fr">Contact</a> · Hébergeur\u00a0: <a href="https://pages.github.com" target="_blank">GitHub Pages</a></p>
    <p class="disclaimer">Marque indépendante. Le bleu et le rouge ne représentent aucun camp politique.</p>
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

  header { background: var(--bleu-nuit); color: #fff; padding: 32px 28px 24px; }
  header .header-inner { max-width: 1180px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; }
  header img { width: 180px; display: block; }
  header .header-title { font-family: var(--titre); font-weight: 500; font-size: 24px;
    letter-spacing: -0.01em; color: #fff; margin-top: 12px; }
  .countdown { text-align: right; color: #fff; flex-shrink: 0; }
  .cd-big { font-family: var(--titre); font-size: 28px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; }
  .cd-small { font-size: 12px; color: rgba(255,255,255,0.7); margin-top: 2px; }

  nav.section-nav { position: sticky; top: 0; z-index: 20; background: var(--bleu-nuit);
    border-bottom: 1px solid rgba(255,255,255,0.12); display: flex; align-items: center;
    padding: 0 28px; overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
  nav.section-nav::-webkit-scrollbar { display: none; }
  nav.section-nav .nav-inner { max-width: 1180px; margin: 0 auto; display: flex; width: 100%; align-items: center; }
  nav.section-nav .nav-sep { width: 1px; height: 16px; background: rgba(255,255,255,0.2); margin: 0 4px; flex-shrink: 0; }
  nav.section-nav a { font-family: var(--corps); font-size: 13px; font-weight: 500;
    color: rgba(255,255,255,0.6); padding: 10px 14px; white-space: nowrap;
    border-bottom: 2px solid transparent; transition: all 0.15s; text-decoration: none; }
  nav.section-nav a:hover { color: #fff; text-decoration: none; }
  nav.section-nav a.active { color: #fff; border-bottom-color: #fff; }

  main { max-width: 1180px; margin: 0 auto; padding: 26px 28px 40px; }

  footer { background: var(--bleu-nuit); color: rgba(255,255,255,0.72); padding: 34px 28px 26px; font-size: 13px; }
  footer .footer-inner { max-width: 1180px; margin: 0 auto; }
  footer a { color: rgba(255,255,255,0.72); }
  footer a:hover { color: #fff; text-decoration: none; }
  footer .disclaimer { font-size: 12.5px; line-height: 1.6; margin-top: 8px; }

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
    header { padding: 22px 16px 16px; }
    header .header-inner { flex-wrap: wrap; }
    header img { width: 130px; }
    header .header-title { font-size: 18px; }
    .countdown { text-align: left; width: 100%; margin-top: 10px; }
    .cd-big { font-size: 22px; }
    nav.section-nav { padding: 0 12px; }
    main { padding: 14px 12px 30px; }
    .chart-wrap { height: 300px; }
    footer { padding: 24px 16px; }
  }"""


HEAD_COMMON = """\
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="{prefix}assets/logo-sondax.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<script data-goatcounter="https://sondax.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>"""


# ---------------------------------------------------------------------------
# Génération des pages de duel
# ---------------------------------------------------------------------------

def render_table_html(entries, cid_a, cid_b, candidats):
    rows = []
    for e in entries:
        ech = f'{round(e["echantillon"]):,}'.replace(",", "\u202f") if e["echantillon"] else "—"
        source = f'<a href="{html_mod.escape(e["url_source"])}" target="_blank">Notice</a>' if e["url_source"] else "—"
        rows.append(
            f"<tr><td>{html_mod.escape(e['institut'])}</td>"
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
    """JS pour dessiner le graphique Chart.js du duel."""
    sorted_entries = sorted(entries, key=lambda e: e["terrain_fin"])
    data_a = json.dumps([{"x": e["terrain_fin"], "y": e["scores"][cid_a]} for e in sorted_entries])
    data_b = json.dumps([{"x": e["terrain_fin"], "y": e["scores"][cid_b]} for e in sorted_entries])
    nom_a = nom_court(cid_a, candidats)
    nom_b = nom_court(cid_b, candidats)
    col_a = couleur(cid_a, candidats)
    col_b = couleur(cid_b, candidats)

    all_vals = [e["scores"][cid_a] for e in sorted_entries] + [e["scores"][cid_b] for e in sorted_entries]
    lo = min(all_vals)
    hi = max(all_vals)
    y_min = min(int(lo // 5) * 5, 45)
    y_max = max(-(-int(hi) // 5) * 5 + 5, 55)

    return f"""\
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/date-fns@3/locale/fr/cdn.min.js"></script>
<script>
(function() {{
  var dataA = {data_a};
  var dataB = {data_b};
  function parseD(s) {{ var p=s.split('-').map(Number); return new Date(p[0],p[1]-1,p[2]); }}
  var ptsA = dataA.map(function(d){{ return {{x:parseD(d.x),y:d.y}}; }});
  var ptsB = dataB.map(function(d){{ return {{x:parseD(d.x),y:d.y}}; }});
  var ligne50 = {{
    id:'ligne50',
    beforeDraw:function(chart) {{
      var y=chart.scales.y.getPixelForValue(50);
      var ctx=chart.ctx, left=chart.chartArea.left, right=chart.chartArea.right;
      ctx.save(); ctx.strokeStyle='rgba(32,38,50,0.25)'; ctx.lineWidth=1;
      ctx.setLineDash([6,4]); ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(right,y); ctx.stroke();
      ctx.fillStyle='rgba(32,38,50,0.4)'; ctx.font="11px 'IBM Plex Sans',sans-serif";
      ctx.textBaseline='bottom'; ctx.fillText('50\\u00a0%',left+4,y-3); ctx.restore();
    }}
  }};
  var locale = window.dateFns && window.dateFns.locale && window.dateFns.locale.fr;
  new Chart(document.getElementById('chart-duel'), {{
    type:'line',
    data:{{ datasets:[
      {{ label:{json.dumps(nom_a)}, data:ptsA, borderColor:{json.dumps(col_a)}, backgroundColor:{json.dumps(col_a)},
         borderWidth:2, pointRadius:4, tension:0, fill:false }},
      {{ label:{json.dumps(nom_b)}, data:ptsB, borderColor:{json.dumps(col_b)}, backgroundColor:{json.dumps(col_b)},
         borderWidth:2, pointRadius:4, tension:0, fill:false }}
    ] }},
    plugins:[ligne50],
    options:{{
      responsive:true, maintainAspectRatio:false,
      interaction:{{ mode:'nearest', axis:'x', intersect:false }},
      scales:{{
        x:{{ type:'time', time:{{ unit:'month', displayFormats:{{month:'MMM yyyy'}}, tooltipFormat:'d MMMM yyyy' }},
             adapters:{{ date:{{ locale:locale }} }},
             ticks:{{ maxRotation:0, autoSkip:true }}, grid:{{ color:'#edeee9' }} }},
        y:{{ min:{y_min}, max:{y_max}, ticks:{{ callback:function(v){{return v+'\\u00a0%'}} }},
             grid:{{ color:'#edeee9' }} }}
      }},
      plugins:{{
        legend:{{ display:true, position:'top', labels:{{ font:{{ family:"'IBM Plex Sans'" }} }} }},
        tooltip:{{ callbacks:{{ label:function(ctx){{ return ctx.dataset.label+'\\u00a0: '+ctx.parsed.y.toFixed(1).replace('.',',')+'\\u00a0%'; }} }} }}
      }}
    }}
  }});
}})();
</script>"""


def generate_duel_page(slug, entries, candidats, out_dir):
    pair = slug.split("-", 1)
    # Re-split properly: the slug is two candidate keys joined by '-', but keys themselves
    # can contain '-' (e.g. le-pen, dupont-aignan). We need to find the split point.
    cid_a, cid_b = find_pair_from_slug(slug, candidats)

    nom_a = nom_court(cid_a, candidats)
    nom_b = nom_court(cid_b, candidats)
    title = f"Sondages second tour 2027 : {nom_a} – {nom_b}"
    description = f"Tous les sondages du duel {nom_a} – {nom_b} pour le second tour de la présidentielle 2027. Courbe et tableau."
    canonical = f"{BASE_URL}/second-tour/{slug}"
    prefix = "../"

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
  <h1>{html_mod.escape(title)}</h1>
  <p class="subtitle">{len(entries)} sondage{"s" if len(entries) > 1 else ""} · Dernier : {fmt_date(entries[0]["terrain_fin"])}</p>

  <div class="chart-wrap"><canvas id="chart-duel"></canvas></div>

  <h2>Tous les sondages</h2>
  {render_table_html(entries, cid_a, cid_b, candidats)}
</main>

{footer(depth=1)}

{chart_js(entries, cid_a, cid_b, candidats)}

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


def generate_sitemap(duel_slugs):
    urls = []
    for page in STATIC_PAGES:
        urls.append(f"  <url><loc>{BASE_URL}/{page}</loc></url>")
    for slug in sorted(duel_slugs):
        urls.append(f"  <url><loc>{BASE_URL}/second-tour/{slug}</loc></url>")

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

    pages_generated = []
    for slug, entries in sorted(duels.items(), key=lambda x: -len(x[1])):
        n = len(entries)
        cid_a, cid_b = find_pair_from_slug(slug, candidats)
        label = f"{nom_court(cid_a, candidats)} – {nom_court(cid_b, candidats)}"
        if n >= SEUIL:
            generate_duel_page(slug, entries, candidats, out_dir)
            pages_generated.append(slug)
            print(f"  ✓ {label} ({n} sondages) → {slug}.html")
        else:
            print(f"  · {label} ({n} sondages) → tableau dans index")

    generate_index_page(duels, candidats, out_dir)
    print(f"Page d'entrée : {out_dir / 'index.html'}")

    generate_sitemap(pages_generated)

    print(f"\n{len(pages_generated)} pages de duel, {len(duels) - len(pages_generated)} en tableau")


if __name__ == "__main__":
    main()
