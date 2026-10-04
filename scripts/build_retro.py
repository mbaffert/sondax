"""Rétro-Sondax : « À J-x de la présidentielle, qui était en tête des sondages ? »

Lit data/historique.json (sondages 2007-2022, §12) et data/derived/historique.json
(couleurs et noms courts, produit par series_historique.py). Pour 2022, 2017, 2012
et 2007, et pour chaque J-x de 365 à 1, calcule les quatre premiers de la moyenne
du premier tour avec la fonction de tendance de la home (series.calculer_series),
écrit data/derived/retro.json et injecte le bloc #retro-sondax dans
site/index.html, pour le J-x du jour du build. SPEC §15.

retro.json contient aussi 2002 (même calcul) et 2027 (sondages de data/
sondages.json, jours déjà écoulés seulement), pour le Rétro-Sondax à curseur de
precedentes-elections.html (rendu par scripts/build_pages_elections.py, qui
appelle rendre_bloc_page()). Le bloc de la home ne lit que les quatre élections
de ANNEES.

Candidats non désignés : tant qu'un parti n'a pas désigné son candidat, la
personne qu'il présente dans une hypothèse est remplacée par une entrée
`type: parti` (« Candidat LR »), qui garde la personne testée (`teste`).
"""

import json, pathlib, datetime, html
from collections import Counter

from series import calculer_series
from principale import calculer as calculer_principale
from series_historique import TOUR1_2027, nom_court, PARTI_COUL

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORIQUE_PATH = ROOT / "data" / "historique.json"
DERIVED_HISTORIQUE_PATH = ROOT / "data" / "derived" / "historique.json"
OUTPUT_PATH = ROOT / "data" / "derived" / "retro.json"
INDEX_PATH = ROOT / "site" / "index.html"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"

BEGIN = "<!-- BEGIN:bloc-retro -->"
END = "<!-- END:bloc-retro -->"

ANNEES = ["2022", "2017", "2012", "2007"]
# Page precedentes-elections.html : 2027 (point de comparaison) puis les cinq
# élections, de la plus récente à la plus ancienne.
ANNEES_PAGE = ["2027", "2022", "2017", "2012", "2007", "2002"]
J_MAX = 365
J_MIN_PAGE = 30   # borne basse du curseur de la page
TOP = 4
SEUIL_APPROX = 2   # sondages dans la fenêtre de 30 jours en deçà duquel on prend le plus proche

# Candidats non désignés, par élection : parti, date de désignation (exclue),
# personnes rattachées au parti. Dans une hypothèse qui en teste plusieurs,
# la première de la liste occupe la place du parti, les autres restent des
# candidats à part entière (dissidents : Villepin 2007, Montebourg 2017...).
NON_DESIGNES = {
    "2022": [("LR", "2021-12-04", ["bertrand", "pecresse", "barnier", "baroin", "ciotti",
                                   "juvin", "payre", "retailleau", "wauquiez"])],
    "2017": [("LR", "2016-11-27", ["juppe", "sarkozy", "fillon", "le-maire",
                                   "kosciusko-morizet", "cope"]),
             ("PS", "2017-01-29", ["hollande", "valls", "montebourg", "hamon", "peillon"])],
    "2012": [("PS", "2011-10-16", ["hollande", "aubry", "strauss-kahn", "royal",
                                   "delanoe", "fabius"])],
    "2007": [("PS", "2006-11-16", ["royal", "strauss-kahn", "fabius", "jospin",
                                   "lang", "hollande"]),
             ("UMP", "2007-01-14", ["sarkozy", "villepin", "alliot-marie", "chirac"])],
}

FEMININ = {"royal", "aubry", "pecresse", "alliot-marie", "kosciusko-morizet"}


def slug_parti(parti):
    return "candidat-" + parti.lower()


def rattacher_partis(sondages, regles):
    """Remplace, avant désignation, la personne d'un parti par l'entrée de parti.

    Modifie les hypothèses en place ; pose `teste` sur chaque hypothèse concernée
    ({slug_parti: personne}). Retourne la liste des cas où une hypothèse testait
    plusieurs personnes du même parti."""
    multiples = []
    for s in sondages:
        for h in s["hypotheses"]:
            if h["tour"] != 1:
                continue
            for parti, designation, personnes in regles:
                if s["terrain_fin"] >= designation:
                    continue
                presents = [p for p in personnes if p in h["scores"]]
                if not presents:
                    continue
                if len(presents) > 1:
                    multiples.append((s["id"], parti, presents))
                p = presents[0]
                slug = slug_parti(parti)
                h["scores"][slug] = h["scores"].pop(p)
                h["candidats"] = [slug if c == p else c for c in h["candidats"]]
                h.setdefault("teste", {})[slug] = p
    return multiples


