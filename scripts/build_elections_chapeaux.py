"""Injecte un chapeau, un tableau et le bloc des résultats dans chaque page
presidentielle-XXXX.html, et le contenu statique de precedentes-elections.html.

Chapeau, deux phrases : résultat du premier tour (trois premiers) et du second,
lus dans data/resultats.json (scripts/collecte_resultats.py). Sans ce fichier,
ancien chapeau tiré de data/derived/historique.json (derniers sondages,
résultats des deux tours).

Bloc « Les résultats du scrutin », sous le bloc des sondages : un tableau par
tour (voix, % des exprimés avec barre, % des inscrits) et une ligne de
participation. Absent tant que data/resultats.json n'existe pas.

Tableau, sous les graphiques : moyenne mensuelle des sondages de premier tour
des principaux candidats (score de chaque sondage retenu comme pour la courbe,
series.score_candidat), résultat du premier tour en dernière ligne.

precedentes-elections.html : un paragraphe d'introduction (nombre de sondages
et période couverte par élection) et une carte par élection, liée à sa page
presidentielle-XXXX.html. Les cartes étaient rendues en JavaScript ; elles
sont écrites au build pour que les liens figurent dans le HTML servi.
"""

import html, json, pathlib, sys
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORIQUE_PATH = ROOT / "data" / "derived" / "historique.json"
HISTORIQUE_BRUT_PATH = ROOT / "data" / "historique.json"
RESULTATS_PATH = ROOT / "data" / "resultats.json"

sys.path.insert(0, str(ROOT / "scripts"))
from series import score_candidat
from balise_time import time_tag

BEGIN = "<!-- BEGIN:chapeau-election -->"
END = "<!-- END:chapeau-election -->"
BEGIN_MOY = "<!-- BEGIN:moyennes-election -->"
END_MOY = "<!-- END:moyennes-election -->"
BEGIN_INTRO = "<!-- BEGIN:intro-elections -->"
END_INTRO = "<!-- END:intro-elections -->"
BEGIN_CARTES = "<!-- BEGIN:cartes-elections -->"
END_CARTES = "<!-- END:cartes-elections -->"
BEGIN_RES = "<!-- BEGIN:resultats-election -->"
END_RES = "<!-- END:resultats-election -->"
ANNEES = ["2002", "2007", "2012", "2017", "2022"]

# Principaux candidats : présents au premier tour, et 5 % des suffrages
# exprimés ou 10 % de moyenne mensuelle au moins une fois.
SEUIL_RESULTAT = 5
SEUIL_MOYENNE = 10

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def fmt_pct(v):
    if v is None:
        return "—"
    return f"{v:.2f}\u00a0%".replace(".", ",")


def fmt_pct1(v):
    if v is None:
        return "—"
    return f"{v:.1f}\u00a0%".replace(".", ",")


def last_trend_value(info):
    """Extrait la dernière valeur non-nulle de la série compressée 'v'."""
    v_str = info.get("v", "")
    if not v_str:
        return None
    vals = v_str.split(",")
    for raw in reversed(vals):
        raw = raw.strip()
        if raw:
            try:
                return float(raw) / 10
            except ValueError:
                continue
    return None


def generate_chapeau(year, election):
    """Génère le HTML du chapeau pour une élection."""
    cands = election.get("candidats", {})
    res_t2 = election.get("resultats_t2", {})
    duel = election.get("duel_final", "")

    # Top 2 par résultat T1
    top = sorted(
        ((c, info) for c, info in cands.items() if info.get("resultat")),
        key=lambda x: x[1]["resultat"],
        reverse=True,
    )[:2]

    if not top:
        return ""

    phrases = []

    # Phrase 1 : derniers sondages
    sondage_parts = []
    for c, info in top:
        nom = info.get("nom", c)
        v = last_trend_value(info)
        if v is not None:
            sondage_parts.append(f"{nom} ({fmt_pct1(v)})")

    if sondage_parts:
        phrases.append(
            f"Dans les derniers sondages avant le scrutin, "
            f"{sondage_parts[0]} arrivait en tête"
            + (f", devant {sondage_parts[1]}" if len(sondage_parts) > 1 else "")
            + "."
        )

    # Phrase 2 : résultat T1
    result_parts = []
    for c, info in top:
        nom = info.get("nom", c)
        res = info.get("resultat")
        result_parts.append(f"{nom} a obtenu {fmt_pct(res)}")

    if result_parts:
        phrases.append(
            f"Au premier tour, {' et '.join(result_parts)}."
        )

    # Phrase 3 : résultat T2
    if duel and res_t2:
        pair = duel.split("|")
        if len(pair) == 2 and all(p in res_t2 for p in pair):
            noms = [cands.get(p, {}).get("nom", p) for p in pair]
            scores = [res_t2[p] for p in pair]
            # Vainqueur en premier
            if scores[1] > scores[0]:
                noms[0], noms[1] = noms[1], noms[0]
                scores[0], scores[1] = scores[1], scores[0]
            phrases.append(
                f"Au second tour, {noms[0]} l\u2019a emporté avec "
                f"{fmt_pct(scores[0])} contre {fmt_pct(scores[1])}."
            )

    if not phrases:
        return ""

    return f'    <p class="subtitle">{" ".join(phrases)}</p>'


