"""Import unique des sondages des présidentielles 2002-2022 (en.wikipedia).

Pages anglaises plutôt que françaises : ce sont les seules à donner l'échantillon
pour 2002-2012, et elles sont plus complètes. Les dates y portent l'année.

Source : pages « Opinion polling for the {année} French presidential election »,
wikitexte figé par revid. Données figées : pas de cron, pas de PR quotidienne.

Champs propres à l'historique, en plus du format de sondages.json :
  institut_page        libellé tel qu'écrit sur la page (institut = forme normalisée)
  rolling              vague d'un rolling quotidien (échantillons qui se recouvrent).
                       2007, 2012, 2017 : règle énoncée en tête de page ; 2002 : aucun ;
                       2022 : détecté (vague qui chevauche une autre vague du même
                       institut et finit 1 à 2 jours avant ou après)
  marque_page          astérisques de la page ; traduits en sous_echantillon,
                       hors_commission ou telephone selon la légende de chaque page
  scores_inferieurs_a  candidat testé, publié « < x % » (hors de scores)
  scores_groupes       une seule valeur publiée pour plusieurs candidats (cellule fusionnée)
  autres               colonne « Others » quand elle existe
  somme_hors_bornes    somme hors 95-105 (T1) ou 99-101 (T2), valeur de la page
Clés candidats : nom de famille slugifié, comme candidats.json ('le-pen' = Marine Le Pen,
'le-pen-jean-marie' pour son père). 'candidat-npa' : colonne de parti sans personne.

Sortie : data/historique.json. Snapshots : data/snapshots/historique/{revid}.wikitext
(téléchargés une fois avec --telecharger, jamais modifiés ensuite).

Aucune décision de méthode n'est appliquée ici (rollings, hypothèse principale,
regroupement par famille) : on stocke le brut avec des marqueurs, le traitement
se fait dans les séries dérivées.
"""
import re, json, sys, unicodedata, datetime, pathlib
from collections import defaultdict
from wikitable import iter_tables, parse_rows, to_grid

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / 'data' / 'snapshots' / 'historique'
OUTPUT = ROOT / 'data' / 'historique.json'
PAGE = 'Opinion polling for the {} French presidential election'

ELECTIONS = {
    2002: dict(revid=1329460026, tour1='2002-04-21', tour2='2002-05-05'),
    2007: dict(revid=1341388824, tour1='2007-04-22', tour2='2007-05-06'),
    2012: dict(revid=1279812574, tour1='2012-04-22', tour2='2012-05-06'),
    2017: dict(revid=1213598918, tour1='2017-04-23', tour2='2017-05-07'),
    2022: dict(revid=1363121499, tour1='2022-04-10', tour2='2022-04-24'),
}

# Sections écartées : sous-échantillons géographiques ou par électorat, graphiques.
EXCLUS = re.compile(r'region|department|commune|constituency|by first round'
                    r'|subsample|abroad|overseas', re.I)

MOIS = {m: i for i, m in enumerate(
    'jan feb mar apr may jun jul aug sep oct nov dec'.split(), 1)}

