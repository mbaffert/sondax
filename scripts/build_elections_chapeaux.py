"""Injecte un chapeau statique dans chaque page presidentielle-XXXX.html.

Lit data/derived/historique.json et génère deux ou trois phrases :
- candidats en tête dans les derniers sondages, avec leurs scores moyens
- résultat réel du premier tour, écart avec la moyenne
- résultat du second tour
"""

import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORIQUE_PATH = ROOT / "data" / "derived" / "historique.json"

BEGIN = "<!-- BEGIN:chapeau-election -->"
END = "<!-- END:chapeau-election -->"


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


def inject(path, chapeau_html):
    content = path.read_text(encoding="utf-8")
    try:
        i_begin = content.index(BEGIN)
        i_end = content.index(END) + len(END)
    except ValueError:
        print(f"  Marqueurs introuvables dans {path.name}, ignoré")
        return
    new_content = (
        content[:i_begin] + BEGIN + "\n"
        + chapeau_html + "\n"
        + END + content[i_end:]
    )
    path.write_text(new_content, encoding="utf-8")


def main():
    historique = json.loads(HISTORIQUE_PATH.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    main()
