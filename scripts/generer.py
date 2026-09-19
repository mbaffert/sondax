#!/usr/bin/env python3
"""Génère une page par candidat : identité, courbe, évolution, électorat, origine des voix."""
import json, math, datetime as dt, unicodedata, os, sys

HYP_CROIS = "R. Glucksmann, G. Attal, E. Philippe"
AUJ = dt.date(2026, 9, 19)
ORDRE_PCS = ["Cadres","Prof. intermédiaires","Employés","Ouvriers",
             "Agriculteurs et prof. indépendantes","Retraités CSP+","Retraités CSP-"]
ART = {"Cadres":"les cadres","Prof. intermédiaires":"les professions intermédiaires",
       "Employés":"les employés","Ouvriers":"les ouvriers",
       "Agriculteurs et prof. indépendantes":"les agriculteurs et indépendants",
       "Retraités CSP+":"les retraités aisés","Retraités CSP-":"les retraités modestes"}
JOLI = {"Prof. intermédiaires":"Professions intermédiaires",
        "Agriculteurs et prof. indépendantes":"Agriculteurs, indépendants",
        "Retraités CSP+":"Retraités aisés","Retraités CSP-":"Retraités modestes"}
EXCLUS_2022 = {"Jean Lassalle","Nicolas Dupont-Aignan"}   # lignes non fiables (parser)
MOIS = ['jan','fév','mars','avr','mai','juin','juil','août','sept','oct','nov','déc']

def slugify(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return ''.join(c if c.isalnum() else '-' for c in s.lower()).strip('-')

def fr(x, d=1):
    return f"{x:.{d}f}".replace('.', ',')

def age(naissance):
    n = dt.date.fromisoformat(naissance)
    return AUJ.year - n.year - ((AUJ.month, AUJ.day) < (n.month, n.day))

# ---------- graphique ----------
def svg(serie, bruts, couleur, succession=None):
    W, H, MB, MT = 1000, 400, 30, 22
    xs = [dt.date.fromisoformat(d).toordinal() for d, _ in serie] + \
         [dt.date.fromisoformat(d).toordinal() for d, _ in bruts]
    x0, x1 = min(xs), max(xs)
    ymax = max(max(v for _, v in serie), max(v for _, v in bruts)) * 1.15
    px = lambda o: 6 + (o - x0) / (x1 - x0) * (W - 12)
    py = lambda v: MT + (1 - v / ymax) * (H - MT - MB)
    P = [(px(dt.date.fromisoformat(d).toordinal()), py(v)) for d, v in serie]
    ligne = f"M{P[0][0]:.1f},{P[0][1]:.1f}"
    for i in range(1, len(P)):
        (ax, ay), (bx, by) = P[i-1], P[i]; m = (ax + bx) / 2
        ligne += f" C{m:.1f},{ay:.1f} {m:.1f},{by:.1f} {bx:.1f},{by:.1f}"
    aire = ligne + f" L{P[-1][0]:.1f},{H-MB} L{P[0][0]:.1f},{H-MB} Z"
    pas = 5 if ymax <= 22 else 10
    grille = "".join(
        f'<line x1="0" y1="{py(v):.1f}" x2="{W}" y2="{py(v):.1f}" stroke="currentColor" opacity=".10"/>'
        f'<text x="6" y="{py(v)-5:.1f}" font-size="11" fill="currentColor" opacity=".45" '
        f'font-family="IBM Plex Mono,monospace">{v}%</text>'
        for v in range(pas, int(ymax), pas))
    mois = ""; cur = dt.date.fromordinal(x0).replace(day=1)
    while cur.toordinal() <= x1:
        if cur.toordinal() >= x0:
            mois += (f'<text x="{px(cur.toordinal()):.1f}" y="{H-8}" text-anchor="middle" '
                     f'font-size="11" fill="currentColor" opacity=".45">{MOIS[cur.month-1]}</text>')
        cur = (cur.replace(day=28) + dt.timedelta(days=8)).replace(day=1)
    pts = "".join(f'<circle cx="{px(dt.date.fromisoformat(d).toordinal()):.1f}" cy="{py(v):.1f}" '
                  f'r="3" fill="{couleur}" opacity=".25"/>' for d, v in bruts)
    repere = ""
    if succession:
        dsucc, avant, apres = succession
        xo = dt.date.fromisoformat(dsucc).toordinal()
        if x0 <= xo <= x1:
            X = px(xo)
            cote = "end" if X > W * 0.62 else "start"
            dx = -8 if cote == "end" else 8
            repere = (f'<line x1="{X:.1f}" y1="{MT}" x2="{X:.1f}" y2="{H-MB}" '
                      f'stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 4" opacity=".45"/>'
                      f'<text x="{X+dx:.1f}" y="{MT+13}" text-anchor="{cote}" font-size="11.5" '
                      f'fill="currentColor" opacity=".7">{apres} remplace {avant}</text>')
    gid = "g" + slugify(couleur)
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="none" '
            f'style="display:block;color:var(--texte)" role="img">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{couleur}" stop-opacity=".28"/>'
            f'<stop offset="100%" stop-color="{couleur}" stop-opacity="0"/></linearGradient></defs>'
            f'{grille}{mois}<path d="{aire}" fill="url(#{gid})"/>{pts}{repere}'
            f'<path d="{ligne}" fill="none" stroke="{couleur}" stroke-width="3.2" stroke-linecap="round"/>'
            f'<circle cx="{P[-1][0]:.1f}" cy="{P[-1][1]:.1f}" r="6" fill="{couleur}" '
            f'stroke="var(--carte)" stroke-width="2.5"/></svg>')

