"""Résultats officiels des présidentielles 2002 à 2022, figés dans deux JSON.

Script à lancer à la main, une fois : ces résultats ne bougent plus. Il n'est
pas dans la collecte quotidienne.

    pip install -r requirements-resultats.txt
    python scripts/collecte_resultats.py
    python scripts/collecte_resultats.py --cache /tmp/elections   # garde les Parquet

Source : « Données des élections agrégées », data.gouv.fr (jeu
6481e741d4cf002ec0efec9d), Ministère de l'Intérieur, Licence Ouverte. Deux
fichiers Parquet au bureau de vote, ~220 Mo à eux deux.

Écrit :
- data/resultats.json              : national, une entrée par année
- data/resultats-departements.json : même structure par département (pas
  encore affiché ; prévu pour une carte)

Agrégation : somme des effectifs bruts des bureaux de vote, jamais moyenne de
ratios. Aucun code_departement n'est écarté : outre-mer, collectivités
d'outre-mer et Français de l'étranger font partie du total national.
Pourcentages recalculés sur les sommes, arrondis à deux décimales.

Blancs et nuls : avant 2017, la colonne `blancs` est vide et `nuls` contient le
total blancs + nuls (distinction de la loi du 21 février 2014, appliquée à la
présidentielle à partir de 2017). On écrit alors `blancs_et_nuls` et on laisse
`blancs` et `nuls` à null, jamais à 0. À partir de 2017, l'inverse.

Contrôles bloquants (rien n'est écrit si l'un échoue) :
- somme des voix des candidats = exprimés
- votants = exprimés + blancs + nuls (ou + blancs_et_nuls)
- inscrits = votants + abstentions
- exactement 2 candidats au second tour
- score du second tour de chaque finaliste = celui de data/historique.json,
  affiché sur precedentes-elections.html et dans le chapeau des pages
"""

import argparse
import json
import pathlib
import sys
import tempfile
import unicodedata
import urllib.request
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

ROOT = pathlib.Path(__file__).resolve().parent.parent
SORTIE_NATIONAL = ROOT / "data" / "resultats.json"
SORTIE_DEPARTEMENTS = ROOT / "data" / "resultats-departements.json"
HISTORIQUE = ROOT / "data" / "historique.json"

BASE_URL = "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/elections/"
FICHIERS = ["general_results.parquet", "candidats_results.parquet"]

ANNEES = ["2002", "2007", "2012", "2017", "2022"]
ELECTIONS = [f"{a}_pres_t{t}" for a in ANNEES for t in (1, 2)]
# Blancs comptés à part à la présidentielle à partir de 2017.
PREMIERE_ANNEE_BLANCS = 2017
# Écart toléré avec les scores de second tour déjà publiés (arrondis au centième).
TOLERANCE_T2 = 0.015

COLS_GENERAL = ["id_election", "code_departement", "libelle_departement",
                "inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes"]
COLS_CANDIDATS = ["id_election", "code_departement", "nom", "prenom", "voix"]
EFFECTIFS = ["inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes"]


def cle(nom, prenom):
    """Clé de correspondance : capitales sans accents, espaces normalisés.
    "LE PEN|JEAN-MARIE", "MELENCHON|JEAN-LUC", "DE VILLIERS|PHILIPPE"."""
    def norm(s):
        s = unicodedata.normalize("NFKD", s or "")
        s = "".join(c for c in s if not unicodedata.combining(c))
        return " ".join(s.replace("’", "'").upper().split())
    return f"{norm(nom)}|{norm(prenom)}"


