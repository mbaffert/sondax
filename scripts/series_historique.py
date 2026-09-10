"""Calcul des données front pour la rubrique « Précédentes élections ».

Lit data/historique.json, calcule les séries T1 via series.calculer_series,
prépare les duels T2, et écrit data/derived/historique.json.
"""

import json, pathlib, datetime, colorsys
from collections import defaultdict
from series import calculer_series, score_candidat, poids, choisir_demi_vie, FENETRE_JOURS, MIN_SONDAGES

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORIQUE_PATH = ROOT / "data" / "historique.json"
OUTPUT_PATH = ROOT / "data" / "derived" / "historique.json"

TOUR1_2027 = datetime.date(2027, 4, 18)

# Couleurs par parti (identiques à ref/build_prototype.py)
PARTI_COUL = {
    'FN': '#0D378A', 'RN': '#0D378A', 'LO': '#8B0000', 'NPA': '#F4511E', 'LCR': '#F4511E',
    'PT': '#6E1414', 'POI': '#6E1414',
    'PCF': '#DD1111', 'FG': '#CC2443', 'LFI': '#CC2443', 'FI': '#CC2443',
    'PS': '#FF8080', 'PRG': '#F5A3B8', 'MRC': '#AD1457', 'MDC': '#AD1457',
    'G.s': '#E0609A', 'DVG': '#E57399',
    'EELV': '#2E9E4F', 'LV': '#2E9E4F', 'EE': '#2E9E4F', 'GE': '#5FB36F', 'MEI': '#5FB36F',
    'Cap21': '#7CB87A',
    'UDF': '#F9A825', 'MoDem': '#F9A825', 'NC': '#F4A340', 'UDI': '#F4A340',
    'LREM': '#7E57C2', 'EM': '#7E57C2',
    'RPR': '#2F80ED', 'UMP': '#2F80ED', 'LR': '#2F80ED', 'DL': '#3D86D6', 'DVD': '#5A8FD0',
    'SL': '#5A8FD0', 'PR': '#6FA0D8', 'RS': '#8B6914',
    'DLR': '#1E9BB0', 'DLF': '#1E9BB0', 'MPF': '#6B4F2A', 'RPF': '#6B4F2A',
    'CPNT': '#7A6A3A', 'UPR': '#556B2F', 'LP': '#34495E', 'PCD': '#8D6E63',
    'FRS': '#8D6E63', 'REC': '#1A1A2E', 'MNR': '#3B2A1A', 'RES': '#A1887F',
    'PA': '#26A69A', 'S&P': '#9E9E9E', 'SE': '#8A8F98',
}

FAMILLES = {
    '#FF8080': ['#FF8080', '#D9577E', '#F4AFC0', '#B8405E', '#FF9F80'],
    '#2F80ED': ['#2F80ED', '#4FC3F7', '#9FB3D9', '#5C6BC0', '#1B4F9C'],
    '#CC2443': ['#CC2443', '#E06B7E'], '#2E9E4F': ['#2E9E4F', '#7BC98F'],
    '#F9A825': ['#F9A825', '#FFCC80'], '#0D378A': ['#0D378A', '#4A63B0'],
}

EXTRA = ['#8A8F98', '#607D8B', '#A1887F', '#9575CD', '#4DB6AC', '#AED581',
         '#FFB300', '#78909C', '#BA68C8', '#90A4AE', '#BCAAA4', '#80CBC4']

# Candidats dont la couleur vient du référentiel 2027 quand elle est disponible
REF_2027_CANDS = {'le-pen', 'melenchon', 'zemmour', 'roussel'}