def somme_hors_bornes(h):
    t = sum(h["scores"].values()) + h.get("autres", 0)
    return not (95 <= t <= 105), round(t, 1)


def calculer_election(annee, election, derived, jusqu_au=None, declares=None):
    """Top TOP de chaque J-x. `jusqu_au` : dernier jour calculé (2027, scrutin
    à venir) ; `declares` : candidats.json, pour choisir l'hypothèse principale
    d'après les déclarations de candidature (aucune pour les élections passées)."""
    t1 = datetime.date.fromisoformat(election["tour1"])
    info = election["candidats"]
    couleurs = derived.get("candidats", {})
    regles = NON_DESIGNES.get(annee, [])

    sondages = json.loads(json.dumps(election["sondages"]))   # copie profonde
    multiples = rattacher_partis(sondages, regles)
    calculer_principale(sondages, declares or {})     # sans declare_le : plus de candidats, puis ordre de la page
    # Hypothèse principale seule : un candidat qui n'y figure pas n'a pas de
    # score dans ce sondage (pas de repli sur une autre hypothèse, qui mêlerait
    # des candidatures alternatives, Juppé ou Fillon à la place de Sarkozy en 2012).
    for s in sondages:
        s["hypotheses"] = [h for h in s["hypotheses"] if h["tour"] != 1 or h["principale"]]
    dernier = t1 - datetime.timedelta(days=1)
    if jusqu_au:
        dernier = min(dernier, jusqu_au)
    S = calculer_series(sondages, jusqu_au=dernier)

    principale = {s["id"]: next((h for h in s["hypotheses"] if h.get("principale")), None)
                  for s in sondages}
    dates_t1 = sorted((datetime.date.fromisoformat(s["terrain_fin"]), s["id"])
                      for s in sondages if principale[s["id"]])

    # Une entrée de parti s'efface au premier sondage postérieur à la désignation,
    # où la personne désignée prend le relais : pas de survie par la fenêtre
    # glissante, pas de doublon « Candidat LR » / Pécresse.
    releve = {}
    for parti, designation, _ in regles:
        apres = [d for d, _ in dates_t1 if d.isoformat() >= designation]
        releve[slug_parti(parti)] = min(apres) if apres else datetime.date.fromisoformat(designation)

    series = {c: {p["d"]: p["v"] for p in pts} for c, pts in S["series"].items()}
    n_fenetre = {p["d"]: p["n"] for p in S["demi_vies"]}

    def teste_a(slug, jour):
        """Personne testée : celle de l'hypothèse principale la plus récente."""
        for d, i in reversed(dates_t1):
            h = principale[i]
            if d <= jour and slug in h["scores"]:
                return h["teste"][slug]
        return None

    candidats_out = {}

    def declarer(cid):
        if cid in candidats_out:
            return
        if cid.startswith("candidat-") and cid[9:].upper() in {p for p, _, _ in regles}:
            parti = cid[9:].upper()
            candidats_out[cid] = {"nom": f"Candidat {parti}", "nom_court": f"Candidat {parti}",
                                  "couleur": PARTI_COUL.get(parti, "#8A8F98"), "type": "parti"}
            return
        ci = info.get(cid, {"nom": cid, "type": "personne", "partis": []})
        partis = ci.get("partis") or ["SE"]
        coul = couleurs.get(cid, {}).get("couleur") or PARTI_COUL.get(partis[0], "#8A8F98")
        candidats_out[cid] = {"nom": ci["nom"], "nom_court": nom_court(cid, ci),
                              "couleur": coul, "type": ci.get("type", "personne")}

    jours, anomalies_somme = {}, set()
    for x in range(J_MAX, 0, -1):
        jour = t1 - datetime.timedelta(days=x)
        if jour > dernier:
            continue      # jour à venir (2027)
        d = jour.isoformat()
        n = n_fenetre.get(d, 0)
        if n >= SEUIL_APPROX:
            valeurs = [(c, v[d]) for c, v in series.items() if v.get(d) is not None
                       and not (c in releve and jour >= releve[c])]
            teste = {c: teste_a(c, jour) for c, _ in valeurs if c in releve}
            source = None
        else:
            # Moins de 2 sondages dans la fenêtre : sondage le plus proche
            # (le plus ancien en cas d'égalité), hypothèse principale.
            _, sid = min(dates_t1, key=lambda di: (abs((di[0] - jour).days), di[0]))
            if jour < dates_t1[0][0]:
                continue  # avant le premier sondage (2027) : pas de valeur
            h = principale[sid]
            valeurs = list(h["scores"].items())
            teste = dict(h.get("teste", {}))
            source = sid
        valeurs.sort(key=lambda cv: (-cv[1], cv[0]))
        top = []
        for c, v in valeurs[:TOP]:
            declarer(c)
            e = {"id": c, "v": round(v, 1)}
            if c in teste:
                e["teste"] = teste[c]
            top.append(e)
        entree = {"date": d, "approx": source is not None, "top": top}
        if source:
            entree["sondage"] = source
        jours[str(x)] = entree

    # Contrôle de somme (§8, règle 1) sur les hypothèses principales de la période
    debut = (t1 - datetime.timedelta(days=J_MAX + 30)).isoformat()
    for s in sondages:
        h = principale[s["id"]]
        if h and debut <= s["terrain_fin"] < election["tour1"]:
            hors, t = somme_hors_bornes(h)
            if hors:
                anomalies_somme.add((s["id"], t))

    # Les personnes testées sous une entrée de parti sont aussi décrites
    for e in jours.values():
        for c in e["top"]:
            if "teste" in c:
                declarer(c["teste"])

    return {
        "premier_tour": election["tour1"],
        "source": {"url": election["url"], "revid": election["revid"]},
        "non_designes": [{"id": slug_parti(p), "designation": dd} for p, dd, _ in regles],
        "candidats": candidats_out,
        "jours": jours,
    }, multiples, sorted(anomalies_somme)


