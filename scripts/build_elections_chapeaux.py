"""Injecte un chapeau et un tableau statiques dans chaque page presidentielle-XXXX.html.

Chapeau, lu dans data/derived/historique.json, deux ou trois phrases :
- candidats en tête dans les derniers sondages, avec leurs scores moyens
- résultat réel du premier tour, écart avec la moyenne
- résultat du second tour

Tableau, sous les graphiques : moyenne mensuelle des sondages de premier tour
des principaux candidats (score de chaque sondage retenu comme pour la courbe,
series.score_candidat), résultat du premier tour en dernière ligne.
"""

import json, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORIQUE_PATH = ROOT / "data" / "derived" / "historique.json"
HISTORIQUE_BRUT_PATH = ROOT / "data" / "historique.json"

sys.path.insert(0, str(ROOT / "scripts"))
from series import score_candidat
from balise_time import time_tag

BEGIN = "<!-- BEGIN:chapeau-election -->"
END = "<!-- END:chapeau-election -->"
BEGIN_MOY = "<!-- BEGIN:moyennes-election -->"
END_MOY = "<!-- END:moyennes-election -->"

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

    for year in ["2002", "2007", "2012", "2017", "2022"]:
        if year not in historique:
            print(f"  {year} : pas de données")
            continue
        page_path = ROOT / "site" / f"presidentielle-{year}.html"
        if not page_path.exists():
            print(f"  {year} : page introuvable")
            continue

        chapeau = generate_chapeau(year, historique[year])
        if chapeau:
            inject(page_path, chapeau)
            print(f"  {year} : chapeau injecté")
        else:
            print(f"  {year} : pas de données suffisantes")

        moyennes = generate_moyennes(historique_brut[year], historique[year])
        inject(page_path, moyennes, BEGIN_MOY, END_MOY)
        print(f"  {year} : moyennes mensuelles {'injectées' if moyennes else 'absentes'}")


if __name__ == "__main__":
    main()
