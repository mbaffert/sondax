#!/usr/bin/env python3
"""Génère une page par institut (site/instituts/<slug>.html) et la page de
référence site/instituts.html.

Données sources :
- data/instituts.json            référentiel édité à la main
- data/sondages.json             (champ `principale` posé par principale.py)
- data/candidats.json
- data/derived/series-t1.json    moyenne pondérée (écart à la moyenne)
- data/derived/commanditaires.json  produit par scripts/instituts.py
- scripts/bios.json              slugs candidat ayant une page dédiée
"""

import datetime
import html as html_mod
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SITE = ROOT / "site"
DATA = ROOT / "data"

sys.path.insert(0, str(SCRIPTS))
from site_template import render_page
from instituts import charger_referentiel, slug_institut, logo_disponible

BASE = "https://sondax.fr"
SEUIL_MESURES = 3

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

ESC = html_mod.escape


# ---------- chargement ----------

def charger(nom):
    return json.loads((DATA / nom).read_text(encoding="utf-8"))


referentiel = charger_referentiel()
sondages = charger("sondages.json")
candidats = charger("candidats.json")
bios = json.loads((SCRIPTS / "bios.json").read_text(encoding="utf-8"))

_series_path = DATA / "derived" / "series-t1.json"
series_data = json.loads(_series_path.read_text(encoding="utf-8")) if _series_path.exists() else {}
_comm_path = DATA / "derived" / "commanditaires.json"
commanditaires = json.loads(_comm_path.read_text(encoding="utf-8")) if _comm_path.exists() else {}


# ---------- helpers ----------

def date_lettres(iso):
    y, m, d = iso.split("-")
    j = "1er" if d == "01" else str(int(d))
    return f"{j} {MOIS[int(m) - 1]} {y}"


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def fmt_ech(n):
    return f"{round(n):,}".replace(",", "\u202f")


def fmt_ecart(v):
    v = round(v, 1)
    if v == 0:
        v = 0.0  # évite « -0,0 »
    signe = "+" if v > 0 else ("−" if v < 0 else "")
    return f"{signe}{abs(v):.1f}".replace(".", ",") + "\u202fpt"


def periode(debut, fin):
    """Période « du 22 mars au 10 septembre 2026 » (année omise si identique)."""
    if debut == fin:
        return f"le {date_lettres(fin)}"
    d = date_lettres(debut)
    if debut[:4] == fin[:4]:
        d = d.rsplit(" ", 1)[0]
    return f"du {d} au {date_lettres(fin)}"


def nom_candidat(cid):
    c = candidats.get(cid, {})
    parts = [p for p in (c.get("prenom", ""), c.get("nom", "")) if p]
    return " ".join(parts) if parts else cid


def lien_candidat(cid, prefix):
    esc = ESC(nom_candidat(cid))
    if cid in bios:
        return f'<a href="{prefix}{ESC(cid)}.html">{esc}</a>'
    return esc


def moyenne_a_date(cid, date_iso):
    """Valeur de la série lissée pour `cid` à `date_iso`, ou None.

    Même calcul que la colonne « Écart / moy. » des fiches sondage
    (build_sondage_pages.moyenne_a_date)."""
    val = None
    for p in series_data.get("series", {}).get(cid, []):
        if p["d"] > date_iso:
            break
        if p["v"] is not None:
            val = p["v"]
    return val


def hypothese_principale(sondage):
    for h in sondage.get("hypotheses", []):
        if h.get("tour") == 1 and h.get("principale"):
            return h
    return None


def est_notice(url):
    return bool(url) and "commission-des-sondages.fr" in url


def nom_commanditaire(sondage):
    return (commanditaires.get(sondage["id"]) or {}).get("nom")


# ---------- regroupement ----------

par_institut = {}
for s in sondages:
    slug = slug_institut(s["institut"], referentiel)
    if not slug:
        print(f"  institut absent du référentiel : {s['institut']} ({s['id']})")
        continue
    par_institut.setdefault(slug, []).append(s)

for lst in par_institut.values():
    lst.sort(key=lambda s: (s["terrain_fin"], s.get("echantillon") or 0), reverse=True)


# ---------- calculs ----------