# Nom d'affichage de chaque candidat, écrit à la main : 61 candidatures,
# 42 personnes, sur cinq élections. Un nom absent de la table arrête le script.
NOMS = {
    # 2002
    "CHIRAC|JACQUES": "Jacques Chirac",
    "LE PEN|JEAN-MARIE": "Jean-Marie Le Pen",
    "JOSPIN|LIONEL": "Lionel Jospin",
    "BAYROU|FRANCOIS": "François Bayrou",
    "LAGUILLER|ARLETTE": "Arlette Laguiller",
    "CHEVENEMENT|JEAN-PIERRE": "Jean-Pierre Chevènement",
    "MAMERE|NOEL": "Noël Mamère",
    "BESANCENOT|OLIVIER": "Olivier Besancenot",
    "SAINT-JOSSE|JEAN": "Jean Saint-Josse",
    "MADELIN|ALAIN": "Alain Madelin",
    "HUE|ROBERT": "Robert Hue",
    "MEGRET|BRUNO": "Bruno Mégret",
    "TAUBIRA|CHRISTIANE": "Christiane Taubira",
    "LEPAGE|CORINNE": "Corinne Lepage",
    "BOUTIN|CHRISTINE": "Christine Boutin",
    "GLUCKSTEIN|DANIEL": "Daniel Gluckstein",
    # 2007
    "SARKOZY|NICOLAS": "Nicolas Sarkozy",
    "ROYAL|SEGOLENE": "Ségolène Royal",
    "DE VILLIERS|PHILIPPE": "Philippe de Villiers",
    "VILLIERS|PHILIPPE DE": "Philippe de Villiers",
    "BUFFET|MARIE-GEORGE": "Marie-George Buffet",
    "VOYNET|DOMINIQUE": "Dominique Voynet",
    "BOVE|JOSE": "José Bové",
    "NIHOUS|FREDERIC": "Frédéric Nihous",
    "SCHIVARDI|GERARD": "Gérard Schivardi",
    # 2012
    "HOLLANDE|FRANCOIS": "François Hollande",
    "LE PEN|MARINE": "Marine Le Pen",
    "MELENCHON|JEAN-LUC": "Jean-Luc Mélenchon",
    "JOLY|EVA": "Eva Joly",
    "DUPONT-AIGNAN|NICOLAS": "Nicolas Dupont-Aignan",
    "POUTOU|PHILIPPE": "Philippe Poutou",
    "ARTHAUD|NATHALIE": "Nathalie Arthaud",
    "CHEMINADE|JACQUES": "Jacques Cheminade",
    # 2017
    "MACRON|EMMANUEL": "Emmanuel Macron",
    "FILLON|FRANCOIS": "François Fillon",
    "HAMON|BENOIT": "Benoît Hamon",
    "LASSALLE|JEAN": "Jean Lassalle",
    "ASSELINEAU|FRANCOIS": "François Asselineau",
    # 2022
    "ZEMMOUR|ERIC": "Éric Zemmour",
    "PECRESSE|VALERIE": "Valérie Pécresse",
    "JADOT|YANNICK": "Yannick Jadot",
    "ROUSSEL|FABIEN": "Fabien Roussel",
    "HIDALGO|ANNE": "Anne Hidalgo",
}

# Finalistes, pour le contrôle contre data/historique.json (identifiants du site).
IDS_SITE = {
    "Jacques Chirac": "chirac", "Jean-Marie Le Pen": "le-pen-jean-marie",
    "Nicolas Sarkozy": "sarkozy", "Ségolène Royal": "royal",
    "François Hollande": "hollande", "Emmanuel Macron": "macron",
    "Marine Le Pen": "le-pen",
}


class ControleEchoue(Exception):
    pass