def fmt_entier(n):
    """48747876 → '48 747 876', espace fine insécable entre les milliers."""
    return f"{n:,}".replace(",", " ")


def pct_exact(n, base):
    """Pourcentage au centième, arrondi demi vers le haut (comme collecte_resultats.py)."""
    q = Decimal(n) * 100 / Decimal(base)
    return float(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def generate_chapeau_resultats(res):
    """Deux phrases : trois premiers du premier tour, issue du second."""
    t1, t2 = res["t1"]["candidats"], res["t2"]["candidats"]
    d1, d2 = res["date_t1"], res["date_t2"]
    y, m, d = (int(x) for x in d2.split("-"))
    date2 = time_tag(d2, f"{d} {MOIS[m - 1]}")
    suivants = [f"{c['nom']} ({fmt_pct(c['pct_exprimes'])})" for c in t1[1:3]]
    p1 = (f"Au premier tour, le {time_tag(d1, date_fr(d1, True))}, {t1[0]['nom']} a recueilli "
          f"{fmt_pct(t1[0]['pct_exprimes'])} des suffrages exprimés, devant "
          f"{' et '.join(suivants)}.")
    p2 = (f"Au second tour, le {date2}, {t2[0]['nom']} l’a emporté avec "
          f"{fmt_pct(t2[0]['pct_exprimes'])} des voix, contre "
          f"{fmt_pct(t2[1]['pct_exprimes'])} pour {t2[1]['nom']}.")
    return f'    <p class="subtitle">{p1} {p2}</p>'


def couleurs_par_nom(election_brute, election):
    """{nom complet: couleur} : nom de data/historique.json, couleur du dérivé."""
    derives = election.get("candidats", {})
    return {info["nom"]: derives[cid]["couleur"]
            for cid, info in election_brute["candidats"].items()
            if derives.get(cid, {}).get("couleur")}


def tableau_tour(tour, legende, couleurs):
    """Tableau d'un tour, barre colorée sous le % des exprimés, ligne de participation."""
    tete = tour["candidats"][0]["voix"] or 1
    lignes = []
    for c in tour["candidats"]:
        w = round(c["voix"] / tete, 4)
        coul = couleurs.get(c["nom"], "#8A8F98")
        lignes.append(
            f'<tr><th scope="row">{html.escape(c["nom"])}</th>'
            f'<td class="num">{fmt_entier(c["voix"])}</td>'
            f'<td class="num barre"><span class="barre-fond" style="--w:{w};background:{coul}"></span>'
            f'<span class="barre-val">{fmt_pct(c["pct_exprimes"])}</span></td>'
            f'<td class="num">{fmt_pct(c["pct_inscrits"])}</td></tr>')
    ins = tour["inscrits"]
    part = [f"Inscrits {fmt_entier(ins)}",
            f"Votants {fmt_entier(tour['votants'])} ({fmt_pct(pct_exact(tour['votants'], ins))})",
            f"Abstention {fmt_pct(pct_exact(tour['abstentions'], ins))}"]
    if tour.get("blancs_et_nuls") is not None:
        part.append(f"Blancs et nuls {fmt_entier(tour['blancs_et_nuls'])}")
    else:
        part += [f"Blancs {fmt_entier(tour['blancs'])}", f"Nuls {fmt_entier(tour['nuls'])}"]
    return f"""    <div class="res-scroll">
      <table class="res-table">
        <caption>{legende}</caption>
        <colgroup><col class="c-nom"><col class="c-voix"><col class="c-exp"><col class="c-ins"></colgroup>
        <thead><tr><th scope="col">Candidat</th><th scope="col" class="num">Voix</th><th scope="col" class="num">% des exprimés</th><th scope="col" class="num">% des inscrits</th></tr></thead>
        <tbody>
          {(chr(10) + "          ").join(lignes)}
        </tbody>
      </table>
    </div>
    <p class="res-participation">{" · ".join(part)}</p>"""


def generate_resultats(res, couleurs):
    """Bloc « Les résultats du scrutin » : premier tour puis second tour."""
    t1 = tableau_tour(res["t1"], f"Premier tour, {time_tag(res['date_t1'], date_fr(res['date_t1'], True))}", couleurs)
    t2 = tableau_tour(res["t2"], f"Second tour, {time_tag(res['date_t2'], date_fr(res['date_t2'], True))}", couleurs)
    return f"""  <style>
    .res-scroll {{ overflow-x: auto; margin-top: 14px; }}
    .res-table {{ border-collapse: collapse; width: 100%; min-width: 540px; table-layout: fixed; font-size: 13.5px; }}
    .res-table col.c-nom {{ width: 32%; }} .res-table col.c-voix {{ width: 18%; }}
    .res-table col.c-exp {{ width: 32%; }} .res-table col.c-ins {{ width: 18%; }}
    .res-table caption {{ text-align: left; font-family: var(--titre); font-size: 17px; font-weight: 600;
      color: var(--texte); padding-bottom: 8px; }}
    .res-table th, .res-table td {{ padding: 6px 10px; border-bottom: 1px solid #EDEEEA;
      text-align: left; white-space: nowrap; }}
    .res-table thead th {{ font-size: 13px; font-weight: 600; color: var(--gris); border-bottom-color: #DDDFDA; }}
    .res-table tbody th {{ font-weight: 500; }}
    .res-table .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .res-table th:first-child {{ position: sticky; left: 0; background: #fff; z-index: 1; }}
    .res-table .barre {{ position: relative; }}
    .res-table .barre-fond {{ position: absolute; left: 10px; top: 6px; bottom: 6px; border-radius: 3px;
      opacity: 0.85; width: calc((100% - 6.5em) * var(--w)); }}
    .res-table .barre-val {{ position: relative; font-weight: 600; }}
    .res-participation {{ font-size: 13px; color: var(--gris); margin: 8px 0 18px; }}
    .res-participation:last-child {{ margin-bottom: 0; }}
    @media (max-width: 600px) {{
      .res-table {{ min-width: 0; font-size: 12.5px; }}
      .res-table col.c-nom {{ width: 36%; }} .res-table col.c-voix {{ width: 25%; }}
      .res-table col.c-exp {{ width: 22%; }} .res-table col.c-ins {{ width: 17%; }}
      .res-table th, .res-table td {{ padding: 6px 4px; white-space: normal; }}
      .res-table td.num {{ white-space: nowrap; }}
      .res-table thead th {{ font-size: 11.5px; vertical-align: bottom; }}
      .res-table .barre-fond {{ left: 0; top: 3px; bottom: 3px; opacity: 0.28; width: calc(100% * var(--w)); }}
    }}
  </style>
  <div class="bloc" id="resultats">
    <h2>Les résultats du scrutin</h2>
{t1}
{t2}
  </div>"""


def moyennes_mensuelles(election_brute, election):
    """{candidat: {"AAAA-MM": moyenne}} des sondages de premier tour du
    périmètre affiché (début de terrain à partir de la borne, fin de terrain
    avant le premier tour)."""
    borne, tour1 = election["borne"], election["tour1"]
    valeurs = defaultdict(lambda: defaultdict(list))
    for s in election_brute["sondages"]:
        if s["terrain_debut"] < borne or s["terrain_fin"] >= tour1:
            continue
        mois = s["terrain_fin"][:7]
        for cid in election["candidats"]:
            score, _ = score_candidat(s, cid)
            if score is not None:
                valeurs[cid][mois].append(score)
    return {cid: {m: sum(v) / len(v) for m, v in par_mois.items()}
            for cid, par_mois in valeurs.items()}


def generate_moyennes(election_brute, election):
    """Tableau HTML : une ligne par mois, une colonne par principal candidat,
    le résultat du premier tour en dernière ligne."""
    moyennes = moyennes_mensuelles(election_brute, election)
    cands = election["candidats"]
    principaux = [
        c for c, info in cands.items()
        if info.get("resultat") is not None and c in moyennes
        and (info["resultat"] >= SEUIL_RESULTAT
             or max(moyennes[c].values()) >= SEUIL_MOYENNE)
    ]
    principaux.sort(key=lambda c: -cands[c]["resultat"])
    mois = sorted({m for c in principaux for m in moyennes[c]})
    if not principaux or not mois:
        return ""

    tete = "".join(f'<th scope="col" class="num">{cands[c]["nom"]}</th>' for c in principaux)
    lignes = []
    for m in mois:
        y, mm = m.split("-")
        cellules = "".join(
            f'<td class="num">{fmt_pct1(moyennes[c][m]) if m in moyennes[c] else "—"}</td>'
            for c in principaux)
        lignes.append(f'<tr><th scope="row">{time_tag(m, f"{MOIS[int(mm) - 1]} {y}")}</th>{cellules}</tr>')
    resultats = "".join(f'<td class="num">{fmt_pct(cands[c]["resultat"])}</td>' for c in principaux)
    lignes.append(f'<tr class="resultat"><th scope="row">Résultat du premier tour</th>{resultats}</tr>')

    return f"""    <style>
      .moyennes-scroll {{ overflow-x: auto; margin-top: 22px; }}
      .moyennes {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
      .moyennes th, .moyennes td {{ padding: 6px 10px; border-bottom: 1px solid #EDEEEA;
        text-align: left; white-space: nowrap; }}
      .moyennes thead th {{ font-weight: 600; color: var(--gris); border-bottom-color: #DDDFDA; }}
      .moyennes tbody th {{ font-weight: 400; color: var(--gris); }}
      .moyennes .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
      .moyennes .resultat th, .moyennes .resultat td {{ font-weight: 600; color: var(--texte);
        border-top: 1px solid #DDDFDA; border-bottom: 0; }}
      .moyennes th:first-child {{ position: sticky; left: 0; background: #fff; }}
      @media (max-width: 600px) {{
        .moyennes .resultat th {{ white-space: normal; min-width: 7.5em; }}
      }}
    </style>
    <div class="moyennes-scroll">
      <table class="moyennes">
        <thead><tr><th scope="col">Mois</th>{tete}</tr></thead>
        <tbody>
          {(chr(10) + "          ").join(lignes)}
        </tbody>
      </table>
    </div>"""


def date_fr(iso, premier=False):
    """'2002-04-21' → '21 avril 2002' ; '1er' pour le premier du mois si premier."""
    y, m, d = (int(x) for x in iso.split("-"))
    jour = "1er" if premier and d == 1 else str(d)
    return f"{jour} {MOIS[m - 1]} {y}"


def sondages_perimetre(election_brute, election):
    """Sondages de la série affichée : terrain commencé à partir de la borne."""
    return [s for s in election_brute["sondages"] if s["terrain_debut"] >= election["borne"]]


def generate_intro(historique, historique_brut):
    """Paragraphe d'introduction : sondages et période couverte par élection."""
    parts, total = [], 0
    for year in ANNEES:
        if year not in historique:
            continue
        sondages = sondages_perimetre(historique_brut[year], historique[year])
        if not sondages:
            continue
        debut = min(s["terrain_debut"] for s in sondages)
        fin = max(s["terrain_fin"] for s in sondages)
        total += len(sondages)
        parts.append(f"{len(sondages)} pour {year} (du {time_tag(debut, date_fr(debut, True))} "
                     f"au {time_tag(fin, date_fr(fin, True))})")
    if not parts:
        return ""
    total_txt = f"{total:,}".replace(",", "\u00a0")
    enum = ", ".join(parts[:-1]) + " et " + parts[-1] if len(parts) > 1 else parts[0]
    return (f'  <p class="intro">{total_txt} sondages sur {len(parts)} élections présidentielles, '
            f"premier et second tours confondus. Pour chaque élection, la série commence au "
            f"1er janvier de l\u2019année précédant le scrutin et s\u2019arrête au dernier "
            f"sondage réalisé avant le second tour\u00a0: {enum}.</p>")


def generate_carte(year, e):
    """Carte d'une élection, liée à presidentielle-XXXX.html (rendu de l'ancien script client)."""
    res_t2 = e.get("resultats_t2") or {}
    pair = e["duel_final"].split("|") if e.get("duel_final") else []
    duel = ""
    if len(pair) == 2:
        noms = [e["candidats"][c]["nom"] if c in e["candidats"] else c for c in pair]
        scores = [f"{res_t2[c]:.1f}".replace(".", ",") if res_t2.get(c) is not None else "?"
                  for c in pair]
        duel = f"{noms[0]} – {noms[1]} · {scores[0]} / {scores[1]}"
    nb = e.get("nb_sondages_perimetre") or e.get("nb_sondages_t1")
    lignes = [
        f'<a class="carte" href="presidentielle-{year}.html">',
        f'  <div class="annee">Présidentielle {year}</div>',
        f'  <div class="dates">{time_tag(e["tour1"], date_fr(e["tour1"]))} – '
        f'{time_tag(e["tour2"], date_fr(e["tour2"]))}</div>',
    ]
    if duel:
        lignes.append(f'  <div class="duel">{duel}</div>')
    lignes += [
        f'  <div class="stats">{nb} sondages depuis janvier {e["borne"][:4]}</div>',
        '  <span class="fleche">→</span>',
        '</a>',
    ]
    return "\n".join(lignes)


def inject_precedentes(historique, historique_brut):
    page_path = ROOT / "site" / "precedentes-elections.html"
    if not page_path.exists():
        print("  precedentes-elections.html introuvable")
        return
    inject(page_path, generate_intro(historique, historique_brut), BEGIN_INTRO, END_INTRO)
    cartes = [generate_carte(y, historique[y]) for y in sorted(historique, reverse=True)]
    inject(page_path, "\n".join(cartes), BEGIN_CARTES, END_CARTES)
    print(f"  precedentes-elections : introduction et {len(cartes)} cartes injectées")


def inject(path, chapeau_html, begin=BEGIN, end=END):
    content = path.read_text(encoding="utf-8")
    try:
        i_begin = content.index(begin)
        i_end = content.index(end) + len(end)
    except ValueError:
        print(f"  Marqueurs introuvables dans {path.name}, ignoré")
        return
    new_content = (
        content[:i_begin] + begin + "\n"
        + chapeau_html + "\n"
        + end + content[i_end:]
    )
    path.write_text(new_content, encoding="utf-8")


def main():
    historique = json.loads(HISTORIQUE_PATH.read_text(encoding="utf-8"))
    historique_brut = json.loads(HISTORIQUE_BRUT_PATH.read_text(encoding="utf-8"))["elections"]
    resultats = (json.loads(RESULTATS_PATH.read_text(encoding="utf-8"))
                 if RESULTATS_PATH.exists() else {})

    for year in ANNEES:
        if year not in historique:
            print(f"  {year} : pas de données")
            continue
        page_path = ROOT / "site" / f"presidentielle-{year}.html"
        if not page_path.exists():
            print(f"  {year} : page introuvable")
            continue

        res = resultats.get(year)
        chapeau = (generate_chapeau_resultats(res) if res
                   else generate_chapeau(year, historique[year]))
        if chapeau:
            inject(page_path, chapeau)
            print(f"  {year} : chapeau injecté")
        else:
            print(f"  {year} : pas de données suffisantes")

        moyennes = generate_moyennes(historique_brut[year], historique[year])
        inject(page_path, moyennes, BEGIN_MOY, END_MOY)
        print(f"  {year} : moyennes mensuelles {'injectées' if moyennes else 'absentes'}")

        bloc = (generate_resultats(res, couleurs_par_nom(historique_brut[year], historique[year]))
                if res else "")
        inject(page_path, bloc, BEGIN_RES, END_RES)
        print(f"  {year} : résultats {'injectés' if bloc else 'absents (data/resultats.json manquant)'}")

    inject_precedentes(historique, historique_brut)


if __name__ == "__main__":
    main()
