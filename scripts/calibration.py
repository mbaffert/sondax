#!/usr/bin/env python3
"""Calibration historique du modèle Sondax (SPEC §14.5).

Pour chaque élection et chaque candidat ayant un résultat officiel au premier
tour, compare la moyenne simple des sondages de la dernière semaine (terrain_fin
de J−7 à J−1, rollings compris) au résultat. En tire l'erreur absolue moyenne,
l'écart-type et l'estimation de N_eff par la méthode des moments :

    N_eff = Σ p(1−p) / Σ erreur² − 1

Deux estimations de N_eff par jeu :
- « dernière semaine » : moyenne simple des sondages de J−7 à J−1 (mesure des
  erreurs des sondages eux-mêmes, publiée sur la page Méthode) ;
- « moyenne Sondax à J−7 » : la moyenne que le modèle utilise réellement
  (courbe du §4, sondages connus sept jours avant le scrutin). C'est celle-ci
  qui règle le moteur (§14.5) : on calibre sur ce qu'on publie, à l'horizon de
  « si on votait dimanche ».

Le script propose ; la valeur utilisée par le moteur est dans data/config.json.
Écrit data/derived/calibration.json.
"""

import datetime, json, math, pathlib, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from series import calculer_series  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = {
    "presidentielles": ROOT / "data" / "historique.json",
    "europeennes": ROOT / "data" / "historique_europeennes.json",
}
OUTPUT_PATH = ROOT / "data" / "derived" / "calibration.json"

FENETRE_JOURS = 7
HORIZON_SONDAX = 7          # jours avant le scrutin pour la moyenne Sondax
TRANCHES = [("plus_20", 20, 101), ("10_20", 10, 20), ("moins_10", 0, 10)]
PAS_HISTOGRAMME = 0.5


def _date(s):
    return datetime.date.fromisoformat(s)


def hypothese_t1(sondage, officiels):
    """Hypothèse T1 contenant tous les candidats officiels, à défaut celle qui en
    contient le plus. None si le sondage n'a pas de premier tour."""
    t1 = [h for h in sondage["hypotheses"] if h["tour"] == 1]
    if not t1:
        return None
    return max(t1, key=lambda h: (len(officiels & h["scores"].keys()), len(h["scores"])))


def moyenne_avant(election, jour_limite, jours=FENETRE_JOURS):
    """Moyenne simple par candidat officiel des sondages dont terrain_fin est
    dans [jour_limite − jours, jour_limite − 1]. Retourne ({candidat: moyenne},
    [ids des sondages])."""
    officiels = set(election["resultats"]["tour1"])
    valeurs = {c: [] for c in officiels}
    ids = []
    for s in election["sondages"]:
        ecart = (jour_limite - _date(s["terrain_fin"])).days
        if not 1 <= ecart <= jours:
            continue
        h = hypothese_t1(s, officiels)
        if h is None:
            continue
        ids.append(s["id"])
        for c in officiels:
            if c in h["scores"]:
                valeurs[c].append(h["scores"][c])
    return {c: statistics.fmean(v) for c, v in valeurs.items() if v}, ids


def moyenne_sondax(election, jour):
    """Moyenne Sondax (dernier point de la courbe) avec les seuls sondages dont
    terrain_fin ≤ jour, pour les candidats officiels. ({candidat: v}, date_fin)."""
    sondages = [s for s in election["sondages"] if _date(s["terrain_fin"]) <= jour]
    series = calculer_series(sondages)
    moy = {}
    for c in election["resultats"]["tour1"]:
        pts = series["series"].get(c)
        if pts and pts[-1]["v"] is not None:
            moy[c] = pts[-1]["v"]
    return moy, series["date_fin"]


def comparaisons_sondax(elections, jours=HORIZON_SONDAX):
    """Comme comparaisons(), avec la moyenne Sondax à J−jours."""
    lignes = []
    for annee, e in sorted(elections.items()):
        moy, _ = moyenne_sondax(e, _date(e["tour1"]) - datetime.timedelta(days=jours))
        total = sum(moy.values())
        for c, m in moy.items():
            lignes.append({"election": annee, "candidat": c, "moyenne": m,
                           "part": 100 * m / total, "resultat": e["resultats"]["tour1"][c]})
    return lignes


def comparaisons(elections):
    """Une ligne par élection × candidat : moyenne, part normalisée, résultat."""
    lignes = []
    for annee, e in sorted(elections.items()):
        moy, _ = moyenne_avant(e, _date(e["tour1"]))
        total = sum(moy.values())
        for c, m in moy.items():
            lignes.append({
                "election": annee,
                "candidat": c,
                "moyenne": m,
                "part": 100 * m / total,
                "resultat": e["resultats"]["tour1"][c],
            })
    return lignes


def estimer_neff(lignes):
    """Méthode des moments sur les parts normalisées, en proportion."""
    num = sum((l["part"] / 100) * (1 - l["part"] / 100) for l in lignes)
    den = sum(((l["part"] - l["resultat"]) / 100) ** 2 for l in lignes)
    return num / den - 1 if den else None


