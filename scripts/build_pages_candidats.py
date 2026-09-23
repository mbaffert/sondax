#!/usr/bin/env python3
"""Génère une page HTML par candidat dans site/<slug>.html.

Utilise generer.py (fonction page()) avec les données de :
- data/derived/series-t1.json (séries lissées + points bruts)
- data/candidats.json (couleurs, slugs)
- data/croisements.json
- scripts/bios.json (fiches biographiques)
- data/photos.json (portraits)
- data/duels.json (duels de second tour)

generer.page() renvoie un document HTML autonome. Ce script en extrait
le contenu <main> et les balises SEO du <head>, puis les injecte dans
le gabarit du site (header, footer, feuille de style du site).
"""

import json, pathlib, datetime, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SITE = ROOT / "site"

import sys
sys.path.insert(0, str(SCRIPTS))
import generer

# ---------- chargement ----------

series_data = json.loads((ROOT / "data" / "derived" / "series-t1.json").read_text())
candidats = json.loads((ROOT / "data" / "candidats.json").read_text())
bios = json.loads((SCRIPTS / "bios.json").read_text())
croisements_raw = json.loads((ROOT / "data" / "croisements.json").read_text())
photos_meta = json.loads((ROOT / "data" / "photos.json").read_text())
duels = json.loads((ROOT / "data" / "duels.json").read_text())

# ---------- noms et pages ----------
noms = {slug: c.get("nom", slug) for slug, c in candidats.items()}
pages = {slug: fiche["nom"] for slug, fiche in bios.items()}

# ---------- photos & crédits ----------

for slug, info in photos_meta.items():
    generer.PHOTOS[slug] = info["fichier"]
    generer.CREDITS[slug] = {
        "auteur": info["auteur"],
        "licence": info["licence"],
        "page": info["source"],
    }

# ---------- croisements ----------
# generer.py attend l'hypothèse correspondant à HYP_CROIS
crois = croisements_raw.get(generer.HYP_CROIS, {})

# Calcul du score national (moyenne pondérée globale depuis les séries)
date_fin = series_data["date_fin"]
national = {}
for cid, pts in series_data["series"].items():
    for p in reversed(pts):
        if p["v"] is not None:
            national[cid] = p["v"]
            break
crois["_national"] = national

# ---------- séries et bruts par candidat ----------

def serie_et_bruts(cid):
    """Retourne (serie, bruts, n_sondages) pour un candidat."""
    # Série lissée : [(date_iso, valeur)]
    raw_serie = series_data["series"].get(cid, [])
    serie = [(p["d"], p["v"]) for p in raw_serie if p["v"] is not None]

    # Points bruts : [(date_iso, score)]
    bruts = []
    for pb in series_data["points_bruts"]:
        if cid in pb["scores"]:
            bruts.append((pb["d"], pb["scores"][cid]))

    # Nombre de sondages dans la fenêtre de 30 jours
    fin = datetime.date.fromisoformat(date_fin)
    debut = fin - datetime.timedelta(days=30)
    n = sum(1 for pb in series_data["points_bruts"]
            if pb["d"] >= debut.isoformat() and cid in pb["scores"])

    return serie, bruts, n


def rangs_et_ecart(cid):
    """Calcule les rangs quotidiens et l'écart avec le candidat devant.

    Les rangs quotidiens viennent des séries lissées (position dans la tendance).
    L'écart avec le candidat devant vient du dernier sondage réel où le candidat
    figure dans l'hypothèse principale — pas des moyennes lissées, pour éviter
    de comparer des candidats qui ne sont jamais testés ensemble.
    """
    all_series = series_data["series"]

    # Exclure prédécesseurs/successeurs du classement (même créneau, jamais testés ensemble)
    exclude = set()
    c_data = candidats.get(cid, {})
    if c_data.get("succede_a"):
        exclude.add(c_data["succede_a"])
    # Aussi exclure les successeurs de ce candidat
    for s, sc in candidats.items():
        if sc.get("succede_a") == cid:
            exclude.add(s)

    # Rangs quotidiens depuis les séries lissées
    pts = all_series.get(cid, [])
    rangs = []
    for i, p in enumerate(pts):
        if p["v"] is None:
            continue
        d = p["d"]
        scores_jour = {}
        for c2, pts2 in all_series.items():
            if c2 in exclude:
                continue
            if i < len(pts2) and pts2[i]["v"] is not None:
                scores_jour[c2] = pts2[i]["v"]
        if cid not in scores_jour:
            continue
        sorted_cids = sorted(scores_jour, key=lambda c: -scores_jour[c])
        rang = sorted_cids.index(cid) + 1
        rangs.append((d, rang))

    # Écart : depuis le dernier sondage réel (hypothèse principale)
    ecart_devant = None
    sondages_raw = json.loads((ROOT / "data" / "sondages.json").read_text())
    # Parcourir les sondages du plus récent au plus ancien
    sondages_raw.sort(key=lambda s: s["terrain_fin"], reverse=True)
    for s in sondages_raw:
        # Trouver l'hypothèse principale T1 contenant ce candidat
        for h in s["hypotheses"]:
            if h.get("tour") != 1 or not h.get("principale"):
                continue
            if cid not in h.get("scores", {}):
                continue
            # Classer les scores de cette hypothèse
            scores = {k: v for k, v in h["scores"].items() if k != "autre"}
            sorted_cids = sorted(scores, key=lambda c: -scores[c])
            rang_ici = sorted_cids.index(cid) + 1
            if rang_ici > 1:
                devant_cid = sorted_cids[rang_ici - 2]
                devant_nom = (bios.get(devant_cid, {}).get("nom")
                              or candidats.get(devant_cid, {}).get("nom", devant_cid))
                ecart = scores[devant_cid] - scores[cid]
                ecart_devant = (devant_nom, round(ecart, 1))
            break
        if ecart_devant is not None or any(
            h.get("tour") == 1 and h.get("principale") and cid in h.get("scores", {})
            for h in s["hypotheses"]
        ):
            break  # On a trouvé le dernier sondage avec ce candidat

    return rangs, ecart_devant