def ecarts_par_candidat(liste):
    """{cid: [écart, ...]} sur l'hypothèse principale T1 de chaque sondage."""
    ecarts = {}
    scores = {}
    for s in liste:
        h = hypothese_principale(s)
        if not h:
            continue
        for cid, score in h.get("scores", {}).items():
            if cid == "autre":
                continue
            moy = moyenne_a_date(cid, s["terrain_fin"])
            if moy is None:
                continue
            ecarts.setdefault(cid, []).append(score - moy)
            scores.setdefault(cid, []).append(score)
    return ecarts, scores


def chapeau(inst, liste):
    n = len(liste)
    nom = ESC(inst["nom_complet"])
    debut = min(s["terrain_fin"] for s in liste)
    fin = max(s["terrain_fin"] for s in liste)

    if n == 1:
        phrases = [f"Sondax recense un sondage {nom} sur la présidentielle 2027, "
                   f"dont le terrain s’est achevé le {date_lettres(fin)}."]
    else:
        jours = (datetime.date.fromisoformat(fin) - datetime.date.fromisoformat(debut)).days
        intervalle = round(jours / (n - 1))
        frequence = (f", soit en moyenne un sondage tous les {intervalle}\u00a0jours"
                     if intervalle >= 1 else "")
        phrases = [f"Sondax recense {n}\u00a0sondages {nom} sur la présidentielle 2027, "
                   f"dont les terrains se sont achevés {periode(debut, fin)}{frequence}."]

    comm = Counter(c for c in (nom_commanditaire(s) for s in liste) if c)
    if comm:
        top = comm.most_common(3)
        items = [f"{ESC(c)} ({k})" if n > 1 else ESC(c) for c, k in top]
        if len(items) == 1:
            if n == 1:
                phrases.append(f"Commanditaire : {items[0]}.")
            else:
                c, k = top[0]
                phrases.append(f"Principal commanditaire : {ESC(c)} "
                               f"({k}\u00a0sondage{'s' if k > 1 else ''} sur {n}).")
        else:
            txt = ", ".join(items[:-1]) + " et " + items[-1]
            phrases.append(f"Principaux commanditaires : {txt}.")

    mode = inst.get("mode_recueil")
    if mode:
        phrases.append(f"Recueil {ESC(mode)}.")

    return " ".join(phrases).replace(" :", "\u00a0:")


# ---------- page institut ----------

EXTRA_CSS = """<style>
.institut-page { padding: 24px 16px 40px; }
.institut-inner { max-width: 780px; margin: 0 auto; }

.inst-logo { display: block; height: 28px; width: auto; max-width: 220px;
  margin: 0 0 16px; }
.inst-site { font-size: 13.5px; color: var(--gris); margin: -8px 0 0; }
.inst-site a { font-weight: 500; }
.inst-chapeau { font-size: 15px; margin-top: 16px; max-width: 64ch; }

.section-sep { border-top: 1px solid var(--bord); margin: 24px 0 20px; }
.institut-page h2 { font-size: 18px; margin: 0 0 6px; }
.note { font-size: 13px; color: var(--gris); margin: 0 0 12px; max-width: 64ch; }

.institut-page table { font-size: 14px; }
.institut-page th { font-size: 11px; padding: 0 12px 6px 0; }
.institut-page td { padding: 6px 12px 6px 0; }
.institut-page tr:last-child td { border-bottom: none; }
.num { text-align: right; white-space: nowrap; }
.institut-page th.num { text-align: right; }
.cand a, .date a { font-weight: 500; }
.cand a { color: var(--texte); }
.cand a:hover { color: var(--bleu-vif); }
td.muet { color: var(--gris); }
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }

/* Liste des instituts */
.liste-instituts td { vertical-align: middle; }
.liste-instituts .logo-cell { width: 120px; padding-right: 16px; }
.liste-instituts .logo-cell img { display: block; height: 18px; width: auto; max-width: 110px; }
.liste-instituts .inst-nom a { font-weight: 600; }

@media (max-width: 600px) {
  .institut-page h1 { font-size: 24px; }
  .liste-instituts .logo-cell { width: 76px; padding-right: 10px; }
  .liste-instituts .logo-cell img { height: 14px; max-width: 70px; }
  .col-ech { display: none; }
}

/* Thème sombre : contenu de la page (le bandeau d'en-tête reste commun au site) */
@media (prefers-color-scheme: dark) {
  :root { --fond: #14181E; --carte: #1C212A; --bord: #2B313A;
          --texte: #E9EBE6; --gris: #96A0AC; --bleu-vif: #5B9DFF; }
  .logo-mono { filter: invert(1); }
}
</style>"""