ANOMALIES = []
PARTIS = defaultdict(list)   # cible wiki -> partis lus dans les en-têtes
PARTIS_ABR = {
    'Socialist Party (France)': 'PS', 'The Republicans (France)': 'LR', 'Rally for the Republic': 'RPR',
    'Lutte Ouvrière': 'LO', 'French Communist Party': 'PCF', 'La République En Marche!': 'LREM',
    'National Rally (France)': 'RN', 'Europe Ecology – The Greens': 'EELV', 'The Greens (France)': 'LV',
    'New Anticapitalist Party': 'NPA', 'La France Insoumise': 'LFI', 'La France insoumise': 'LFI',
    'Résistons!': 'RES', 'Debout la France': 'DLF', 'Radical Party of the Left': 'PRG',
    'Movement of Citizens': 'MDC', 'Union for French Democracy': 'UDF', 'National Front (France)': 'FN',
    'Popular Republican Union (2007)': 'UPR', 'Reconquête (political party)': 'REC',
    'Miscellaneous left': 'DVG', 'Miscellaneous right': 'DVD', 'Liberal Democracy (France)': 'DL',
    'Forum of Social Republicans': 'FRS', 'National Republican Movement': 'MNR',
    'Revolutionary Communist League (France)': 'LCR', 'Cap21': 'Cap21', 'Rally for France': 'RPF',
    'Hunting, Fishing, Nature and Traditions': 'CPNT', 'Animalist Party': 'PA',
    'The Patriots (France)': 'LP', "Workers' Party (France)": 'PT',
    'Union of Democrats and Independents': 'UDI', 'Movement for France': 'MPF',
    'Christian Democratic Party (France)': 'PCD', 'Soyons libres': 'SL', 'Solidarity and Progress': 'S&P',
    'Independent Ecological Movement': 'MEI', 'Ecology Generation': 'GE', 'Independent (politician)': 'SE',
    'Génération.s': 'G.s', 'New Deal (France)': 'ND',
}


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def nettoie(t):
    t = re.sub(r'<ref[^>]*/>', '', t)
    t = re.sub(r'<ref[^>]*>.*?</ref>', '', t, flags=re.S)
    t = re.sub(r'\{\{efn[^{}]*(\{\{[^{}]*\}\}[^{}]*)*\}\}', '', t, flags=re.I)
    t = re.sub(r'\{\{(?:Webarchive|webarchive|Cite|cite|Dead link|dead link)[^{}]*\}\}', '', t)
    t = re.sub(r'\{\{(?:small|nowrap|abbr)\|([^{}|]*)(\|[^{}]*)?\}\}', r'\1', t)
    t = re.sub(r"'''?", '', t)
    t = re.sub(r'<br\s*/?>', ' ', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('\u00a0', ' ').replace('&nbsp;', ' ')
    return t.strip()


# ---------------------------------------------------------------------------
# Valeurs
# ---------------------------------------------------------------------------

def valeur(txt):
    """-> ('abs', None) | ('val', float) | ('inf', float) | ('bad', texte)"""
    t = nettoie(txt)
    t = re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]', r'\1', t)
    t = t.replace(' ', '')
    if t in ('', '–', '-', '—', '?', 'N/A', 'n/a'):
        return 'abs', None
    m = re.fullmatch(r'<(\d+(?:[.,]\d+)?)%?', t)
    if m:
        return 'inf', float(m.group(1).replace(',', '.'))
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)%?', t)
    if m:
        return 'val', float(m.group(1).replace(',', '.'))
    return 'bad', t


def echantillon(txt):
    t = nettoie(txt).replace(',', '').replace(' ', '')
    m = re.match(r'^(\d{2,6})', t)
    return int(m.group(1)) if m else None


def _date(j, m, a):
    return datetime.date(int(a), MOIS[m[:3].lower()], int(j))


def dates(txt):
    """'7–8 Apr 2022' | '31 Mar–1 Apr 2022' | '28 Dec 2021–3 Jan 2022' | '8 Apr 2022'"""
    t = nettoie(txt).replace('—', '–').replace(' - ', '–').replace('-', '–')
    t = re.sub(r'\s+', ' ', t)
    M = r'([A-Z][a-z]{2,8})'
    pats = [
        (rf'^(\d{{1,2}}) {M} (\d{{4}}) ?– ?(\d{{1,2}}) {M} (\d{{4}})$',
         lambda g: (_date(g[0], g[1], g[2]), _date(g[3], g[4], g[5]))),
        (rf'^(\d{{1,2}}) {M} ?– ?(\d{{1,2}}) {M} (\d{{4}})$',
         lambda g: (_date(g[0], g[1], g[4]), _date(g[2], g[3], g[4]))),
        (rf'^(\d{{1,2}}) ?– ?(\d{{1,2}}) {M} (\d{{4}})$',
         lambda g: (_date(g[0], g[2], g[3]), _date(g[1], g[2], g[3]))),
        (rf'^(\d{{1,2}}) {M} (\d{{4}})$',
         lambda g: (_date(g[0], g[1], g[2]),) * 2),
        (rf'^{M} (\d{{4}})$', None),  # mois seul : imprécis
    ]
    for p, f in pats:
        m = re.match(p, t)
        if m:
            if f is None:
                return None, None, t
            try:
                deb, fin = f(m.groups())
            except (KeyError, ValueError):
                return None, None, t
            if deb > fin:  # '28 Dec–3 Jan 2022' : début l'année d'avant
                deb = deb.replace(year=deb.year - 1)
            return deb, fin, None
    return None, None, t