def shade(hexc, k):
    if k == 0:
        return hexc
    r, g, b = [int(hexc[i:i+2], 16) / 255 for i in (1, 3, 5)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = min(0.85, l + 0.13 * k) if l < 0.55 else max(0.2, l - 0.15 * k)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return '#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255))


def nom_court(cid, cand_info):
    if cid == 'le-pen-jean-marie':
        return 'J.-M. Le Pen'
    if cand_info['type'] == 'parti':
        return cand_info['nom']
    n = cand_info['nom']
    return n.split(' ', 1)[1] if ' ' in n else n


def load_ref_2027():
    """Charge le référentiel 2027 pour récupérer les couleurs des candidats communs."""
    path = ROOT / "data" / "candidats.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def traiter_election(annee_str, election, ref_2027):
    annee = int(annee_str)
    t1_date = datetime.date.fromisoformat(election['tour1'])
    t2_date = datetime.date.fromisoformat(election['tour2'])
    borne = f"{annee - 1}-01-01"
    sondages = election['sondages']
    candidats_info = election['candidats']
    resultats = election.get('resultats', {})
    res_t1 = resultats.get('tour1', {})
    res_t2 = resultats.get('tour2', {})

    def jour_relatif(iso_date):
        return (datetime.date.fromisoformat(iso_date) - t1_date).days

    # --- Premier tour ---
    S = calculer_series(sondages)
    if S is None:
        return None

    j0_series = jour_relatif(S['date_debut'])

    # Points bruts dans le périmètre (terrain_debut >= borne)
    debut_par_id = {s['id']: s['terrain_debut'] for s in sondages}
    raw_par_cand = defaultdict(list)
    for p in S['points_bruts']:
        if debut_par_id[p['id']] < borne:
            continue
        for c, v in p['scores'].items():
            raw_par_cand[c].append([jour_relatif(p['d']), v])

    # Sélection des candidats : au moins 3 points bruts dans le périmètre
    cands_t1 = []
    for cid, ser in S['series'].items():
        if len(raw_par_cand.get(cid, [])) < 3:
            continue
        # Série : null avant la borne (filtre d'affichage)
        vals = [None if p['v'] is None or p['d'] < borne else round(p['v'], 1) for p in ser]
        mx = max((v for v in vals if v is not None), default=0)
        cands_t1.append((cid, vals, mx))

    # Couleurs
    used, taken = {}, set()
    cands_t1.sort(key=lambda x: -(res_t1.get(x[0], 0) * 10 + x[2]))
    cands_out = {}
    for cid, vals, mx in cands_t1:
        ci = candidats_info.get(cid, {'nom': cid, 'type': 'personne', 'partis': []})
        partis = ci.get('partis') or [ci.get('parti')]
        parti = partis[0] if partis and partis[0] else 'SE'
        base = PARTI_COUL.get(parti, '#8A8F98')
        fam = FAMILLES.get(base)
        if cid in REF_2027_CANDS and ref_2027.get(cid, {}).get('couleur') not in taken:
            col = ref_2027[cid]['couleur']
        else:
            options = (fam or [base]) + [shade(base, k) for k in range(1, 5)] + EXTRA
            col = next(o for o in options if o not in taken)
        taken.add(col)
        visible = res_t1.get(cid, 0) >= 3 or mx >= 15
        # Compacter la série : trim début/fin des nulls
        i_start = next((k for k, x in enumerate(vals) if x is not None), 0)
        i_end = len(vals) - next((k for k, x in enumerate(reversed(vals)) if x is not None), 0)
        trimmed = vals[i_start:i_end]
        # Encoder en entiers ×10 (format du prototype)
        v_encoded = ','.join('' if x is None else str(int(round(x * 10))) for x in trimmed)
        pts_encoded = [[a, int(round(b * 10))] for a, b in raw_par_cand[cid]]

        cands_out[cid] = {
            'nom': nom_court(cid, ci),
            'parti': parti,
            'couleur': col,
            'resultat': res_t1.get(cid),
            'visible': visible,
            'j0': j0_series + i_start,
            'v': v_encoded,
            'pts': pts_encoded,
            'n': len(raw_par_cand[cid]),
        }

    # Comptages dans le périmètre
    sondages_perimetre = [s for s in sondages if s['terrain_debut'] >= borne]
    t1_perimetre = [s for s in sondages_perimetre if any(h['tour'] == 1 for h in s['hypotheses'])]
    nb_rollings_t1 = sum(1 for s in t1_perimetre if s['rolling'])

    # --- Second tour ---
    duels_raw = {}
    for s in sondages:
        if s['terrain_debut'] < borne:
            continue
        for h in s['hypotheses']:
            if h['tour'] != 2 or len(h['scores']) != 2:
                continue
            pair = sorted(h['scores'].keys())
            key = '|'.join(pair)
            if key not in duels_raw:
                duels_raw[key] = []
            duels_raw[key].append({
                'institut': s['institut'],
                'terrain_debut': s['terrain_debut'],
                'terrain_fin': s['terrain_fin'],
                'echantillon': s.get('echantillon'),
                'jour': jour_relatif(s['terrain_fin']),
                'scores': {c: h['scores'][c] for c in pair},
                'rolling': s.get('rolling', False),
            })

    # Duel final
    duel_final = None
    if res_t2:
        final_pair = sorted(res_t2.keys())
        final_key = '|'.join(final_pair)
        if final_key in duels_raw:
            duel_final = final_key

    duels_out = {}
    for key, mesures in duels_raw.items():
        mesures.sort(key=lambda m: m['terrain_fin'])
        pair = key.split('|')
        entry = {'mesures': mesures}

        # Moyenne glissante T2 (même méthode que T1)
        if len(mesures) >= 5:
            jours = [m['jour'] for m in mesures]
            j_min, j_max = min(jours), max(jours)
            series_t2 = {c: [] for c in pair}
            for j in range(j_min, j_max + 1):
                ages_global = [j - mj for mj in jours if 0 <= j - mj <= FENETRE_JOURS]
                T = choisir_demi_vie(ages_global) if ages_global else 14
                for c in pair:
                    pts_fenetre = []
                    for m in mesures:
                        age = j - m['jour']
                        if 0 <= age <= FENETRE_JOURS:
                            pts_fenetre.append((age, m['scores'][c]))
                    if len(pts_fenetre) < MIN_SONDAGES:
                        series_t2[c].append(None)
                    else:
                        weights = [poids(a, T) for a, _ in pts_fenetre]
                        num = sum(w * sc for w, (_, sc) in zip(weights, pts_fenetre))
                        den = sum(weights)
                        series_t2[c].append(round(num / den, 2))
            # Encode: j0 + array of values (×10, compact)
            entry['series_j0'] = j_min
            for c in pair:
                vals = series_t2[c]
                entry[f'serie_{c}'] = ','.join(
                    '' if v is None else str(int(round(v * 10))) for v in vals
                )

        duels_out[key] = entry

    return {
        'tour1': election['tour1'],
        'tour2': election['tour2'],
        'borne': borne,
        'revid': election['revid'],
        'resultats_t1': res_t1,
        'resultats_t2': res_t2,
        'nb_sondages_perimetre': len(sondages_perimetre),
        'nb_sondages_t1': len(t1_perimetre),
        'nb_rollings_t1': nb_rollings_t1,
        'j_debut': jour_relatif(S['date_debut']),
        'j_fin': jour_relatif(S['date_fin']),
        'candidats': cands_out,
        'duels': duels_out,
        'duel_final': duel_final,
    }


def main():
    historique = json.loads(HISTORIQUE_PATH.read_text())
    ref_2027 = load_ref_2027()

    out = {}
    for annee_str in sorted(historique['elections']):
        election = historique['elections'][annee_str]
        result = traiter_election(annee_str, election, ref_2027)
        if result is None:
            print(f"{annee_str} : aucun sondage T1")
            continue
        out[annee_str] = result

        cands = result['candidats']
        vis = sum(1 for v in cands.values() if v['visible'])
        nb_duels = len(result['duels'])
        nb_mesures_t2 = sum(len(d['mesures']) for d in result['duels'].values())
        final = result['duel_final']
        nb_final = len(result['duels'].get(final, {}).get('mesures', [])) if final else 0
        final_noms = ' – '.join(sorted(
            (cands.get(c, {}).get('nom', c) for c in final.split('|')),
            key=lambda n: n
        )) if final else '—'

        print(f"{annee_str} : T1 {result['nb_sondages_t1']} sondages "
              f"({result['nb_rollings_t1']} rollings), {len(cands)} candidats ({vis} visibles) | "
              f"T2 {nb_duels} duels, {nb_mesures_t2} mesures, "
              f"final {final_noms} ({nb_final})")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"Écrit : {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024} ko)")


if __name__ == '__main__':
    main()