def logo_html(inst, classe, prefix):
    chemin = logo_disponible(inst)
    if not chemin:
        return ""
    return (f'<img class="{classe} logo-mono" src="{prefix}{ESC(chemin)}" '
            f'alt="Logo {ESC(inst["nom_complet"])}">')


def jsonld_institut(inst, titre, canonical):
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": inst["nom_complet"],
    }
    if inst["nom"] != inst["nom_complet"]:
        org["alternateName"] = inst["nom"]
    if inst.get("site"):
        org["url"] = inst["site"]
    chemin = logo_disponible(inst)
    if chemin:
        org["logo"] = f"{BASE}/{chemin}"
    org["subjectOf"] = {"@type": "WebPage", "name": titre, "url": canonical}
    return ('<script type="application/ld+json">'
            + json.dumps(org, ensure_ascii=False)
            + "</script>")


def table_ecarts(inst, liste, prefix):
    ecarts, scores = ecarts_par_candidat(liste)
    retenus = [cid for cid, e in ecarts.items() if len(e) >= SEUIL_MESURES]
    if not retenus:
        return ""
    # Ordre : score moyen mesuré par l'institut, décroissant (pas l'écart,
    # pour ne pas présenter le tableau comme un classement)
    retenus.sort(key=lambda c: (-sum(scores[c]) / len(scores[c]), nom_candidat(c)))
    rows = []
    for cid in retenus:
        e = ecarts[cid]
        rows.append(
            f'<tr><td class="cand">{lien_candidat(cid, prefix)}</td>'
            f'<td class="num">{fmt_ecart(sum(e) / len(e))}</td>'
            f'<td class="num muet">{len(e)}</td></tr>'
        )
    nom = ESC(inst["nom_complet"])
    return f"""<div class="section-sep"></div>
    <h2>Écart moyen à la moyenne Sondax</h2>
    <p class="note">Pour chaque sondage {nom}, score de l’hypothèse principale du premier tour
    comparé à la moyenne pondérée Sondax à la date de fin de terrain, comme dans la colonne
    «\u00a0Écart / moy.\u00a0» des fiches. Candidats mesurés au moins {SEUIL_MESURES}\u00a0fois.
    Ces écarts décrivent les résultats publiés\u00a0; ils ne corrigent pas la moyenne.</p>
    <table>
      <thead><tr><th>Candidat</th><th class="num">Écart moyen</th><th class="num">Mesures</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>"""


def table_sondages(liste, prefix):
    rows = []
    for s in liste:
        if s["terrain_debut"] and s["terrain_debut"] != s["terrain_fin"]:
            dates = f'{fmt_date(s["terrain_debut"])} → {fmt_date(s["terrain_fin"])}'
        else:
            dates = fmt_date(s["terrain_fin"])
        comm = nom_commanditaire(s)
        comm_html = ESC(comm) if comm else "—"
        ech = fmt_ech(s["echantillon"]) if s.get("echantillon") else "—"
        url = s.get("url_source")
        if url:
            lib = "Notice" if est_notice(url) else "Publication"
            src = f'<a href="{ESC(url)}" target="_blank" rel="noopener">{lib}</a>'
        else:
            src = "—"
        rows.append(
            f'<tr><td class="date"><a href="{prefix}sondages/{ESC(s["id"])}.html">{dates}</a></td>'
            f'<td>{comm_html}</td>'
            f'<td class="num col-ech">{ech}</td>'
            f'<td>{src}</td></tr>'
        )
    return f"""<div class="section-sep"></div>
    <h2>Sondages publiés</h2>
    <div class="table-scroll">
    <table>
      <thead><tr><th>Terrain</th><th>Commanditaire</th><th class="num col-ech">Échantillon</th><th>Source</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
    </div>"""


