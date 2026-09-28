#!/usr/bin/env python3
"""Backtest du modèle Sondax et validation de la loi (SPEC §14.17, §14.20).

Qu'aurait affiché Sondax avant les présidentielles 2002-2022 ? Pour chaque
élection, en leave-one-out : N_eff calibré sur toutes les autres élections
(présidentielles et européennes), avec l'estimateur du moteur (moyenne Sondax à
J−7), moyenne Sondax à J−7 de l'élection testée, moteur actuel (mélange k de
config.json), comparaison au résultat. Le même exercice est refait avec la
méthode de la phase A (moyenne simple de la dernière semaine, sans mélange)
pour mesurer ce que la correction apporte. Puis confrontation de la loi de Dirichlet aux erreurs
historiques. Écrit data/derived/backtest.json.
"""

import datetime, json, math, pathlib, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import calibration, modele  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "derived" / "backtest.json"
CONFIG_PATH = ROOT / "data" / "config.json"

HORIZON_JOURS = 7
TRANCHES_FIABILITE = [(0, 10), (10, 25), (25, 60), (60, 90), (90, 100.01)]
TRANCHES_NIVEAU = calibration.TRANCHES


moyenne_sondax = calibration.moyenne_sondax


def top2(d):
    return sorted(d, key=d.get, reverse=True)[:2]


def backtest_election(annee, election, n_eff, reglages, k=None):
    t1 = datetime.date.fromisoformat(election["tour1"])
    moy, date_moy = moyenne_sondax(election, t1 - datetime.timedelta(days=HORIZON_JOURS))
    slugs = sorted(moy)
    total = sum(moy.values())
    parts = [100 * moy[c] / total for c in slugs]
    comptes = modele.simuler(parts, n_eff, reglages["tirages"], reglages["graine"], k)
    n = comptes["tirages"]
    resultat = election["resultats"]["tour1"]
    qualifies = set(top2(resultat))

    candidats = []
    for i, c in enumerate(slugs):
        q = 100 * (comptes["r1"][i] + comptes["r2"][i]) / n
        candidats.append({
            "candidat": c,
            "nom": election["candidats"].get(c, {}).get("nom", c),
            "moyenne": round(moy[c], 2),
            "qualification": round(q, 2),
            "resultat": resultat[c],
            "qualifie": c in qualifies,
        })
    candidats.sort(key=lambda l: -l["qualification"])

    duels = sorted(((slugs[i], slugs[j], 100 * k / n)
                    for (i, j), k in comptes["duels"].items()), key=lambda d: -d[2])
    reel = sorted(qualifies)
    chance_reel = next((d[2] for d in duels if sorted(d[:2]) == reel), 0.0)
    return {
        "election": annee,
        "N_eff": round(n_eff, 1),
        "date_moyenne": date_moy,
        "candidats": candidats,
        "duel_principal": {"candidats": sorted(duels[0][:2]), "chance": round(duels[0][2], 2)},
        "duel_reel": {"candidats": reel, "chance": round(chance_reel, 2),
                      "rang": next((k + 1 for k, d in enumerate(duels)
                                    if sorted(d[:2]) == reel), None)},
    }


def fiabilite(runs):
    """Brier et table de fiabilité sur l'événement « qualifié »."""
    evts = [(l["qualification"] / 100, 1 if l["qualifie"] else 0)
            for r in runs for l in r["candidats"]]
    brier = statistics.fmean((p - o) ** 2 for p, o in evts)
    table = []
    for bas, haut in TRANCHES_FIABILITE:
        dans = [(p, o) for p, o in evts if bas <= 100 * p < haut]
        table.append({
            "de": bas, "a": min(haut, 100), "n": len(dans),
            "annonce": round(100 * statistics.fmean(p for p, _ in dans), 1) if dans else None,
            "observe": round(100 * statistics.fmean(o for _, o in dans), 1) if dans else None,
            "qualifies": sum(o for _, o in dans),
        })
    return {"brier": round(brier, 4), "n": len(evts), "table": table}