def pct(voix, base):
    """Pourcentage arrondi au centième, demi vers le haut (pas d'arrondi bancaire)."""
    if not base:
        return None
    q = Decimal(voix) * 100 / Decimal(base)
    return float(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def telecharger(dossier):
    chemins = {}
    for nom in FICHIERS:
        chemin = dossier / nom
        if chemin.exists() and chemin.stat().st_size > 0:
            print(f"  {nom} : déjà présent ({chemin.stat().st_size / 1e6:.0f} Mo)")
        else:
            print(f"  {nom} : téléchargement…", flush=True)
            tmp = chemin.with_suffix(".part")
            with urllib.request.urlopen(BASE_URL + nom, timeout=120) as r, open(tmp, "wb") as f:
                while bloc := r.read(1 << 20):
                    f.write(bloc)
            tmp.rename(chemin)
            print(f"  {nom} : {chemin.stat().st_size / 1e6:.0f} Mo")
        chemins[nom] = chemin
    return chemins


def lire(chemin, colonnes):
    """Lignes des dix scrutins, colonnes demandées, en liste de dicts par colonne."""
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    import pyarrow as pa
    table = pq.read_table(chemin, columns=colonnes,
                          filters=[("id_election", "in", ELECTIONS)])
    # Codes en texte quel que soit le type stocké (2A, 2B, ZZ…).
    for col in ("id_election", "code_departement", "libelle_departement", "nom", "prenom"):
        if col in table.column_names and table.schema.field(col).type != pa.string():
            i = table.column_names.index(col)
            table = table.set_column(i, col, pc.cast(table[col], pa.string()))
    return table.to_pydict()


def entier(v):
    """Effectif d'un bureau : None reste None (colonne vide), sinon entier."""
    if v is None:
        return None
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        if v != int(v):
            raise ControleEchoue(f"effectif non entier : {v}")
    return int(v)


def agreger_general(d):
    """{(id_election, code_dep): {effectif: somme ou None si toujours vide}}."""
    tot = defaultdict(lambda: {k: None for k in EFFECTIFS})
    libelles = {}
    n = len(d["id_election"])
    for i in range(n):
        dep = (d["code_departement"][i] or "").strip()
        k = (d["id_election"][i], dep)
        libelles.setdefault(dep, d["libelle_departement"][i])
        t = tot[k]
        for col in EFFECTIFS:
            v = entier(d[col][i])
            if v is not None:
                t[col] = (t[col] or 0) + v
    return tot, libelles


def agreger_candidats(d):
    """{(id_election, code_dep): {nom affiché: voix}} ; arrête sur un nom inconnu."""
    tot = defaultdict(lambda: defaultdict(int))
    inconnus = set()
    for i in range(len(d["id_election"])):
        dep = (d["code_departement"][i] or "").strip()
        brut = (d["nom"][i], d["prenom"][i])
        nom = NOMS.get(cle(*brut))
        if nom is None:
            inconnus.add((d["id_election"][i], *brut))
            continue
        tot[(d["id_election"][i], dep)][nom] += entier(d["voix"][i]) or 0
    if inconnus:
        lignes = "\n".join(f"    {e} : nom={n!r} prenom={p!r} (clé {cle(n, p)})"
                           for e, n, p in sorted(inconnus, key=str))
        raise ControleEchoue("noms de candidats absents de la table NOMS :\n" + lignes)
    return tot


def scrutin(annee, gen, voix, contexte):
    """Bloc t1/t2 au format de data/resultats.json, contrôles d'équilibre compris."""
    if gen["inscrits"] is None or gen["votants"] is None or gen["exprimes"] is None:
        raise ControleEchoue(f"{contexte} : inscrits, votants ou exprimés vides")
    ancien = int(annee) < PREMIERE_ANNEE_BLANCS
    if ancien:
        if gen["blancs"]:
            raise ControleEchoue(f"{contexte} : colonne blancs renseignée avant 2017 ({gen['blancs']})")
        blancs, nuls, bn = None, None, gen["nuls"]
        if bn is None:
            raise ControleEchoue(f"{contexte} : blancs et nuls (colonne nuls) vide")
    else:
        blancs, nuls, bn = gen["blancs"], gen["nuls"], None
        if blancs is None or nuls is None:
            raise ControleEchoue(f"{contexte} : blancs ou nuls vide après 2017")
    abstentions = gen["abstentions"]
    if abstentions is None:
        raise ControleEchoue(f"{contexte} : abstentions vide")

    somme = sum(voix.values())
    if somme != gen["exprimes"]:
        raise ControleEchoue(f"{contexte} : somme des voix {somme} ≠ exprimés {gen['exprimes']} "
                             f"(écart {somme - gen['exprimes']})")
    non_exprimes = bn if ancien else blancs + nuls
    if gen["votants"] != gen["exprimes"] + non_exprimes:
        raise ControleEchoue(f"{contexte} : votants {gen['votants']} ≠ exprimés {gen['exprimes']} "
                             f"+ {'blancs et nuls' if ancien else 'blancs + nuls'} {non_exprimes}")
    if gen["inscrits"] != gen["votants"] + abstentions:
        raise ControleEchoue(f"{contexte} : inscrits {gen['inscrits']} ≠ votants {gen['votants']} "
                             f"+ abstentions {abstentions}")

    candidats = [
        {"nom": nom, "voix": v,
         "pct_exprimes": pct(v, gen["exprimes"]),
         "pct_inscrits": pct(v, gen["inscrits"])}
        for nom, v in sorted(voix.items(), key=lambda x: (-x[1], x[0]))
    ]
    return {
        "inscrits": gen["inscrits"],
        "votants": gen["votants"],
        "abstentions": abstentions,
        "blancs": blancs,
        "nuls": nuls,
        "blancs_et_nuls": bn,
        "exprimes": gen["exprimes"],
        "candidats": candidats,
    }


def construire(general, candidats, historique):
    tot_gen, libelles = agreger_general(general)
    tot_voix = agreger_candidats(candidats)

    # National : somme de tous les départements, sans exception.
    nat_gen = defaultdict(lambda: {k: None for k in EFFECTIFS})
    nat_voix = defaultdict(lambda: defaultdict(int))
    for (eid, _), t in tot_gen.items():
        for col, v in t.items():
            if v is not None:
                nat_gen[eid][col] = (nat_gen[eid][col] or 0) + v
    for (eid, _), vs in tot_voix.items():
        for nom, v in vs.items():
            nat_voix[eid][nom] += v

    manquants = [e for e in ELECTIONS if e not in nat_gen or e not in nat_voix]
    if manquants:
        raise ControleEchoue(f"scrutins absents des fichiers : {', '.join(manquants)}")

    national, departements = {}, {}
    for annee in ANNEES:
        h = historique[annee]
        national[annee] = {"date_t1": h["tour1"], "date_t2": h["tour2"]}
        for t in ("t1", "t2"):
            eid = f"{annee}_pres_{t}"
            national[annee][t] = scrutin(annee, nat_gen[eid], nat_voix[eid], eid)

        t2 = national[annee]["t2"]["candidats"]
        if len(t2) != 2:
            raise ControleEchoue(f"{annee}_pres_t2 : {len(t2)} candidats au lieu de 2")
        publies = h["resultats"]["tour2"]
        for c in t2:
            cid = IDS_SITE.get(c["nom"])
            if cid not in publies:
                raise ControleEchoue(f"{annee}_pres_t2 : {c['nom']} absent des résultats publiés")
            if abs(c["pct_exprimes"] - publies[cid]) > TOLERANCE_T2:
                raise ControleEchoue(f"{annee}_pres_t2 : {c['nom']} {c['pct_exprimes']} % "
                                     f"≠ {publies[cid]} % publié sur le site")

        # Départements : mêmes contrôles d'équilibre, au département.
        deps = {}
        for dep in sorted({d for (e, d) in tot_gen if e.startswith(annee + "_")}):
            entree = {"libelle": libelles.get(dep)}
            for t in ("t1", "t2"):
                eid = f"{annee}_pres_{t}"
                if (eid, dep) not in tot_gen:
                    continue
                entree[t] = scrutin(annee, tot_gen[(eid, dep)],
                                    tot_voix.get((eid, dep), {}), f"{eid} département {dep}")
            deps[dep] = entree
        departements[annee] = {"date_t1": h["tour1"], "date_t2": h["tour2"], "departements": deps}

    return national, departements


def resume(national):
    for annee, e in national.items():
        for t in ("t1", "t2"):
            s = e[t]
            tete = ", ".join(f"{c['nom']} {c['pct_exprimes']}" for c in s["candidats"][:3])
            print(f"  {annee} {t} : {len(s['candidats'])} candidats, {s['exprimes']:,} exprimés · {tete}")


def ecrire(chemin, donnees):
    texte = json.dumps(donnees, ensure_ascii=False, indent=1) + "\n"
    chemin.write_text(texte, encoding="utf-8")
    print(f"  {chemin.relative_to(ROOT)} écrit ({len(texte) / 1e3:.0f} ko)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", type=pathlib.Path,
                        help="dossier où garder les Parquet entre deux exécutions")
    args = parser.parse_args()

    historique = json.loads(HISTORIQUE.read_text(encoding="utf-8"))["elections"]

    with tempfile.TemporaryDirectory() as tmp:
        dossier = args.cache or pathlib.Path(tmp)
        dossier.mkdir(parents=True, exist_ok=True)
        print("Téléchargement")
        chemins = telecharger(dossier)
        print("Lecture et agrégation")
        general = lire(chemins["general_results.parquet"], COLS_GENERAL)
        candidats = lire(chemins["candidats_results.parquet"], COLS_CANDIDATS)
        print(f"  {len(general['id_election']):,} bureaux, "
              f"{len(candidats['id_election']):,} lignes candidat")

    try:
        national, departements = construire(general, candidats, historique)
    except ControleEchoue as e:
        print(f"\nContrôle échoué, rien n'est écrit : {e}", file=sys.stderr)
        sys.exit(1)

    print("Contrôles passés")
    resume(national)
    ecrire(SORTIE_NATIONAL, national)
    ecrire(SORTIE_DEPARTEMENTS, departements)


if __name__ == "__main__":
    main()
