"""Génère les pages des présidentielles passées : precedentes-elections.html et
presidentielle-{2002,2007,2012,2017,2022}.html (remplace build_elections_chapeaux.py).

Chaque page est réécrite en entier à chaque exécution : ne pas la modifier à la
main, modifier ce script (HTML) ou site/assets/historique.css (styles).

Données lues, sans valeur recopiée dans le script :
- data/resultats.json (collecte_resultats.py) : résultats officiels des deux
  tours (voix, % des exprimés, % des inscrits, inscrits, votants, blancs, nuls) ;
- data/derived/historique.json (series_historique.py) : noms courts, couleurs,
  dates des tours, duel final, sondages ; data/historique.json : noms complets
  (rapprochement avec resultats.json) et sondages bruts pour les moyennes
  mensuelles ;
- data/derived/retro.json (build_retro.py) : Rétro-Sondax de la page d'index.

Page d'une élection, dans l'ordre : synthèse (trois premiers du premier tour,
finalistes, participation), sondages du premier tour (graphique de
assets/historique.js), résultats définitifs du premier tour, sondages du second
tour (graphique, duel final par défaut), résultats définitifs du second tour,
navigation vers les autres millésimes. Les moyennes mensuelles des sondages de
premier tour restent dans le HTML, repliées sous le graphique.

À lancer après build_retro.py ; avant build_header.py --injecter, build_dates.py
et build_jsonld_navigation.py, qui complètent les pages.
"""

import html, json, pathlib, sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
HISTORIQUE_PATH = ROOT / "data" / "derived" / "historique.json"
HISTORIQUE_BRUT_PATH = ROOT / "data" / "historique.json"
RESULTATS_PATH = ROOT / "data" / "resultats.json"
RETRO_PATH = ROOT / "data" / "derived" / "retro.json"

sys.path.insert(0, str(ROOT / "scripts"))
from series import score_candidat
from balise_time import time_tag
from build_retro import rendre_bloc_page, j_du_jour

ANNEES = ["2002", "2007", "2012", "2017", "2022"]

# Principaux candidats du tableau des moyennes : présents au premier tour, et
# 5 % des suffrages exprimés ou 10 % de moyenne mensuelle au moins une fois.
SEUIL_RESULTAT = 5
SEUIL_MOYENNE = 10

# Président sortant, quand son élection précédente est hors de resultats.json
# (2002 : Jacques Chirac, élu en 1995). Sert au « réélu » du titre de synthèse ;
# pour les autres années, le sortant se déduit de l'élection précédente du fichier.
SORTANT_HORS_FICHIER = {"2002": "Jacques Chirac"}

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
NBSP = " "


# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------

def fmt_pct(v):
    return "—" if v is None else f"{v:.2f}{NBSP}%".replace(".", ",")


def fmt_pct1(v):
    return "—" if v is None else f"{v:.1f}{NBSP}%".replace(".", ",")


def fmt_entier(n):
    """48747876 → '48 747 876' (espaces insécables)."""
    return f"{n:,}".replace(",", NBSP)


