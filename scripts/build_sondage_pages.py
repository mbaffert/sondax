#!/usr/bin/env python3
"""Génère une page HTML par sondage dans site/sondages/<id>.html.

Données sources :
- data/sondages.json
- data/candidats.json
- data/derived/series-t1.json  (écart à la moyenne)
- scripts/bios.json (slugs avec page dédiée)

Chaque page porte un chapô rédigé au build à partir des données (podium,
évolution depuis le précédent sondage de l'institut, hypothèses testées,
duels de second tour), sur le modèle du chapeau de l'accueil
(build_index_premier_tour.py) : texte déterministe, sans appel à un modèle.
"""

import json
import math
import pathlib
import re
import html as html_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SITE = ROOT / "site"

import sys
sys.path.insert(0, str(SCRIPTS))
from site_template import render_page
from instituts import charger_referentiel, lien_institut
from balise_time import time_tag
from pages_second_tour import load_duels

referentiel = charger_referentiel()

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

# ---------- chargement ----------

sondages = json.loads((ROOT / "data" / "sondages.json").read_text(encoding="utf-8"))
candidats = json.loads((ROOT / "data" / "candidats.json").read_text(encoding="utf-8"))
bios = json.loads((SCRIPTS / "bios.json").read_text(encoding="utf-8"))

series_path = ROOT / "data" / "derived" / "series-t1.json"
series_data = json.loads(series_path.read_text(encoding="utf-8")) if series_path.exists() else {}

# Ensemble des slugs ayant une page dédiée
slugs_avec_page = set(bios.keys())

# Duels ayant une page /second-tour/<slug>.html (pages_second_tour.py en
# génère une pour chaque duel mesuré ; slug = clés triées, jointes par un tiret)
duels_avec_page = set(load_duels()[0].keys())


# ---------- ordre chronologique ----------

# Tous instituts confondus, pour la navigation précédent / suivant
chronologie = sorted(
    sondages, key=lambda s: (s["terrain_fin"], s.get("terrain_debut", ""), s["id"])
)


def prev_next(sondage):
    """Retourne (prev_sondage, next_sondage) dans l'ordre chronologique global."""
    idx = next((i for i, s in enumerate(chronologie) if s["id"] == sondage["id"]), -1)
    if idx < 0:
        return None, None
    prev_s = chronologie[idx - 1] if idx > 0 else None
    next_s = chronologie[idx + 1] if idx < len(chronologie) - 1 else None
    return prev_s, next_s


def precedent_meme_institut(sondage):
    """Dernier sondage du même institut, antérieur et comportant un tour 1."""
    idx = next(i for i, s in enumerate(chronologie) if s["id"] == sondage["id"])
    for s in reversed(chronologie[:idx]):
        if s["institut"] == sondage["institut"] and hypothese_principale(s):
            return s
    return None


# ---------- moyenne pondérée à une date ----------

def moyenne_a_date(cid, date_iso):
    """Retourne la valeur de la série lissée pour `cid` à `date_iso`, ou None."""
    pts = series_data.get("series", {}).get(cid, [])
    val = None
    for p in pts:
        if p["d"] > date_iso:
            break
        if p["v"] is not None:
            val = p["v"]
    return val


# ---------- helpers ----------

def candidate_full_name(cid):
    c = candidats.get(cid)
    if not c:
        return cid
    prenom = c.get("prenom", "")
    nom = c.get("nom", "")
    parts = [p for p in (prenom, nom) if p]
    return " ".join(parts) if parts else cid