def _stats(erreurs):
    if not erreurs:
        return {"n": 0, "erreur_absolue_moyenne": None, "ecart_type": None}
    return {
        "n": len(erreurs),
        "erreur_absolue_moyenne": round(statistics.fmean(abs(x) for x in erreurs), 2),
        "ecart_type": round(math.sqrt(statistics.fmean(x * x for x in erreurs)), 2),
    }


def qualifies_justes(elections):
    res = {}
    for annee, e in sorted(elections.items()):
        moy, _ = moyenne_avant(e, _date(e["tour1"]))
        officiel = e["resultats"]["tour1"]
        annonces = set(sorted(moy, key=moy.get, reverse=True)[:2])
        reels = set(sorted(officiel, key=officiel.get, reverse=True)[:2])
        res[annee] = annonces == reels
    return res


def resumer(elections):
    lignes = comparaisons(elections)
    for l in lignes:
        l["erreur"] = l["moyenne"] - l["resultat"]
    erreurs = [l["erreur"] for l in lignes]
    stats = _stats(erreurs)
    neff = estimer_neff(lignes)

    par_tranche = {}
    for cle, bas, haut in TRANCHES:
        par_tranche[cle] = _stats([l["erreur"] for l in lignes if bas <= l["moyenne"] < haut])

    histo = {}
    for x in erreurs:
        k = math.floor(x / PAS_HISTOGRAMME)
        histo[k] = histo.get(k, 0) + 1
    histogramme = [{"de": k * PAS_HISTOGRAMME, "a": (k + 1) * PAS_HISTOGRAMME, "n": n}
                   for k, n in sorted(histo.items())]

    principales = sorted(lignes, key=lambda l: abs(l["erreur"]), reverse=True)[:10]
    sx = comparaisons_sondax(elections)
    ecarts_sx = [l["part"] - l["resultat"] for l in sx]
    return {
        "elections": sorted(elections),
        "n_comparaisons": stats["n"],
        "erreur_absolue_moyenne": stats["erreur_absolue_moyenne"],
        "ecart_type": stats["ecart_type"],
        "N_eff": round(neff, 1) if neff is not None else None,
        "moyenne_sondax_j7": {
            "n_comparaisons": len(sx),
            "ecart_type": round(math.sqrt(statistics.fmean(x * x for x in ecarts_sx)), 2),
            "N_eff": round(estimer_neff(sx), 1),
        },
        "par_tranche": par_tranche,
        "histogramme": histogramme,
        "principales_erreurs": [
            {"election": l["election"], "candidat": l["candidat"],
             "moyenne": round(l["moyenne"], 2), "resultat": l["resultat"],
             "erreur": round(l["erreur"], 2)}
            for l in principales
        ],
        "qualifies_annonces_justes": qualifies_justes(elections),
        "comparaisons": [
            {k: (round(v, 2) if isinstance(v, float) else v) for k, v in l.items()}
            for l in lignes
        ],
    }


def charger_elections():
    jeux = {}
    for nom, chemin in SOURCES.items():
        if chemin.exists():
            jeux[nom] = json.loads(chemin.read_text())["elections"]
    return jeux


def calibrer():
    jeux = charger_elections()
    sortie = {nom: resumer(el) for nom, el in jeux.items()}
    if len(jeux) > 1:
        ensemble = {}
        for nom, el in jeux.items():
            ensemble.update({f"{nom}-{a}": e for a, e in el.items()})
        sortie["ensemble"] = resumer(ensemble)
    return {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fenetre_jours": FENETRE_JOURS,
        "jeux": sortie,
    }


def main():
    resultat = calibrer()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(resultat, ensure_ascii=False, indent=1) + "\n")

    config = json.loads((ROOT / "data" / "config.json").read_text()).get("modele", {})
    for nom, j in resultat["jeux"].items():
        faux = [a for a, ok in j["qualifies_annonces_justes"].items() if not ok]
        sx = j["moyenne_sondax_j7"]
        print(f"{nom:16} {j['n_comparaisons']} comparaisons, erreur absolue moyenne "
              f"{j['erreur_absolue_moyenne']}, écart-type {j['ecart_type']}, "
              f"N_eff {j['N_eff']} ; moyenne Sondax à J−7 : écart-type {sx['ecart_type']}, "
              f"N_eff {sx['N_eff']} ; qualifiés faux : {', '.join(faux) or 'aucun'}")
    source = config.get("N_eff_source", "")
    jeu = source.removesuffix("_sondax_j7")
    if jeu in resultat["jeux"] and config.get("N_eff"):
        j = resultat["jeux"][jeu]
        estime = j["moyenne_sondax_j7"]["N_eff"] if source.endswith("_sondax_j7") else j["N_eff"]
        if abs(config["N_eff"] - estime) / estime > 0.2:
            print(f"  attention : N_eff retenu ({config['N_eff']}) à plus de 20 % "
                  f"de l'estimation « {source} » ({estime})", file=sys.stderr)
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