def institut(txt):
    t = re.sub(r'\{\{[^{}]*\}\}', '', txt)
    t = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', t, flags=re.S)
    url = None
    m = re.search(r'\[(https?://\S+)\s+([^\]]+)\]', t)
    if m:
        url, nom = m.group(1), m.group(2)
        reste = t[m.end():]
    else:
        nom, reste = t, ''
    nom = nettoie(re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]|\[\[([^\]]*)\]\]',
                         lambda x: x.group(1) or x.group(2), nom))
    marques = re.findall(r'\*+', nom + nettoie(reste))
    nom = nom.replace('*', '').strip()
    return nom, url, (max(marques, key=len) if marques else '')


def lien_personne(txt):
    """Premier lien wiki qui n'est ni un fichier ni un parti (avant le 1er <br>)."""
    # un <br> peut couper un nom à l'intérieur du lien : 'Dupont-<br>Aignan'
    t = re.sub(r'\[\[[^\]]*\]\]', lambda m: re.sub(r'<br\s*/?>', '', m.group(0)), txt)
    t = re.split(r'<br\s*/?>', t)[0]
    for m in re.finditer(r'\[\[([^\]|]+)(?:\|([^\]]*))?\]\]', t):
        cible = m.group(1).strip()
        if re.match(r'(File|Image|Fichier):', cible, re.I):
            continue
        return cible, (m.group(2) or cible).strip()
    return None


# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------

