#!/usr/bin/env python3
"""Moteur du modèle Sondax (SPEC §14.4 à §14.12).

« Et si on votait dimanche ? » : à partir de la moyenne Sondax du jour
(data/derived/series-t1.json), refait le premier tour `tirages` fois selon une
loi de Dirichlet de paramètre N_eff · p, et compte qualifications, rangs et
duels. Écrit data/derived/modele.json.

Phase A : ni évolutions, ni point de bascule, ni historique.
"""

import collections, datetime, json, pathlib, sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERIES_PATH = ROOT / "data" / "derived" / "series-t1.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
CONFIG_PATH = ROOT / "data" / "config.json"
OUTPUT_PATH = ROOT / "data" / "derived" / "modele.json"

CONFIG_REF = {"attal", "philippe"}      # configuration de référence (§4)
FENETRE_JOURS = 30                      # fenêtre de base de la moyenne (§4)
FENETRE_MIN_CANDIDAT = 3
FENETRE_MAX_JOURS = 90
EXCLUS = {"autre"}

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

def tirer(parts, n_eff, tirages, graine):
    """Tirages de Dirichlet(N_eff · p), une ligne par premier tour simulé.
    `parts` : vecteur de parts (somme quelconque, renormalisé ici)."""
    p = np.asarray(parts, dtype=float)
    p = p / p.sum()
    rng = np.random.default_rng(graine)
    g = rng.gamma(shape=n_eff * p, size=(tirages, len(p)))
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


def simuler(parts, n_eff, tirages, graine):
    return compter(tirer(parts, n_eff, tirages, graine))


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


def accroche(candidats, qualif, duels, ordre):
    """Accroche de phase A (§14.11) : aucun mot qui suppose un changement."""
    q = [qualif[s] for s in ordre]
    un, deux, trois = ordre[:3]
    duel = libelle_duel(candidats, duels[0]["candidats"], ordre)
    if q[1] >= 80 and q[2] < 20:
        return {
            "regle": "dessine",
            "titre": "Le second tour semble se dessiner.",
            "detail": f"{duel} est aujourd'hui le second tour le plus plausible : "
                      f"les deux premiers ont une nette avance sur leurs poursuivants.",
        }
    if q[1] - q[2] < 15:
        return {
            "regle": "serree",
            "titre": "La course à la deuxième place est serrée.",
            "detail": f"{nom_court(candidats, deux)} et {nom_court(candidats, trois)} "
                      f"ont des chances très proches d'être au second tour.",
        }
    return {
        "regle": "general",
        "titre": f"{duel} est aujourd'hui le second tour le plus plausible.",
        "detail": f"{nom_court(candidats, trois)} a {formater_chance(q[2])} "
                  f"d'y être.",
    }


def formater_chance(v, suffixe="sur 100"):
    """« 38 chances sur 100 », « moins de 1 chance sur 100 », « plus de 99 … »."""
    if v < 0.5:
        return f"moins de 1 chance {suffixe}"
    if v > 99.5:
        return f"plus de 99 chances {suffixe}"
    n = arrondi_chance(v)
    return f"{n} chance{'s' if n > 1 else ''} {suffixe}"


# ------------------------------------------------------------------- calcul

def calculer(series, sondages, candidats, reglages, maintenant=None):
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
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
    comptes = simuler([normalisees[c] for c in slugs], n_eff, tirages, graine)

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
        }
    ordre = sorted(slugs, key=lambda c: (-qualif[c], -moyennes[c], c))
    res_cand = {c: res_cand[c] for c in ordre}

    duels = sorted(
        ({"candidats": [slugs[i], slugs[j]], "chance": arrondi_chance(100 * n / tirages),
          "chance_exacte": round(100 * n / tirages, 2)}
         for (i, j), n in comptes["duels"].items()),
        key=lambda d: (-d["chance_exacte"], d["candidats"]))

    return {
        "date": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jour_moyenne": series["date_fin"],
        "revid": derniere_revid(sondages),
        "configuration": slugs,
        "ecartes": ecartes,
        "n_sondages": len(utilises),
        "sondages_utilises": utilises,
        "N_eff": n_eff,
        "N_eff_source": reglages.get("N_eff_source"),
        "tirages": tirages,
        "graine": graine,
        "comptes": {"r1": dict(zip(slugs, comptes["r1"])),
                    "r2": dict(zip(slugs, comptes["r2"])),
                    "duels": {f"{slugs[i]}+{slugs[j]}": n
                              for (i, j), n in comptes["duels"].items()}},
        "candidats": res_cand,
        "duels": duels,
        "accroche": accroche(candidats, qualif, duels, ordre),
    }


def derniere_revid(sondages):
    revids = [s.get("revid") for s in sondages if s.get("revid")]
    return max(revids) if revids else None


def charger():
    series = json.loads(SERIES_PATH.read_text())
    sondages = json.loads(SONDAGES_PATH.read_text())
    candidats = json.loads(CANDIDATS_PATH.read_text())
    reglages = json.loads(CONFIG_PATH.read_text())["modele"]
    return series, sondages, candidats, reglages


def main():
    resultat = calculer(*charger())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(resultat, ensure_ascii=False, indent=1) + "\n")
    print(f"Modèle au {resultat['jour_moyenne']} : {len(resultat['configuration'])} "
          f"candidats, {resultat['n_sondages']} sondages, N_eff {resultat['N_eff']}")
    for c, v in resultat["candidats"].items():
        print(f"  {c:15} {v['moyenne_normalisee']:5.1f} %  → {v['qualification_exacte']:6.2f} "
              f"sur 100  ({v['verdict']})")
    for d in resultat["duels"][:4]:
        print(f"  {'+'.join(d['candidats']):28} {d['chance_exacte']:6.2f}")
    if resultat["ecartes"]:
        print(f"  écartés (courbe interrompue) : {', '.join(resultat['ecartes'])}",
              file=sys.stderr)
    print(f"  {resultat['accroche']['titre']} {resultat['accroche']['detail']}")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
