#!/usr/bin/env python3
"""Import unique des sondages des européennes 2019 et 2024 (SPEC §14.16).

Même démarche que import_historique.py : pages anglaises figées par revid,
snapshots dans data/snapshots/historique/ (--telecharger pour les récupérer),
sortie data/historique_europeennes.json au schéma de historique.json. Les listes
remplacent les candidats (type « liste »), identifiées par le sigle de la
colonne.

- 2019 : page « Opinion polling for the 2019 European Parliament election in
  France » ; le résultat officiel est la ligne de l'élection en tête du tableau.
- 2024 : pas de page de sondages en anglais ; tableau de la section « Opinion
  polling » de l'article sur l'élection. Résultat : voix du modèle
  {{Election results}} du même article, rapportées aux suffrages exprimés, avec
  une table de correspondance écrite à la main (RESULTATS_2024).

Rien n'est corrigé : une ligne dont le nombre de cellules ne correspond pas à
l'en-tête est écartée et comptée ; une cellule fusionnée sur plusieurs listes va
dans scores_groupes ; « <0,5 » va dans scores_inferieurs_a.
"""
import datetime, json, re, sys, unicodedata, pathlib
from wikitable import iter_tables, parse_rows, to_grid

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshots" / "historique"
OUTPUT = ROOT / "data" / "historique_europeennes.json"

ELECTIONS = {
    "2019": dict(revid=1306346350, tour1="2019-05-26",
                 page="Opinion polling for the 2019 European Parliament election in France"),
    "2024": dict(revid=1370942182, tour1="2024-06-09",
                 page="2024 European Parliament election in France"),
}

COLONNES_HORS_LISTE = {"polling firm", "fieldwork date", "sample", "sample size", "abs.", "others", "lead", "div"}

# 2024 : indice du parti dans {{Election results}} → sigle de la colonne des sondages.
RESULTATS_2024 = {
    1: "RN", 2: "Ens.", 3: "PS–PP", 4: "LFI", 5: "LR", 6: "EELV", 7: "REC", 8: "PCF",
    9: "AR", 10: "PA", 11: "EAC", 12: "UPR", 13: "LP–VIA", 14: "LO", 15: "ÉPT",
    17: "PRG", 18: "NPA", 19: "PP", 20: "UDMF", 22: "ND",
}

MOIS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
ANOMALIES = []


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def texte(cell):
    """Texte lisible d'une cellule d'en-tête : sigle avant le premier <br>."""
    s = re.split(r"<br\s*/?>", cell, maxsplit=1)[0]
    s = re.sub(r"\{\{(?:abbr|abbreviation)\|([^|}]*)\|[^}]*\}\}", r"\1", s)
    s = re.sub(r"\{\{tooltip\|2=[^|}]*\|([^}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{ill\|[^}]*?lt=([^|}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{efn[^{}]*(\{\{[^}]*\}\}[^{}]*)*\}\}", "", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def valeur(cell):
    """(nombre, inferieur_a) ; (None, None) pour « – » ou vide."""
    s = re.sub(r"\{\{efn[^{}]*(\{\{[^}]*\}\}[^{}]*)*\}\}", "", cell)
    s = re.sub(r"\{\{[^}]*\}\}|'''|%|\s", "", s).replace(",", ".")
    m = re.fullmatch(r"<(\d+(?:\.\d+)?)", s)
    if m:
        return None, float(m.group(1))
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:\(.*)?", s)
    return (float(m.group(1)), None) if m else (None, None)


def date_fin(cell, annee_defaut):
    """Dernier jour du terrain : {{Opdrts|j1|j2|Mois|Année|...}} ou « 23–24 May 2019 »."""
    m = re.search(r"\{\{Opdrts\|(\d*)\|(\d+)\|(\w+)\|(\d{4})", cell)
    if m:
        return datetime.date(int(m.group(4)), MOIS[m.group(3)[:3].lower()], int(m.group(2)))
    s = re.sub(r"\{\{[^}]*\}\}|\[\[|\]\]", "", cell)
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})\s*$", s.strip())
    if m:
        return datetime.date(int(m.group(3)), MOIS[m.group(2).lower()], int(m.group(1)))
    return None


def institut(cell):
    m = re.search(r"\[https?://\S+\s+([^\]]+)\]", cell)
    s = m.group(1) if m else texte(cell)
    return re.sub(r"<[^>]+>|\{\{[^}]*\}\}", "", s).strip()


def echantillon(cell):
    s = re.sub(r"\{\{[^}]*\}\}|[,.\s]", "", cell)
    return int(s) if s.isdigit() else None


def tableau_sondages(wikitexte):
    for _, t in iter_tables(wikitexte):
        if "Polling firm" in t[:3000] and "Fieldwork" in t[:3000]:
            return t
    raise SystemExit("import_europeennes : tableau des sondages introuvable")


def colonnes(grille):
    """Sigle de chaque colonne, lu dans la première ligne d'en-tête."""
    return [texte(c.content) for c in grille[0]]