def score_log(runs):
    """Perte logarithmique sur l'événement « qualifié » (plus bas = mieux) et
    chances données au qualifié le moins attendu de chaque élection."""
    evts = [(l["qualification"] / 100, l["qualifie"]) for r in runs for l in r["candidats"]]
    perte = -statistics.fmean(math.log(max(p if o else 1 - p, 1e-4)) for p, o in evts)
    surprises = {r["election"]: min(l["qualification"] for l in r["candidats"] if l["qualifie"])
                 for r in runs}
    return {"perte_log": round(perte, 4), "qualifie_le_moins_attendu": surprises}


def valider_loi(lignes, n_eff):
    """Erreurs historiques confrontées à la Dirichlet(N_eff · p). Les candidats
    sondés à 0 sont écartés : la loi ne leur laisse aucune marge."""
    zeros = [l["candidat"] for l in lignes if l["part"] == 0]
    lignes = [l for l in lignes if l["part"] > 0]
    for l in lignes:
        p = l["part"] / 100
        l["sd_attendu"] = 100 * math.sqrt(p * (1 - p) / (n_eff + 1))
        l["z"] = l["erreur"] / l["sd_attendu"]

    def bloc(sel):
        if not sel:
            return {"n": 0}
        return {
            "n": len(sel),
            "ecart_type_observe": round(math.sqrt(statistics.fmean(l["erreur"] ** 2 for l in sel)), 2),
            "ecart_type_attendu": round(math.sqrt(statistics.fmean(l["sd_attendu"] ** 2 for l in sel)), 2),
            "rapport_variance": round(statistics.fmean(l["z"] ** 2 for l in sel), 2),
        }

    n = len(lignes)
    queues = {}
    for k, attendu in ((2, 0.0455), (3, 0.0027)):
        obs = sum(1 for l in lignes if abs(l["z"]) > k)
        queues[f"au_dela_{k}_ecarts_types"] = {
            "observe": obs, "attendu": round(attendu * n, 1)}

    par_tranche = {cle: bloc([l for l in lignes if bas <= l["moyenne"] < haut])
                   for cle, bas, haut in TRANCHES_NIVEAU}

    # Corrélations : entre les quatre premiers de chaque élection, covariance
    # observée des erreurs rapportée à celle de la loi (−pᵢpⱼ/(N+1)).
    paires, obs, att = [], 0.0, 0.0
    par_election = {}
    for l in lignes:
        par_election.setdefault(l["election"], []).append(l)
    for annee, ls in sorted(par_election.items()):
        top = sorted(ls, key=lambda l: -l["moyenne"])[:4]
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                a, b = top[i], top[j]
                prod = a["erreur"] * b["erreur"]
                cov = -(a["part"] / 100) * (b["part"] / 100) / (n_eff + 1) * 10_000
                obs += prod
                att += cov
                paires.append({"election": annee, "candidats": [a["candidat"], b["candidat"]],
                               "erreurs": [round(a["erreur"], 2), round(b["erreur"], 2)],
                               "meme_sens": prod > 0})
    return {
        "N_eff": n_eff,
        "ecartes_sondes_a_zero": zeros,
        "global": bloc(lignes),
        "queues": queues,
        "par_niveau": par_tranche,
        "correlations": {
            "paires": len(paires),
            "meme_sens": sum(p["meme_sens"] for p in paires),
            "covariance_moyenne_observee": round(obs / len(paires), 3),
            "covariance_moyenne_attendue": round(att / len(paires), 3),
            "exemples_meme_sens": sorted(
                (p for p in paires if p["meme_sens"]),
                key=lambda p: -abs(p["erreurs"][0] * p["erreurs"][1]))[:5],
        },
    }