def date_lettres(iso):
    """'2026-08-25' → '25 août 2026'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def fmt_ech(n):
    return f"{round(n):,}".replace(",", "\u202f")


def fmt_pct(v):
    return f"{v:.1f}".replace(".", ",") + "\u202f%"


def marge_erreur(score, n):
    p = score / 100.0
    if n <= 0 or p <= 0 or p >= 1:
        return None
    return 1.96 * math.sqrt(p * (1 - p) / n) * 100


def candidate_link(cid, nom_complet):
    esc = html_mod.escape(nom_complet)
    if cid in slugs_avec_page:
        return f'<a href="../{html_mod.escape(cid)}.html">{esc}</a>'
    return esc


def is_type_parti(cid):
    return candidats.get(cid, {}).get("type") == "parti"


# ---------- texte rédigé ----------
# Même mécanique que le chapeau de l'accueil : chaque phrase est calculée à
# partir des données et omise si une donnée manque. Chiffres au format
# français, espace insécable avant « % ».

NOMBRES = [
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
    "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf", "vingt",
]


def nombre_lettres(n, feminin=False):
    if n == 1:
        return "une" if feminin else "un"
    return NOMBRES[n] if 0 <= n < len(NOMBRES) else str(n)


def majuscule(texte):
    return texte[:1].upper() + texte[1:]


def enumeration_fr(items, conj="et"):
    """['A', 'B', 'C'] → 'A, B et C'"""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {conj} " + items[-1]


def fmt_nombre(v):
    """33.0 → '33', 14.5 → '14,5'"""
    v = round(v, 1)
    return str(int(v)) if v == int(v) else f"{v:.1f}".replace(".", ",")


def fmt_pct_txt(v):
    return fmt_nombre(v) + "\u00a0%"


def fmt_points(delta):
    d = abs(delta)
    return f"{fmt_nombre(d)}\u00a0{'point' if d < 2 else 'points'}"


def jour_mois(iso, annee=True):
    """'2026-09-01' → '1er septembre 2026'"""
    y, m, d = iso.split("-")
    jour = "1er" if int(d) == 1 else str(int(d))
    return f"{jour} {MOIS[int(m) - 1]}" + (f" {y}" if annee else "")


def terrain_lettres(debut, fin):
    """Période de terrain : 'du 24 au 25 août 2026', 'le 10 juillet 2026',
    chaque borne dans une balise <time>."""
    fin_t = time_tag(fin, jour_mois(fin))
    if not debut or debut == fin:
        return f"le {fin_t}"
    if debut[:4] != fin[:4]:
        return f"du {time_tag(debut, jour_mois(debut))} au {fin_t}"
    if debut[:7] == fin[:7]:
        return f"du {time_tag(debut, jour_mois(debut).split(' ')[0])} au {fin_t}"
    return f"du {time_tag(debut, jour_mois(debut, annee=False))} au {fin_t}"


def nom_court(cid):
    return candidats.get(cid, {}).get("nom", cid)


def genre(cid):
    return candidats.get(cid, {}).get("genre", "m")


def scores_tries(hyp):
    return sorted(
        ((cid, v) for cid, v in hyp.get("scores", {}).items() if cid != "autre"),
        key=lambda kv: -kv[1],
    )


def candidats_hyp(hyp):
    return set(hyp.get("scores", {})) - {"autre"}


def hypothese_principale(sondage):
    """Hypothèse T1 marquée principale (principale.py), sinon la plus fournie."""
    t1 = [h for h in sondage.get("hypotheses", []) if h.get("tour") == 1]
    if not t1:
        return None
    for h in t1:
        if h.get("principale"):
            return h
    return max(t1, key=lambda h: len(candidats_hyp(h)))


def duels(sondage):
    return [
        h for h in sondage.get("hypotheses", [])
        if h.get("tour") == 2 and len(candidats_hyp(h)) == 2
    ]


def phrase_podium(principale):
    """a. « Marine Le Pen arrive en tête avec 33 %, devant X (16 %) et Y (14,5 %). »"""
    top = scores_tries(principale)
    if not top:
        return None
    score_1 = top[0][1]
    tete = [cid for cid, v in top if v == score_1]
    if len(tete) > 1:
        noms = enumeration_fr([candidate_full_name(c) for c in tete])
        phrase = f"{noms} arrivent en tête à égalité avec {fmt_pct_txt(score_1)}"
        suivants = top[len(tete):3] if len(tete) < 3 else []
    else:
        phrase = f"{candidate_full_name(tete[0])} arrive en tête avec {fmt_pct_txt(score_1)}"
        suivants = top[1:3]
    if suivants:
        autres = [f"{candidate_full_name(c)} ({fmt_pct_txt(v)})" for c, v in suivants]
        phrase += f", devant {enumeration_fr(autres)}"
    return html_mod.escape(phrase) + "."


def phrase_evolution(sondage, principale):
    """b. Évolution des trois premiers depuis le précédent sondage de l'institut.

    Comparaison d'hypothèse principale à hypothèse principale : un candidat
    absent de celle du précédent sondage est signalé, jamais comparé à une
    autre configuration.
    """
    institut = sondage["institut"]
    prec = precedent_meme_institut(sondage)
    if prec is None:
        return html_mod.escape(f"C\u2019est le premier sondage {institut} de la série.")

    top = [cid for cid, _ in scores_tries(principale)[:3]]
    if not top:
        return None
    avant = hypothese_principale(prec)["scores"]
    actuel = principale["scores"]

    mouvements, stables, absents = {}, [], []
    for cid in top:
        if cid not in avant:
            absents.append(cid)
            continue
        delta = round(actuel[cid] - avant[cid], 1)
        if abs(delta) >= 1:
            # Mouvements identiques regroupés : « Le Pen et Mélenchon gagnent 1 point »
            mouvements.setdefault(delta, []).append(nom_court(cid))
        else:
            stables.append(nom_court(cid))

    fragments = []
    for delta, noms in mouvements.items():
        if delta > 0:
            verbe = "gagne" if len(noms) == 1 else "gagnent"
        else:
            verbe = "perd" if len(noms) == 1 else "perdent"
        fragments.append(f"{enumeration_fr(noms)} {verbe} {fmt_points(delta)}")
    if stables:
        verbe = "est stable" if len(stables) == 1 else "sont stables"
        fragments.append(f"{enumeration_fr(stables)} {verbe}")
    # Mouvements et stables séparés par des virgules, l'absence par un point-virgule
    texte = ", ".join(fragments)
    if absents:
        verbe = "ne figurait pas" if len(absents) == 1 else "ne figuraient pas"
        verbe += " dans son hypothèse principale"
        absence = f"{enumeration_fr([nom_court(c) for c in absents])} {verbe}"
        texte = f"{texte}\u00a0; {absence}" if texte else absence

    meme_annee = prec["terrain_fin"][:4] == sondage["terrain_fin"][:4]
    ref = (f"l\u2019enquête {html_mod.escape(institut)} du "
           f"{time_tag(prec['terrain_fin'], jour_mois(prec['terrain_fin'], annee=not meme_annee))}")
    lien = f'<a href="{html_mod.escape(prec["id"])}.html">{ref}</a>'
    return f"Par rapport à {lien}, {html_mod.escape(texte)}."


def phrase_hypotheses(t1, principale):
    """c. Nombre de configurations testées et ce qui les distingue."""
    n = len(t1)
    if n == 0:
        return None
    if n == 1:
        return "L\u2019institut n\u2019a testé qu\u2019une configuration de premier tour."

    base = candidats_hyp(principale)
    autres = [h for h in t1 if h is not principale]
    # Candidats de l'hypothèse principale absents d'au moins une autre
    alternants = [c for c in sorted(base) if any(c not in candidats_hyp(h) for h in autres)]
    # Candidats absents de l'hypothèse principale, ajoutés ailleurs
    entrants = {}
    for h in autres:
        for c in sorted(candidats_hyp(h) - base):
            entrants[c] = entrants.get(c, 0) + 1

    # Les candidats à 5 % ou plus suffisent à caractériser les configurations ;
    # à défaut, tous les candidats qui varient
    scores_p = principale["scores"]
    notables = [c for c in alternants if scores_p[c] >= 5] or alternants
    notables = sorted(notables, key=lambda c: -scores_p[c])[:3]
    max_score = {c: max(h["scores"].get(c, 0) for h in autres) for c in entrants}
    entrants_tries = sorted(entrants, key=lambda c: -max_score[c])[:3]

    debut = f"L\u2019institut a testé {nombre_lettres(n, feminin=True)} configurations"
    frag_entrants = []
    for i, c in enumerate(entrants_tries):
        k = nombre_lettres(entrants[c], feminin=True)
        if i == 0:
            mot = "hypothèse" if entrants[c] == 1 else "hypothèses"
            frag_entrants.append(f"{k} {mot} avec {candidate_full_name(c)}")
        else:
            frag_entrants.append(f"{k} avec {candidate_full_name(c)}")

    if notables:
        phrase = f"{debut}, avec ou sans {enumeration_fr([candidate_full_name(c) for c in notables])}"
        if frag_entrants:
            suite = enumeration_fr(frag_entrants)
            elision = "qu\u2019" if suite.startswith("un") else "que "
            phrase += f", ainsi {elision}{suite}"
    elif frag_entrants:
        phrase = f"{debut}, dont {enumeration_fr(frag_entrants)}"
    else:
        phrase = f"{debut} avec la même liste de candidats"
    return html_mod.escape(phrase) + "."


def fmt_duel(hyp):
    (_, a), (_, b) = scores_tries(hyp)
    return f"{fmt_nombre(a)}-{fmt_nombre(b)}"


def phrase_duels(t2):
    """d. Nombre de duels, vainqueur, duel le plus serré."""
    n = len(t2)
    if n == 0:
        return None
    issues = []  # (vainqueur ou None, perdant/adversaire, écart, hyp)
    for h in t2:
        (ca, a), (cb, b) = scores_tries(h)
        issues.append((ca if a > b else None, cb, ca, round(a - b, 1), h))

    if n == 1:
        v, cb, ca, ecart, h = issues[0]
        if v:
            return html_mod.escape(
                f"Un seul duel de second tour a été testé\u00a0: {nom_court(ca)} "
                f"l\u2019emporte face à {nom_court(cb)} ({fmt_duel(h)})."
            )
        return html_mod.escape(
            f"Un seul duel de second tour a été testé\u00a0: {nom_court(ca)} et "
            f"{nom_court(cb)} sont à égalité ({fmt_duel(h)})."
        )

    phrases = [f"{majuscule(nombre_lettres(n))} duels de second tour ont été testés."]
    ecart_min = min(i[3] for i in issues)
    serres = [i for i in issues if i[3] == ecart_min]

    communs = set.intersection(*(candidats_hyp(h) for h in t2))
    if len(communs) == 1:
        pivot = communs.pop()
        victoires = sum(1 for i in issues if i[0] == pivot)
        if victoires == n:
            face = " et ".join(
                f"{'face ' if k == 0 else ''}à {nom_court(i[1])} ({fmt_duel(i[4])})"
                for k, i in enumerate(serres)
            )
            tous = "les deux" if n == 2 else "tous"
            phrases.append(
                f"{majuscule(nom_court(pivot))} l\u2019emporte dans {tous}, "
                f"avec un écart minimal {face}."
            )
            return html_mod.escape(" ".join(phrases))
        if victoires == 0 and all(i[0] for i in issues):
            battu = "battue" if genre(pivot) == "f" else "battu"
            tous = "les deux" if n == 2 else "tous"
            phrases.append(f"{majuscule(nom_court(pivot))} est {battu} dans {tous}.")
        else:
            phrases.append(
                f"{majuscule(nom_court(pivot))} l\u2019emporte dans "
                f"{nombre_lettres(victoires)} des {nombre_lettres(n)}."
            )
    else:
        compte = {}
        for i in issues:
            if i[0]:
                compte[i[0]] = compte.get(i[0], 0) + 1
        if compte:
            ordre = sorted(compte, key=lambda c: -compte[c])
            frags = []
            for k, c in enumerate(ordre):
                nb = nombre_lettres(compte[c])
                if k == 0:
                    frags.append(f"{majuscule(nom_court(c))} l\u2019emporte dans "
                                 f"{nb} duel{'s' if compte[c] > 1 else ''}")
                else:
                    frags.append(f"{nom_court(c)} dans {nb}")
            phrases.append(enumeration_fr(frags) + ".")

    duels_serres = [
        f"{nom_court(i[2])} à {nom_court(i[1])} ({fmt_duel(i[4])})" for i in serres
    ]
    if ecart_min == 0:
        phrases.append(f"Le duel le plus serré est à égalité\u00a0: {enumeration_fr(duels_serres)}.")
    else:
        verbe = "oppose" if len(serres) == 1 else "opposent"
        sujet = "Le duel le plus serré" if len(serres) == 1 else "Les duels les plus serrés"
        phrases.append(f"{sujet} {verbe} {enumeration_fr(duels_serres)}.")
    return html_mod.escape(" ".join(phrases))


def chapo_phrases(sondage):
    """Liste des phrases du chapô (HTML), dans l'ordre a, b, c, d."""
    t1 = [h for h in sondage.get("hypotheses", []) if h.get("tour") == 1]
    principale = hypothese_principale(sondage)
    phrases = []
    if principale:
        phrases += [
            phrase_podium(principale),
            phrase_evolution(sondage, principale),
            phrase_hypotheses(t1, principale),
        ]
    phrases.append(phrase_duels(duels(sondage)))
    return [p for p in phrases if p]


