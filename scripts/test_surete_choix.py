"""Tests de la rubrique « sûreté du choix » (surete_choix.py, build_index_surete_choix.py).

Même convention que test_modele.py et test_fusion.py : fonctions test_* sans
dépendance, sortie 1 au premier échec. Lancé par `python scripts/test_surete_choix.py`
et par `python scripts/validation.py --modele`.
"""

import copy, datetime as dt, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import surete_choix as sc
import build_index_surete_choix as bi

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATS = json.loads((ROOT / "data" / "candidats.json").read_text(encoding="utf-8"))
REEL = sc.charger()

# Évolutions affichées par Elabe lui-même sur sa slide (contrôle d'intégrité).
ECARTS_ELABE = {"le-pen": 3, "melenchon": -1, "zemmour": -2, "glucksmann": 5,
                "retailleau": -1, "tondelier": 3, "philippe": -10, "villepin": -9,
                "ensemble": 1}
FICHES = ["attal", "glucksmann", "le-pen", "melenchon", "philippe",
          "retailleau", "roussel", "tondelier", "zemmour"]


def vague(id_="v1", fin="2026-11-13", cands=None, ensemble=50, config="premier-tour-1", **extra):
    v = copy.deepcopy(REEL["vagues"][-1])
    v.update({"id": id_, "terrain_debut": fin, "terrain_fin": fin, "publiee_le": fin,
              "configuration": config, "ensemble": ensemble,
              "candidats": cands if cands is not None else {"le-pen": 80, "philippe": 30},
              "omis": []})
    v.update(extra)
    return v


def fichier(*vagues):
    d = copy.deepcopy(REEL)
    d["vagues"] = list(vagues)
    return d


def rejette(data, morceau):
    try:
        sc.valider(data, CANDIDATS)
    except ValueError as e:
        assert morceau in str(e), f"message sans « {morceau} » : {e}"
        return
    raise AssertionError(f"fichier accepté alors que « {morceau} » attendu")


# --- intégrité des données saisies -------------------------------------------

def test_donnees_reelles_valides():
    assert sc.valider(REEL, CANDIDATS)
    assert [v["id"] for v in REEL["vagues"]] == ["elabe-2026-10-16", "elabe-2026-11-13"]
    assert REEL["vagues"][0]["effectifs_utiles"] is None


def test_ecarts_identiques_a_ceux_d_elabe():
    ev = sc.evolutions(REEL["vagues"])[1]
    assert ev == ECARTS_ELABE, {k: (ev.get(k), ECARTS_ELABE[k]) for k in ECARTS_ELABE if ev.get(k) != ECARTS_ELABE[k]}


def test_aucune_evolution_stockee():
    for v in REEL["vagues"]:
        assert not any("evol" in k for k in v), "une évolution est stockée dans le JSON"


# --- validation ---------------------------------------------------------------

def test_id_candidat_inconnu_rejete():
    rejette(fichier(vague(cands={"le-pen": 80, "inconnu": 10})), "inconnu")


def test_id_omis_inconnu_rejete():
    rejette(fichier(vague(omis=["fantome"])), "fantome")


def test_vagues_non_triees_rejetees():
    rejette(fichier(vague("a", "2026-11-13"), vague("b", "2026-10-16")), "terrain_fin croissant")


def test_meme_terrain_fin_rejete():
    rejette(fichier(vague("a", "2026-11-13"), vague("b", "2026-11-13")), "terrain_fin croissant")


def test_effectifs_utiles_null_accepte():
    d = fichier(vague(effectifs_utiles=None))
    assert sc.valider(d, CANDIDATS)
    assert sc.vue(d, dt.date(2026, 11, 20), CANDIDATS)["vague"]["effectifs_utiles"] is None
    assert "effectifs utiles" not in sc.mentions_html(d["vagues"][0], d["base"])


def test_valeur_hors_bornes_rejetee():
    rejette(fichier(vague(cands={"le-pen": 120})), "le-pen")