def lire(annee, cfg):
    wt = (SNAP / f"{cfg['revid']}.wikitext").read_text()
    grille = to_grid(parse_rows(tableau_sondages(wt)))
    sigles = colonnes(grille)
    n_col = len(sigles)
    listes = {i: s for i, s in enumerate(sigles) if s.lower() not in COLONNES_HORS_LISTE}
    tour = datetime.date.fromisoformat(cfg["tour1"])

    sondages, resultat, ecartees = {}, None, 0
    for ligne in grille:
        if all(c.header for c in ligne):
            continue
        if len(ligne) != n_col:
            ecartees += 1
            continue
        firme = ligne[0].content
        if "European Parliament election" in firme:
            if annee in firme and annee == "2019":
                resultat = {}
                for i, s in listes.items():
                    v, _ = valeur(ligne[i].content)
                    if v is not None:
                        resultat[slug(s)] = v
            continue
        fin = date_fin(ligne[1].content, annee)
        if fin is None or fin >= tour:
            continue
        scores, inferieurs, groupes, vus = {}, {}, {}, {}
        for i, s in listes.items():
            c = ligne[i]
            vus.setdefault(c.uid, []).append(slug(s))
        for i, s in listes.items():
            c = ligne[i]
            membres = vus[c.uid]
            if membres[0] != slug(s):
                continue
            v, inf = valeur(c.content)
            if len(membres) > 1:
                if v is not None:
                    groupes["+".join(membres)] = v
            elif v is not None:
                scores[slug(s)] = v
            elif inf is not None:
                inferieurs[slug(s)] = inf
        if not scores:
            continue
        nom = institut(firme)
        cle = (nom, fin.isoformat(), echantillon(ligne[2].content))
        s = sondages.setdefault(cle, {
            "id": f"{slug(nom)}-{fin.isoformat()}",
            "institut": nom,
            "terrain_fin": fin.isoformat(),
            "echantillon": cle[2],
            "rolling": False,
            "hypotheses": [],
        })
        h = {"tour": 1, "echantillon": None, "scores": scores}
        if inferieurs:
            h["scores_inferieurs_a"] = inferieurs
        if groupes:
            h["scores_groupes"] = groupes
        s["hypotheses"].append(h)

    if annee == "2024":
        resultat = resultats_2024(wt)
    if not resultat:
        raise SystemExit(f"import_europeennes : résultat {annee} introuvable")

    # Identifiants uniques (même institut, même date, échantillons différents)
    vus_ids, liste = {}, []
    for s in sorted(sondages.values(), key=lambda s: (s["terrain_fin"], s["id"])):
        n = vus_ids.get(s["id"], 0)
        vus_ids[s["id"]] = n + 1
        if n:
            s["id"] = f"{s['id']}-{n + 1}"
        liste.append(s)
    if ecartees:
        ANOMALIES.append(f"{annee} : {ecartees} ligne(s) écartée(s) (cellules ≠ en-tête)")

    return {
        "tour1": cfg["tour1"],
        "page": cfg["page"],
        "revid": cfg["revid"],
        "url": f"https://en.wikipedia.org/w/index.php?oldid={cfg['revid']}",
        "resultats": {"tour1": resultat},
        "candidats": {slug(s): {"nom": s, "type": "liste", "partis": [s]}
                      for s in listes.values()},
        "sondages": liste,
    }


def resultats_2024(wt):
    """Voix du modèle {{Election results}}, en % des exprimés (toutes listes)."""
    bloc = wt[wt.index("{{Election results"):]
    voix = {int(n): int(v) for n, v in re.findall(r"\|votes(\d+)=(\d+)", bloc[:20000])}
    total = sum(voix.values())
    return {slug(sigle): round(100 * voix[n] / total, 2) for n, sigle in RESULTATS_2024.items()}


def telecharger():
    import urllib.parse, urllib.request
    SNAP.mkdir(parents=True, exist_ok=True)
    for annee, cfg in ELECTIONS.items():
        dest = SNAP / f"{cfg['revid']}.wikitext"
        if dest.exists():
            continue
        url = ("https://en.wikipedia.org/w/api.php?action=parse&format=json&prop=wikitext"
               f"&oldid={cfg['revid']}")
        req = urllib.request.Request(url, headers={"User-Agent": "sondax/1.0 (https://sondax.fr)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_text(json.loads(r.read())["parse"]["wikitext"]["*"])
        print(f"snapshot {dest.name}")


def main():
    if "--telecharger" in sys.argv:
        telecharger()
    sortie = {
        "source": {"site": "en.wikipedia.org", "licence": "CC BY-SA 4.0",
                   "extrait_le": datetime.date.today().isoformat(),
                   "script": "scripts/import_europeennes.py"},
        "elections": {a: lire(a, cfg) for a, cfg in ELECTIONS.items()},
    }
    OUTPUT.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n")
    for a, e in sortie["elections"].items():
        tour = datetime.date.fromisoformat(e["tour1"])
        derniers = [s for s in e["sondages"]
                    if 1 <= (tour - datetime.date.fromisoformat(s["terrain_fin"])).days <= 7]
        print(f"{a} : {len(e['sondages'])} sondages, dont {len(derniers)} dans la dernière semaine ; "
              f"{len(e['resultats']['tour1'])} listes avec résultat")
    for x in ANOMALIES:
        print("  " + x)
    print(f"Écrit dans {OUTPUT}")


if __name__ == "__main__":
    main()