def pct_exact(n, base):
    """Pourcentage au centième, arrondi demi vers le haut (comme collecte_resultats.py)."""
    q = Decimal(n) * 100 / Decimal(base)
    return float(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def date_fr(iso, premier=False):
    """'2002-04-21' → '21 avril 2002' ('1er' pour le premier du mois si premier)."""
    y, m, d = (int(x) for x in iso.split("-"))
    jour = "1er" if premier and d == 1 else str(d)
    return f"{jour} {MOIS[m - 1]} {y}"


def date_tag(iso):
    return time_tag(iso, date_fr(iso, True))


def dates_courtes(iso1, iso2):
    """'10 et 24 avril' (même mois) ou '22 avril et 6 mai', avec une balise time par date."""
    (_, m1, d1), (_, m2, d2) = ([int(x) for x in i.split("-")] for i in (iso1, iso2))
    j1 = "1er" if d1 == 1 else str(d1)
    j2 = "1er" if d2 == 1 else str(d2)
    if m1 == m2:
        return f'{time_tag(iso1, j1)} et {time_tag(iso2, f"{j2} {MOIS[m2 - 1]}")}'
    return f'{time_tag(iso1, f"{j1} {MOIS[m1 - 1]}")} et {time_tag(iso2, f"{j2} {MOIS[m2 - 1]}")}'


def esc(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------------------
# Données d'une élection
# ---------------------------------------------------------------------------

class Election:
    """Résultats officiels + habillage (noms courts, couleurs) d'une élection."""

    def __init__(self, annee, derive, brut, res):
        self.annee = annee
        self.derive = derive
        self.brut = brut
        self.res = res
        self.tour1, self.tour2 = res["date_t1"], res["date_t2"]
        self.t1, self.t2 = res["t1"], res["t2"]
        # nom complet (resultats.json) → (nom court, couleur) du dérivé
        self.habillage = {}
        for cid, info in brut["candidats"].items():
            d = derive["candidats"].get(cid)
            if d:
                self.habillage[info["nom"]] = (d["nom"], d.get("couleur") or "#8A8F98")

    def court(self, nom):
        return self.habillage.get(nom, (nom, "#8A8F98"))[0]

    def couleur(self, nom):
        return self.habillage.get(nom, (nom, "#8A8F98"))[1]

    @property
    def vainqueur(self):
        return max(self.t2["candidats"], key=lambda c: c["voix"])


def charger():
    for p in (HISTORIQUE_PATH, HISTORIQUE_BRUT_PATH, RESULTATS_PATH, RETRO_PATH):
        if not p.exists():
            sys.exit(f"Fichier manquant : {p.relative_to(ROOT)} (lancer series_historique.py, build_retro.py)")
    derive = json.loads(HISTORIQUE_PATH.read_text(encoding="utf-8"))
    brut = json.loads(HISTORIQUE_BRUT_PATH.read_text(encoding="utf-8"))["elections"]
    resultats = json.loads(RESULTATS_PATH.read_text(encoding="utf-8"))
    retro = json.loads(RETRO_PATH.read_text(encoding="utf-8"))
    elections = {}
    for a in ANNEES:
        if a not in derive or a not in resultats:
            sys.exit(f"{a} : données manquantes (historique.json ou resultats.json)")
        elections[a] = Election(a, derive[a], brut[a], resultats[a])
    return elections, brut, retro


# ---------------------------------------------------------------------------
# Blocs HTML
# ---------------------------------------------------------------------------

def barres(lignes, classe=""):
    """Liste de barres horizontales : [(nom, pct, couleur, largeur en %)]."""
    items = "".join(
        f'<li><span class="b-nom">{esc(nom)}</span><span class="b-val">{fmt_pct(pct)}</span>'
        f'<span class="b-piste"><span class="b-barre" style="width:{larg:.1f}%;background:{coul}"></span></span></li>'
        for nom, pct, coul, larg in lignes)
    return f'<ul class="barres{" " + classe if classe else ""}">{items}</ul>'


def titre_synthese(e, elections):
    gagnant = e.vainqueur
    precedent = str(int(e.annee) - 5)
    sortant = (elections[precedent].vainqueur["nom"] if precedent in elections
               else SORTANT_HORS_FICHIER.get(e.annee))
    verbe = "réélu" if sortant == gagnant["nom"] else "élu"
    return f'{esc(gagnant["nom"])} {verbe} avec {fmt_pct(gagnant["pct_exprimes"])} des suffrages exprimés'


def bloc_synthese(e, elections):
    top = e.t1["candidats"][:3]
    tete = top[0]["pct_exprimes"]
    t1 = barres([(e.court(c["nom"]), c["pct_exprimes"], e.couleur(c["nom"]),
                  100 * c["pct_exprimes"] / tete) for c in top])
    t2 = barres([(e.court(c["nom"]), c["pct_exprimes"], e.couleur(c["nom"]), c["pct_exprimes"])
                 for c in e.t2["candidats"]], "barres-t2")
    part = pct_exact(e.t2["votants"], e.t2["inscrits"])
    return f"""  <section class="carte" id="synthese" aria-labelledby="h-synthese">
    <p class="surtitre">L’élection en un coup d’œil</p>
    <h2 id="h-synthese">{titre_synthese(e, elections)}</h2>
    <div class="synthese-grille">
      <div class="synthese-col">
        <h3>Premier tour</h3>
        <p class="date">{date_tag(e.tour1)}</p>
        {t1}
      </div>
      <div class="synthese-col">
        <h3>Second tour</h3>
        <p class="date">{date_tag(e.tour2)}</p>
        {t2}
        <p class="participation">Participation : <strong>{fmt_pct(part)}</strong></p>
      </div>
    </div>
  </section>"""


def groupe_periode(ident, annee, borne):
    """Boutons de période d'un graphique (lus par historique.js)."""
    return f"""<div class="groupe" id="{ident}" role="group" aria-label="Période affichée">
        <button type="button" data-months="0" class="active">Depuis <time datetime="{borne[:7]}">{MOIS[int(borne[5:7]) - 1]} {borne[:4]}</time></button>
        <button type="button" data-months="12">1 an</button>
        <button type="button" data-months="6">6 mois</button>
        <button type="button" data-months="3">3 mois</button>
      </div>"""


def moyennes_mensuelles(brut, derive):
    """{candidat: {"AAAA-MM": moyenne}} des sondages de premier tour du périmètre affiché
    (terrain commencé à partir de la borne, fini avant le premier tour)."""
    borne, tour1 = derive["borne"], derive["tour1"]
    valeurs = defaultdict(lambda: defaultdict(list))
    for s in brut["sondages"]:
        if s["terrain_debut"] < borne or s["terrain_fin"] >= tour1:
            continue
        mois = s["terrain_fin"][:7]
        for cid in derive["candidats"]:
            score, _ = score_candidat(s, cid)
            if score is not None:
                valeurs[cid][mois].append(score)
    return {cid: {m: sum(v) / len(v) for m, v in par_mois.items()}
            for cid, par_mois in valeurs.items()}


def tableau_moyennes(brut, derive):
    """Tableau HTML : une ligne par mois, une colonne par principal candidat,
    le résultat du premier tour en dernière ligne ; '' sans donnée."""
    moyennes = moyennes_mensuelles(brut, derive)
    cands = derive["candidats"]
    principaux = [
        c for c, info in cands.items()
        if info.get("resultat") is not None and c in moyennes
        and (info["resultat"] >= SEUIL_RESULTAT or max(moyennes[c].values()) >= SEUIL_MOYENNE)
    ]
    principaux.sort(key=lambda c: -cands[c]["resultat"])
    mois = sorted({m for c in principaux for m in moyennes[c]})
    if not principaux or not mois:
        return ""
    tete = "".join(f'<th scope="col" class="num">{esc(cands[c]["nom"])}</th>' for c in principaux)
    lignes = []
    for m in mois:
        y, mm = m.split("-")
        cellules = "".join(
            f'<td class="num">{fmt_pct1(moyennes[c][m]) if m in moyennes[c] else "—"}</td>'
            for c in principaux)
        lignes.append(f'<tr><th scope="row">{time_tag(m, f"{MOIS[int(mm) - 1]} {y}")}</th>{cellules}</tr>')
    resultats = "".join(f'<td class="num">{fmt_pct(cands[c]["resultat"])}</td>' for c in principaux)
    lignes.append(f'<tr class="resultat"><th scope="row">Résultat du premier tour</th>{resultats}</tr>')
    return f"""<details class="moyennes-details">
      <summary>Moyennes mensuelles des sondages</summary>
      <div class="moyennes-scroll">
        <table class="moyennes">
          <thead><tr><th scope="col">Mois</th>{tete}</tr></thead>
          <tbody>
            {(chr(10) + "            ").join(lignes)}
          </tbody>
        </table>
      </div>
    </details>"""


def bloc_sondages_t1(e):
    d = e.derive
    resume = f"{d['nb_sondages_t1']} sondages depuis janvier {d['borne'][:4]}"
    if d.get("nb_rollings_t1", 0) > 0:
        resume += f" dont {d['nb_rollings_t1']} vagues de rolling"
    return f"""  <section class="carte" id="sondages-premier-tour" aria-labelledby="h-sondages-t1">
    <p class="surtitre">Sondages · Premier tour</p>
    <h2 id="h-sondages-t1"><span class="sr-only">Sondages du premier tour de la présidentielle {e.annee} : </span>Évolution des intentions de vote</h2>
    <p class="subtitle">L’évolution des principales candidatures jusqu’au premier tour.</p>
    <div class="controles">
      {groupe_periode("periode-t1", e.annee, d["borne"])}
    </div>
    <div class="chart-wrap"><canvas id="chart-t1" role="img" aria-label="Graphique de l’évolution des intentions de vote au premier tour de la présidentielle {e.annee}"></canvas></div>
    <p class="resume" id="resume">{resume}.</p>
    <div class="candidats" id="candidats-t1"></div>
    {tableau_moyennes(e.brut, d)}
  </section>"""


def ordre_duel(e):
    """Candidats du duel final, vainqueur d'abord, en noms courts."""
    return [e.court(c["nom"]) for c in sorted(e.t2["candidats"], key=lambda c: -c["voix"])]


def bloc_sondages_t2(e):
    noms = " – ".join(esc(n) for n in ordre_duel(e))
    return f"""  <section class="carte" id="sondages-second-tour" aria-labelledby="h-sondages-t2">
    <p class="surtitre">Sondages · Second tour</p>
    <h2 id="h-sondages-t2"><span class="sr-only">Sondages du second tour de la présidentielle {e.annee} : </span><span id="t2-titre">{noms}</span> : évolution des intentions de vote</h2>
    <p class="subtitle">L’évolution des enquêtes de second tour jusqu’au vote.</p>
    <div class="controles">
      <div class="duel-select" id="duel-select">
        <label for="duel-cand1">Candidat :</label>
        <select id="duel-cand1"></select>
        <label for="duel-cand2">contre :</label>
        <select id="duel-cand2"></select>
      </div>
      {groupe_periode("periode-t2", e.annee, e.derive["borne"])}
    </div>
    <div id="t2-content"></div>
  </section>"""


def tableau_resultats(tour, e):
    """Tableau des résultats d'un tour : voix, % des exprimés (avec barre), % des inscrits."""
    tete = tour["candidats"][0]["voix"] or 1
    lignes = []
    for c in tour["candidats"]:
        w = round(c["voix"] / tete, 4)
        lignes.append(
            f'<tr><th scope="row">{esc(c["nom"])}</th>'
            f'<td class="num">{fmt_entier(c["voix"])}</td>'
            f'<td class="num barre"><span class="barre-fond" style="--w:{w};background:{e.couleur(c["nom"])}"></span>'
            f'<span class="barre-val">{fmt_pct(c["pct_exprimes"])}</span></td>'
            f'<td class="num">{fmt_pct(c["pct_inscrits"])}</td></tr>')
    ins = tour["inscrits"]
    stats = [("Inscrits", fmt_entier(ins)),
             ("Votants", fmt_entier(tour["votants"])),
             ("Participation", fmt_pct(pct_exact(tour["votants"], ins))),
             ("Abstention", fmt_pct(pct_exact(tour["abstentions"], ins)))]
    if tour.get("blancs_et_nuls") is not None:     # 2002-2012 : un seul total publié
        stats.append(("Blancs et nuls", fmt_entier(tour["blancs_et_nuls"])))
    else:
        stats += [("Blancs", fmt_entier(tour["blancs"])), ("Nuls", fmt_entier(tour["nuls"]))]
    dl = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in stats)
    return f"""    <div class="res-scroll">
      <table class="res-table">
        <colgroup><col class="c-nom"><col class="c-voix"><col class="c-exp"><col class="c-ins"></colgroup>
        <thead><tr><th scope="col">Candidat</th><th scope="col" class="num">Voix</th><th scope="col" class="num">% exprimés</th><th scope="col" class="num">% inscrits</th></tr></thead>
        <tbody>
          {(chr(10) + "          ").join(lignes)}
        </tbody>
      </table>
    </div>
    <dl class="scrutin-stats">{dl}</dl>"""


def bloc_resultats(e, numero):
    tour = e.t1 if numero == 1 else e.t2
    iso = e.tour1 if numero == 1 else e.tour2
    nom = "premier" if numero == 1 else "second"
    return f"""  <section class="carte" id="resultats-{'premier' if numero == 1 else 'second'}-tour" aria-labelledby="h-res-t{numero}">
    <p class="surtitre">Résultats définitifs</p>
    <h2 id="h-res-t{numero}"><span class="sr-only">Résultats du {nom} tour de la présidentielle {e.annee} : </span>{nom.capitalize()} tour — {date_tag(iso)}</h2>
    <p class="subtitle">Nombre de voix, part des suffrages exprimés et part des inscrits.</p>
{tableau_resultats(tour, e)}
  </section>"""


def navigation(annee):
    i = ANNEES.index(annee)
    liens = []
    if i > 0:
        a = ANNEES[i - 1]
        liens.append(f'<a class="precedent" href="presidentielle-{a}.html" rel="prev">← Présidentielle {a}</a>')
    liens.append('<a class="toutes" href="precedentes-elections.html">Toutes les présidentielles</a>')
    if i < len(ANNEES) - 1:
        a = ANNEES[i + 1]
        liens.append(f'<a class="suivant" href="presidentielle-{a}.html" rel="next">Présidentielle {a} →</a>')
    return (f'  <nav class="nav-millesimes" aria-label="Autres présidentielles">{"".join(liens)}</nav>\n'
            f'  <p class="voir-aussi"><a href="/">Sondages de la présidentielle 2027</a></p>')


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def tete_page(titre, description, og_titre, url, extra_css=()):
    css = "".join(f'<link rel="stylesheet" href="assets/{c}">\n' for c in extra_css)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre}</title>
