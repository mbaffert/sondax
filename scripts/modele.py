#!/usr/bin/env python3
"""Moteur du modèle Sondax (SPEC §14.4 à §14.12).

« Et si on votait dimanche ? » : à partir de la moyenne Sondax du jour
(data/derived/series-t1.json), refait le premier tour `tirages` fois selon une
loi de Dirichlet de paramètre N_eff · p, et compte qualifications, rangs et
duels. Écrit data/derived/modele.json.

Historique : data/modele_history.json, versionné (§14.13). Options :
  --historiser    ajoute l'entrée du run à l'historique (run de collecte)
  --reconstituer  recalcule l'historique depuis le premier sondage de référence
"""

import collections, datetime, json, pathlib, sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
CONFIG_PATH = ROOT / "data" / "config.json"
OUTPUT_PATH = ROOT / "data" / "derived" / "modele.json"
HISTORY_PATH = ROOT / "data" / "modele_history.json"

CONFIG_REF = {"attal", "philippe"}      # configuration de référence (§4)
FENETRE_JOURS = 30                      # fenêtre de base de la moyenne (§4)
FENETRE_MIN_CANDIDAT = 3
FENETRE_MAX_JOURS = 90
EXCLUS = {"autre"}

HORIZONS = {"1j": 1, "7j": 7, "30j": 30}   # évolutions (§14.9)
SEUIL_VARIATION = 5                        # événement « gain / perte » (§14.10)
SEUIL_BASCULE_CHANGE = 1.0
BASCULE_CIBLE = 50.0                       # point de bascule (§14.7)
BASCULE_MAX_ECART = 10.0
BASCULE_TOLERANCE = 0.05
BASCULE_AFFICHAGE_MAX = 4.0
BASCULE_RANG_MAX = 4

# Verdicts (§14.8), sur la chance arrondie affichée : (minimum inclus, clé).
VERDICTS = [
    (91, "quasi_sur"),
    (60, "bien_place"),
    (25, "rien_nest_joue"),
    (8, "surprise"),
    (0, "tres_improbable"),
]


def _date(s):
    return datetime.date.fromisoformat(s)


# ---------------------------------------------------------------- moteur

def tirer(parts, n_eff, tirages, graine, k=None):
    """Tirages de Dirichlet(n · p), une ligne par premier tour simulé.
    `parts` : vecteur de parts (somme quelconque, renormalisé ici).

    Sans `k`, n = N_eff pour tous les tirages. Avec `k` (§14.6, mélange), n est
    tiré pour chaque premier tour selon une loi gamma de forme k telle que
    E[1/n] = 1/N_eff : l'ampleur moyenne des erreurs est celle qui a été
    calibrée, mais certaines élections se trompent plus que d'autres (queues
    plus épaisses)."""
    p = np.asarray(parts, dtype=float)
    p = p / p.sum()
    rng = np.random.default_rng(graine)
    if k is None:
        n = n_eff
    else:
        n = rng.gamma(shape=k, scale=n_eff / (k - 1), size=(tirages, 1))
    g = rng.gamma(shape=np.maximum(n * p, 1e-12), size=(tirages, len(p)))
    return g / g.sum(axis=1, keepdims=True)


def compter(x):
    """Comptes exacts à partir des tirages : premier, deuxième, duels.
    Égalité exacte : ordre des colonnes (tri stable)."""
    n, k = x.shape
    ordre = np.argsort(-x, axis=1, kind="stable")
    premier, second = ordre[:, 0], ordre[:, 1]
    r1 = np.bincount(premier, minlength=k)
    r2 = np.bincount(second, minlength=k)
    a, b = np.minimum(premier, second), np.maximum(premier, second)
    paires = np.bincount(a * k + b, minlength=k * k).reshape(k, k)
    duels = {(i, j): int(paires[i, j]) for i in range(k) for j in range(i + 1, k)
             if paires[i, j]}
    return {"tirages": n, "r1": r1.tolist(), "r2": r2.tolist(), "duels": duels}


def simuler(parts, n_eff, tirages, graine, k=None):
    return compter(tirer(parts, n_eff, tirages, graine, k))