def test_commanditaire_inconnu_rejete():
    rejette(fichier(vague(commanditaires=["bfmtv", "nulle-part"])), "nulle-part")


# --- évolutions ---------------------------------------------------------------

def test_candidat_absent_de_la_vague_precedente_sans_evolution():
    a = vague("a", "2026-10-16", {"le-pen": 79, "philippe": 38})
    b = vague("b", "2026-11-13", {"le-pen": 82, "philippe": 28, "tondelier": 31})
    ev = sc.evolutions([a, b])[1]
    assert ev["tondelier"] is None, "absent de la vague précédente : pas d'évolution"
    assert ev["tondelier"] != 0
    assert ev["le-pen"] == 3 and ev["philippe"] == -10


def test_premiere_vague_sans_evolution():
    ev = sc.evolutions([vague()])[0]
    assert ev["le-pen"] is None and ev["ensemble"] is None


def test_evolution_contre_la_meme_configuration():
    a = vague("a", "2026-09-18", {"le-pen": 70}, config="premier-tour-1")
    b = vague("b", "2026-10-16", {"le-pen": 99}, config="premier-tour-2")
    c = vague("c", "2026-11-13", {"le-pen": 82}, config="premier-tour-1")
    evs = sc.evolutions([a, b, c])
    assert evs[1]["le-pen"] is None, "première vague de la configuration 2"
    assert evs[2]["le-pen"] == 12, "comparé à la vague de la même configuration, pas à la précédente"


def test_evolution_nulle_est_un_zero_et_pas_un_tiret():
    a = vague("a", "2026-10-16", {"le-pen": 80})
    b = vague("b", "2026-11-13", {"le-pen": 80})
    assert sc.evolutions([a, b])[1]["le-pen"] == 0


# --- règle de péremption --------------------------------------------------------

def test_peremption_dix_semaines():
    fin = dt.date.fromisoformat(REEL["vagues"][-1]["terrain_fin"])
    assert not sc.est_perimee(REEL, fin + dt.timedelta(days=70)), "70 jours : encore affiché"
    assert sc.est_perimee(REEL, fin + dt.timedelta(days=71)), "71 jours : masqué"
    assert sc.vue(REEL, fin + dt.timedelta(days=70), CANDIDATS) is not None
    assert sc.vue(REEL, fin + dt.timedelta(days=71), CANDIDATS) is None


def test_peremption_regarde_la_vague_la_plus_recente():
    # une vague ancienne ne masque rien tant qu'une vague récente existe
    assert not sc.est_perimee(REEL, dt.date(2026, 11, 22))


# --- fiches ---------------------------------------------------------------------

def test_phrase_fiche_et_accord_genre():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    f = sc.ligne_fiche(vue, "le-pen", CANDIDATS["le-pen"]["genre"])
    m = sc.ligne_fiche(vue, "melenchon", CANDIDATS["melenchon"]["genre"])
    assert f == ("Parmi les électeurs qui la placent en tête au 1er tour, 82 % "
                 "se disent sûrs de leur choix (+3 en un mois)."), f
    assert "qui le placent en tête" in m and "75 %" in m and "(−1 en un mois)" in m, m


def test_sept_fiches_sur_neuf():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    avec = [c for c in FICHES if sc.ligne_fiche(vue, c, CANDIDATS[c].get("genre", "m"))]
    assert len(avec) == 7, avec
    assert set(FICHES) - set(avec) == {"attal", "roussel"}


def test_candidat_non_mesure_n_affiche_rien():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    for cid in ("attal", "roussel"):
        assert sc.ligne_fiche(vue, cid) == "", f"{cid} : ni ligne, ni tiret, ni zéro"


def test_fiches_masquees_si_perime():
    assert sc.ligne_fiche(None, "le-pen") == ""


def test_pas_d_evolution_pas_de_parenthese():
    d = fichier(vague())
    vue = sc.vue(d, dt.date(2026, 11, 20), CANDIDATS)
    ligne = sc.ligne_fiche(vue, "le-pen", "f")
    assert "(" not in ligne and ligne.endswith("de leur choix."), ligne