def roles_colonnes(grid):
    """Identifie l'en-tête (lignes entièrement '!') et le rôle de chaque colonne."""
    nh = 0
    while nh < len(grid) and all(c.header for c in grid[nh]):
        nh += 1
    ncol = max(len(r) for r in grid[:max(nh, 1)])
    roles = []
    for c in range(ncol):
        vus, textes, attrs, personne = set(), [], [], None
        # la cellule de couleur n'a pas de rowspan : on la lit dans toutes les lignes d'en-tête
        for r in range(nh):
            if c >= len(grid[r]):
                continue
            cell = grid[r][c]
            if cell.uid in vus:
                continue
            vus.add(cell.uid)
            textes.append(cell.content)
            attrs.append(cell.attrs)
            # un en-tête qui couvre plusieurs colonnes (bandeau de groupe) ne nomme pas une personne
            if personne is None and cell.colspan == 1:
                personne = lien_personne(cell.content)
        brut = ' '.join(nettoie(x) for x in textes).lower()
        if re.search(r'polling|pollster|firm', brut):
            roles.append(('institut', None))
        elif re.search(r'fieldwork|date', brut):
            roles.append(('dates', None))
        elif re.search(r'sample', brut):
            roles.append(('echantillon', None))
        elif re.search(r'\babs', brut):
            roles.append(('abstention', None))
        elif re.search(r'\bothers?\b|\bautres?\b|\bdivers\b', brut) and not personne:
            roles.append(('autres', None))
        elif re.search(r'\blead\b|undecided|blank|none', brut) and not personne:
            roles.append(('ignore', brut))
        elif personne:
            roles.append(('candidat', personne))
            liens = re.findall(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', ' '.join(textes))
            partis = [(lab or cib).strip() for cib, lab in liens
                      if cib.strip() != personne[0] and not re.match(r'(File|Image|Fichier):', cib, re.I)]
            if not partis:  # à défaut, la ligne de couleur : {{party color|Parti}}
                coul = re.findall(r'party colou?r\|([^}|]+)', ' '.join(textes + attrs))
                partis = [PARTIS_ABR.get(x.strip(), x.strip()) for x in coul]
            PARTIS[personne[0]].append(nettoie(partis[-1]) if partis else None)
        elif re.search(r'nominee|candidate', brut):
            # colonne « candidat du parti X », personne non désignée
            partis = re.findall(r'\[\[[^\]|]+\|([^\]]+)\]\]', ' '.join(textes))
            roles.append(('candidat', ('__parti__', partis[-1] if partis else brut)))
        else:
            roles.append(('inconnu', brut))
    return nh, roles


def lire_tableau(tab, tour, chemin, annee):
    grid = to_grid(parse_rows(tab))
    if not grid:
        return [], None
    nh, roles = roles_colonnes(grid)
    kinds = [r[0] for r in roles]
    if 'institut' not in kinds or 'dates' not in kinds or 'candidat' not in kinds:
        return [], None
    for i, (k, info) in enumerate(roles):
        if k == 'inconnu':
            ANOMALIES.append(f'{annee} {chemin} : colonne {i} non identifiée ({info!r})')
    ci, cd = kinds.index('institut'), kinds.index('dates')
    ce = kinds.index('echantillon') if 'echantillon' in kinds else None
    ca = kinds.index('autres') if 'autres' in kinds else None
    cands = {i: info for i, (k, info) in enumerate(roles) if k == 'candidat'}
    ncol = len(roles)

    lignes, resultat = [], None
    for r in grid[nh:]:
        if not r or all(c.header for c in r):
            continue
        c0 = r[0]
        if c0.colspan >= ncol - 1 or len({c.uid for c in r}) == 1:
            continue  # bandeau d'événement
        if len(r) < ncol:
            ANOMALIES.append(f'{annee} {chemin} : ligne courte ({len(r)}/{ncol}) : {nettoie(c0.content)[:60]!r}')
            continue
        brut0 = c0.content
        scores, inf, groupes, bad, vus = {}, {}, [], [], set()
        for i, cible in cands.items():
            cell = r[i]
            k, v = valeur(cell.content)
            couverts = [j for j in cands if r[j] is cell]
            if len(couverts) > 1:
                if (cell.uid, 'g') in vus or k == 'abs':
                    continue
                vus.add((cell.uid, 'g'))
                if k in ('val', 'inf'):
                    groupes.append({'candidats': [cands[j] for j in couverts], 'score': v,
                                    'inferieur': k == 'inf'})
                else:
                    bad.append(f'{cible[1]}={v!r}')
                continue
            if k == 'val':
                scores[cible] = v
            elif k == 'inf':
                inf[cible] = v
            elif k == 'bad':
                bad.append(f'{cible[1]}={v!r}')
        autres = None
        if ca is not None:
            k, v = valeur(r[ca].content)
            autres = v if k == 'val' else None
        if re.search(r'election', brut0, re.I) and 'http' not in brut0:
            _, fin_r, _ = dates(r[cd].content)
            if fin_r and fin_r.year == annee and resultat is None:
                resultat = {'scores': scores, 'autres': autres, 'date': fin_r}
            continue
        nom, url, marque = institut(brut0)
        deb, fin, err = dates(r[cd].content)
        if bad:
            ANOMALIES.append(f'{annee} {chemin} : {nom} {nettoie(r[cd].content)} : valeurs illisibles {bad}')
        if fin is None:
            ANOMALIES.append(f'{annee} {chemin} : {nom} : date illisible {err!r}')
            continue
        lignes.append(dict(
            cle=(c0.uid, r[cd].uid), institut_page=nom, url=url, marque=marque,
            debut=deb, fin=fin,
            echantillon=echantillon(r[ce].content) if ce is not None else None,
            hyp=dict(tour=tour, scores=scores, inferieurs=inf, groupes=groupes, autres=autres),
        ))
    return lignes, resultat


def sections(text):
    """(position, chemin de titres) pour chaque titre."""
    out = []
    for m in re.finditer(r'^(={2,6})\s*(.*?)\s*\1\s*$', text, re.M):
        out.append((m.start(), len(m.group(1)), nettoie(m.group(2))))
    return out


def chemin_a(pos, heads):
    path = []
    for p, lvl, titre in heads:
        if p > pos:
            break
        path = path[:lvl - 2] + [titre]
    return path


# ---------------------------------------------------------------------------
# Instituts : forme normalisée (la forme de la page est conservée à part)
# ---------------------------------------------------------------------------

INSTITUTS = [
    (r'^ifop', 'Ifop'), (r'^ipsos', 'Ipsos'), (r'^(tns )?sofres|^kantar|^tns', 'Kantar-Sofres'),
    (r'^opinionway', 'OpinionWay'), (r'harris', 'Harris Interactive'), (r'^bva', 'BVA'),
    (r'^csa', 'CSA'), (r'^elabe', 'Elabe'), (r'^odoxa', 'Odoxa'), (r'^lh2', 'LH2'),
    (r'^cluster', 'Cluster17'), (r'^yougov', 'YouGov'), (r'^viavoice', 'Viavoice'),
    (r'^cevipof|^ipsos.*cevipof', 'Cevipof'),
]


def institut_norm(nom):
    n = nom.lower()
    for p, v in INSTITUTS:
        if re.search(p, n):
            return v
    return nom


# ---------------------------------------------------------------------------
# Assemblage par élection
# ---------------------------------------------------------------------------

def tour_de(path):
    p = ' > '.join(path).lower()
    if EXCLUS.search(p):
        return None
    if p.startswith('first round'):
        return 1
    if p.startswith('second round'):
        return 2
    return None


def lire_page(annee):
    text = (SNAP / f"{ELECTIONS[annee]['revid']}.wikitext").read_text()
    heads = sections(text)
    lignes, resultats = [], {}
    for ti, (pos, tab) in enumerate(iter_tables(text)):
        path = chemin_a(pos, heads)
        tour = tour_de(path)
        if tour is None:
            continue
        ch = ' > '.join(path)
        l, res = lire_tableau(tab, tour, ch, annee)
        for x in l:
            x['section'] = ch
            x['cle'] = (ti,) + x['cle']
        lignes += l
        if res and tour not in resultats:
            resultats[tour] = res
    return lignes, resultats


# ---------------------------------------------------------------------------
# Candidats : clés alignées sur le référentiel 2027 (nom de famille slugifié)
# ---------------------------------------------------------------------------

CLES_FORCEES = {
    'Jean-Marie Le Pen': 'le-pen-jean-marie',   # 'le-pen' = Marine Le Pen dans candidats.json
    'Dieudonné (comedian)': 'dieudonne',
    "Dieudonné M'bala M'bala": 'dieudonne',
    'Dominique de Villepin': 'villepin',
    'Philippe de Villiers': 'de-villiers',
    'Jack Lang (French politician)': 'lang',
    'Nathalie Kosciusko-Morizet': 'kosciusko-morizet',
}
NOMS_AFFICHES = {'Dieudonné (comedian)': 'Dieudonné', "Dieudonné M'bala M'bala": 'Dieudonné',
                 'Jack Lang (French politician)': 'Jack Lang'}


def cle_candidat(cible, libelles):
    if cible == '__parti__':
        return None
    if cible in CLES_FORCEES:
        return CLES_FORCEES[cible]
    courts = [l for l in libelles if l != cible]
    if courts:
        return slug(max(set(courts), key=courts.count))
    return slug(cible.split(' ', 1)[1] if ' ' in cible else cible)


MARQUES = {  # légendes en tête de chaque page
    2002: {'*': 'sous_echantillon'},
    2007: {'*': 'sous_echantillon'},
    2012: {'*': 'hors_rolling', '**': 'sous_echantillon'},
    2017: {'*': 'hors_rolling', '**': 'hors_commission', '***': 'telephone'},
    2022: {},
}


def est_rolling_note(annee, p):
    """Règles énoncées dans l'introduction de chaque page."""
    m = MARQUES[annee].get(p['marque'])
    if m == 'hors_rolling':
        return False
    f = p['fin']
    if annee == 2007:
        return p['institut'] == 'Ipsos' and f >= datetime.date(2007, 3, 1) and not p['marque']
    if annee == 2012:
        return p['institut_page'] == 'Ifop-Fiducial' and f >= datetime.date(2012, 1, 12)
    if annee == 2017:
        return p['institut_page'] in ('Ifop-Fiducial', 'OpinionWay') and f >= datetime.date(2017, 2, 1)
    if annee == 2002:
        return False  # la page 2007 date le premier rolling français de mars 2007
    return None  # 2022 : pas de note, détection par recouvrement


def assemble(annee):
    PARTIS.clear()
    lignes, resultats = lire_page(annee)
    # 1. clés candidats
    libelles = defaultdict(list)
    for x in lignes:
        h = x['hyp']
        for c in list(h['scores']) + list(h['inferieurs']) + [c for g in h['groupes'] for c in g['candidats']]:
            libelles[c[0]].append(c[1])
    for res in resultats.values():
        for c in res['scores']:
            libelles[c[0]].append(c[1])
    cles = {}
    for cible, libs in libelles.items():
        if cible == '__parti__':
            for l in set(libs):
                cles[('__parti__', l)] = 'candidat-' + slug(l)
        else:
            cles[cible] = cle_candidat(cible, libs)
    def k(c):
        return cles[c] if c[0] == '__parti__' else cles[c[0]]
    inverse = defaultdict(set)
    for cible, cle in cles.items():
        inverse[cle].add(cible if isinstance(cible, str) else cible[1])
    for cle, cibles in inverse.items():
        if len(cibles) > 1 and cle != 'dieudonne':
            ANOMALIES.append(f'{annee} : clé {cle!r} partagée par {sorted(cibles)}')

    def conv(h):
        out = {'tour': h['tour'], 'echantillon': None}
        sc = {k(c): v for c, v in h['scores'].items()}
        out['candidats'] = sorted(set(sc) | {k(c) for c in h['inferieurs']}
                                  | {k(c) for g in h['groupes'] for c in g['candidats']})
        out['scores'] = sc
        if h['inferieurs']:
            out['scores_inferieurs_a'] = {k(c): v for c, v in h['inferieurs'].items()}
        if h['groupes']:
            out['scores_groupes'] = [{'candidats': [k(c) for c in g['candidats']], 'score': g['score']}
                                     for g in h['groupes']]
        if h['autres'] is not None:
            out['autres'] = h['autres']
        return out

    # 2. regroupement
    # a) dans un tableau, les lignes qui partagent la cellule institut (rowspan) sont
    #    les hypothèses d'un même sondage ;
    # b) un même sondage peut figurer au T1 et au T2, avec un libellé ou une date de début
    #    légèrement différents ('Ifop-Fiducial' / 'Ifop') : on rapproche les groupes par
    #    institut, date de fin et échantillon (ou dates exactes si pas d'échantillon).
    groupes = {}
    for x in lignes:
        groupes.setdefault(x['cle'][:2], []).append(x)
    polls = []
    index = defaultdict(list)  # (institut, marque, fin) -> sondages
    for g in groupes.values():
        x0 = g[0]
        inst = institut_norm(x0['institut_page'])
        t1 = any(x['hyp']['tour'] == 1 for x in g)
        ech = next((x['echantillon'] for x in g if x['echantillon']), None)
        cible = None
        cands = sorted(index[(inst, x0['marque'], x0['fin'])],
                       key=lambda p: (p['institut_page'] != x0['institut_page'], p['echantillon'] != ech))
        for p in cands:
            if not (p['debut'] <= x0['fin'] and x0['debut'] <= p['fin']):
                continue
            # deux relevés de T1 avec des échantillons différents = deux sondages distincts
            if t1 and p['t1'] and ech and p['echantillon'] and ech != p['echantillon']:
                continue
            cible = p
            break
        if cible is None:
            cible = dict(institut=inst, institut_page=x0['institut_page'], marque=x0['marque'],
                         debut=x0['debut'], fin=x0['fin'], echantillon=ech, url=x0['url'],
                         hyps=[], t1=False)
            polls.append(cible)
            index[(inst, x0['marque'], x0['fin'])].append(cible)
        if t1 and not cible['t1']:
            # l'échantillon et les dates de référence sont ceux du relevé de premier tour
            cible['t1'] = True
            if ech:
                ancien = cible['echantillon']
                cible['echantillon'] = ech
                for h in cible['hyps']:
                    if h['echantillon'] is None and ancien and ancien != ech:
                        h['echantillon'] = ancien
            cible['debut'] = min(cible['debut'], x0['debut'])
        for x in g:
            h = conv(x['hyp'])
            if x['echantillon'] and cible['echantillon'] and x['echantillon'] != cible['echantillon']:
                h['echantillon'] = x['echantillon']
            if cible['url'] is None:
                cible['url'] = x['url']
            cible['hyps'].append(h)

    # 3. doublons d'hypothèses (même sondage recopié dans deux tableaux)
    doublons = 0
    for p in polls:
        vus, garde = set(), []
        for h in p['hyps']:
            sig = json.dumps(h, sort_keys=True)
            if sig in vus:
                doublons += 1; continue
            vus.add(sig); garde.append(h)
        p['hyps'] = garde

    # 4. rollings
    liste = sorted(polls, key=lambda p: (p['fin'], p['institut']))
    par_inst = defaultdict(list)
    for p in liste:
        par_inst[(p['institut'], p['marque'])].append(p)
    # rolling (détection) : vague qui chevauche une autre vague du même institut
    # et se termine 1 à 2 jours avant ou après (publication quotidienne)
    for grp in par_inst.values():
        for p in grp:
            p['recouvre'] = any(q is not p and q['debut'] <= p['fin'] and p['debut'] <= q['fin']
                                and 1 <= abs((q['fin'] - p['fin']).days) <= 2 for q in grp)
    desaccords = []
    for p in liste:
        note = est_rolling_note(annee, p)
        p['rolling'] = p['recouvre'] if note is None else note
        if note is not None and note != p['recouvre']:
            desaccords.append(p)

    # 5. sortie
    sondages, ids = [], defaultdict(int)
    for p in liste:
        base = f"{slug(p['institut'])}-{p['fin'].isoformat()}"
        ids[base] += 1
        pid = base if ids[base] == 1 else f'{base}-{ids[base]}'
        s = {'id': pid, 'institut': p['institut'], 'institut_page': p['institut_page'],
             'terrain_debut': p['debut'].isoformat(), 'terrain_fin': p['fin'].isoformat(),
             'echantillon': p['echantillon'], 'url_source': p['url'], 'rolling': p['rolling']}
        m = MARQUES[annee].get(p['marque'])
        if p['marque']:
            s['marque_page'] = p['marque']
        if m and m != 'hors_rolling':
            s[m] = True
        for h in p['hyps']:
            t = sum(h['scores'].values()) + sum(g['score'] for g in h.get('scores_groupes', [])) \
                + h.get('autres', 0)
            lo, hi = (95, 105) if h['tour'] == 1 else (99, 101)
            if not lo <= t <= hi:
                h['somme_hors_bornes'] = round(t, 2)
                ANOMALIES.append(f"{annee} {pid} T{h['tour']} : somme {t:g} (valeur de la page)")
        s['hypotheses'] = p['hyps']
        sondages.append(s)

    candidats = {}
    for cible, cle in cles.items():
        if isinstance(cible, tuple):
            candidats[cle] = {'nom': f'Candidat {cible[1]}', 'type': 'parti', 'parti': cible[1],
                              'cible_wikipedia': None}
            continue
        partis = [x for x in PARTIS.get(cible, []) if x]
        if cle in candidats:
            continue
        candidats[cle] = {'nom': NOMS_AFFICHES.get(cible, cible), 'type': 'personne',
                          'partis': sorted(set(partis), key=lambda x: -partis.count(x)),
                          'cible_wikipedia': cible}

    res_out = {}
    for t, r in resultats.items():
        attendu = ELECTIONS[annee][f'tour{t}']
        if r['date'].isoformat() != attendu:
            ANOMALIES.append(f'{annee} : ligne de résultat T{t} datée {r["date"]} (attendu {attendu})')
        res_out[f'tour{t}'] = {k(c): v for c, v in r['scores'].items()}
    stats = dict(lignes=len(lignes), sondages=len(sondages), doublons_retires=doublons,
                 collisions_id=sum(v - 1 for v in ids.values()),
                 rolling_desaccord_note_recouvrement=len(desaccords))
    return dict(sondages=sondages, candidats=candidats, resultats=res_out, stats=stats,
                desaccords=desaccords)


# ---------------------------------------------------------------------------

def telecharger():
    import urllib.request, urllib.parse
    SNAP.mkdir(parents=True, exist_ok=True)
    for annee, e in ELECTIONS.items():
        dest = SNAP / f"{e['revid']}.wikitext"
        if dest.exists():
            continue
        url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode(
            {'action': 'parse', 'oldid': e['revid'], 'prop': 'wikitext', 'format': 'json',
             'formatversion': 2})
        req = urllib.request.Request(url, headers={'User-Agent': 'sondax/1.0 (https://sondax.fr)'})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_text(json.loads(r.read())['parse']['wikitext'])
        print(f'snapshot {dest.name}')


def main():
    if '--telecharger' in sys.argv:
        telecharger()
    out = {
        'source': {
            'site': 'en.wikipedia.org',
            'licence': 'CC BY-SA 4.0',
            'extrait_le': datetime.date.today().isoformat(),
            'script': 'scripts/import_historique.py',
        },
        'elections': {},
    }
    for annee, e in ELECTIONS.items():
        r = assemble(annee)
        out['elections'][str(annee)] = {
            'tour1': e['tour1'], 'tour2': e['tour2'],
            'page': PAGE.format(annee), 'revid': e['revid'],
            'url': f"https://en.wikipedia.org/w/index.php?oldid={e['revid']}",
            'resultats': r['resultats'],
            'candidats': dict(sorted(r['candidats'].items())),
            'sondages': r['sondages'],
        }
        st = r['stats']
        n1 = sum(1 for s in r['sondages'] if any(h['tour'] == 1 for h in s['hypotheses']))
        nh = {t: sum(1 for s in r['sondages'] for h in s['hypotheses'] if h['tour'] == t) for t in (1, 2)}
        nr = sum(1 for s in r['sondages'] if s['rolling'])
        print(f"{annee} : {st['sondages']} sondages ({n1} avec T1), hypothèses T1={nh[1]} T2={nh[2]}, "
              f"rollings={nr}, {len(r['candidats'])} candidats, "
              f"{r['sondages'][0]['terrain_fin']} → {r['sondages'][-1]['terrain_fin']}")
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(f'écrit : {OUTPUT}')
    if ANOMALIES:
        print(f'{len(ANOMALIES)} anomalie(s) :')
        for a in ANOMALIES:
            print('  -', a)


if __name__ == '__main__':
    main()