# ---------- textes ----------
MOIS_LONG = ['janvier','février','mars','avril','mai','juin','juillet','août',
             'septembre','octobre','novembre','décembre']

def rang_mot(n, f=False):
    m = {1:"premier",2:"deuxième",3:"troisième",4:"quatrième",5:"cinquième",
         6:"sixième",7:"septième",8:"huitième",9:"neuvième",10:"dixième",
         11:"onzième",12:"douzième"}.get(n, f"{n}e")
    return m + "e" if (f and n == 1) else m

def texte_evolution(nom, serie, n_sondages, rangs, ecart_devant, genre="m", succession=None):
    F = (genre == "f")
    IL = "Elle" if F else "Il"
    cur = serie[-1][1]
    d0 = dt.date.fromisoformat(serie[-1][0])
    ref = [v for d, v in serie if dt.date.fromisoformat(d) <= d0 - dt.timedelta(days=91)]
    mx = max(serie, key=lambda x: x[1]); mn = min(serie, key=lambda x: x[1])
    r = [x[1] for x in rangs]
    p = []
    if r:
        actuel = r[-1]
        depuis = dt.date.fromisoformat(rangs[0][0])
        quand = f"{MOIS_LONG[depuis.month-1]} {depuis.year}"
        art = "la" if F else "le"
        if len(set(r)) == 1 and actuel == 1:
            p.append(f"{nom} arrive <b>en tête</b> du premier tour dans tous les sondages "
                     f"depuis que son nom y est testé, en {quand}.")
        elif len(set(r)) == 1:
            p.append(f"{nom} est <b>{rang_mot(actuel, F)}</b> des intentions de vote au premier tour, "
                     f"rang {'qu-elle' if F else 'qu-il'} occupe sans discontinuer depuis {quand}."
                     .replace("qu-elle", "qu'elle").replace("qu-il", "qu'il"))
        else:
            p.append(f"{nom} est <b>{rang_mot(actuel, F)}</b> des intentions de vote au premier tour. "
                     f"Depuis {quand}, {'elle' if F else 'il'} a occupé le "
                     f"{rang_mot(min(r))} comme le {rang_mot(max(r))} rang.")
        if ecart_devant:
            devant, ecart = ecart_devant
            p.append(f"{IL} compte {fr(ecart)} point{'s' if ecart >= 2 else ''} de retard sur {devant}.")
    p.append(f"{IL} est mesuré{'e' if F else ''} à <b>{fr(cur)}&nbsp;%</b>, moyenne pondérée de "
             f"{n_sondages} sondages sur les trente derniers jours.")
    if ref:
        e = cur - ref[-1]
        if abs(e) < 0.7:
            p.append(f"Son niveau n'a pratiquement pas bougé depuis trois mois ({fr(ref[-1])}&nbsp;%).")
        else:
            p.append(f"{IL} a {'gagné' if e > 0 else 'perdu'} {fr(abs(e))} "
                     f"point{'s' if abs(e) >= 2 else ''} en trois mois (contre {fr(ref[-1])}&nbsp;%).")
    if mx[1] - mn[1] >= 1.5:
        p.append(f"Sur l'ensemble de la période mesurée, {'elle' if F else 'il'} oscille entre "
                 f"{fr(mn[1])} et {fr(mx[1])}&nbsp;%.")
    if succession:
        dsucc, avant, apres = succession
        d = dt.date.fromisoformat(dsucc)
        p.append(f"La courbe couvre la candidature de son parti : jusqu'au "
                 f"{d.day} {MOIS_LONG[d.month-1]} {d.year}, les instituts testaient {avant}, "
                 f"que {apres} a remplacé. Les deux n'ont jamais été proposés ensemble.")
    return " ".join(p)