<meta name="description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Sondax">
<meta property="og:locale" content="fr_FR">
<meta property="og:url" content="https://sondax.fr/{url}">
<meta property="og:title" content="{og_titre}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="https://sondax.fr/assets/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://sondax.fr/{url}">
<!-- TODO: créer le compte GoatCounter et confirmer le sous-domaine -->
<script data-goatcounter="https://sondax.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/header.css?v=5">
{css}</head>
<body>

<div id="site-header" class="sh"></div>
<script src="assets/header-data.js"></script>
<script src="assets/header.js?v=8"></script>

"""


def page_election(e, elections):
    a = e.annee
    description = (f"Résultats de la présidentielle {a} : voix et pourcentages par candidat aux deux tours, "
                   f"et évolution des sondages.")
    tete = tete_page(f"Résultats et sondages de la présidentielle {a}, premier et second tour — Sondax",
                     description, f"Résultats et sondages de la présidentielle {a}",
                     f"presidentielle-{a}.html", ["historique.css?v=2"])
    corps = f"""<main>
  <p class="retour"><a href="precedentes-elections.html">← Toutes les présidentielles</a></p>
  <header class="hero">
    <p class="surtitre">Présidentielle {a}</p>
    <h1>Sondages et résultats de la présidentielle {a}</h1>
    <p class="hero-dates">Premier tour : {date_tag(e.tour1)} · Second tour : {date_tag(e.tour2)}</p>
  </header>