def arrondi_chance(v):
    return int(round(v))


def verdict(chance_arrondie):
    for seuil, cle in VERDICTS:
        if chance_arrondie >= seuil:
            return cle


# ---------------------------------------------------------- données d'entrée

def sondages_par_candidat(sondages, jour):
    """Sondages (id, terrain_fin) portant chaque candidat dans sa fenêtre
    effective au jour donné : 30 jours, étendue jusqu'à 3 sondages dans la
    limite de 90 jours (§4)."""
    par_candidat = collections.defaultdict(list)
    for s in sondages:
        fin = _date(s["terrain_fin"])
        if fin > jour:
            continue
        cands = set()
        for h in s["hypotheses"]:
            if h["tour"] == 1:
                cands |= h["scores"].keys()
        for c in cands - EXCLUS:
            par_candidat[c].append((fin, s["id"]))
    fenetres = {}
    for c, liste in par_candidat.items():
        liste.sort(reverse=True)
        dans = [i for d, i in liste if (jour - d).days <= FENETRE_JOURS]
        if len(dans) < FENETRE_MIN_CANDIDAT:
            etendus = [i for d, i in liste if (jour - d).days <= FENETRE_MAX_JOURS]
            dans = etendus[:max(FENETRE_MIN_CANDIDAT, len(dans))]
        fenetres[c] = dans
    return fenetres


def configuration(sondages, jour):
    """Ensemble de candidats le plus fréquent parmi les hypothèses de référence
    (Attal et Philippe) des sondages de la fenêtre de base (§14.4). Égalité :
    celui de l'hypothèse la plus récente."""
    compte = collections.Counter()
    recence = {}
    for s in sondages:
        fin = _date(s["terrain_fin"])
        if not 0 <= (jour - fin).days <= FENETRE_JOURS:
            continue
        for h in s["hypotheses"]:
            if h["tour"] == 1 and CONFIG_REF <= h["scores"].keys():
                cle = frozenset(h["scores"].keys() - EXCLUS)
                compte[cle] += 1
                recence[cle] = max(recence.get(cle, fin), fin)
    if not compte:
        return None
    return max(compte, key=lambda c: (compte[c], recence[c]))


def valeur_du_jour(serie):
    """Dernier point de la série et sa valeur (None si courbe interrompue)."""
    if not serie:
        return None
    return serie[-1]["v"]


# ------------------------------------------------------------------- textes

def nom_court(candidats, slug):
    return candidats[slug]["nom"]


def libelle_duel(candidats, paire, ordre):
    """« Le Pen – Mélenchon » : le mieux placé en premier."""
    a, b = sorted(paire, key=lambda s: ordre.index(s))
    return f"{nom_court(candidats, a)} – {nom_court(candidats, b)}"



def formater_chance(v, suffixe="sur 100"):
    """« 38 chances sur 100 », « moins de 1 chance sur 100 », « plus de 99 … »."""
    if v < 0.5:
        return f"moins de 1 chance {suffixe}"
    if v > 99.5:
        return f"plus de 99 chances {suffixe}"
    n = arrondi_chance(v)
    return f"{n} chance{'s' if n > 1 else ''} {suffixe}"


def cle_duel(paire):
    return "+".join(sorted(paire))


# ------------------------------------------------------------ point de bascule

def point_de_bascule(normalisees, slug, n_eff, tirages, graine, k=None):
    """Part (échelle normalisée) qui donne environ 50 chances sur 100 au
    candidat, les autres rendant ou prenant la différence au prorata (§14.7).
    Retourne None si 50 n'est pas atteint à +10 points."""
    slugs = sorted(normalisees)
    i = slugs.index(slug)
    p0 = normalisees[slug]

    def chance(x):
        facteur = (100 - x) / (100 - p0)
        parts = [x if c == slug else normalisees[c] * facteur for c in slugs]
        c = simuler(parts, n_eff, tirages, graine, k)
        return 100 * (c["r1"][i] + c["r2"][i]) / tirages

    bas, haut = p0, min(p0 + BASCULE_MAX_ECART, 99.0)
    if chance(haut) < BASCULE_CIBLE:
        return None
    while haut - bas > BASCULE_TOLERANCE:
        milieu = (bas + haut) / 2
        if chance(milieu) < BASCULE_CIBLE:
            bas = milieu
        else:
            haut = milieu
    return (bas + haut) / 2