def nat_txt(v):
    return fr(v, 0) if float(v).is_integer() else fr(v, 1)

def texte_electorat(nom, national, pcs, sexe, ages, genre="m"):
    if not pcs: return None
    hi = max(pcs.items(), key=lambda x: x[1]); lo = min(pcs.items(), key=lambda x: x[1])
    ecarts = [abs(v - national) for v in pcs.values()]
    if max(ecarts) < 3:
        t = (f"Le profil de l'électorat de {nom} est remarquablement uniforme : aucune catégorie "
             f"socioprofessionnelle ne s'écarte de plus de trois points de son score national "
             f"de {nat_txt(national)}&nbsp;%.")
    else:
        t = (f"Son électorat est d'abord social : <b>{fr(hi[1], 0)}&nbsp;%</b> chez "
             f"{ART.get(hi[0], hi[0].lower())}, contre <b>{fr(lo[1], 0)}&nbsp;%</b> chez "
             f"{ART.get(lo[0], lo[0].lower())}, pour un score national de {nat_txt(national)}&nbsp;%.")
    if ages:
        jeune = ages.get("18-24 ans"); vieux = ages.get("70 ans et plus")
        if jeune is not None and vieux is not None and abs(jeune - vieux) >= 3:
            sens = "plus jeune" if jeune > vieux else "plus âgé"
            t += (f" L'âge {'la' if genre=='f' else 'le'} distingue nettement : {fr(jeune, 0)}&nbsp;% chez les 18-24 ans contre "
                  f"{fr(vieux, 0)}&nbsp;% chez les 70 ans et plus, soit un électorat sensiblement {sens} "
                  f"que la moyenne des Français.")
    if sexe and abs(sexe.get("Hommes", 0) - sexe.get("Femmes", 0)) >= 3:
        h, f = sexe["Hommes"], sexe["Femmes"]
        t += (f" L'écart entre hommes et femmes est marqué : {fr(h, 0)}&nbsp;% contre {fr(f, 0)}&nbsp;%.")
    elif sexe:
        t += f" Le sexe ne {'la' if genre=='f' else 'le'} distingue presque pas."
    return t


# ---------- second tour ----------
def lien_adv(slug, noms, pages):
    n = noms.get(slug, slug)
    return f'<a href="/candidats/{slug}">{n}</a>' if pages and slug in pages else f'<b>{n}</b>'

