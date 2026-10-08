"""Tests de la fusion des sondages (collecte_wikipedia.fusionner) et du retrait.

Même convention que test_modele.py : fonctions test_* sans dépendance, sortie 1
au premier échec. Lancé par `python scripts/test_fusion.py` et par
`python scripts/validation.py --modele`.
"""

import copy, json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import collecte_wikipedia as cw
import sondages_io
import validation
import series


def sondage(id_, institut="Ifop", fin="2026-09-10", scores=None, revid=100, **extra):
    scores = scores or {"le-pen": 33.0, "philippe": 20.0, "melenchon": 15.0}
    s = {"id": id_, "institut": institut, "terrain_debut": "2026-09-08",
         "terrain_fin": fin, "echantillon": 1000.0, "url_source": "https://x",
         "hypotheses": [{"tour": 1, "echantillon": None,
                         "candidats": sorted(scores), "scores": dict(scores)}],
         "revid": revid}
    s.update(extra)
    return s


def test_ajout():
    res, rap = cw.fusionner([sondage("ifop-2026-09-10")], [sondage("harris-2026-09-12", "Harris", "2026-09-12")])
    assert [s["id"] for s in res] == ["harris-2026-09-12", "ifop-2026-09-10"], res
    assert rap["ajoutes"] == ["harris-2026-09-12"] and not rap["modifies"]


def test_mise_a_jour_et_revid():
    ancien = sondage("ifop-2026-09-10", revid=100)
    nouveau = sondage("ifop-2026-09-10", scores={"le-pen": 34.0, "philippe": 20.0, "melenchon": 15.0}, revid=200)
    res, rap = cw.fusionner([ancien], [nouveau])
    assert len(res) == 1
    assert res[0]["hypotheses"][0]["scores"]["le-pen"] == 34.0
    assert res[0]["revid"] == 200
    (id_, diff), = rap["modifies"]
    assert id_ == "ifop-2026-09-10" and diff == ["hyp.1 T1 le-pen : 33.0 → 34.0"], diff


def test_inchange_garde_revid():
    """Rien n'a changé : l'entrée reste telle quelle, revid compris."""
    ancien = sondage("ifop-2026-09-10", revid=100)
    res, rap = cw.fusionner([ancien], [sondage("ifop-2026-09-10", revid=200)])
    assert res == [ancien] and not rap["modifies"]


def test_conservation_sondage_disparu():
    a, b = sondage("ifop-2026-09-10"), sondage("harris-2026-09-05", "Harris", "2026-09-05")
    res, rap = cw.fusionner([a, b], [copy.deepcopy(a)])
    assert res == [a, b], "le sondage absent de Wikipédia doit être conservé tel quel"
    assert rap["absents"] == ["harris-2026-09-05"]
    res, rap = cw.fusionner([a, b], [])   # page Wikipédia vide ou tronquée à zéro
    assert len(res) == 2 and rap["absents"] == ["ifop-2026-09-10", "harris-2026-09-05"]


def test_doublon_date_decalee():
    ancien = sondage("ifop-2026-09-10", fin="2026-09-10")
    for decalage, attendu_doublon in [("2026-09-11", False), ("2026-09-12", False),
                                      ("2026-09-08", False), ("2026-09-13", True)]:
        entrant = sondage("ifop-" + decalage, fin=decalage, revid=200)
        res, rap = cw.fusionner([ancien], [entrant])
        if attendu_doublon:
            assert len(res) == 2 and rap["ajoutes"], (decalage, res)
        else:
            assert len(res) == 1, (decalage, res)
            assert res[0]["id"] == "ifop-2026-09-10", "l'id est figé (URL publique)"
            assert res[0]["terrain_fin"] == decalage, res[0]
            assert res[0]["revid"] == 200
            assert rap["deplaces"] and rap["deplaces"][0][:2] == ("ifop-2026-09-10", "ifop-" + decalage)
            assert rap["modifies"][0][1] == [f"terrain_fin : '2026-09-10' → {decalage!r}"], rap["modifies"]
    # Stable au run suivant : l'entrée décalée est retrouvée, rien de nouveau.
    res, _ = cw.fusionner([ancien], [sondage("ifop-2026-09-11", fin="2026-09-11")])
    res2, rap2 = cw.fusionner(res, [sondage("ifop-2026-09-11", fin="2026-09-11")])
    assert res2 == res and not rap2["modifies"] and not rap2["ajoutes"]


def test_pas_de_doublon_si_valeurs_ou_institut_differents():
    ancien = sondage("ifop-2026-09-10")
    autre_valeurs = sondage("ifop-2026-09-11", fin="2026-09-11", scores={"le-pen": 30.0, "philippe": 22.0, "melenchon": 15.0})
    autre_institut = sondage("harris-2026-09-11", "Harris", "2026-09-11")
    for entrant in (autre_valeurs, autre_institut):
        res, rap = cw.fusionner([ancien], [entrant])
        assert len(res) == 2 and rap["ajoutes"] == [entrant["id"]], res


def test_deux_sondages_distincts_proches_ne_fusionnent_pas():
    """Deux vagues du même institut à un jour d'écart, toutes deux sur Wikipédia :
    chacune reste ce qu'elle est (appariement par id d'abord)."""
    a = sondage("ifop-2026-09-10", fin="2026-09-10")
    b = sondage("ifop-2026-09-11", fin="2026-09-11")   # mêmes valeurs
    res, rap = cw.fusionner([a, b], [copy.deepcopy(a), copy.deepcopy(b)])
    assert len(res) == 2 and not rap["modifies"] and not rap["deplaces"]


