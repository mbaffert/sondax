"""Candidats « interchangeables » : même parti, presque jamais testés ensemble.

Avant qu'un camp ait désigné son candidat, les instituts posent plusieurs
hypothèses de premier tour : une avec Juppé, une avec Fillon, une avec
Sarkozy… Chaque courbe vient de son propre scénario, si bien qu'à une date
donnée les scores de ces candidats ne s'additionnent pas. Ce module repère ces
groupes pour que l'infobulle des graphiques les présente comme des
alternatives (« LR, selon le candidat : Juppé · ou Fillon · ou Sarkozy »).

Deux candidats du même parti sont des alternatives quand ils figurent
ensemble dans au plus SEUIL_COEXISTENCE des hypothèses du moins testé des
deux. Au-delà, ce sont des candidatures concurrentes réellement mesurées côte
à côte (Sarkozy et Borloo en 2012, Retailleau et Lisnard en 2027) et ils ne
sont pas regroupés.
"""

import itertools
from collections import Counter

SEUIL_COEXISTENCE = 0.25
MIN_HYPOTHESES = 2
SANS_PARTI = {None, "", "SE", "DIV"}  # sans étiquette : aucun lien entre eux


def groupes_alternatifs(hypotheses, parti_de):
    """Renvoie {cid: groupe} pour les candidats appartenant à un groupe d'au
    moins deux alternatives. `hypotheses` : itérable de dicts {cid: score}
    (hypothèses de premier tour). `parti_de(cid)` : code du parti ou None.

    Le groupe vaut le code du parti ; un parti n'a qu'un groupe, le plus
    fourni. Chaque groupe est une clique : tous ses membres sont deux à deux
    des alternatives."""
    n, ensemble = Counter(), Counter()
    for scores in hypotheses:
        cids = sorted(c for c in scores if c != "autre")
        n.update(cids)
        ensemble.update(itertools.combinations(cids, 2))

    def alternatives(a, b):
        co = ensemble[tuple(sorted((a, b)))]
        return co <= SEUIL_COEXISTENCE * min(n[a], n[b])

    par_parti = {}
    for cid in sorted(n, key=lambda c: (-n[c], c)):
        if n[cid] < MIN_HYPOTHESES:
            continue
        parti = parti_de(cid)
        if parti in SANS_PARTI:
            continue
        groupes = par_parti.setdefault(parti, [])
        for g in groupes:
            if all(alternatives(cid, m) for m in g):
                g.append(cid)
                break
        else:
            groupes.append([cid])

    # Un seul groupe par parti, le plus fourni : deux lignes « PS, selon le
    # candidat » dans la même infobulle seraient illisibles.
    out = {}
    for parti, groupes in par_parti.items():
        g = max(groupes, key=lambda g: (len(g), sum(n[c] for c in g)))
        if len(g) >= 2:
            for cid in g:
                out[cid] = parti
    return out
