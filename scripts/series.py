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
FENETRE_MIN_CANDIDAT = 3  # minimum de sondages par candidat, fenêtre extensible
FENETRE_MAX_JOURS = 90    # borne supérieure de l'extension

# Configuration de référence : hypothèses contenant à la fois Attal et Philippe.
# Quand elles existent, elles mesurent le bloc central au complet et évitent
# l'alternance bimodale entre hypothèses avec/sans l'un des deux.
CONFIG_REF = {"attal", "philippe"}


def score_candidat(sondage, candidat):
    """Score d'un candidat dans un sondage.

    Priorité aux hypothèses T1 de la configuration de référence (contenant
    CONFIG_REF). Fallback sur les hypothèses avec le plus de candidats testés.
    En cas d'égalité, moyenne des hypothèses ex æquo.

    Retourne (score, is_ref) ou (None, None) si absent.
    is_ref vaut True si le score vient d'une hypothèse de référence."""
    t1 = [h for h in sondage["hypotheses"]
          if h["tour"] == 1 and candidat in h["scores"]]
    if not t1:
        return None, None
    # Priorité : hypothèses contenant la config de référence
    ref = [h for h in t1 if CONFIG_REF.issubset(h["scores"].keys())]
    is_ref = bool(ref)
    pool = ref if ref else t1
    max_cands = max(len(h["scores"]) for h in pool)
    meilleures = [h for h in pool if len(h["scores"]) == max_cands]
    score = round(sum(h["scores"][candidat] for h in meilleures) / len(meilleures), 2)
    return score, is_ref


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


def calculer_series(sondages_raw):
    """Calcule les séries de tendance T1 à partir d'une liste de sondages.

    Retourne un dict avec date_debut, date_fin, fenetre_jours, demi_vies,
    points_bruts et series. Réutilisable pour 2027 et l'historique."""
    # Pré-traitement : liste de (date, sondage) pour les sondages ayant au moins une hyp T1
    sondages = []
    for s in sondages_raw:
        if any(h["tour"] == 1 for h in s["hypotheses"]):
            d = datetime.date.fromisoformat(s["terrain_fin"])
            sondages.append({"date": d, "raw": s})
    sondages.sort(key=lambda s: s["date"])

    if not sondages:
        return None

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
            sc, is_ref = score_candidat(s["raw"], c)
            if sc is not None:
                points_par_candidat[c].append({
                    "date": s["date"],
                    "score": sc,
                    "ref": is_ref,
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
        for c in sorted(all_candidats):
            sc, _ = score_candidat(s["raw"], c)
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

        # Moyenne pondérée par candidat (fenêtre extensible)
        for c in serie_par_candidat:
            # D'abord les sondages dans la fenêtre fixe de 30 jours
            pts_fenetre = []
            for p in points_par_candidat[c]:
                age = (jour - p["date"]).days
                if 0 <= age <= FENETRE_JOURS:
                    pts_fenetre.append((age, p["score"], p["ref"]))

            # Si < FENETRE_MIN_CANDIDAT, étendre vers le passé (borne FENETRE_MAX_JOURS)
            if len(pts_fenetre) < FENETRE_MIN_CANDIDAT:
                older = []
                for p in points_par_candidat[c]:
                    age = (jour - p["date"]).days
                    if FENETRE_JOURS < age <= FENETRE_MAX_JOURS:
                        older.append((age, p["score"], p["ref"]))
                older.sort(key=lambda x: x[0])  # par âge croissant
                while len(pts_fenetre) < FENETRE_MIN_CANDIDAT and older:
                    pts_fenetre.append(older.pop(0))

            if len(pts_fenetre) < MIN_SONDAGES:
                serie_par_candidat[c].append({"d": jour.isoformat(), "v": None, "n": 0, "ref": True})
                continue

            weights = [poids(age, T) for age, _ , _ in pts_fenetre]
            num = sum(w * score for w, (_, score, _) in zip(weights, pts_fenetre))
            den = sum(weights)
            val = round(num / den, 2)

            # ref = True si tous les sondages de la fenêtre viennent de la config de référence
            all_ref = all(r for _, _, r in pts_fenetre)

            # Invariant : une moyenne pondérée ne peut pas sortir de [min, max]
            raw = [score for _, score, _ in pts_fenetre]
            assert min(raw) - 0.01 <= val <= max(raw) + 0.01, (
                f"{c} {jour}: lissé={val} hors [{min(raw)}, {max(raw)}]"
            )

            serie_par_candidat[c].append({
                "d": jour.isoformat(),
                "v": val,
                "n": len(pts_fenetre),
                "ref": all_ref,
            })

    # Date du premier sondage contenant la config de référence
    first_ref_date = None
    for s in sondages:
        has_ref = any(
            CONFIG_REF.issubset(h["scores"].keys())
            for h in s["raw"]["hypotheses"] if h["tour"] == 1
        )
        if has_ref:
            first_ref_date = s["date"].isoformat()
            break

    return {
        "date_debut": date_debut.isoformat(),
        "date_fin": date_fin.isoformat(),
        "fenetre_jours": FENETRE_JOURS,
        "first_ref_date": first_ref_date,
        "demi_vies": demi_vies_par_date,
        "points_bruts": points_bruts,
        "series": serie_par_candidat,
    }


def main():
    sondages_raw = json.loads(SONDAGES_PATH.read_text())

    output = calculer_series(sondages_raw)
    if output is None:
        print("Aucun sondage T1 trouvé.")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n")

    # Rapport
    sondages = [s for s in sondages_raw if any(h["tour"] == 1 for h in s["hypotheses"])]
    all_candidats = set()
    for s in sondages:
        for h in s["hypotheses"]:
            if h["tour"] == 1:
                all_candidats.update(h["scores"].keys())

    print(f"{len(sondages)} sondages T1, {len(all_candidats)} candidats")
    print(f"Période : {output['date_debut']} → {output['date_fin']} ({len(output['demi_vies'])} jours)")
    from collections import Counter
    t_values = [d["T"] for d in output["demi_vies"] if d["n"] > 0]
    if t_values:
        print(f"Demi-vies utilisées : {dict(sorted(Counter(t_values).items()))}")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