def test_sondage_retire():
    r = sondage("ifop-2026-09-10", retire=True, retire_motif="doublon", retire_le="2026-10-08")
    # Wikipédia le modifie : valeurs mises à jour, retrait intact
    entrant = sondage("ifop-2026-09-10", scores={"le-pen": 35.0, "philippe": 20.0, "melenchon": 15.0}, revid=200)
    res, rap = cw.fusionner([r], [entrant])
    assert res[0]["retire"] is True and res[0]["retire_motif"] == "doublon" and res[0]["retire_le"] == "2026-10-08"
    assert rap["retires_touches"] == ["ifop-2026-09-10"]
    # Wikipédia le republie avec une date décalée : pas de résurrection en doublon
    res, rap = cw.fusionner([r], [sondage("ifop-2026-09-12", fin="2026-09-12")])
    assert len(res) == 1 and res[0]["retire"] is True and res[0]["id"] == "ifop-2026-09-10"
    # Disparu de Wikipédia : conservé, toujours retiré
    res, _ = cw.fusionner([r], [])
    assert res == [r]


def test_sondage_retire_exclu_du_chargement_et_des_calculs():
    actif = sondage("ifop-2026-09-10")
    retire = sondage("harris-2026-09-10", "Harris", retire=True, retire_motif="erreur", retire_le="2026-10-08")
    assert sondages_io.actifs([actif, retire]) == [actif]
    with tempfile.TemporaryDirectory() as d:
        chemin = pathlib.Path(d) / "sondages.json"
        chemin.write_text(json.dumps([actif, retire]))
        assert [s["id"] for s in sondages_io.charger(chemin)] == ["ifop-2026-09-10"]
        assert len(sondages_io.charger_tous(chemin)) == 2
    # series.main lit via sondages_io.charger : un retiré n'entre pas dans les séries
    assert series.charger_sondages is sondages_io.charger


def test_validation_bloque_si_le_total_baisse():
    s100 = {"le-pen": 40.0, "philippe": 35.0, "melenchon": 25.0}
    a = sondage("ifop-2026-09-10", scores=s100)
    b = sondage("harris-2026-09-05", "Harris", "2026-09-05", scores=s100)
    avant = validation.load_previous_sondages
    try:
        validation.load_previous_sondages = lambda: [a, b]
        ok, erreurs = validation.validate([a, b], {"le-pen": {}, "philippe": {}, "melenchon": {}})
        assert ok, erreurs
        ok, erreurs = validation.validate([a], {"le-pen": {}, "philippe": {}, "melenchon": {}})
        assert not ok and any("régression" in e for e in erreurs), erreurs
        # même total mais un id remplacé : bug de fusion aussi
        c = sondage("elabe-2026-09-01", "Elabe", "2026-09-01", scores=s100)
        ok, erreurs = validation.validate([a, c], {"le-pen": {}, "philippe": {}, "melenchon": {}})
        assert not ok and any("disparus" in e for e in erreurs), erreurs
    finally:
        validation.load_previous_sondages = avant


def test_fichier_actuel_inchange_par_la_fusion():
    """Rejouer le snapshot de référence sur data/sondages.json ne change rien et
    n'en perd aucun ; avec une page tronquée, tout est conservé."""
    racine = cw.ROOT
    actuel = json.loads(cw.OUTPUT_PATH.read_text())
    snap = sorted(cw.SNAPSHOTS_DIR.glob("*.wikitext"), key=lambda p: int(p.stem))[-1]
    candidats = json.loads(cw.CANDIDATS_PATH.read_text())
    alias = cw.build_alias_map(candidats)
    cw.ANOMALIES.clear()
    entrants = cw.extract_sondages(snap.read_text(encoding="utf-8"))
    assert not cw.ANOMALIES, cw.ANOMALIES
    for s in entrants:
        cw.resolve_scores(s["hypotheses"], alias)
        s["revid"] = int(snap.stem)
    complets = {}
    for s in entrants:
        if s["id"] in complets:
            complets[s["id"]]["hypotheses"] += s["hypotheses"]
        else:
            complets[s["id"]] = s
    entrants = list(complets.values())
    res, _ = cw.fusionner(actuel, entrants)
    assert len(res) >= len(actuel), (len(res), len(actuel))
    assert {s["id"] for s in actuel} <= {s["id"] for s in res}
    res, rap = cw.fusionner(actuel, entrants[:24])   # le scénario du 08/10 : 24 sondages
    assert len(res) == len(actuel) and len(rap["absents"]) >= len(actuel) - 24 - 1


TESTS = [test_ajout, test_mise_a_jour_et_revid, test_inchange_garde_revid,
         test_conservation_sondage_disparu, test_doublon_date_decalee,
         test_pas_de_doublon_si_valeurs_ou_institut_differents,
         test_deux_sondages_distincts_proches_ne_fusionnent_pas,
         test_sondage_retire, test_sondage_retire_exclu_du_chargement_et_des_calculs,
         test_validation_bloque_si_le_total_baisse,
         test_fichier_actuel_inchange_par_la_fusion]


def main():
    echecs = 0
    for t in TESTS:
        try:
            t()
            print(f"  ok     {t.__name__}")
        except AssertionError as e:
            echecs += 1
            print(f"  ÉCHEC  {t.__name__} : {e}", file=sys.stderr)
    if echecs:
        sys.exit(1)
    print("Tests de fusion : OK")


if __name__ == "__main__":
    main()