# ---------- extraction du HTML de generer.py ----------

def extract_seo(head_html):
    """Extrait title, meta description, canonical, OG, twitter et JSON-LD du <head>."""
    tags = []
    # <title>
    m = re.search(r'<title>.*?</title>', head_html, re.S)
    if m: tags.append(m.group())
    # meta description
    m = re.search(r'<meta name="description"[^>]*>', head_html)
    if m: tags.append(m.group())
    # canonical
    m = re.search(r'<link rel="canonical"[^>]*>', head_html)
    if m: tags.append(m.group())
    # OG tags
    for m in re.finditer(r'<meta property="og:[^"]*"[^>]*>', head_html):
        tags.append(m.group())
    # twitter card
    for m in re.finditer(r'<meta name="twitter:[^"]*"[^>]*>', head_html):
        tags.append(m.group())
    # JSON-LD
    m = re.search(r'<script type="application/ld\+json">.*?</script>', head_html, re.S)
    if m: tags.append(m.group())
    return "\n".join(tags)


def extract_main(raw_html):
    """Extrait le contenu de <div class="page-candidat"><main>...</main></div>."""
    # Essayer d'abord le wrapper page-candidat
    m = re.search(r'<div class="page-candidat">\s*<main>(.*?)</main>\s*</div>', raw_html, re.S)
    if m:
        return m.group(1).strip()
    # Fallback sur <main>...</main>
    m = re.search(r'<main>(.*)</main>', raw_html, re.S)
    return m.group(1).strip() if m else raw_html


def extract_head(raw_html):
    """Extrait le contenu entre <head> et </head>."""
    m = re.search(r'<head>(.*?)</head>', raw_html, re.S)
    return m.group(1) if m else ""


# Le CSS candidat (déjà scopé sous .page-candidat), lu une seule fois
_RAW_CANDIDAT_CSS = (SITE / "style-candidat.css").read_text()


def wrap_in_site_template(slug, fiche, raw_html):
    """Injecte le contenu candidat dans le gabarit du site."""
    coul = fiche["couleur"]
    head_html = extract_head(raw_html)
    seo_tags = extract_seo(head_html)
    main_content = extract_main(raw_html)

    # CSS candidat avec la couleur du candidat injectée
    candidat_css = _RAW_CANDIDAT_CSS.replace("__COULEUR__", coul)

    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{seo_tags}
<meta property="og:site_name" content="Sondax">
<meta property="og:locale" content="fr_FR">
<meta property="og:image" content="https://sondax.fr/assets/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<script data-goatcounter="https://sondax.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
<link rel="icon" type="image/svg+xml" href="assets/logo-sondax.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/header.css?v=3">
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

  /* Footer du site */
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
<style>
/* CSS candidat (scopé sous .page-candidat) */
{candidat_css}
</style>
</head>
<body>

<div id="site-header" class="sh"></div>
<script src="assets/header-data.js?v=3"></script>
<script src="assets/header.js?v=3"></script>

<div class="page-candidat">
<main>
{main_content}
</main>
</div>

<footer class="site-footer">
  <div class="footer-inner">
    <div>
      <div style="margin-bottom:10px;">
        <img src="assets/logo-sondax-blanc.svg" alt="Sondax" style="height:22px;">
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
        <a href="methodologie.html">Méthodologie</a>
        <a href="sondages.html">Tous les sondages</a>
        <a href="donnees.html">Données</a>
        <a href="a-propos.html">À propos</a>
      </div>
    </div>
    <div>
      <div><a href="mailto:contact@sondax.fr">Contact</a></div>
      <div>Hébergeur · <a href="https://pages.github.com" target="_blank">GitHub Pages</a></div>
    </div>
  </div>
</footer>

</body>
</html>'''


# ---------- génération ----------

count = 0
for slug, fiche in bios.items():
    serie, bruts, n_sondages = serie_et_bruts(slug)
    if not serie:
        print(f"  skip  {slug} (aucune série)")
        continue

    rangs, ecart_devant = rangs_et_ecart(slug)

    # Succession (ex. Bardella → Le Pen)
    c_data = candidats.get(slug, {})
    pred = c_data.get("succede_a")
    succession = None
    if pred:
        succ_date = c_data.get("succession_le")
        pred_nom = candidats.get(pred, {}).get("prenom", "") + " " + candidats.get(pred, {}).get("nom", pred)
        succ_nom = fiche["nom"]
        succession = (succ_date, pred_nom.strip(), succ_nom)

    raw_html = generer.page(
        slug=slug,
        fiche=fiche,
        serie=serie,
        bruts=bruts,
        n_sondages=n_sondages,
        crois=crois,
        base=None,
        rangs=rangs,
        ecart_devant=ecart_devant,
        duels=duels,
        noms=noms,
        pages=pages,
        succession=succession,
    )

    final_html = wrap_in_site_template(slug, fiche, raw_html)

    out = SITE / f"{slug}.html"
    out.write_text(final_html, encoding="utf-8")
    count += 1
    print(f"  OK  {slug}.html")

print(f"\n{count} pages candidat générées dans site/")