def bascule_affichee(delta):
    """Demi-point le plus proche, 0,5 minimum ; None au-delà de 4 points."""
    if delta is None or delta > BASCULE_AFFICHAGE_MAX:
        return None
    return max(0.5, round(delta * 2) / 2)


# ---------------------------------------------------------------- historique

def charger_historique():
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return []


def entree_historique(m, reconstitue=False):
    return {
        "date": m["date"],
        "reconstitue": reconstitue,
        "jour_moyenne": m["jour_moyenne"],
        "configuration": m["configuration"],
        "sondages_utilises": m["sondages_utilises"],
        "moyennes": {c: v["moyenne_normalisee"] for c, v in m["candidats"].items()},
        "qualification": {c: v["qualification_exacte"] for c, v in m["candidats"].items()},
        "rangs": {c: v["rang_exact"] for c, v in m["candidats"].items()},
        "duels": {cle_duel(d["candidats"]): d["chance_exacte"] for d in m["duels"]},
        "delta_bascule": {c: v["delta_bascule"] for c, v in m["candidats"].items()
                          if v.get("delta_bascule") is not None},
    }


def _jour(iso):
    return datetime.date.fromisoformat(iso[:10])


def entree_avant(historique, maintenant, jours):
    """Dernière entrée datée de J−jours ou avant."""
    limite = maintenant.date() - datetime.timedelta(days=jours)
    avant = [h for h in historique if _jour(h["date"]) <= limite]
    return avant[-1] if avant else None