def main():
    reglages = json.loads(CONFIG_PATH.read_text())["modele"]
    elections = json.loads(calibration.SOURCES["presidentielles"].read_text())["elections"]

    tout = {}
    for nom, el in calibration.charger_elections().items():
        tout.update({f"{nom}-{an}": e for an, e in el.items()})

    runs, runs_a = [], []
    for annee in sorted(elections):
        autres = {x: e for x, e in tout.items() if x != f"presidentielles-{annee}"}
        n_eff = calibration.estimer_neff(calibration.comparaisons_sondax(autres))
        runs.append(backtest_election(annee, elections[annee], n_eff, reglages,
                                      reglages.get("k_melange")))
        # Méthode de la phase A : présidentielles, moyenne simple, sans mélange
        autres_a = {a: e for a, e in elections.items() if a != annee}
        n_a = calibration.estimer_neff(calibration.comparaisons(autres_a))
        runs_a.append(backtest_election(annee, elections[annee], n_a, reglages))

    lignes = calibration.comparaisons_sondax(elections)
    for l in lignes:
        l["erreur"] = l["moyenne"] - l["resultat"]
    loi = valider_loi(lignes, reglages["N_eff"])
    loi_ensemble = None
    if calibration.SOURCES["europeennes"].exists():
        tout = {}
        for nom, el in calibration.charger_elections().items():
            tout.update({f"{nom}-{an}": e for an, e in el.items()})
        lignes_tout = calibration.comparaisons_sondax(tout)
        for l in lignes_tout:
            l["erreur"] = l["moyenne"] - l["resultat"]
        loi_ensemble = valider_loi(lignes_tout, reglages["N_eff"])

    sortie = {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "horizon_jours": HORIZON_JOURS,
        "methode": "leave-one-out : N_eff calibré sur les quatre autres présidentielles",
        "runs": runs,
        "fiabilite": fiabilite(runs),
        "comparaison": {
            "actuelle": {"methode": "moyenne Sondax à J−7, toutes élections, mélange k="
                         f"{reglages.get('k_melange')}", **score_log(runs), **fiabilite(runs)},
            "phase_a": {"methode": "moyenne simple de la dernière semaine, présidentielles, sans mélange",
                        **score_log(runs_a), **fiabilite(runs_a)},
        },
        "loi": loi,
        "loi_ensemble": loi_ensemble,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n")

    for r in runs:
        print(f"{r['election']}  N_eff {r['N_eff']:6.1f}  moyenne au {r['date_moyenne']}")
        for l in r["candidats"][:5]:
            print(f"    {l['candidat']:18} {l['moyenne']:5.1f}  → {l['qualification']:6.2f} sur 100"
                  f"   résultat {l['resultat']:5.2f}{'  qualifié' if l['qualifie'] else ''}")
        d, dr = r["duel_principal"], r["duel_reel"]
        print(f"    duel principal {'+'.join(d['candidats'])} {d['chance']} ; "
              f"réel {'+'.join(dr['candidats'])} {dr['chance']} (rang {dr['rang']})")
    for cle, c in sortie["comparaison"].items():
        print(f"{cle:8} Brier {c['brier']}  perte log {c['perte_log']}  "
              f"qualifié le moins attendu {c['qualifie_le_moins_attendu']}")
    f = sortie["fiabilite"]
    print(f"Brier {f['brier']} sur {f['n']} cas")
    for t in f["table"]:
        print(f"    {t['de']:>3}-{t['a']:<3}  n={t['n']:3}  annoncé {t['annonce']}  observé {t['observe']}")
    print(json.dumps({k: loi[k] for k in ("global", "queues", "par_niveau")}, ensure_ascii=False))
    c = loi["correlations"]
    print(f"Corrélations : {c['meme_sens']}/{c['paires']} paires de même sens ; covariance "
          f"observée {c['covariance_moyenne_observee']} contre {c['covariance_moyenne_attendue']} attendue")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
