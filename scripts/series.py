"""Calcul des séries de tendance T1 (spec §4).

Lit data/sondages.json, sélectionne l'hypothèse principale de chaque sondage,
calcule la moyenne pondérée glissante avec demi-vie adaptative, et écrit
data/derived/series-t1.json.
"""

import json, math, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SONDAGES_PATH = ROOT / "data" / "sondages.json"
OUTPUT_PATH = ROOT / "data" / "derived" / "series-t1.json"

FENETRE_JOURS = 30
DEMI_VIES = [4, 7, 14]
NEFF_SEUIL = 4
MIN_SONDAGES = 2


def hypothese_principale(sondage):
    """Hypothèse T1 avec le plus de candidats testés ; en cas d'égalité, la première."""
    t1 = [h for h in sondage["hypotheses"] if h["tour"] == 1]
    if not t1:
        return None
    return max(t1, key=lambda h: len(h["scores"]))


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
    sondages = json.loads(SONDAGES_PATH.read_text())

    # Extraire les points bruts : (date, {candidat: score})
    points = []
    for s in sondages:
        hyp = hypothese_principale(s)
        if hyp is None:
            continue
        d = datetime.date.fromisoformat(s["terrain_fin"])
        points.append({"date": d, "scores": hyp["scores"], "id": s["id"]})

    points.sort(key=lambda p: p["date"])

    if not points:
        print("Aucun sondage T1 trouvé.")
        return

    # Tous les candidats rencontrés
    all_candidats = set()
    for p in points:
        all_candidats.update(p["scores"].keys())

    # Calculer la courbe jour par jour, de la première à la dernière mesure
    date_debut = points[0]["date"]
    date_fin = points[-1]["date"]
    nb_jours = (date_fin - date_debut).days + 1

    serie_par_candidat = {c: [] for c in sorted(all_candidats)}
    demi_vies_par_date = []
    points_bruts = []

    for i in range(nb_jours):
        jour = date_debut + datetime.timedelta(days=i)

        # Sondages dans la fenêtre de 30 jours
        dans_fenetre = []
        for p in points:
            age = (jour - p["date"]).days
            if 0 <= age <= FENETRE_JOURS:
                dans_fenetre.append((age, p))

        # Points bruts de ce jour exact
        for p in points:
            if p["date"] == jour:
                points_bruts.append({
                    "d": jour.isoformat(),
                    "id": p["id"],
                    "scores": p["scores"],
                })

        # Interruption si < 2 sondages dans la fenêtre
        if len(dans_fenetre) < MIN_SONDAGES:
            demi_vies_par_date.append({
                "d": jour.isoformat(),
                "T": None,
                "n": len(dans_fenetre),
                "neff": None,
            })
            for c in serie_par_candidat:
                serie_par_candidat[c].append({"d": jour.isoformat(), "v": None})
            continue

        # Demi-vie adaptative
        ages = [age for age, _ in dans_fenetre]
        T = choisir_demi_vie(ages)
        weights = [poids(age, T) for age in ages]
        neff = neff_kish(weights)

        demi_vies_par_date.append({
            "d": jour.isoformat(),
            "T": T,
            "n": len(dans_fenetre),
            "neff": round(neff, 2),
        })

        # Moyenne pondérée par candidat
        for c in serie_par_candidat:
            num, den = 0, 0
            for (age, p), w in zip(dans_fenetre, weights):
                if c in p["scores"]:
                    num += w * p["scores"][c]
                    den += w
            if den > 0:
                serie_par_candidat[c].append({
                    "d": jour.isoformat(),
                    "v": round(num / den, 2),
                })
            else:
                serie_par_candidat[c].append({"d": jour.isoformat(), "v": None})

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
    print(f"{len(points)} sondages T1, {len(all_candidats)} candidats")
    print(f"Période : {date_debut} → {date_fin} ({nb_jours} jours)")
    # Résumé demi-vies
    t_values = [d["T"] for d in demi_vies_par_date if d["T"] is not None]
    if t_values:
        from collections import Counter
        counts = Counter(t_values)
        print(f"Demi-vies utilisées : {dict(sorted(counts.items()))}")
    nulls = sum(1 for d in demi_vies_par_date if d["T"] is None)
    if nulls:
        print(f"Jours sans courbe (< {MIN_SONDAGES} sondages) : {nulls}")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