def election_2027():
    """Pseudo-élection 2027 (sondages et candidats de data/), pour calculer_election."""
    declares = json.loads(CANDIDATS_PATH.read_text())
    candidats, derived = {}, {}
    for cid, c in declares.items():
        nom = f"{c['prenom']} {c['nom']}" if c.get("prenom") else c["nom"]
        candidats[cid] = {"nom": nom, "type": c.get("type", "personne"), "partis": [c["parti"]]}
        derived[cid] = {"couleur": c.get("couleur")}
    election = {"tour1": TOUR1_2027.isoformat(), "url": "", "revid": None, "candidats": candidats,
                "sondages": json.loads(SONDAGES_PATH.read_text())}
    return election, {"candidats": derived}, declares


# ---------------------------------------------------------------------------
# Rendu du bloc
# ---------------------------------------------------------------------------

def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",")


def cellule(e, cands):
    c = cands[e["id"]]
    note = ""
    if c["type"] == "parti":
        p = cands[e["teste"]]["nom_court"] if e.get("teste") else None
        if p:
            accord = "testée" if e["teste"] in FEMININ else "testé"
            note = f"{html.escape(p)} {accord}"
    classe = "rs-cell rs-parti" if c["type"] == "parti" else "rs-cell"
    couleur = "" if c["type"] == "parti" else f";background:{c['couleur']}"
    return (f'<div class="{classe}">'
            f'<div class="rs-nom">{html.escape(c["nom_court"])}</div>'
            f'<div class="rs-score">{fmt_pct(e["v"])}<span class="pct"> %</span></div>'
            f'<div class="rs-bar-wrap"><div class="rs-bar" style="width:{{w}}%{couleur}"></div></div>'
            f'<div class="rs-note">{note or "&nbsp;"}</div>'
            f'</div>')


def rendre_bloc(retro, x):
    if not 1 <= x <= J_MAX:
        return ""
    colonnes = []
    for annee in ANNEES:
        el = retro["elections"][annee]
        top = el["jours"][str(x)]["top"]
        tete = top[0]["v"] if top else 1
        cells = "".join(cellule(e, el["candidats"]).replace("{w}", str(round(100 * e["v"] / tete)))
                        for e in top)
        colonnes.append(f'    <div class="rs-col"><div class="rs-annee">{annee}</div>{cells}</div>')
    return (f'<div class="bloc" id="retro-sondax">\n'
            f'  <h2>Rétro-Sondax</h2>\n'
            f'  <p class="subtitle">À J-{x} de la présidentielle, qui était en tête des sondages ?</p>\n'
            f'  <div class="rs-grille">\n' + "\n".join(colonnes) + '\n  </div>\n</div>')