{bloc_synthese(e, elections)}

{bloc_sondages_t1(e)}

{bloc_resultats(e, 1)}

{bloc_sondages_t2(e)}

{bloc_resultats(e, 2)}

{navigation(a)}
</main>

<footer>
  <div class="footer-inner">
    <p id="attribution"></p>
    <p>Résultats · Ministère de l’Intérieur via <a href="https://www.data.gouv.fr/datasets/6481e741d4cf002ec0efec9d" target="_blank">data.gouv.fr</a> (Licence Ouverte).</p>
    <div id="footer-run"></div>
    <p><a href="mailto:contact@sondax.fr">Contact</a> · <a href="a-propos.html">À propos</a> · Hébergeur : <a href="https://pages.github.com" target="_blank">GitHub Pages</a></p>
  </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="assets/end-labels.js?v=1"></script>
<script src="assets/historique.js?v=3"></script>
<script>initHistorique('{a}');</script>

</body>
</html>
"""
    return tete + corps


def carte_election(e):
    """Carte d'une élection sur precedentes-elections.html : finalistes et résultat, bouton."""
    finalistes = barres([(e.court(c["nom"]), c["pct_exprimes"], e.couleur(c["nom"]), c["pct_exprimes"])
                         for c in sorted(e.t2["candidats"], key=lambda c: -c["voix"])], "barres-t2")
    a = e.annee
    return f"""    <article class="election-carte">
      <h3 class="annee">{a}</h3>
      <p class="dates">{dates_courtes(e.tour1, e.tour2)}</p>
      {finalistes}
      <a class="btn" href="presidentielle-{a}.html">Explorer {a} <span aria-hidden="true">→</span></a>
    </article>"""