def bloc_second_tour(slug, nom, duels, noms, genre="m", pages=None):
    mes = []
    for cle, v in duels.items():
        a, b = cle.split("|")
        if slug not in (a, b): continue
        adv = b if slug == a else a
        mes.append((adv, v))
    if not mes: return "", ""
    mes.sort(key=lambda x: -len(x[1]))
    F = (genre == "f")
    lignes = ""
    gagne, perd = [], []
    for adv, v in mes:
        der = v[-1]
        moi, lui = der["s"][slug], der["s"][adv]
        (gagne if moi > lui else perd).append(noms.get(adv, adv))
        detail = ""
        if len(v) >= 5:
            xs = [x["s"][slug] for x in v]
            detail = (f"{len(v)} mesures depuis {dt.date.fromisoformat(v[0]['d']).strftime('%m/%Y')}, "
                      f"entre {fr(min(xs),0)} et {fr(max(xs),0)} %")
        else:
            detail = f"{len(v)} mesure{'s' if len(v) > 1 else ''} seulement"
        gagnant = moi > lui
        lignes += (f'<div class="duel{" gagne" if gagnant else ""}">'
                   f'<div class="duel-adv">face à {lien_adv(adv, noms, pages)}</div>'
                   f'<div class="duel-barre"><span style="width:{moi}%"></span>'
                   f'<em class="moi">{fr(moi,0)}</em><em class="lui">{fr(lui,0)}</em></div>'
                   f'<div class="duel-note">{detail}</div></div>')
    if gagne and not perd:
        intro = (f"{nom} l'emporte dans {'tous les duels' if len(gagne) > 1 else 'le seul duel'} "
                 f"de second tour {'testés' if len(gagne) > 1 else 'testé'} par les instituts.")
    elif perd and not gagne:
        intro = (f"{nom} est {'battue' if F else 'battu'} dans "
                 f"{'tous les duels de second tour testés' if len(perd) > 1 else 'le seul duel de second tour testé'} "
                 f"par les instituts, face à {', '.join(perd)}.")
    else:
        intro = (f"{nom} l'emporte face à {', '.join(gagne)}, mais est "
                 f"{'battue' if F else 'battu'} par {', '.join(perd)}.")
    if all(len(v) < 5 for _, v in mes):
        intro += (" Attention : trop peu de mesures pour parler de tendance, ces chiffres sont "
                  "des relevés ponctuels.")
    corps = (f'<section class="carte"><div class="pad">'
             f'<div class="label">Second tour</div><h2>{nom} au second tour</h2>'
             f'<div class="sous">Dernière mesure de chaque duel testé</div>'
             f'<div class="txt"><p>{intro}</p></div>{lignes}</div></section>')
    return corps, intro

# ---------- barres ----------
def barres_ecart(rows, national, couleur):
    amp = max(4, max(abs(v - national) for _, v in rows))
    out = ""
    for lab, v in rows:
        e = v - national; w = abs(e) / amp * 48
        cote = f"left:50%;width:{w:.1f}%" if e > 0 else f"right:50%;width:{w:.1f}%"
        cls = "pos" if e > 0 else "neg"
        out += (f'<div class="ligne"><div class="lab">{JOLI.get(lab, lab)}</div>'
                f'<div class="piste"><span class="axe"></span>'
                f'<span class="barre {cls}" style="{cote}"></span></div>'
                f'<div class="val">{fr(v,0)}&nbsp;%<em>{"+" if e>0 else ""}{fr(e,0)}</em></div></div>')
    return out

def barres_simple(rows):
    mx = max(v for _, v in rows) or 1
    return "".join(f'<div class="ligne s"><div class="lab">{lab}</div>'
                   f'<div class="piste"><span class="barre pos" style="left:0;width:{v/mx*100:.1f}%"></span></div>'
                   f'<div class="val">{fr(v,0)}&nbsp;%</div></div>' for lab, v in rows)

CSS = open(os.path.join(os.path.dirname(__file__), "style-candidat.css")).read()

PHOTOS = {}      # slug -> data-URI ou chemin, injecté par le script appelant
CREDITS = {}     # slug -> {"auteur":..., "licence":..., "page":...}

def portrait_html(slug, nom, fiche):
    src = PHOTOS.get(slug)
    if not src:
        ini = ''.join(w[0] for w in nom.split()[:2]).upper()
        return f'<div class="portrait" aria-hidden="true">{ini}</div>'
    return f'<img class="portrait" src="{src}" alt="{nom}" width="104" height="104" loading="lazy">'

def credit_html(slug):
    c = CREDITS.get(slug)
    if not c: return ""
    a = f'<a href="{c["page"]}" rel="nofollow">{c["licence"]}</a>'
    return f'<div class="credit">Portrait : {c["auteur"]} — {a}, via Wikimedia Commons</div>'

def liens_autres(slug, noms):
    return " · ".join(f'<a href="/candidats/{s}">{n}</a>'
                      for s, n in noms.items() if s != slug)

