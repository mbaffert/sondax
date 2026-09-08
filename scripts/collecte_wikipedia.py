import re, json, unicodedata, datetime

MOIS = {'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
        'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12,'decembre':12}

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
    """Retourne (valeur, candidat_substitué). Une cellule peut remplacer le candidat
    de la colonne : '7,5<br><small>[[François Hollande|Hollande]] (PS)</small>'."""
    parts = re.split(r'<br\s*/?>', txt, maxsplit=1)
    val = clean_num(parts[0])
    sub = None
    if len(parts) > 1:
        m = re.search(r'\[\[[^|\]]+\|([^\]]+)\]\]', parts[1])
        if m:
            sub = re.sub(r'\{\{blanc\|([^}]*)\}\}', r'\1', m.group(1)).strip(" '")
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
            cands.append(m.group(1).strip())
        else:  # colonne générique type 'Candidat RN' : le candidat est dans la cellule
            nom = re.sub(r'^!.*?\|', '', l).strip()
            cands.append(re.sub(r'\[\[|\]\]|<[^>]+>', ' ', nom).strip() or 'Indetermine')
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
                    vals += [(None, None)] * (n - 1)   # colonnes fusionnées
                i += 1
            if vals: cur['hypotheses'].append(vals)
            continue
        i += 1

    out = []
    for s in sondages:
        deb, fin = parse_dates(s['_dates'], annee)
        if not fin: continue
        hyps = []
        for v in s['hypotheses']:
            scores = {}
            for nom, (val, sub) in zip(colonnes, v):
                nom = sub or nom
                if nom != 'Autre' and val is not None: scores[slug(nom)] = val
            if scores: hyps.append({'tour': tour, 'echantillon': None,
                                    'candidats': sorted(scores), 'scores': scores})
        if not hyps: continue
        out.append({'id': f"{slug(s['institut'])}-{fin.isoformat()}",
                    'institut': s['institut'], 'terrain_debut': deb.isoformat(),
                    'terrain_fin': fin.isoformat(), 'echantillon': s['echantillon'],
                    'url_source': s['url_source'], 'hypotheses': hyps})
    return out

# ---- découpage de la page
raw = open('page.wikitext').read()
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

fusion = {}
for s in res:
    if s['id'] in fusion: fusion[s['id']]['hypotheses'] += s['hypotheses']
    else: fusion[s['id']] = s
res = sorted(fusion.values(), key=lambda s: s['terrain_fin'], reverse=True)
json.dump(res, open('sondages.json','w'), ensure_ascii=False, indent=1)

nh = sum(len(s['hypotheses']) for s in res)
print(f"{len(res)} sondages, {nh} hypothèses")
print("période :", res[-1]['terrain_fin'], "→", res[0]['terrain_fin'])
bad = 0
for s in res:
    for h in s['hypotheses']:
        t = sum(h['scores'].values())
        lo, hi = (95,105) if h['tour']==1 else (99,101)
        if not lo <= t <= hi:
            bad += 1
            if bad <= 6: print(f"  HORS BORNES {s['id']} T{h['tour']} somme={t}")
print("hypothèses hors bornes :", bad)