def test_ecart_non_mensuel_cite_la_date():
    a = vague("a", "2026-09-04", {"le-pen": 70})
    b = vague("b", "2026-11-13", {"le-pen": 82})
    vue = sc.vue(fichier(a, b), dt.date(2026, 11, 20), CANDIDATS)
    assert "(+12 depuis le 4 septembre)" in sc.ligne_fiche(vue, "le-pen", "f")


# --- bloc d'accueil ---------------------------------------------------------------

FAUSSE_PAGE = ("<body>\n<!-- BEGIN:bloc-modele -->\n<div>modèle</div>\n<!-- END:bloc-modele -->\n\n"
               "  <!-- BEGIN:second-tour -->\n  <div>second tour</div>\n<!-- END:second-tour -->\n\n"
               "  <!-- Bloc 2 -->\n</body>\n")


def test_bloc_place_apres_modele_avant_second_tour():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    page = bi.inject(FAUSSE_PAGE, bi.generate_bloc(vue, CANDIDATS))
    i_modele = page.index("<!-- END:bloc-modele -->")
    i_bloc = page.index(bi.BEGIN_MARKER)
    i_t2 = page.index("<!-- BEGIN:second-tour -->")
    assert i_modele < i_bloc < page.index(bi.END_MARKER) < i_t2


def test_mention_source_dans_le_bloc():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    bloc = bi.generate_bloc(vue, CANDIDATS)
    assert "Sondage Elabe pour BFMTV et La Tribune Dimanche" in bloc
    assert "pas une moyenne Sondax" in bloc
    assert "certitude d’aller voter" in bloc
    assert bloc.index("Sondage Elabe pour BFMTV") < bloc.index("<table"), "la source se lit avant le tableau"


def test_bloc_huit_candidats_tries_avec_ensemble():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    bloc = bi.generate_bloc(vue, CANDIDATS)
    assert bloc.count('<th scope="row">') == 9  # 8 candidats + ensemble
    parts = [int(x) for x in __import__("re").findall(r'<td class="sc-num">(\d+) %</td>', bloc)]
    assert parts == [82, 75, 65, 44, 36, 31, 28, 26, 55], parts
    assert "Ensemble des électeurs" in bloc


def test_bloc_masque_sans_trou():
    vue_perimee = sc.vue(REEL, dt.date(2027, 3, 1), CANDIDATS)
    assert vue_perimee is None
    assert bi.generate_bloc(vue_perimee, CANDIDATS) == ""
    # page sans la rubrique : masquer n'y change rien
    assert bi.inject(FAUSSE_PAGE, "") == FAUSSE_PAGE
    # page avec la rubrique : masquer la rend strictement identique à la page d'origine
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    avec = bi.inject(FAUSSE_PAGE, bi.generate_bloc(vue, CANDIDATS))
    assert avec != FAUSSE_PAGE
    sans = bi.inject(avec, bi.generate_bloc(vue_perimee, CANDIDATS))
    assert sans == FAUSSE_PAGE, "il reste un trou ou un marqueur après le masquage"
    assert "surete" not in sans and "\n\n\n" not in sans


def test_injection_idempotente():
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    bloc = bi.generate_bloc(vue, CANDIDATS)
    une = bi.inject(FAUSSE_PAGE, bloc)
    assert bi.inject(une, bloc) == une
    assert une.count(bi.BEGIN_MARKER) == 1


def test_masquage_sur_la_vraie_page_d_accueil():
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    vue = sc.vue(REEL, dt.date(2026, 11, 22), CANDIDATS)
    avec = bi.inject(page, bi.generate_bloc(vue, CANDIDATS))
    assert bi.inject(avec, "") == bi.inject(page, ""), "la page masquée diffère de la page d'origine"


def test_reperes_absents_declenchent_une_erreur():
    try:
        bi.inject("<body></body>", "<div>x</div>")
    except ValueError:
        return
    raise AssertionError("insertion silencieuse sans repères")


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


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
    print("Tests de la sûreté du choix : OK")


if __name__ == "__main__":
    main()
