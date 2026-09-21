"""Gabarit HTML partagé par tous les scripts de build.

Usage :
    from site_template import render_page
    html = render_page(
        title="Mon titre — Sondax",
        meta_description="Description pour le SEO.",
        canonical="https://sondax.fr/ma-page.html",
        body_content="<main>...</main>",
        extra_head="<style>...</style>",  # optionnel
        depth=0,  # 0 = racine, 1 = sous-dossier
    )
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def _prefix(depth):
    """Préfixe de chemin relatif pour les assets."""
    return "../" * depth if depth else ""


def render_page(*, title, meta_description, canonical, body_content,
                extra_head="", depth=0, og_type="website"):
    p = _prefix(depth)
    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Sondax">
<meta property="og:locale" content="fr_FR">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_description}">
<meta property="og:image" content="https://sondax.fr/assets/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{canonical}">
<script data-goatcounter="https://sondax.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
<link rel="icon" type="image/svg+xml" href="{p}assets/logo-sondax.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{p}assets/header.css?v=3">
<style>
  :root {{
    --bleu-vif: #0C6CF2;
    --bleu-nuit: #0B2E6F;
    --fond: #F7F8F5;
    --carte: #fff;
    --bord: #E3E5E0;
    --texte: #202632;
    --gris: #66707D;
    --titre: 'Space Grotesk', system-ui, sans-serif;
    --corps: 'IBM Plex Sans', system-ui, sans-serif;
    --mono: 'IBM Plex Mono', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: var(--corps); background: var(--fond); color: var(--texte);
         font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  a {{ color: var(--bleu-vif); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  main {{ max-width: 1060px; margin: 0 auto; padding: 24px 24px 64px; }}
  h1 {{ font-family: var(--titre); font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 18px; }}
  h2 {{ font-family: var(--titre); font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 24px 0 12px; }}

  .fil {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em;
          text-transform: uppercase; color: var(--gris); padding: 0 0 18px; }}

  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--bord); }}
  th {{ font-weight: 600; font-size: 12px; color: var(--gris); text-transform: uppercase;
       letter-spacing: 0.06em; font-family: var(--mono); }}
  td {{ font-variant-numeric: tabular-nums; }}

  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 11px; font-weight: 600; }}
  .badge-principale {{ background: #E8F5E9; color: #2E7D32; }}

  footer.site-footer {{ background: var(--bleu-nuit); color: rgba(255,255,255,0.72); padding: 34px 28px 26px; font-size: 13px; }}
  footer.site-footer .footer-inner {{ max-width: 1180px; margin: 0 auto; display: grid;
    grid-template-columns: 1.2fr 1fr 1fr 1fr; gap: 16px 32px; }}
  footer.site-footer .footer-col-title {{ color: #fff; font-weight: 600; margin-bottom: 9px; font-size: 12.5px; }}
  footer.site-footer a {{ color: rgba(255,255,255,0.72); text-decoration: none; }}
  footer.site-footer a:hover {{ color: #fff; text-decoration: none; }}
  footer.site-footer .disclaimer {{ font-size: 12.5px; line-height: 1.6; }}
  @media (max-width: 900px) {{
    footer.site-footer {{ padding: 24px 16px; }}
    footer.site-footer .footer-inner {{ grid-template-columns: 1fr; gap: 20px; }}
  }}
</style>
{extra_head}
</head>
<body>

<div id="site-header" class="sh"></div>
<script src="{p}assets/header-data.js?v=3"></script>
<script src="{p}assets/header.js?v=3"></script>

{body_content}

<footer class="site-footer">
  <div class="footer-inner">
    <div>
      <div style="margin-bottom:10px;">
        <img src="{p}assets/logo-sondax-blanc.svg" alt="Sondax" style="height:22px;">
      </div>
      <p class="disclaimer">Marque indépendante. Le bleu et le rouge ne représentent aucun camp politique.</p>
    </div>
    <div>
      <div class="footer-col-title">Données</div>
      <div style="display:flex;flex-direction:column;gap:5px;">
        <a href="https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027" target="_blank">Sondages · Wikipédia (CC BY-SA 4.0)</a>
        <a href="https://polymarket.com" target="_blank">Cotes · Polymarket</a>
      </div>
    </div>
    <div>
      <div class="footer-col-title">Le site</div>
      <div style="display:flex;flex-direction:column;gap:5px;">
        <a href="{p}methodologie.html">Méthodologie</a>
        <a href="{p}sondages.html">Tous les sondages</a>
      </div>
    </div>
    <div>
      <div id="footer-run"></div>
      <div><a href="mailto:contact@sondax.fr">Contact</a></div>
      <div>Hébergeur · <a href="https://pages.github.com" target="_blank">GitHub Pages</a></div>
    </div>
  </div>
</footer>

</body>
</html>'''