def texte_brut(fragment_html):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", fragment_html))


def meta_description_chapo(phrases, limite=155):
    """Première phrase du chapô, plus la seconde si l'ensemble tient en 155 caractères."""
    brutes = [texte_brut(p) for p in phrases]
    if not brutes:
        return ""
    texte = brutes[0]
    if len(brutes) > 1 and len(texte) + 1 + len(brutes[1]) <= limite:
        texte += " " + brutes[1]
    return html_mod.escape(texte)


def libelle_hypothese(i, hyp, principale):
    """« Hypothèse 2 — sans Attal », calculé par différence avec la principale."""
    label = f"Hypothèse\u00a0{i}"
    if hyp is principale or principale is None:
        return label
    base, mine = candidats_hyp(principale), candidats_hyp(hyp)
    avec = sorted(sorted(mine - base), key=lambda c: -hyp["scores"][c])
    sans = sorted(sorted(base - mine), key=lambda c: -principale["scores"][c])
    parts = []
    if avec:
        parts.append("avec " + enumeration_fr([nom_court(c) for c in avec]))
    if sans:
        parts.append("sans " + enumeration_fr([nom_court(c) for c in sans]))
    if not parts:
        return label
    return f"{label} \u2014 {html_mod.escape(', '.join(parts))}"


