"""Collecte des sondages depuis la page Wikipédia de l'élection présidentielle 2027.

Récupère le wikitexte via l'API MediaWiki, conserve un snapshot horodaté,
parse les tableaux et résout les noms via alias_wikipedia de candidats.json.

data/sondages.json est la référence : le résultat Wikipédia (et les sondages
manuels) y est FUSIONNÉ par `id`, jamais substitué. Un sondage absent de
Wikipédia est conservé ; seul le champ `retire` (SPEC §3.2) l'exclut des
calculs et des pages.
"""

import re, json, unicodedata, datetime, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
MANUELS_PATH = ROOT / "data" / "sondages_manuels.json"
OUTPUT_PATH = ROOT / "data" / "sondages.json"
SNAPSHOTS_DIR = ROOT / "data" / "snapshots"

WIKI_API = ("https://fr.wikipedia.org/w/api.php"
            "?action=parse"
            "&page=Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027"
            "&prop=wikitext|revid&format=json")

MOIS = {'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
        'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12,'decembre':12}

# Lignes de données rencontrées mais non converties en sondage. Toute entrée ici
# arrête le run (spec §6) : un sondage qui disparaît en silence ne se voit pas.
ANOMALIES = []

# Marqueur interne : une cellule étiquetée [[vote blanc]] porte le score du vote
# blanc, pas celui d'un candidat. Il est stocké à part, dans `vote_blanc`.
VOTE_BLANC = '__vote_blanc__'

def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z0-9]+','-', s.lower()).strip('-')

def split_cell(line):
    """Sépare attributs et contenu d'une cellule wiki. Le séparateur est le premier
    '|' de niveau 0 (hors {{ }} et [[ ]])."""
    s = line[1:] if line.startswith('|') else line
    depth = 0
    for i,c in enumerate(s):
        if s[i:i+2] in ('{{','[['): depth += 1
        elif s[i:i+2] in ('}}',']]'): depth -= 1
        elif c == '|' and depth == 0:
            return s[:i], s[i+1:]
    return '', s

def cell_value(txt):
    """Retourne la liste des (valeur, candidat_substitué) d'une cellule.

    Une cellule peut remplacer le candidat de sa colonne :
    '7,5<br><small>[[François Hollande|Hollande]] (PS)</small>'.
    Elle peut aussi en contenir plusieurs, séparés par <hr> :
    '4<br><small>Ruffin</small><hr>4<br><small>Lisnard</small>'.
    Chaque fragment est une mesure à part entière ; leurs scores ne s'additionnent pas."""
    return [_une_valeur(f) for f in re.split(r'<hr\s*/?>', txt)]

def _une_valeur(txt):
    parts = re.split(r'<br\s*/?>', txt, maxsplit=1)
    val = clean_num(parts[0])
    sub = None
    if len(parts) > 1 and re.search(r'\[\[\s*vote blanc\s*(\||\]\])', parts[1], re.I):
        return val, VOTE_BLANC
    if len(parts) > 1:
        m = re.search(r'\[\[[^|\]]+\|([^\]]+)\]\]', parts[1])
        if m:
            sub = re.sub(r'\{\{blanc\|([^}]*)\}\}', r'\1', m.group(1))
            sub = re.sub(r'</?[^>]+>', '', sub).strip(" '")
    return val, sub