def entree_precedente(historique, maintenant):
    avant = [h for h in historique if h["date"] < maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")]
    return avant[-1] if avant else None


def entres_depuis(m, entree):
    if entree is None:
        return []
    return sorted(set(m["sondages_utilises"]) - set(entree["sondages_utilises"]))


def ajouter_evolutions(m, historique, maintenant):
    refs = {h: entree_avant(historique, maintenant, j) for h, j in HORIZONS.items()}
    m["sondages_entres"] = {h: entres_depuis(m, e) if e else None for h, e in refs.items()}
    m["sondages_entres_7j"] = len(m["sondages_entres"]["7j"] or [])
    for c, v in m["candidats"].items():
        for h, e in refs.items():
            avant = e["qualification"].get(c) if e else None
            v[f"evolution_{h}"] = (arrondi_chance(v["qualification_exacte"] - avant)
                                   if avant is not None else None)
    for d in m["duels"]:
        for h, e in refs.items():
            avant = e["duels"].get(cle_duel(d["candidats"]), 0.0) if e else None
            d[f"evolution_{h}"] = (arrondi_chance(d["chance_exacte"] - avant)
                                   if avant is not None else None)
    return refs


# ------------------------------------------------------ événement du jour

def _ordre(qualif):
    return sorted(qualif, key=lambda c: -qualif[c])


def _duel_principal(duels):
    return max(duels, key=duels.get) if duels else None


def detecter(m, entree):
    """Première règle vérifiée entre `entree` (historique) et aujourd'hui (§14.10)."""
    q_av, q_ap = entree["qualification"], {c: v["qualification_exacte"]
                                           for c, v in m["candidats"].items()}
    d_av = entree["duels"]
    d_ap = {cle_duel(d["candidats"]): d["chance_exacte"] for d in m["duels"]}

    principal_av, principal_ap = _duel_principal(d_av), _duel_principal(d_ap)
    if principal_av and principal_av != principal_ap:
        return {"type": "duel_principal_change", "duel": principal_ap.split("+"),
                "duel_avant": principal_av.split("+"),
                "avant": round(d_av.get(principal_ap, 0.0), 2), "apres": d_ap[principal_ap]}

    o_av, o_ap = _ordre(q_av), _ordre(q_ap)
    if len(o_av) > 1 and o_av[1] != o_ap[1]:
        x, y = o_ap[1], o_av[1]
        return {"type": "deuxieme_change", "candidate": x, "depasse": y,
                "avant": round(q_av.get(x, 0.0), 2), "apres": q_ap[x],
                "autre_avant": round(q_av.get(y, 0.0), 2), "autre_apres": q_ap.get(y, 0.0)}

    ecarts = {c: q_ap[c] - q_av[c] for c in q_ap if c in q_av}
    if ecarts:
        c = max(ecarts, key=lambda k: abs(ecarts[k]))
        if abs(arrondi_chance(ecarts[c])) >= SEUIL_VARIATION:
            return {"type": "candidate_gain" if ecarts[c] > 0 else "candidate_loss",
                    "candidate": c, "avant": round(q_av[c], 2), "apres": q_ap[c],
                    "delta": arrondi_chance(ecarts[c])}

    changes = [c for c in ecarts if verdict(arrondi_chance(q_av[c])) != verdict(arrondi_chance(q_ap[c]))]
    if changes:
        c = max(changes, key=lambda k: abs(ecarts[k]))
        return {"type": "verdict_change", "candidate": c, "avant": round(q_av[c], 2),
                "apres": q_ap[c], "verdict": verdict(arrondi_chance(q_ap[c])),
                "delta": arrondi_chance(ecarts[c])}

    b_av = entree.get("delta_bascule", {})
    for c, v in m["candidats"].items():
        a, b = bascule_affichee(b_av.get(c)), bascule_affichee(v.get("delta_bascule"))
        if a is not None and b is not None and abs(a - b) >= SEUIL_BASCULE_CHANGE:
            return {"type": "bascule_change", "candidate": c, "avant": a, "apres": b}

    return {"type": "peu_de_changement"}


def changement(m, historique, maintenant, refs):
    precedente = entree_precedente(historique, maintenant)
    entres_maj = entres_depuis(m, precedente)
    entres_7j = m["sondages_entres"]["7j"]
    if precedente is None:
        return None
    if entres_maj:
        ev = detecter(m, precedente)
        ev.update(horizon="maj", sondages_declencheurs=entres_maj)
        return ev
    if refs["7j"] is not None and entres_7j:
        # Un ou deux sondages seulement : le texte les nomme (attribution), ce
        # qui reste honnête même sous le seuil des trois sondages du §14.9.
        ev = detecter(m, refs["7j"])
        ev.update(horizon="7j", sondages_declencheurs=entres_7j)
        return ev
    return {"type": "aucun_sondage", "horizon": "maj", "sondages_declencheurs": []}


# ------------------------------------------------------------------- accroche

def accroche(candidats, m, ref_7j=None):
    """Accroche (§14.11). Sans historique (ou sans trois sondages sur 7 jours),
    aucun mot ne suppose un changement."""
    qualif = {c: v["qualification_exacte"] for c, v in m["candidats"].items()}
    ordre = list(m["candidats"])
    q = [qualif[s] for s in ordre]
    deux, trois = ordre[1], ordre[2]
    duel = libelle_duel(candidats, m["duels"][0]["candidats"], ordre)
    semaine = ref_7j is not None
    if ref_7j is not None:
        q7 = ref_7j["qualification"]
        o7 = sorted(q7, key=lambda c: -q7[c])
        principal_7j = _duel_principal(ref_7j["duels"])

    if q[1] >= 80 and q[2] < 20:
        deja = ref_7j is not None and len(o7) > 2 and q7[o7[1]] >= 80 and q7[o7[2]] < 20
        return {
            "regle": "dessine",
            "titre": "Le second tour se stabilise." if deja else "Le second tour semble se dessiner.",
            "detail": f"{duel} est aujourd’hui le second tour le plus plausible : "
                      f"les deux premiers ont une nette avance sur leurs poursuivants.",
        }
    if q[1] - q[2] < 15:
        resserre = (semaine and len(o7) > 2
                    and (q7[o7[1]] - q7[o7[2]]) - (q[1] - q[2]) >= 5)
        return {
            "regle": "serree",
            "titre": ("La course à la deuxième place se resserre." if resserre
                      else "La course à la deuxième place est serrée."),
            "detail": f"{nom_court(candidats, deux)} et {nom_court(candidats, trois)} "
                      f"ont {'désormais ' if resserre else ''}des chances très proches "
                      f"d’être au second tour.",
        }
    reste = ref_7j is not None and principal_7j == cle_duel(m["duels"][0]["candidats"])
    detail = f"{nom_court(candidats, trois)} a {formater_chance(q[2])} d’y être"
    if semaine and trois in q7 and abs(arrondi_chance(q[2] - q7[trois])) >= 2:
        detail += f", contre {arrondi_chance(q7[trois])} il y a une semaine"
    return {
        "regle": "general",
        "titre": f"{duel} {'reste' if reste else 'est'} aujourd’hui le second tour le plus plausible.",
        "detail": detail + ".",
    }


# ------------------------------------------------------------------- calcul

def calculer(series, sondages, candidats, reglages, maintenant=None,
             historique=None, bascule=True):
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    historique = historique or []
    jour = _date(series["date_fin"])
    config = configuration(sondages, jour)
    if config is None:
        raise SystemExit("modele : aucune hypothèse de référence dans la fenêtre")

    moyennes, ecartes = {}, []
    for c in sorted(config):
        v = valeur_du_jour(series["series"].get(c))
        if v is None:
            ecartes.append(c)
        else:
            moyennes[c] = v
    slugs = sorted(moyennes)
    total = sum(moyennes.values())
    normalisees = {c: 100 * moyennes[c] / total for c in slugs}

    n_eff, tirages, graine = reglages["N_eff"], reglages["tirages"], reglages["graine"]
    k = reglages.get("k_melange")
    comptes = simuler([normalisees[c] for c in slugs], n_eff, tirages, graine, k)

    fenetres = sondages_par_candidat(sondages, jour)
    utilises = sorted({i for c in slugs for i in fenetres.get(c, [])})

    res_cand, qualif = {}, {}
    for i, c in enumerate(slugs):
        r1 = 100 * comptes["r1"][i] / tirages
        r2 = 100 * comptes["r2"][i] / tirages
        q = r1 + r2
        qualif[c] = q
        res_cand[c] = {
            "moyenne": round(moyennes[c], 2),
            "moyenne_normalisee": round(normalisees[c], 2),
            "qualification": arrondi_chance(q),
            "qualification_exacte": round(q, 2),
            "verdict": verdict(arrondi_chance(q)),
            "rang": {"1": arrondi_chance(r1), "2": arrondi_chance(r2),
                     "3plus": arrondi_chance(100 - q)},
            "rang_exact": {"1": round(r1, 2), "2": round(r2, 2),
                           "3plus": round(100 - q, 2)},
            "seuil_bascule": None,
            "delta_bascule": None,
        }
    ordre = sorted(slugs, key=lambda c: (-qualif[c], -moyennes[c], c))
    res_cand = {c: res_cand[c] for c in ordre}

    if bascule:
        for c in ordre[:BASCULE_RANG_MAX]:
            if qualif[c] >= BASCULE_CIBLE:
                continue
            seuil = point_de_bascule(normalisees, c, n_eff, tirages, graine, k)
            if seuil is not None:
                res_cand[c]["seuil_bascule"] = round(seuil, 1)
                res_cand[c]["delta_bascule"] = round(seuil - normalisees[c], 1)

    duels = sorted(
        ({"candidats": [slugs[i], slugs[j]], "chance": arrondi_chance(100 * n / tirages),
          "chance_exacte": round(100 * n / tirages, 2)}
         for (i, j), n in comptes["duels"].items()),
        key=lambda d: (-d["chance_exacte"], d["candidats"]))

    m = {
        "date": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jour_moyenne": series["date_fin"],
        "revid": derniere_revid(sondages),
        "configuration": slugs,
        "ecartes": ecartes,
        "n_sondages": len(utilises),
        "sondages_utilises": utilises,
        "N_eff": n_eff,
        "N_eff_source": reglages.get("N_eff_source"),
        "k_melange": k,
        "tirages": tirages,
        "graine": graine,
        "comptes": {"r1": dict(zip(slugs, comptes["r1"])),
                    "r2": dict(zip(slugs, comptes["r2"])),
                    "duels": {f"{slugs[i]}+{slugs[j]}": n
                              for (i, j), n in comptes["duels"].items()}},
        "candidats": res_cand,
        "duels": duels,
    }
    refs = ajouter_evolutions(m, historique, maintenant)
    m["changement"] = changement(m, historique, maintenant, refs)
    m["accroche"] = accroche(candidats, m, refs["7j"])
    return m


def derniere_revid(sondages):
    revids = [s.get("revid") for s in sondages if s.get("revid")]
    return max(revids) if revids else None


def charger():
    """Données d'entrée. La série est recalculée ici, avec les hypothèses
    principales posées par principale.py, exactement comme au déploiement :
    la collecte (qui ne lance pas principale.py) et le déploiement
    obtiennent ainsi les mêmes chiffres."""
    import principale
    from series import calculer_series
    sondages = json.loads(SONDAGES_PATH.read_text())
    candidats = json.loads(CANDIDATS_PATH.read_text())
    principale.calculer(sondages, candidats)
    series = calculer_series(sondages, candidats)
    reglages = json.loads(CONFIG_PATH.read_text())["modele"]
    return series, sondages, candidats, reglages


def ecrire_historique(historique):
    HISTORY_PATH.write_text(json.dumps(historique, ensure_ascii=False, indent=1) + "\n")


def reconstituer(sondages, candidats, reglages):
    """Une entrée par jour de fin de terrain depuis le premier sondage de
    référence, avec les sondages dont terrain_fin ≤ ce jour (§14.13)."""
    import principale
    from series import calculer_series
    principale.calculer(sondages, candidats)
    jours = sorted({s["terrain_fin"] for s in sondages})
    historique = []
    for j in jours:
        connus = [s for s in sondages if s["terrain_fin"] <= j]
        series = calculer_series(connus, candidats)
        if configuration(connus, _date(j)) is None:
            continue
        instant = datetime.datetime.fromisoformat(j + "T18:00:00+00:00")
        m = calculer(series, connus, candidats, reglages, instant, historique)
        historique.append(entree_historique(m, reconstitue=True))
        print(f"  {j}  {len(m['sondages_utilises'])} sondages")
    return historique


def main():
    series, sondages, candidats, reglages = charger()
    if "--reconstituer" in sys.argv:
        historique = reconstituer(sondages, candidats, reglages)
        ecrire_historique(historique)
        print(f"{len(historique)} entrées reconstituées dans {HISTORY_PATH}")
        return

    historique = charger_historique()
    resultat = calculer(series, sondages, candidats, reglages, historique=historique)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(resultat, ensure_ascii=False, indent=1) + "\n")
    if "--historiser" in sys.argv:
        import veille
        if veille.en_veille():
            print("Veille électorale (loi de 1977) : aucune entrée ajoutée à l'historique")
        else:
            historique.append(entree_historique(resultat))
            ecrire_historique(historique)

    print(f"Modèle au {resultat['jour_moyenne']} : {len(resultat['configuration'])} "
          f"candidats, {resultat['n_sondages']} sondages, N_eff {resultat['N_eff']}")
    for c, v in resultat["candidats"].items():
        b = f"  bascule +{v['delta_bascule']}" if v["delta_bascule"] is not None else ""
        print(f"  {c:15} {v['moyenne_normalisee']:5.1f} %  → {v['qualification_exacte']:6.2f} "
              f"sur 100  7j {v['evolution_7j']}  ({v['verdict']}){b}")
    for d in resultat["duels"][:4]:
        print(f"  {'+'.join(d['candidats']):28} {d['chance_exacte']:6.2f}  7j {d['evolution_7j']}")
    if resultat["ecartes"]:
        print(f"  écartés (courbe interrompue) : {', '.join(resultat['ecartes'])}",
              file=sys.stderr)
    print(f"  {resultat['accroche']['titre']} {resultat['accroche']['detail']}")
    print(f"  changement : {resultat['changement']}")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
