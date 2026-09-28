#!/usr/bin/env python3
"""Tests du moteur du modèle Sondax (SPEC §14.18).

Sans argument : tests du moteur sur des vecteurs fixes, puis contrôle de
data/derived/modele.json s'il existe. Sortie 1 au premier échec.
"""

import json, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import modele  # noqa: E402

N_EFF = 350
TIRAGES = 50_000
GRAINE = 20270418


def test_tirages_totalisent_100():
    x = modele.tirer([40, 20, 15, 10, 8, 7], N_EFF, TIRAGES, GRAINE)
    assert np.all(np.abs(x.sum(axis=1) - 1) < 1e-9), "un tirage ne totalise pas 100"
    assert np.all(x >= 0), "part négative"


def test_sommes_des_comptes():
    c = modele.simuler([30, 20, 20, 15, 10, 5], N_EFF, TIRAGES, GRAINE)
    assert sum(c["r1"]) + sum(c["r2"]) == 2 * TIRAGES, "qualifications ≠ 2 × tirages"
    assert sum(c["r1"]) == TIRAGES and sum(c["r2"]) == TIRAGES
    assert sum(c["duels"].values()) == TIRAGES, "duels ≠ tirages"
    for i in range(6):
        assert c["r1"][i] + c["r2"][i] <= TIRAGES


def test_meme_graine_meme_resultat():
    a = modele.simuler([30, 25, 20, 15, 10], N_EFF, TIRAGES, GRAINE)
    b = modele.simuler([30, 25, 20, 15, 10], N_EFF, TIRAGES, GRAINE)
    assert a == b, "deux runs de même graine diffèrent"


def test_candidat_a_40_quasi_toujours_qualifie():
    c = modele.simuler([40, 20, 15, 10, 8, 7], N_EFF, TIRAGES, GRAINE)
    q = 100 * (c["r1"][0] + c["r2"][0]) / TIRAGES
    assert q >= 99, f"candidat à 40 % qualifié {q:.2f} fois sur 100"


def test_symetrie():
    c = modele.simuler([30, 20, 20, 15, 15], N_EFF, TIRAGES, GRAINE)
    q1 = 100 * (c["r1"][1] + c["r2"][1]) / TIRAGES
    q2 = 100 * (c["r1"][2] + c["r2"][2]) / TIRAGES
    assert abs(q1 - q2) <= 1, f"deux candidats à 20 % : {q1:.2f} contre {q2:.2f}"


def test_verdicts():
    attendus = {100: "quasi_sur", 91: "quasi_sur", 90: "bien_place", 60: "bien_place",
                59: "rien_nest_joue", 25: "rien_nest_joue", 24: "surprise",
                8: "surprise", 7: "tres_improbable", 0: "tres_improbable"}
    for v, cle in attendus.items():
        assert modele.verdict(v) == cle, f"verdict({v}) = {modele.verdict(v)}, attendu {cle}"


def controler_sortie(m):
    """Contrôles de §14.18 sur un modele.json produit."""
    n = m["tirages"]
    cfg = m["configuration"]
    assert len(cfg) >= 3, "configuration de moins de trois candidats"
    r1, r2 = m["comptes"]["r1"], m["comptes"]["r2"]
    assert sum(r1.values()) + sum(r2.values()) == 2 * n, "qualifications ≠ 200"
    assert sum(m["comptes"]["duels"].values()) == n, "duels ≠ 100"
    for c, v in m["candidats"].items():
        assert r1[c] + r2[c] <= n, f"{c} qualifié plus souvent que de tirages"
        assert abs(sum(v["rang_exact"].values()) - 100) < 0.02, f"rangs de {c} ≠ 100"
        for champ in ("qualification", "qualification_exacte"):
            assert 0 <= v[champ] <= 100, f"{c}.{champ} hors de [0, 100]"
    for d in m["duels"]:
        assert 0 <= d["chance_exacte"] <= 100, "chance de duel hors de [0, 100]"


def test_sortie_reproductible():
    donnees = modele.charger()
    a = modele.calculer(*donnees)
    b = modele.calculer(*donnees)
    a.pop("date"), b.pop("date")
    assert a == b, "deux calculs sur les mêmes données diffèrent"
    controler_sortie(a)


TESTS = [test_tirages_totalisent_100, test_sommes_des_comptes,
         test_meme_graine_meme_resultat, test_candidat_a_40_quasi_toujours_qualifie,
         test_symetrie, test_verdicts]


def main():
    tests = list(TESTS)
    if modele.SERIES_PATH.exists():
        tests.append(test_sortie_reproductible)
    echecs = 0
    for t in tests:
        try:
            t()
            print(f"  ok     {t.__name__}")
        except AssertionError as e:
            echecs += 1
            print(f"  ÉCHEC  {t.__name__} : {e}", file=sys.stderr)
    if modele.OUTPUT_PATH.exists():
        try:
            controler_sortie(json.loads(modele.OUTPUT_PATH.read_text()))
            print("  ok     modele.json")
        except AssertionError as e:
            echecs += 1
            print(f"  ÉCHEC  modele.json : {e}", file=sys.stderr)
    if echecs:
        sys.exit(1)
    print("Tests du modèle : OK")


if __name__ == "__main__":
    main()