def clean_num(txt):
    t = txt.strip()
    t = re.sub(r"'''|''", '', t)
    t = re.sub(r'\{\{blanc\|([^}]*)\}\}', r'\1', t)
    t = re.sub(r'\{\{formatnum:([^}]*)\}\}', r'\1', t)
    t = re.sub(r'<ref[^>]*>.*?</ref>|<ref[^>]*/>', '', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('\u00a0','').replace('\u202f','').replace(' ','')
    t = t.replace(',', '.')
    if t in ('—','-','–','','?','nd'): return None
    m = re.match(r'^<?(\d+(?:\.\d+)?)$', t)
    return float(m.group(1)) if m else None

def parse_dates(txt, annee):
    """'2-3 septembre' | '31 août - 2 septembre' | '24 - 25 août 2026' -> (debut, fin)"""
    t = re.sub(r'<[^>]+>|\[\[|\]\]', ' ', txt).replace('–','-').replace('—','-')
    t = re.sub(r'\{\{1er[^}]*\}\}', '1', t)   # '{{1er}} septembre' -> '1 septembre'
    t = re.sub(r'\{\{[^}]*\}\}', ' ', t)
    an = re.search(r'\b(20\d\d)\b', t)
    if an: annee = int(an.group(1)); t = t.replace(an.group(1), '')
    parts = [p.strip() for p in t.split('-')]
    def one(p, mois_defaut=None):
        j = re.search(r'\b(\d{1,2})\b', p)
        m = re.search(r'([a-zéûôA-Zé]+)', p)
        mois = MOIS.get(m.group(1).lower()) if m and m.group(1).lower() in MOIS else mois_defaut
        if not j or not mois: return None, mois
        return datetime.date(annee, mois, int(j.group(1))), mois
    if len(parts) == 1:
        d,_ = one(parts[0]); return d, d
    fin, mois_fin = one(parts[-1])
    deb, _ = one(parts[0], mois_fin)
    if deb and fin and deb > fin:  # chevauchement de mois
        m = mois_fin - 1 or 12
        try: deb = deb.replace(month=m)
        except ValueError: pass
    return deb, fin

def colspan_entete(ligne):
    """Nombre de colonnes occupées par une cellule d'en-tête ('! ... | contenu')."""
    attrs, _ = split_cell('|' + ligne.lstrip('!'))
    m = re.search(r'colspan\s*=\s*"?(\d+)', attrs or '')
    return int(m.group(1)) if m else 1


def parse_table(txt, annee, tour):
    lines = [l.rstrip() for l in txt.split('\n')]
    # --- en-tête : la ligne d'en-têtes contenant les noms liés
    cands, header_end = [], 0
    # la ligne des noms est le dernier bloc de '!' avant la ligne de couleurs de parti
    bloc, dernier = [], []
    for i, l in enumerate(lines):
        if l.startswith('!'):
            bloc.append(l)
        else:
            if 'couleurs|' in l:
                break
            if bloc and not any('Fichier:' in b or 'File:' in b for b in bloc):
                dernier = bloc
            bloc = []
    for l in dernier:
        tete = l.split('<br')[0]
        m = re.search(r'\[\[[^|\]]+\|([^\]]+)\]\]', tete)
        if m:
            nom = m.group(1).strip()
        else:  # colonne générique type 'Candidat RN' : le candidat est dans la cellule
            brut = re.sub(r'^!.*?\|', '', l).strip()
            nom = re.sub(r'\[\[|\]\]|<[^>]+>', ' ', brut).strip() or 'Indetermine'
        # Un en-tête peut porter un colspan (colonne double PS-PP d'octobre 2026) :
        # il occupe alors plusieurs colonnes, que les cellules de données
        # fusionnent elles aussi. Sans cette répétition, tout ce qui suit la
        # colonne est décalé d'un cran (§9).
        cands.extend([nom] * colspan_entete(l))
    for i, l in enumerate(lines):
        if 'couleurs|' in l:
            header_end = i
            break
    autre = 'Autre' in txt[:txt.find('|-')+2000] and tour == 1
    colonnes = cands + (['Autre'] if autre else [])

    sondages, cur, rows = [], None, []
    i = header_end
    while i < len(lines):
        l = lines[i]
        if l.startswith('|-'):
            i += 1; continue
        if l.startswith('|}'): break
        if 'colspan=' in l:  # ligne d'événement
            i += 1; continue
        if not l.startswith('|'):
            i += 1; continue
        attrs, content = split_cell(l)
        rs = re.search(r'rowspan\s*=\s*"?(\d+)', attrs)
        # une nouvelle enquête commence par une cellule Sondeur (lien externe / Sondeur)
        if 'Sondeur' in attrs or (rs and '[http' in content):
            nb = int(rs.group(1)) if rs else 1
            inst = re.search(r'\[(https?://\S+)\s+([^\]]+)\]', content)
            cur = {'institut': (inst.group(2) if inst else re.sub(r'\W+','',content)).strip(),
                   'url_source': inst.group(1) if inst else None,
                   'nb_hyp': nb, 'hypotheses': []}
            sondages.append(cur)
            _, dtxt = split_cell(lines[i+1]); _, etxt = split_cell(lines[i+2])
            cur['_dates'] = dtxt; cur['echantillon'] = clean_num(etxt)
            i += 3
            vals = []
            while len(cur['hypotheses']) < nb and i < len(lines):
                l2 = lines[i]
                if l2.startswith('|}'): break
                if l2.startswith('|-'):
                    if vals: cur['hypotheses'].append(vals); vals = []
                    i += 1; continue
                if l2.startswith('|'):
                    a, c = split_cell(l2)
                    cs = re.search(r'colspan\s*=\s*"?(\d+)', a)
                    n = int(cs.group(1)) if cs else 1
                    if n >= len(colonnes):   # ligne d'événement, pas une donnée
                        i += 1; continue
                    vals.append(cell_value(c))
                    vals += [[(None, None)]] * (n - 1)   # colonnes fusionnées
                i += 1
            if vals: cur['hypotheses'].append(vals)
            continue
        i += 1

    out = []
    for s in sondages:
        deb, fin = parse_dates(s['_dates'], annee)
        if not fin:
            ANOMALIES.append(f"date illisible : {s['institut']} — {s['_dates']!r}")
            continue
        hyps = []
        for v in s['hypotheses']:
            scores, blanc = {}, None
            for nom_col, mesures in zip(colonnes, v):
                for val, sub in mesures:
                    nom = sub or nom_col
                    if nom == VOTE_BLANC:
                        if val is not None: blanc = val
                    elif nom != 'Autre' and val is not None: scores[slug(nom)] = val
            if scores:
                hyp = {'tour': tour, 'echantillon': None,
                       'candidats': sorted(scores), 'scores': scores}
                if blanc is not None: hyp['vote_blanc'] = blanc
                hyps.append(hyp)
        if not hyps:
            ANOMALIES.append(f"aucune hypothèse exploitable : {s['institut']} — {s['_dates']!r}")
            continue
        out.append({'id': f"{slug(s['institut'])}-{fin.isoformat()}",
                    'institut': s['institut'], 'terrain_debut': deb.isoformat(),
                    'terrain_fin': fin.isoformat(), 'echantillon': s['echantillon'],
                    'url_source': s['url_source'], 'hypotheses': hyps})
    return out

# ---------------------------------------------------------------------------
# Résolution des noms : slug(nom_wiki) → clé du référentiel via alias_wikipedia
# ---------------------------------------------------------------------------

def build_alias_map(candidats):
    """Construit un dict slug(alias) → clé candidat."""
    alias_map = {}
    for cid, info in candidats.items():
        for alias in info.get("alias_wikipedia", []):
            s = slug(alias)
            if s in alias_map:
                print(f"ERREUR : alias '{s}' en double ({alias_map[s]} et {cid})", file=sys.stderr)
                sys.exit(1)
            alias_map[s] = cid
    return alias_map


def resolve_scores(hypotheses, alias_map):
    """Remplace les slugs bruts par les clés du référentiel dans chaque hypothèse.
    Erreur bloquante si un candidat n'a pas de correspondance (spec §8 règle 2)."""
    unknown = set()
    for h in hypotheses:
        resolved = {}
        resolved_cands = []
        for s, val in h['scores'].items():
            if s in alias_map:
                resolved[alias_map[s]] = val
                resolved_cands.append(alias_map[s])
            else:
                unknown.add(s)
        h['scores'] = resolved
        h['candidats'] = sorted(resolved_cands)
    return unknown


# ---------------------------------------------------------------------------
# Récupération du wikitexte et découpage de la page
# ---------------------------------------------------------------------------

def fetch_wikitext():
    """Appelle l'API MediaWiki, retourne (wikitext, revid)."""
    req = urllib.request.Request(WIKI_API, headers={"User-Agent": "sondax/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    parse = data["parse"]
    return parse["wikitext"]["*"], parse["revid"]


def save_snapshot(wikitext, revid):
    """Écrit le wikitexte brut dans data/snapshots/{revid}.wikitext."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOTS_DIR / f"{revid}.wikitext"
    path.write_text(wikitext, encoding="utf-8")
    print(f"Snapshot écrit : {path.name}")
    return path


def extract_sondages(raw):
    """Découpe la page en sections et parse les tableaux."""
    res = []
    for titre, annee, tour in [('==== Second semestre 2026 ====', 2026, 1),
                               ('==== Premier semestre 2026 ====', 2026, 1)]:
        d = raw.find(titre)
        if d < 0: continue
        seg = raw[d:]
        seg = seg[:seg.find('\n====', 10) if seg.find('\n====', 10) > 0 else len(seg)]
        res += parse_table(seg, annee, tour)

    for m in re.finditer(r'==== Hypothèse ([^=]+) ====\n(.*?)(?=\n====|\n== )', raw, re.S):
        for s in parse_table(m.group(2), 2026, 2):
            if s['terrain_fin'] >= '2026-01-01': res.append(s)
    return res


# ---------------------------------------------------------------------------
# Fusion avec data/sondages.json (la référence)
# ---------------------------------------------------------------------------

TOLERANCE_JOURS = 2   # même sondage si la fin de terrain bouge de ±2 jours
CHAMPS_RETRAIT = ('retire', 'retire_motif', 'retire_le')


def _hyp_comparable(h):
    """Hypothèse sans les champs calculés ou saisis hors Wikipédia."""
    return {k: v for k, v in h.items() if k != 'principale'}


def _valeurs_hypotheses(s):
    """Signature des valeurs d'hypothèses d'un sondage, indépendante de l'ordre."""
    return sorted(json.dumps({'tour': h['tour'], 'scores': h['scores'],
                              'vote_blanc': h.get('vote_blanc')}, sort_keys=True)
                  for h in s['hypotheses'])


def _ecart_jours(a, b):
    return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)


def meme_sondage(existant, entrant):
    """Même institut, fin de terrain à ±TOLERANCE_JOURS, mêmes valeurs d'hypothèses."""
    return (existant['institut'] == entrant['institut']
            and _ecart_jours(existant['terrain_fin'], entrant['terrain_fin']) <= TOLERANCE_JOURS
            and _valeurs_hypotheses(existant) == _valeurs_hypotheses(entrant))


def _champs_sources(entrant):
    return [k for k in entrant if k not in ('id', 'revid') + CHAMPS_RETRAIT]


def _apparier_hypotheses(anciennes, nouvelles):
    """Apparie les hypothèses par (tour, candidats), puis, parmi les restes, par
    tour seulement (une correction de colonne sur Wikipédia reste une correction,
    pas une hypothèse en plus). Retourne (paires [(i_ancienne, nouvelle)],
    anciennes sans équivalent, nouvelles sans équivalent)."""
    cle = lambda h: (h['tour'], tuple(sorted(h['scores'])))
    restantes = list(nouvelles)
    paires, orphelines = [], []
    for i, a in enumerate(anciennes):
        j = next((j for j, n in enumerate(restantes) if cle(n) == cle(a)), None)
        if j is None:
            orphelines.append(i)
        else:
            paires.append((i, restantes.pop(j)))
    encore = []
    for i in orphelines:
        a = anciennes[i]
        j = next((j for j, n in enumerate(restantes) if n['tour'] == a['tour']), None)
        if j is None:
            encore.append(i)
        else:
            paires.append((i, restantes.pop(j)))
    return paires, encore, restantes


def fusionner_hypotheses(anciennes, nouvelles):
    """Hypothèses fusionnées : celles de Wikipédia mettent à jour leur
    équivalente (même place dans la liste), les nouvelles sont ajoutées à la fin
    et celles que Wikipédia ne renvoie plus sont CONSERVÉES (page tronquée,
    tableau en cours d'édition). Retourne (liste, lignes de journal)."""
    paires, absentes, ajoutees = _apparier_hypotheses(anciennes, nouvelles)
    fusion, lignes = list(anciennes), []
    for i, n in sorted(paires, key=lambda p: p[0]):
        a = anciennes[i]
        n = dict(n)
        if 'principale' in a and 'principale' not in n:
            n['principale'] = a['principale']
        fusion[i] = n
        for c in sorted(set(a['scores']) | set(n['scores'])):
            va, vn = a['scores'].get(c), n['scores'].get(c)
            if va != vn:
                lignes.append(f"hyp.{i+1} T{a['tour']} {c} : "
                              f"{'—' if va is None else va} → {'—' if vn is None else vn}")
        if a.get('vote_blanc') != n.get('vote_blanc'):
            lignes.append(f"hyp.{i+1} T{a['tour']} vote_blanc : "
                          f"{a.get('vote_blanc')} → {n.get('vote_blanc')}")
        if a.get('echantillon') != n.get('echantillon'):
            lignes.append(f"hyp.{i+1} T{a['tour']} echantillon : "
                          f"{a.get('echantillon')} → {n.get('echantillon')}")
    for i in absentes:
        lignes.append(f"hyp.{i+1} T{anciennes[i]['tour']} absente de Wikipédia, conservée "
                      f"({', '.join(sorted(anciennes[i]['scores']))})")
    for n in ajoutees:
        fusion.append(n)
        lignes.append(f"hyp.{len(fusion)} T{n['tour']} ajoutée "
                      f"({', '.join(f'{c} {v}' for c, v in sorted(n['scores'].items()))})")
    return fusion, lignes


def fusionner_sondage(existant, entrant):
    """Valeurs de `entrant` appliquées sur `existant`. Retourne (champs à écrire,
    lignes de journal) ; rien à écrire = aucun changement. Ignore revid,
    `principale` et tout champ que l'entrant ne fournit pas."""
    champs, lignes = {}, []
    for champ in _champs_sources(entrant):
        if champ == 'hypotheses':
            fusion, diff = fusionner_hypotheses(existant.get('hypotheses', []), entrant['hypotheses'])
            if [_hyp_comparable(h) for h in fusion] != [_hyp_comparable(h) for h in existant.get('hypotheses', [])]:
                champs[champ] = fusion
            lignes += diff
        elif existant.get(champ) != entrant[champ]:
            champs[champ] = entrant[champ]
            lignes.append(f"{champ} : {existant.get(champ)!r} → {entrant[champ]!r}")
    return champs, lignes


def fusionner(existants, entrants, dedoublonner=True):
    """Fusionne `entrants` dans `existants` par `id`, sans jamais rien supprimer.

    - id nouveau : ajouté (sauf doublon à date décalée, voir `meme_sondage`) ;
    - id connu, valeurs changées : mis à jour, revid compris ;
    - id absent des entrants : conservé tel quel.
    Les champs de retrait ne sont jamais touchés. Retourne (résultat, rapport)."""
    resultat = [dict(s) for s in existants]
    par_id = {s['id']: s for s in resultat}
    ids_entrants = {e['id'] for e in entrants}
    rapport = {'ajoutes': [], 'modifies': [], 'conserves': [], 'deplaces': [], 'retires_touches': [],
               'absents': []}
    vus = set()

    def appliquer(cible, entrant):
        champs, diff = fusionner_sondage(cible, entrant)
        if champs:
            cible.update(champs)
            if entrant.get('revid') is not None:
                cible['revid'] = entrant['revid']
            if cible.get('retire'):
                rapport['retires_touches'].append(cible['id'])
        if champs:
            rapport['modifies'].append((cible['id'], diff))
        elif diff:      # seulement des hypothèses conservées : rien n'est écrit
            rapport['conserves'].append((cible['id'], diff))
        return diff

    for e in sorted(entrants, key=lambda e: e['id']):
        if e['id'] in par_id:
            vus.add(e['id'])
            appliquer(par_id[e['id']], e)
            continue
        # Id inconnu : le même sondage, avec une date de terrain décalée ?
        candidats = []
        if dedoublonner:
            candidats = sorted(
                (s for s in resultat if s['id'] not in ids_entrants
                 and s['id'] not in vus and meme_sondage(s, e)),
                key=lambda s: (_ecart_jours(s['terrain_fin'], e['terrain_fin']), s['id']))
        if candidats:
            cible = candidats[0]
            vus.add(cible['id'])
            diff = appliquer(cible, e)
            rapport['deplaces'].append((cible['id'], e['id'], diff))
        else:
            nouveau = dict(e)
            resultat.append(nouveau)
            par_id[nouveau['id']] = nouveau
            vus.add(nouveau['id'])
            rapport['ajoutes'].append(nouveau['id'])

    rapport['absents'] = [s['id'] for s in resultat if s['id'] not in vus]
    resultat.sort(key=lambda s: s['terrain_fin'], reverse=True)
    return resultat, rapport


def afficher_rapport(rapport, existants_par_id):
    """Journal des écarts : ajouts, diffs, sondages conservés mais absents de Wikipédia."""
    print(f"\n== Journal des écarts ==")
    print(f"{len(rapport['ajoutes'])} ajouté(s), {len(rapport['modifies'])} mis à jour, "
          f"{len(rapport['absents'])} absent(s) de Wikipédia (conservés)")
    for id_ in rapport['ajoutes']:
        print(f"  + ajouté : {id_}")
    deplaces = {a: n for a, n, _ in rapport['deplaces']}
    for id_, diff in rapport['modifies']:
        suffixe = f" (id Wikipédia {deplaces[id_]}, date décalée)" if id_ in deplaces else ""
        print(f"  ~ modifié : {id_}{suffixe}")
        for l in diff:
            print(f"      {l}")
    for id_, nouvel_id, diff in rapport['deplaces']:
        if not diff:
            print(f"  = {id_} : retrouvé sous l'id Wikipédia {nouvel_id}, rien à changer")
    for id_, diff in rapport['conserves']:
        print(f"  = {id_} : Wikipédia ne renvoie pas tout, rien n'est supprimé")
        for l in diff:
            print(f"      {l}")
    for id_ in rapport['retires_touches']:
        print(f"  ! {id_} est retiré mais Wikipédia l'a modifié : il reste retiré")
    if rapport['absents']:
        print("  Présents chez nous, absents de Wikipédia (conservés tels quels) :")
        for id_ in rapport['absents']:
            s = existants_par_id.get(id_, {})
            note = ", ".join(n for n in (s.get('source') == 'manuel' and 'manuel',
                                         s.get('retire') and 'retiré') if n)
            print(f"    - {id_}" + (f" [{note}]" if note else ""))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', help="wikitexte local (<revid>.wikitext) au lieu de l'API")
    ap.add_argument('--sortie', help="fichier de sortie (défaut : data/sondages.json)")
    args = ap.parse_args(argv)
    sortie = pathlib.Path(args.sortie) if args.sortie else OUTPUT_PATH

    candidats = json.loads(CANDIDATS_PATH.read_text())
    alias_map = build_alias_map(candidats)

    # Récupération du wikitexte
    if args.snapshot:
        chemin = pathlib.Path(args.snapshot)
        raw, revid = chemin.read_text(encoding="utf-8"), int(chemin.stem)
        print(f"Snapshot local : {chemin.name}, {len(raw)} caractères")
    else:
        print("Appel à l'API MediaWiki...")
        raw, revid = fetch_wikitext()
        print(f"revid : {revid}, {len(raw)} caractères")
        save_snapshot(raw, revid)

    # Parsing
    res = extract_sondages(raw)

    if ANOMALIES:
        print("ERREUR : lignes de données non exploitées, aucune écriture :", file=sys.stderr)
        for a in ANOMALIES:
            print(f"  - {a}", file=sys.stderr)
        sys.exit(1)

    # Fusion des sondages présents dans plusieurs sections (T1 + T2)
    fusion = {}
    for s in res:
        if s['id'] in fusion:
            fusion[s['id']]['hypotheses'] += s['hypotheses']
        else:
            fusion[s['id']] = s
    res = sorted(fusion.values(), key=lambda s: s['terrain_fin'], reverse=True)

    # Résolution des noms via alias_wikipedia
    unknown = set()
    for s in res:
        unknown |= resolve_scores(s['hypotheses'], alias_map)
        s['revid'] = revid

    if unknown:
        print(f"ERREUR : candidats inconnus dans le référentiel : {sorted(unknown)}", file=sys.stderr)
        sys.exit(1)

    # Sondages manuels : contrôles avant fusion
    manuels = []
    wiki_ids = {s['id'] for s in res}
    if MANUELS_PATH.exists():
        manuels = json.loads(MANUELS_PATH.read_text())
        candidat_ids = set(candidats.keys())
        for s in manuels:
            if s['id'] in wiki_ids:
                print(f"ERREUR : collision d'id '{s['id']}' — ce sondage est désormais "
                      f"présent sur Wikipédia, supprimer l'entrée manuelle de "
                      f"sondages_manuels.json", file=sys.stderr)
                sys.exit(1)
            # Valider les candidats
            for h in s['hypotheses']:
                for cid in h['scores']:
                    if cid not in candidat_ids:
                        print(f"ERREUR : candidat inconnu '{cid}' dans le sondage "
                              f"manuel '{s['id']}'", file=sys.stderr)
                        sys.exit(1)

    # Fusion dans la référence existante : on ajoute et on met à jour, on ne supprime jamais
    existants = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else []
    existants_par_id = {s['id']: s for s in existants}
    final, rapport = fusionner(existants, res)
    final, _ = fusionner(final, manuels, dedoublonner=False)
    if len(final) < len(existants):   # impossible sans bug de fusion
        print(f"ERREUR : la fusion a perdu des sondages ({len(final)} < {len(existants)}), "
              f"aucune écriture", file=sys.stderr)
        sys.exit(1)
    afficher_rapport(rapport, existants_par_id)
    print(f"{len(manuels)} sondage(s) manuel(s) fusionné(s)")
    res = final

    # Écriture
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")

    # Rapport
    actifs = [s for s in res if not s.get('retire')]
    nh = sum(len(s['hypotheses']) for s in actifs)
    print(f"\n{len(res)} sondages dans le fichier ({len(res) - len(actifs)} retiré(s)), "
          f"{len(actifs)} actifs, {nh} hypothèses")
    print(f"période : {res[-1]['terrain_fin']} → {res[0]['terrain_fin']}")
    bad = 0
    for s in res:
        for h in s['hypotheses']:
            t = sum(h['scores'].values()) + (h.get('vote_blanc') or 0)
            lo, hi = (95, 105) if h['tour'] == 1 else (99, 101)
            if not lo <= t <= hi:
                bad += 1
                if bad <= 6:
                    print(f"  HORS BORNES {s['id']} T{h['tour']} somme={t}")
    print(f"hypothèses hors bornes : {bad}")


if __name__ == "__main__":
    main()