def build_page_institut(slug, inst, liste):
    prefix = "../"
    nom = inst["nom_complet"]
    titre = f"Sondages {nom} — présidentielle 2027"
    canonical = f"{BASE}/instituts/{slug}.html"
    n = len(liste)
    debut = min(s["terrain_fin"] for s in liste)
    fin = max(s["terrain_fin"] for s in liste)
    if n == 1:
        meta = (f"Le sondage {nom} sur la présidentielle 2027 ({date_lettres(fin)}) : "
                f"commanditaire, échantillon, notice et écart à la moyenne Sondax.")
    else:
        meta = (f"Les {n} sondages {nom} sur la présidentielle 2027, "
                f"{periode(debut, fin)} : commanditaires, échantillons, notices "
                f"et écart moyen de chaque candidat à la moyenne Sondax.")

    site_html = ""
    if inst.get("site"):
        dom = inst["site"].split("//", 1)[-1].rstrip("/")
        site_html = f'<p class="inst-site"><a href="{ESC(inst["site"])}">{ESC(dom)}</a></p>'

    body = f"""<main class="institut-page">
  <div class="institut-inner">
    <nav class="fil" aria-label="Fil d’Ariane"><a href="../">Sondax</a> › <a href="../instituts.html">Instituts</a></nav>
    {logo_html(inst, "inst-logo", prefix)}
    <h1>Sondages {ESC(nom)} — présidentielle 2027</h1>
    {site_html}
    <p class="inst-chapeau">{chapeau(inst, liste)}</p>
    {table_ecarts(inst, liste, prefix)}
    {table_sondages(liste, prefix)}
  </div>
</main>"""

    return render_page(
        title=ESC(titre),
        meta_description=ESC(meta),
        canonical=canonical,
        body_content=body,
        extra_head=EXTRA_CSS + "\n" + jsonld_institut(inst, titre, canonical),
        depth=1,
    )


# ---------- page de référence ----------

def build_page_index(slugs):
    total = sum(len(par_institut[s]) for s in slugs)
    debut = min(s["terrain_fin"] for sl in slugs for s in par_institut[sl])
    fin = max(s["terrain_fin"] for sl in slugs for s in par_institut[sl])

    intro = (f"Sondax recense {total}\u00a0sondages d’intentions de vote pour la "
             f"présidentielle 2027, publiés par {len(slugs)}\u00a0instituts. "
             f"Leurs terrains se sont achevés {periode(debut, fin)}.")

    rows = []
    for slug in slugs:
        inst = referentiel[slug]
        liste = par_institut[slug]
        rows.append(
            f'<tr><td class="logo-cell">{logo_html(inst, "", "")}</td>'
            f'<td class="inst-nom"><a href="instituts/{slug}.html">{ESC(inst["nom_complet"])}</a></td>'
            f'<td class="num">{len(liste)}</td>'
            f'<td class="num">{fmt_date(liste[0]["terrain_fin"])}</td></tr>'
        )

    body = f"""<main class="institut-page">
  <div class="institut-inner">
    <nav class="fil" aria-label="Fil d’Ariane"><a href="./">Sondax</a></nav>
    <h1>Instituts de sondage de la présidentielle 2027</h1>
    <p class="inst-chapeau">{intro}</p>
    <div class="section-sep"></div>
    <table class="liste-instituts">
      <thead><tr><th><span class="sr-only">Logo</span></th><th>Institut</th><th class="num">Sondages</th><th class="num">Dernier</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
  </div>
</main>"""

    css = EXTRA_CSS.replace(
        "</style>",
        ".sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }\n</style>",
    )
    return render_page(
        title="Instituts de sondage — présidentielle 2027",
        meta_description=ESC(
            f"Les {len(slugs)} instituts de sondage qui mesurent les intentions de vote "
            f"pour la présidentielle 2027 : {total} sondages, nombre par institut et date du dernier."
        ),
        canonical=f"{BASE}/instituts.html",
        body_content=body,
        extra_head=css,
        depth=0,
    )


# ---------- génération ----------

def main():
    out_dir = SITE / "instituts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.html"):
        f.unlink()

    slugs = sorted(par_institut, key=lambda s: (-len(par_institut[s]),
                                                referentiel[s]["nom_complet"].lower()))
    sans_logo = []
    for slug in slugs:
        inst = referentiel[slug]
        if not logo_disponible(inst):
            sans_logo.append(slug)
        (out_dir / f"{slug}.html").write_text(
            build_page_institut(slug, inst, par_institut[slug]), encoding="utf-8")

    (SITE / "instituts.html").write_text(build_page_index(slugs), encoding="utf-8")
    print(f"{len(slugs)} pages institut générées dans site/instituts/ + site/instituts.html")
    if sans_logo:
        print(f"  logo manquant : {', '.join(sans_logo)}")


if __name__ == "__main__":
    main()
