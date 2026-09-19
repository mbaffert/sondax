#!/usr/bin/env python3
"""Calcule le champ `principale` de chaque sondage (SPEC §4).

Hypothese principale = celle du tour 1 qui contient le plus de candidats
DECLARES A LA DATE DU TERRAIN. Egalite : la premiere de la liste (ordre de
publication par l'institut). Si aucun candidat n'est declare a cette date,
repli sur le nombre total de candidats.
"""
import json, sys, collections

def est_declare(cand, date_terrain):
    d = cand.get("declare_le")
    return d is not None and d <= date_terrain

def calculer(sondages, candidats):
    anomalies = []
    for p in sondages:
        t1 = [h for h in p["hypotheses"] if h["tour"] == 1]
        for h in p["hypotheses"]:
            h["principale"] = False
        if not t1:
            continue
        date = p["terrain_fin"]
        scores = [sum(1 for k in h["scores"]
                      if k in candidats and est_declare(candidats[k], date))
                  for h in t1]
        if max(scores) == 0:                      # repli : aucun declare
            scores = [len(h["scores"]) for h in t1]
            anomalies.append((p["id"], "repli : aucun candidat declare"))
        t1[scores.index(max(scores))]["principale"] = True
    return anomalies

def valider(sondages):
    """Un et un seul `principale` par sondage ayant au moins une hypothese T1."""
    erreurs = []
    for p in sondages:
        t1 = [h for h in p["hypotheses"] if h["tour"] == 1]
        n = sum(1 for h in t1 if h.get("principale"))
        if t1 and n != 1:
            erreurs.append(f"{p['id']} : {n} hypothese(s) principale(s), attendu 1")
    return erreurs

if __name__ == "__main__":
    sondages = json.load(open("data/sondages.json"))
    candidats = json.load(open("data/candidats.json"))
    anomalies = calculer(sondages, candidats)
    erreurs = valider(sondages)
    if erreurs:
        print("ECHEC :", *erreurs, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    for id_, motif in anomalies:
        print(f"  note  {id_} : {motif}")
    json.dump(sondages, open("data/sondages.json", "w"),
              ensure_ascii=False, indent=2)
    print(f"OK  {len(sondages)} sondages traites")