def slug_duel(hyp):
    return "-".join(sorted(candidats_hyp(hyp)))


# ---------- construction d'une hypothèse ----------

def build_hypothesis_html(hyp, sondage_echantillon, is_principale, terrain_fin, label=""):
    tour = hyp.get("tour", "?")
    hyp_ech = hyp.get("echantillon")
    scores = hyp.get("scores", {})

    sorted_scores = sorted(
        ((cid, v) for cid, v in scores.items() if cid != "autre"),
        key=lambda kv: kv[1], reverse=True,
    )

    # Header
    parts = []
    if label:
        parts.append(label)
    if is_principale:
        parts.append('<span class="badge badge-principale">Principale</span>')
    if hyp_ech:
        parts.append(f'<span class="hyp-detail">{fmt_ech(hyp_ech)}\u202fpersonnes</span>')

    # Note marge approximative
    approx_me = not hyp_ech and sondage_echantillon
    n_for_me = hyp_ech if hyp_ech else sondage_echantillon

    # Colonnes : candidat, score, marge, (écart si principale T1)
    show_ecart = is_principale and tour == 1

    # En-tête de tableau
    cols_th = '<th>Candidat</th><th class="col-score">Score</th><th class="col-me">Marge</th>'
    if show_ecart:
        cols_th += '<th class="col-ecart">Écart / moy.</th>'

    rows = []
    for cid, score in sorted_scores:
        nom = candidate_full_name(cid)
        link = candidate_link(cid, nom)
        parti_cls = ' class="type-parti"' if is_type_parti(cid) else ""

        me = marge_erreur(score, n_for_me) if n_for_me else None
        me_str = f"±\u202f{me:.1f}\u202f%" if me is not None else "\u2014"
        if me is not None and approx_me:
            me_str += ' <span class="me-approx">(approx.)</span>'

        ecart_cell = ""
        if show_ecart:
            moy = moyenne_a_date(cid, terrain_fin)
            if moy is not None:
                delta = round(score - moy, 1)
                sign = "+" if delta > 0 else ""
                ecart_cell = f'<td class="col-ecart">{sign}{delta:.1f}'.replace(".", ",") + "\u202fpt</td>"
            else:
                ecart_cell = '<td class="col-ecart">\u2014</td>'

        couleur = candidats.get(cid, {}).get("couleur", "#888")
        bar_w = min(max(score, 0), 60)

        rows.append(
            f'    <tr{parti_cls}>'
            f'<td class="cand-name">{link}</td>'
            f'<td class="col-score"><span class="bar" style="width:{bar_w:.0f}%;background:{couleur}"></span>'
            f'{fmt_pct(score)}</td>'
            f'<td class="col-me">{me_str}</td>'
            f'{ecart_cell}'
            f'</tr>'
        )

    header_html = " ".join(parts)
    rows_html = "\n".join(rows)

    note = ""
    if approx_me:
        note = '<p class="note-approx">Marge approximative, calculée sur l\u2019échantillon total.</p>'

    return f"""<div class="hypothese{' hyp-principale' if is_principale else ''}">
  <div class="hyp-header">{header_html}</div>
  <table class="scores-table">
    <thead><tr>{cols_th}</tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
  {note}
</div>"""