def page_precedentes(elections, retro):
    tete = tete_page(
        "Sondages des présidentielles de 2002 à 2022 — Sondax",
        "Sondages des présidentielles de 2002 à 2022 comparés à 2027, au même nombre de jours avant le scrutin.",
        "Sondages des présidentielles de 2002 à 2022", "precedentes-elections.html",
        ["bloc-retro.css?v=1", "historique.css?v=2"])
    cartes = "\n".join(carte_election(elections[a]) for a in reversed(ANNEES))
    x = j_du_jour()
    corps = f"""<main>
  <header class="hero">
    <p class="surtitre">Archives Sondax</p>
    <h1>Les présidentielles depuis 2002</h1>
    <p class="hero-texte">Retrouvez les sondages et les résultats des cinq dernières élections présidentielles et comparez les campagnes au même nombre de jours avant le premier tour.</p>
  </header>

  <!-- BEGIN:bloc-retro-page -->
{rendre_bloc_page(retro, x)}
  <!-- END:bloc-retro-page -->

  <h2 class="section-titre">Choisir une présidentielle</h2>
  <div class="elections-grille">
{cartes}
  </div>
</main>

<footer>
  <div class="footer-inner">
    <p>Source : pages « Opinion polling for the … French presidential election » de <a href="https://en.wikipedia.org" target="_blank">en.wikipedia.org</a>, versions figées (CC BY-SA 4.0).</p>
    <p>Résultats · Ministère de l’Intérieur via <a href="https://www.data.gouv.fr/datasets/6481e741d4cf002ec0efec9d" target="_blank">data.gouv.fr</a> (Licence Ouverte).</p>
    <p><a href="mailto:contact@sondax.fr">Contact</a> · <a href="a-propos.html">À propos</a> · Hébergeur : <a href="https://pages.github.com" target="_blank">GitHub Pages</a></p>
  </div>
</footer>

<script src="assets/bloc-retro.js?v=3" defer></script>

</body>
</html>
"""
    return tete + corps


def main():
    elections, _, retro = charger()
    for a in ANNEES:
        (SITE / f"presidentielle-{a}.html").write_text(page_election(elections[a], elections), encoding="utf-8")
        print(f"  {a} : page écrite")
    (SITE / "precedentes-elections.html").write_text(page_precedentes(elections, retro), encoding="utf-8")
    print("  precedentes-elections : page écrite")


if __name__ == "__main__":
    main()
