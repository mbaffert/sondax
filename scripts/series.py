"""Calcul des séries de tendance T1 (spec §4).

Lit data/sondages.json, sélectionne pour chaque candidat et chaque sondage
l'hypothèse T1 qui le contient et compte le plus de candidats, calcule la
moyenne pondérée glissante avec demi-vie adaptative, et écrit
data/derived/series-t1.json.
"""

import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SONDAGES_PATH = ROOT / "data" / "sondages.json"
OUTPUT_PATH = ROOT / "data" / "derived" / "series-t1.json"

FENETRE_JOURS = 30
DEMI_VIES = [4, 7, 14]
NEFF_SEUIL = 4
MIN_SONDAGES = 1


def score_candidat(sondage, candidat):
    """Score d'un candidat dans un sondage : moyenne des hypothèses T1 qui le
    contiennent et comptent le plus de candidats. None si absent de toutes."""
    t1 = [h for h in sondage["hypotheses"]
          if h["tour"] == 1 and candidat in h["scores"]]
    if not t1:
        return None
    max_cands = max(len(h["scores"]) for h in t1)
    meilleures = [h for h in t1 if len(h["scores"]) == max_cands]
    return round(sum(h["scores"][candidat] for h in meilleures) / len(meilleures), 2)


def poids(age_jours, demi_vie):
    return 2 ** (-age_jours / demi_vie)


def neff_kish(weights):
    """Nombre effectif de sondages (formule de Kish) : (Σw)² / Σw²."""
    sw = sum(weights)
    sw2 = sum(w * w for w in weights)
    if sw2 == 0:
        return 0
    return (sw * sw) / sw2


def choisir_demi_vie(ages):
    """Retourne la plus courte demi-vie parmi DEMI_VIES donnant neff >= NEFF_SEUIL."""
    for t in DEMI_VIES:
        w = [poids(a, t) for a in ages]
        if neff_kish(w) >= NEFF_SEUIL:
            return t
    return DEMI_VIES[-1]


def main():
    sondages_raw = json.loads(SONDAGES_PATH.read_text())

    # Pré-traitement : liste de (date, sondage) pour les sondages ayant au moins une hyp T1
    sondages = []
    for s in sondages_raw:
        if any(h["tour"] == 1 for h in s["hypotheses"]):
            d = datetime.date.fromisoformat(s["terrain_fin"])
            sondages.append({"date": d, "raw": s})
    sondages.sort(key=lambda s: s["date"])

    if not sondages:
        print("Aucun sondage T1 trouvé.")
        return

    # Tous les candidats rencontrés dans au moins une hypothèse T1
    all_candidats = set()
    for s in sondages:
        for h in s["raw"]["hypotheses"]:
            if h["tour"] == 1:
                all_candidats.update(h["scores"].keys())

    # Points bruts par candidat : pour chaque sondage, le score du candidat
    # (moyenne des meilleures hypothèses ex æquo)
    points_par_candidat = {c: [] for c in sorted(all_candidats)}
    for s in sondages:
        for c in all_candidats:
            sc = score_candidat(s["raw"], c)
            if sc is not None:
                points_par_candidat[c].append({
                    "date": s["date"],
                    "score": sc,
                    "id": s["raw"]["id"],
                })

    date_debut = sondages[0]["date"]
    date_fin = sondages[-1]["date"]
    nb_jours = (date_fin - date_debut).days + 1

    serie_par_candidat = {c: [] for c in sorted(all_candidats)}
    demi_vies_par_date = []
    points_bruts = []

    # Points bruts pour le JSON de sortie (un par sondage-jour, tous candidats)
    for s in sondages:
        scores = {}
        for c in all_candidats:
            sc = score_candidat(s["raw"], c)
            if sc is not None:
                scores[c] = sc
        points_bruts.append({
            "d": s["date"].isoformat(),
            "id": s["raw"]["id"],
            "scores": scores,
        })

    for i in range(nb_jours):
        jour = date_debut + datetime.timedelta(days=i)

        # Demi-vie globale : calculée sur tous les sondages dans la fenêtre
        ages_global = []
        for s in sondages:
            age = (jour - s["date"]).days
            if 0 <= age <= FENETRE_JOURS:
                ages_global.append(age)

        T = choisir_demi_vie(ages_global) if ages_global else DEMI_VIES[-1]

        demi_vies_par_date.append({
            "d": jour.isoformat(),
            "T": T,
            "n": len(ages_global),
            "neff": round(neff_kish([poids(a, T) for a in ages_global]), 2) if ages_global else 0,
        })

        # Moyenne pondérée par candidat
        for c in serie_par_candidat:
            pts_fenetre = []
            for p in points_par_candidat[c]:
                age = (jour - p["date"]).days
                if 0 <= age <= FENETRE_JOURS:
                    pts_fenetre.append((age, p["score"]))

            if len(pts_fenetre) < MIN_SONDAGES:
                serie_par_candidat[c].append({"d": jour.isoformat(), "v": None, "n": 0})
                continue

            weights = [poids(age, T) for age, _ in pts_fenetre]
            num = sum(w * score for w, (_, score) in zip(weights, pts_fenetre))
            den = sum(weights)
            val = round(num / den, 2)

            # Invariant : une moyenne pondérée ne peut pas sortir de [min, max]
            raw = [score for _, score in pts_fenetre]
            assert min(raw) - 0.01 <= val <= max(raw) + 0.01, (
                f"{c} {jour}: lissé={val} hors [{min(raw)}, {max(raw)}]"
            )

            serie_par_candidat[c].append({
                "d": jour.isoformat(),
                "v": val,
                "n": len(pts_fenetre),
            })

    output = {
        "date_debut": date_debut.isoformat(),
        "date_fin": date_fin.isoformat(),
        "fenetre_jours": FENETRE_JOURS,
        "demi_vies": demi_vies_par_date,
        "points_bruts": points_bruts,
        "series": serie_par_candidat,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n")

    # Rapport
    print(f"{len(sondages)} sondages T1, {len(all_candidats)} candidats")
    print(f"Période : {date_debut} → {date_fin} ({nb_jours} jours)")
    from collections import Counter
    t_values = [d["T"] for d in demi_vies_par_date if d["n"] > 0]
    if t_values:
        print(f"Demi-vies utilisées : {dict(sorted(Counter(t_values).items()))}")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