def build_duel_html(hyp, sondage_echantillon):
    """Construit un bloc pour un duel de second tour."""
    scores = hyp.get("scores", {})
    hyp_ech = hyp.get("echantillon")
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if len(sorted_scores) != 2:
        return ""

    (cid_a, score_a), (cid_b, score_b) = sorted_scores
    nom_a = candidate_link(cid_a, candidate_full_name(cid_a))
    nom_b = candidate_link(cid_b, candidate_full_name(cid_b))
    couleur_a = candidats.get(cid_a, {}).get("couleur", "#888")
    couleur_b = candidats.get(cid_b, {}).get("couleur", "#888")

    n_for_me = hyp_ech if hyp_ech else sondage_echantillon
    me_a = marge_erreur(score_a, n_for_me) if n_for_me else None
    me_b = marge_erreur(score_b, n_for_me) if n_for_me else None
    me_a_str = f"±\u202f{me_a:.1f}\u202f%" if me_a else ""
    me_b_str = f"±\u202f{me_b:.1f}\u202f%" if me_b else ""

    lien = ""
    slug = slug_duel(hyp)
    if slug in duels_avec_page:
        a, b = (nom_court(c) for c in sorted(candidats_hyp(hyp)))
        lien = (
            f'  <a class="duel-lien" href="../second-tour/{html_mod.escape(slug)}.html">'
            f'Tous les sondages {html_mod.escape(a)} \u2013 {html_mod.escape(b)} \u2192</a>\n'
        )

    return f"""<div class="duel">
  <div class="duel-bar">
    <span class="duel-part" style="width:{score_a:.1f}%;background:{couleur_a}"></span>
    <span class="duel-part" style="width:{score_b:.1f}%;background:{couleur_b}"></span>
  </div>
  <div class="duel-labels">
    <span class="duel-cand">{nom_a} <strong>{fmt_pct(score_a)}</strong> <span class="duel-me">{me_a_str}</span></span>
    <span class="duel-cand duel-cand-right">{nom_b} <strong>{fmt_pct(score_b)}</strong> <span class="duel-me">{me_b_str}</span></span>
  </div>
{lien}</div>"""


