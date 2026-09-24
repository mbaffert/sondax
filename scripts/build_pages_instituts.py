#!/usr/bin/env python3
"""Génère une page par institut (site/instituts/<slug>.html) et la page de
référence site/instituts.html.

Données sources :
- data/instituts.json            référentiel édité à la main
- data/sondages.json             (champ `principale` posé par principale.py)
- data/candidats.json
- data/derived/series-t1.json    moyenne Sondax, en fond du graphique
- data/derived/commanditaires.json  produit par scripts/instituts.py
- scripts/bios.json              slugs candidat ayant une page dédiée

Le graphique réutilise site/assets/bloc-chart.js, le rendu du graphique de
premier tour de la home.
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
SEUIL_GRAPHIQUE = 5   # sondages de 1er tour, en deçà : pas de graphique
NB_DEFAUT = 4         # candidats cochés par défaut, comme NB_DEFAULT de la home

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
series_t1 = json.loads(_series_path.read_text(encoding="utf-8")).get("series", {}) if _series_path.exists() else {}

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


def periode(debut, fin):
    """Période « du 22 mars au 10 septembre 2026 » (année omise si identique)."""
    if debut == fin:
        return f"le {date_lettres(fin)}"
    d = date_lettres(debut)
    if debut[:4] == fin[:4]:
        d = d.rsplit(" ", 1)[0]
    return f"du {d} au {date_lettres(fin)}"


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

.note { font-size: 13px; color: var(--gris); margin: 4px 0 0; max-width: 64ch; }
/* Graphique : carte blanche comme les blocs de la home, y compris en thème
   sombre (couleurs des candidats et grille pensées pour un fond clair). */
.inst-graph { background: #fff; color: #202632; border: 1px solid #E3E5E0; border-radius: 16px;
  padding: 18px 20px 16px; --gris: #66707D; --bleu-vif: #0C6CF2; }
.inst-graph .candidat-cb { font-size: 14px; }

.section-sep { border-top: 1px solid var(--bord); margin: 24px 0 20px; }
.institut-page h2 { font-size: 18px; margin: 0 0 6px; }

.institut-page table { font-size: 14px; }
.institut-page th { font-size: 11px; padding: 0 12px 6px 0; }
.institut-page td { padding: 6px 12px 6px 0; }
.institut-page tr:last-child td { border-bottom: none; }
.num { text-align: right; white-space: nowrap; }
.institut-page th.num { text-align: right; }
.date a { font-weight: 500; }
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
  .inst-graph { padding: 18px 12px 16px; border-radius: 12px; }
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


def donnees_graphique(liste):
    """Données du graphique institut, ou None sous le seuil.

    Une série par candidat, un point par sondage de l'institut (hypothèse
    principale du 1er tour), None quand le sondage ne le teste pas : la courbe
    s'interrompt, sans interpolation. Candidats : ceux du graphique de la home
    (clés de series-t1.json), « autre » exclu.
    """
    mesures = [(s, h) for s in sorted(liste, key=lambda s: (s["terrain_fin"], s["id"]))
               if (h := hypothese_principale(s))]
    if len(mesures) < SEUIL_GRAPHIQUE:
        return None

    cids = sorted({cid for _, h in mesures for cid in h["scores"]
                   if cid != "autre" and cid in series_t1})
    points = {cid: [] for cid in cids}
    for s, h in mesures:
        meta = {"d": s["terrain_fin"], "institut": s["institut"],
                "terrain_debut": s["terrain_debut"] or s["terrain_fin"],
                "terrain_fin": s["terrain_fin"], "echantillon": s.get("echantillon")}
        for cid in cids:
            points[cid].append({**meta, "v": h["scores"].get(cid)})

    debut, fin = mesures[0][0]["terrain_fin"], mesures[-1][0]["terrain_fin"]
    fond = {cid: [{"d": p["d"], "v": p["v"]} for p in series_t1[cid] if debut <= p["d"] <= fin]
            for cid in cids}

    # Ordre et cases cochées comme sur la home : dernier sondage, score
    # décroissant, les NB_DEFAUT premiers cochés. S'y ajoutent les candidats
    # passés par ce top dans un sondage antérieur mais absents du dernier
    # (Bardella remplacé par Le Pen), pour montrer la rupture.
    def top(h):
        return [c for c, _ in sorted(((c, v) for c, v in h["scores"].items() if c in points),
                                     key=lambda cv: -cv[1])]
    dernier = top(mesures[-1][1])

    def dernier_score(cid):
        return next((p["v"] for p in reversed(points[cid]) if p["v"] is not None), 0)
    ordre = dernier + sorted((c for c in cids if c not in dernier), key=lambda c: -dernier_score(c))
    coches = dernier[:NB_DEFAUT]
    for _, h in mesures:
        coches += [c for c in top(h)[:NB_DEFAUT] if c not in dernier and c not in coches]

    return {
        "dateDebut": debut, "dateFin": fin,
        "candidats": {cid: {k: candidats[cid].get(k) for k in ("nom", "prenom", "couleur", "type")}
                      for cid in cids},
        "points": points, "fond": fond, "ordre": ordre, "coches": coches,
    }


def bloc_graphique(inst, graph):
    donnees = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    pages = json.dumps(sorted(c for c in bios if c in graph["candidats"]))
    nom = ESC(inst["nom_complet"])
    return f"""<div class="section-sep"></div>
    <h2>Évolution des intentions de vote</h2>
    <div class="inst-graph">
      <div class="chart-wrap"><canvas id="chart-institut" role="img"
        aria-label="Intentions de vote au premier tour dans les sondages {nom}"></canvas></div>
      <p class="note">Points : sondages {nom}, hypothèse principale du premier tour.
      Trait fin : moyenne Sondax · <a href="../methodologie.html">méthode</a></p>
      <div class="candidats" id="cb-institut"></div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/date-fns@3/locale/fr/cdn.min.js"></script>
    <script src="../assets/bloc-chart.js?v=1"></script>
    <script>
    const PAGES_CANDIDATS = new Set({pages});
    (function () {{
      const G = {donnees};
      CANDIDATS = G.candidats;
      const bloc = new BlocChart({{
        canvasId: 'chart-institut', cbContainerId: 'cb-institut',
        dateDebut: G.dateDebut, dateFin: G.dateFin, lienPrefix: '../',
      }});
      bloc.courbesBrutes = true;
      bloc.fond = G.fond;
      bloc.enableEndLabels = true;
      bloc.setCandidats(G.points, null, G.ordre, {{ checked: G.coches }});
    }})();
    </script>"""


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
    graph = donnees_graphique(liste)
    evolution = "évolution des intentions de vote, " if graph else ""
    if n == 1:
        meta = (f"Le sondage {nom} sur la présidentielle 2027 ({date_lettres(fin)}) : "
                f"commanditaire, échantillon et notice.")
    else:
        meta = (f"Les {n} sondages {nom} sur la présidentielle 2027, "
                f"{periode(debut, fin)} : {evolution}commanditaires, échantillons et notices.")

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
    {bloc_graphique(inst, graph) if graph else ""}
    {table_sondages(liste, prefix)}
  </div>
</main>"""

    return render_page(
        title=ESC(titre),
        meta_description=ESC(meta),
        canonical=canonical,
        body_content=body,
        extra_head=(EXTRA_CSS + "\n"
                    + ('<link rel="stylesheet" href="../assets/bloc-chart.css?v=1">\n' if graph else "")
                    + jsonld_institut(inst, titre, canonical)),
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