def j_du_jour(aujourd_hui=None):
    """J-x du jour, borné au curseur de la page (J_MIN_PAGE à J_MAX)."""
    x = (TOUR1_2027 - (aujourd_hui or datetime.date.today())).days
    return max(J_MIN_PAGE, min(J_MAX, x))


def rendre_bloc_page(retro, x, aujourd_hui=None):
    """Rétro-Sondax de precedentes-elections.html : 2027 puis les cinq élections,
    au J-x du curseur. Même cellules que la home (cellule()) ; 2027 n'a pas de
    valeur pour les jours à venir. assets/bloc-retro.js recalcule la grille au
    déplacement du curseur, avec le même HTML (colonne())."""
    j_auj = (TOUR1_2027 - (aujourd_hui or datetime.date.today())).days
    colonnes = []
    for annee in ANNEES_PAGE:
        el = retro["elections"][annee]
        jour = el["jours"].get(str(x))
        if jour is None:
            msg = "Date à venir." if x < j_auj else "Aucun sondage à cette date."
            cells = f'<p class="rs-vide">{msg}</p>'
        else:
            tete = jour["top"][0]["v"] if jour["top"] else 1
            cells = "".join(cellule(e, el["candidats"]).replace("{w}", str(round(100 * e["v"] / tete)))
                            for e in jour["top"])
        classe = "rs-col rs-col-2027" if annee == "2027" else "rs-col"
        colonnes.append(f'    <div class="{classe}"><div class="rs-annee">{annee}</div>{cells}</div>')
    return (f'  <section class="carte" id="retro-sondax" data-slider data-annees="{",".join(ANNEES_PAGE)}" '
            f'data-jmin="{J_MIN_PAGE}" data-jmax="{J_MAX}">\n'
            f'    <h2>Rétro-Sondax</h2>\n'
            f'    <p class="subtitle rs-sous-titre">À J-{x}, où en était-on\u00a0?</p>\n'
            f'    <p class="rs-texte">Comparez les rapports de force au même moment de chaque campagne.</p>\n'
            f'    <div class="rs-curseur">\n'
            f'      <label for="rs-range">Jours avant le premier tour</label>\n'
            f'      <input type="range" id="rs-range" min="-{J_MAX}" max="-{J_MIN_PAGE}" step="1" value="-{x}" '
            f'aria-describedby="rs-bornes">\n'
            f'      <div class="rs-bornes" id="rs-bornes"><span>J-{J_MAX}</span><span>J-{J_MIN_PAGE}</span></div>\n'
            f'    </div>\n'
            f'    <div class="rs-grille rs-grille-page">\n' + "\n".join(colonnes) + '\n    </div>\n'
            f'  </section>')


def inject(content, html_bloc):
    i_begin = content.index(BEGIN)
    i_end = content.index(END) + len(END)
    return content[:i_begin] + BEGIN + "\n" + html_bloc + "\n" + END + content[i_end:]


def main():
    historique = json.loads(HISTORIQUE_PATH.read_text())["elections"]
    derived = json.loads(DERIVED_HISTORIQUE_PATH.read_text())

    retro = {"premier_tour_2027": TOUR1_2027.isoformat(), "elections": {}}
    for annee in ANNEES_PAGE:
        if annee == "2027":
            elec, derive27, declares = election_2027()
            el, multiples, sommes = calculer_election(annee, elec, derive27,
                                                      jusqu_au=datetime.date.today(), declares=declares)
        else:
            el, multiples, sommes = calculer_election(annee, historique[annee], derived.get(annee, {}))
        retro["elections"][annee] = el
        nb_approx = sum(1 for j in el["jours"].values() if j["approx"])
        print(f"{annee} : {len(el['jours'])} jours, {nb_approx} approx, "
              f"{len(multiples)} hypothèses à plusieurs personnes d'un parti, "
              f"{len(sommes)} sommes hors 95-105")
        for sid, parti, presents in sorted(set((i, p, tuple(pr)) for i, p, pr in multiples)):
            print(f"    plusieurs {parti} : {sid} {presents} → {presents[0]}")
        for sid, t in sommes:
            print(f"    somme {t} : {sid}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(retro, ensure_ascii=False, separators=(",", ":")) + "\n")

    x = (TOUR1_2027 - datetime.date.today()).days
    content = INDEX_PATH.read_text(encoding="utf-8")
    INDEX_PATH.write_text(inject(content, rendre_bloc(retro, x)), encoding="utf-8")
    print(f"Écrit : {OUTPUT_PATH} ; bloc J-{x} injecté dans index.html")


if __name__ == "__main__":
    main()