# ---------- page complète ----------

def build_page(sondage):
    sid = sondage["id"]
    institut = sondage.get("institut", "")
    terrain_debut = sondage.get("terrain_debut", "")
    terrain_fin = sondage.get("terrain_fin", "")
    echantillon = sondage.get("echantillon")
    population = sondage.get("population")
    url_source = sondage.get("url_source", "")
    hypotheses = sondage.get("hypotheses", [])

    # Titre et SEO
    date_titre = date_lettres(terrain_fin)
    title = f"Sondage {html_mod.escape(institut)} du {date_titre} \u2013 présidentielle 2027"
    canonical = f"https://sondax.fr/sondages/{html_mod.escape(sid)}.html"
    phrases = chapo_phrases(sondage)
    meta_desc = meta_description_chapo(phrases)
    h1 = f"Sondage {html_mod.escape(institut)} du {time_tag(terrain_fin, jour_mois(terrain_fin))}"

    # Breadcrumb
    breadcrumb = (
        '<nav class="fil" aria-label="Fil d\u2019Ariane">'
        '<a href="../">Sondax</a> \u203a '
        '<a href="../sondages.html">Sondages</a>'
        '</nav>'
    )

    # Ligne sous le h1 : terrain complet, échantillon, institut, notice
    meta_parts = [
        f"Terrain {terrain_lettres(terrain_debut, terrain_fin)}",
        lien_institut(institut, referentiel, "../"),
    ]
    if echantillon:
        meta_parts.append(f"{fmt_ech(echantillon)}\u202fpersonnes")
    if population:
        meta_parts.append(html_mod.escape(str(population)))
    if url_source:
        esc = html_mod.escape(url_source)
        meta_parts.append(f'<a href="{esc}" target="_blank" rel="noopener">Notice</a>')

    meta_line = " · ".join(meta_parts)

    # Hypothèses T1 et T2
    t1 = [h for h in hypotheses if h.get("tour") == 1]
    t2 = [h for h in hypotheses if h.get("tour") == 2]

    # Tri T1 : principale d'abord, puis par nombre de candidats décroissant
    t1.sort(key=lambda h: (0 if h.get("principale") else 1, -len(h.get("scores", {}))))

    # Hypothèses T1 avec sous-titres numérotés
    principale = hypothese_principale(sondage)
    hyps_html = []
    for i, hyp in enumerate(t1, 1):
        is_p = bool(hyp.get("principale"))
        label = libelle_hypothese(i, hyp, principale) if len(t1) > 1 else ""
        hyps_html.append(build_hypothesis_html(hyp, echantillon, is_p, terrain_fin, label))

    # Duels T2
    duels_html = []
    for hyp in t2:
        duels_html.append(build_duel_html(hyp, echantillon))

    # Précédent / suivant, tous instituts confondus
    prev_s, next_s = prev_next(sondage)
    nav_parts = []
    if prev_s:
        nav_parts.append(
            f'<a href="{html_mod.escape(prev_s["id"])}.html" class="nav-prev" rel="prev">'
            f'<span class="nav-sens">\u2190 Sondage précédent</span>'
            f'{html_mod.escape(prev_s["institut"])} du {time_tag(prev_s["terrain_fin"], jour_mois(prev_s["terrain_fin"]))}</a>'
        )
    else:
        nav_parts.append('<span></span>')
    if next_s:
        nav_parts.append(
            f'<a href="{html_mod.escape(next_s["id"])}.html" class="nav-next" rel="next">'
            f'<span class="nav-sens">Sondage suivant \u2192</span>'
            f'{html_mod.escape(next_s["institut"])} du {time_tag(next_s["terrain_fin"], jour_mois(next_s["terrain_fin"]))}</a>'
        )
    else:
        nav_parts.append('<span></span>')

    nav_html = f'<nav class="sondage-nav">{"".join(nav_parts)}</nav>'

    # Assemblage
    sections = []
    if hyps_html:
        sections.append(
            '<h2>Premier tour</h2>\n'
            + "\n".join(hyps_html)
        )
    if duels_html:
        sections.append(
            '<div class="section-sep"></div>'
            '<h2>Second tour</h2>\n'
            + "\n".join(duels_html)
        )

    chapo_html = f'    <p class="sondage-chapo">{" ".join(phrases)}</p>\n' if phrases else ""

    body = f"""<main class="sondage-page">
  <div class="sondage-inner">
    {breadcrumb}
    <h1>{h1}</h1>
    <p class="sondage-meta-line">{meta_line}</p>
{chapo_html}
    <div class="section-sep"></div>
    {chr(10).join(sections)}

    {nav_html}
  </div>
</main>"""

    return render_page(
        title=title,
        meta_description=meta_desc,
        canonical=canonical,
        body_content=body,
        extra_head=EXTRA_CSS,
        depth=1,
    )


