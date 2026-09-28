"""Textes générés du modèle Sondax (SPEC §14.9 à §14.11, §14.14).

Fonctions pures : elles reçoivent modele.json, le référentiel des candidats et
l'index des sondages, et rendent du texte (HTML échappé). Aucune n'emploie un mot
réservé à la page Méthode (§14.3).
"""

import datetime, html

e = html.escape

MIN_SONDAGES_EVOLUTION = 3       # §14.9
BASCULE_AFFICHAGE_MAX = 4.0      # §14.7
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
MOINS = "−"


def nom(candidats, slug):
    return candidats[slug]["nom"]


def chances(v):
    """« 38 », « moins de 1 », « plus de 99 » (sans « sur 100 »)."""
    if v < 0.5:
        return "moins de 1"
    if v > 99.5:
        return "plus de 99"
    return str(round(v))


def signe(n):
    return f"+{n}" if n > 0 else f"{MOINS}{abs(n)}"


def date_jour_mois(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]}"


def points(x):
    """« 1 point », « 1,5 point », « 2 points »."""
    txt = (f"{x:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
    return f"{txt}&nbsp;point{'s' if x >= 2 else ''}"


# ---------------------------------------------------------------- évolutions

def evolution(modele, valeur, jours=7, index=None):
    """« +11 en 7 jours », « −5 en 7 jours », « stable », « peu de changement »,
    ou None sans historique (§14.9). Sous trois sondages en 7 jours, avec
    `index`, un mouvement d'au moins 2 est donné en nommant le ou les sondages
    (« −13 en 7 jours, après le sondage Harris du 24 septembre »)."""
    if valeur is None:
        return None
    if jours == 7 and modele.get("sondages_entres_7j", 0) < MIN_SONDAGES_EVOLUTION:
        ids = (modele.get("sondages_entres") or {}).get("7j") or []
        if index is not None and ids and abs(valeur) >= 2:
            qui = nommer_sondages(ids, index)
            return f"{signe(valeur)} en 7&nbsp;jours, après {qui[0].lower() + qui[1:]}"
        return "peu de changement"
    if abs(valeur) <= 1:
        return "stable"
    return f"{signe(valeur)} en {jours}&nbsp;jours"


# ------------------------------------------------------------------- bascule

def bascule_affichee(delta):
    if delta is None or delta > BASCULE_AFFICHAGE_MAX:
        return None
    return max(0.5, round(delta * 2) / 2)


def bascule_courte(v):
    b = bascule_affichee(v.get("delta_bascule"))
    return f"À environ {points(b)} du basculement" if b is not None else None


def bascule_explication(v):
    b = bascule_affichee(v.get("delta_bascule"))
    if b is None:
        return None
    return (f"Avec environ {points(b)} de plus dans les sondages actuels, ses chances "
            f"d’être au second tour seraient proches d’une sur deux.")


def bascule_a_la_une(modele):
    """Candidat dont le point de bascule mérite la une : affichable et chances
    entre 25 et 49 (§14.14.1)."""
    for c, v in modele["candidats"].items():
        if 25 <= v["qualification"] < 50 and bascule_affichee(v.get("delta_bascule")) is not None:
            return c, v
    return None


# ------------------------------------------------------ sondages déclencheurs

def nommer_sondages(ids, index):
    """« Le sondage Harris du 24 septembre » / « Les sondages Harris du 24 et
    Ifop du 25 septembre »."""
    noms = []
    for i in ids:
        s = index.get(i)
        noms.append(f"{s['institut']} du {date_jour_mois(s['terrain_fin'])}" if s else i)
    if len(noms) == 1:
        return f"Le sondage {noms[0]}"
    return f"Les sondages {', '.join(noms[:-1])} et {noms[-1]}"


def _quand(ev):
    return "il y a une semaine" if ev.get("horizon") == "7j" else "à la mise à jour précédente"


# --------------------------------------------------------- ce qui a changé

def changement(modele, candidats, index, ordre):
    """(titre, détail) de l'événement du jour (§14.10), ou None."""
    ev = modele.get("changement")
    if not ev:
        return None
    t = ev["type"]
    ids = ev.get("sondages_declencheurs", [])
    attribue = len(ids) in (1, 2)
    sujet = nommer_sondages(ids, index) if ids else ""
    verbe_pl = len(ids) > 1

    if t == "aucun_sondage":
        return ("Pas de nouveau sondage depuis la dernière mise à jour.",
                "La course au second tour n’a donc pas bougé.")
    if t == "peu_de_changement":
        if ids:
            return ("Peu de changement.",
                    f"{sujet} {'restent' if verbe_pl else 'reste'} proche{'s' if verbe_pl else ''} "
                    f"de la moyenne actuelle et {'modifient' if verbe_pl else 'modifie'} peu "
                    f"la course au second tour.")
        return ("Peu de changement.", "La course au second tour bouge peu.")

    if t == "duel_principal_change":
        duel = " – ".join(nom(candidats, c) for c in sorted(ev["duel"], key=ordre.index))
        titre = f"{duel} devient le second tour le plus fréquent."
        if attribue:
            titre = f"{sujet} {'font' if verbe_pl else 'fait'} de {duel} le second tour le plus fréquent."
        return (titre, f"Il sort {chances(ev['apres'])} fois sur 100, contre "
                       f"{chances(ev['avant'])} {_quand(ev)}.")

    if t == "deuxieme_change":
        x, y = nom(candidats, ev["candidate"]), nom(candidats, ev["depasse"])
        titre = f"{x} repasse devant {y}."
        if attribue:
            titre = f"{sujet} {'font' if verbe_pl else 'fait'} repasser {x} devant {y}."
        return (titre, f"Ses chances d’être au second tour passent de {chances(ev['avant'])} à "
                       f"{chances(ev['apres'])} sur 100 ; celles de {y} de "
                       f"{chances(ev['autre_avant'])} à {chances(ev['autre_apres'])}.")

    if t in ("candidate_gain", "candidate_loss"):
        x = nom(candidats, ev["candidate"])
        gain = t == "candidate_gain"
        if attribue:
            verbe = ("rapprochent" if gain else "éloignent") if verbe_pl else ("rapproche" if gain else "éloigne")
            titre = (f"{sujet} {verbe} {x} du second tour : "
                     f"{signe(ev['delta'])} chances sur 100.")
        else:
            titre = f"{x} {'se rapproche' if gain else 's’éloigne'}."
        return (titre, f"Ses chances d’être au second tour passent de {chances(ev['avant'])} à "
                       f"{chances(ev['apres'])} sur 100.")

    if t == "verdict_change":
        from build_modele import verdict_texte  # évite une dépendance circulaire au chargement
        x = nom(candidats, ev["candidate"])
        return (f"{x} : {verdict_texte(candidats, ev['candidate'], ev['verdict']).lower()}.",
                f"Ses chances d’être au second tour passent de {chances(ev['avant'])} à "
                f"{chances(ev['apres'])} sur 100.")

    if t == "bascule_change":
        x = nom(candidats, ev["candidate"])
        proche = ev["apres"] < ev["avant"]
        return (f"{x} {'se rapproche du basculement' if proche else 's’éloigne du basculement'}.",
                f"Il lui manque désormais environ {points(ev['apres'])}, contre "
                f"{points(ev['avant'])} {_quand(ev)}.")
    return None


def mouvement_accueil(modele, candidats, index, ordre):
    """Une seule phrase pour l'accueil (§14.14.1, point 4)."""
    ev = modele.get("changement")
    if not ev:
        return None
    t = ev["type"]
    ids = ev.get("sondages_declencheurs", [])
    if t in ("candidate_gain", "candidate_loss"):
        x = nom(candidats, ev["candidate"])
        if len(ids) in (1, 2):
            return changement(modele, candidats, index, ordre)[0]
        periode = "en une semaine" if ev.get("horizon") == "7j" else "depuis la dernière mise à jour"
        verbe = "se rapproche" if t == "candidate_gain" else "s’éloigne"
        return f"{x} {verbe} : {signe(ev['delta'])} chances {periode}."
    if t in ("aucun_sondage", "peu_de_changement"):
        return "Peu de changement depuis une semaine."
    return changement(modele, candidats, index, ordre)[0]