def page(slug, fiche, serie, bruts, n_sondages, crois, base, rangs, ecart_devant,
         duels=None, noms=None, pages=None, succession=None):
    nom = fiche["nom"]; coul = fiche["couleur"]
    pcs = {k: v[slug] for k, v in crois.get("pcs", {}).items()
           if slug in v and k in ORDRE_PCS}
    sexe = {k: v[slug] for k, v in crois.get("sexe", {}).items() if slug in v}
    ages = {k: v[slug] for k, v in crois.get("age", {}).items() if slug in v}
    nat = crois.get("_national", {}).get(slug)
    rep = [(k, v[slug]) for k, v in crois.get("vote-2022", {}).items()
           if slug in v and k not in EXCLUS_2022]
    rep.sort(key=lambda x: -x[1]); rep = [r for r in rep if r[1] >= 1][:10]

    blocs = []
    bloc2t, _ = bloc_second_tour(slug, nom, duels or {}, noms or {}, fiche.get("genre","m"), pages)
    if bloc2t: blocs.append(bloc2t)
    if pcs and nat is not None:
        rows = [(k, pcs[k]) for k in ORDRE_PCS if k in pcs]
        rows.sort(key=lambda x: -x[1])
        blocs.append(f'''<section class="carte"><div class="pad">
  <div class="label">Électorat</div><h2>Qui vote pour {nom}&nbsp;?</h2>
  <div class="sous">Écart à son score national, par profession</div>
  <div class="txt"><p>{texte_electorat(nom, nat, pcs, sexe, ages, fiche.get("genre","m"))}</p></div>
  <div class="ref">Score national : {fr(nat,0)}&nbsp;%</div>
  {barres_ecart(rows, nat, coul)}
</div></section>''')
    if rep:
        blocs.append(f'''<section class="carte"><div class="pad">
  <div class="label">Origine des voix</div><h2>D'où vient son électorat</h2>
  <div class="sous">Part de chaque électorat de 2022 qui voterait {nom} aujourd'hui</div>
  {barres_simple(rep)}
</div></section>''')

    bio = "".join(f"<li>{x}</li>" for x in fiche["bio"])
    return f'''<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{nom} — sondages présidentielle 2027 : intentions de vote et électorat | Sondax</title>
<meta name="description" content="Sondages {nom} pour la présidentielle 2027 : moyenne des intentions de vote au premier tour, évolution, duels de second tour et profil de son électorat.">
<link rel="canonical" href="https://sondax.fr/candidats/{slug}">
<meta property="og:title" content="{nom} — sondages présidentielle 2027">
<meta property="og:description" content="Intentions de vote, second tour et électorat de {nom}.">
<meta property="og:type" content="article">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<style>{CSS.replace("__COULEUR__", coul)}</style><script type="application/ld+json">{{
"@context":"https://schema.org","@type":"Person","name":"{nom}",
"affiliation":{{"@type":"Organization","name":"{fiche['parti']}"}},
"subjectOf":{{"@type":"WebPage","name":"Sondages {nom} — présidentielle 2027",
"url":"https://sondax.fr/candidats/{slug}"}}}}</script>
</head><body><div class="page-candidat"><main>
<div class="fil"><a href="/">Sondax</a> › Candidats › {nom}</div>
<section class="carte hero"><div class="pad">
  {portrait_html(slug, nom, fiche)}
  <div class="ident"><span class="parti">{fiche["parti"]}</span><h1>{nom.replace(' ','&nbsp;',1)}</h1>
  <div class="statut">{age(fiche["naissance"])} ans</div></div>
</div><ul class="bio">{bio}</ul></section>
<section class="carte">
  <div class="pad" style="padding-bottom:12px"><div class="label">Tendance</div>
  <h2>Sondages {nom} : évolution des intentions de vote</h2>
  <div class="sous">Moyenne pondérée sur 30 jours · premier tour · hypothèse principale de chaque sondage</div></div>
  <div class="chart">{svg(serie, bruts, coul, succession)}</div>
  <div class="txt" style="padding-bottom:26px"><p>{texte_evolution(nom, serie, n_sondages, rangs, ecart_devant, fiche.get("genre","m"), succession)}</p></div>
</section>
{''.join(blocs)}
<nav class="autres"><span>Autres candidats :</span> {liens_autres(slug, pages or {})}</nav>
<footer><p>Sondages issus de la page Wikipédia « Liste de sondages sur l'élection présidentielle
française de 2027 », sous licence CC BY-SA. Croisements issus de la notice déposée par Ipsos bva
auprès de la commission des sondages.</p>
<p>Les effectifs par catégorie n'étant pas publiés, aucune marge d'erreur par sous-groupe ne peut
être calculée.</p>
{credit_html(slug)}</footer></main></div></body></html>'''