EXTRA_CSS = """<style>
.sondage-page { padding: 24px 16px 40px; }
.sondage-inner { max-width: 780px; margin: 0 auto; }

.sondage-meta-line {
  font-size: 13.5px; color: var(--gris); margin: -8px 0 0;
}
.sondage-meta-line a { font-weight: 500; }
.sondage-chapo {
  font-size: 15.5px; line-height: 1.6; margin-top: 16px; max-width: 68ch;
}

.section-sep {
  border-top: 1px solid var(--bord); margin: 20px 0;
}

/* Hypothèses */
.hypothese { margin-bottom: 18px; }
.hyp-principale { border-left: 3px solid var(--bleu-vif); padding-left: 16px; }
.hyp-header {
  font-size: 14px; font-weight: 600; color: var(--bleu-nuit);
  margin-bottom: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.hyp-detail { font-weight: 400; color: var(--gris); font-size: 13px; }

.scores-table { font-size: 14px; }
.scores-table th { font-size: 11px; padding: 0 8px 6px 0; }
.scores-table td { padding: 5px 8px 5px 0; }
.scores-table tr:last-child td { border-bottom: none; }

.cand-name { min-width: 140px; font-weight: 500; }
.cand-name a { color: var(--texte); }
.cand-name a:hover { color: var(--bleu-vif); }
tr.type-parti .cand-name { font-style: italic; }

.col-score { white-space: nowrap; min-width: 130px; position: relative; }
.bar {
  display: inline-block; height: 6px; border-radius: 3px;
  vertical-align: middle; margin-right: 8px; min-width: 2px;
}
.col-me { font-size: 12.5px; color: var(--gris); white-space: nowrap; }
.me-approx { font-size: 10.5px; color: #aaa; }
.col-ecart { font-size: 12.5px; color: var(--gris); white-space: nowrap; text-align: right; }
.note-approx { font-size: 12px; color: var(--gris); font-style: italic; margin-top: 8px; }

/* Duels T2 */
.duels-section { margin-bottom: 18px; }
.duel { margin-bottom: 14px; }
.duel-bar {
  display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 6px;
}
.duel-part { display: block; height: 100%; }
.duel-labels {
  display: flex; justify-content: space-between; font-size: 14px;
}
.duel-cand strong { font-weight: 600; }
.duel-cand-right { text-align: right; }
.duel-me { font-size: 12px; color: var(--gris); }
.duel-lien { display: inline-block; font-size: 12.5px; margin-top: 4px; }

/* Navigation prev/next */
.sondage-nav {
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 20px; border-top: 1px solid var(--bord); margin-top: 24px;
  font-size: 13.5px;
}
.nav-prev, .nav-next { color: var(--gris); display: flex; flex-direction: column; }
.nav-next { text-align: right; }
.nav-sens { font-size: 11.5px; text-transform: uppercase; letter-spacing: .06em; }
.nav-prev:hover, .nav-next:hover { color: var(--bleu-vif); text-decoration: none; }

@media (max-width: 600px) {
  .col-ecart { display: none; }
  .col-me { font-size: 11.5px; }
  .bar { display: none; }
}
</style>"""


# ---------- génération ----------

out_dir = SITE / "sondages"
out_dir.mkdir(parents=True, exist_ok=True)

count = 0
chapos = {}
for sondage in sondages:
    sid = sondage.get("id")
    if not sid:
        print(f"  skip  (sondage sans id)")
        continue

    html_out = out_dir / f"{sid}.html"
    html_content = build_page(sondage)
    html_out.write_text(html_content, encoding="utf-8")
    count += 1
    chapos.setdefault(" ".join(chapo_phrases(sondage)), []).append(sid)

doublons = [ids for texte, ids in chapos.items() if len(ids) > 1]
if doublons:
    for ids in doublons:
        print(f"ERREUR  chapô identique : {', '.join(ids)}", file=sys.stderr)
    sys.exit(1)

print(f"\n{count} pages sondage générées dans site/sondages/")
