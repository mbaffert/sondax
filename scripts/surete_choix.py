"""Sûreté du choix par candidat (Elabe pour BFMTV et La Tribune Dimanche).

Lit data/surete_choix.json (saisie manuelle, relevée dans les rapports PDF d'Elabe),
le valide, calcule les évolutions entre vagues et fournit les textes communs aux
deux affichages : la ligne des fiches candidat (generer.py) et le tableau de la
page d'accueil (build_index_surete_choix.py).

Ce n'est PAS un agrégat Sondax : une source unique, un institut. Et ce n'est pas la
certitude d'aller voter, qui est une autre donnée.

Règle de péremption : si la vague la plus récente a plus de dix semaines, tout
l'affichage se masque (fiches et accueil). La cadence observée est de quatre
semaines ; dix semaines veut dire qu'Elabe a arrêté.

Sans argument, le script valide le fichier et affiche les évolutions calculées.
"""

import datetime as dt
import html as html_mod
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SURETE_PATH = DATA / "surete_choix.json"

sys.path.insert(0, str(ROOT / "scripts"))

PEREMPTION_JOURS = 70          # dix semaines
UN_MOIS = range(21, 39)        # écart de jours qu'on appelle « un mois »
NB_CONFIGURATIONS_T1 = 6       # configurations de premier tour testées par Elabe
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

CHAMPS_VAGUE = ("id", "terrain_debut", "terrain_fin", "publiee_le", "echantillon",
                "dont_inscrits", "effectifs_utiles", "institut", "commanditaires",
                "configuration", "configuration_libelle", "configuration_note",
                "omis", "omis_motif", "ensemble", "candidats", "url_publication",
                "url_rapport", "page_pdf", "notice")


# ---------------------------------------------------------------------------
# Lecture et validation
# ---------------------------------------------------------------------------

def charger(chemin=None):
    return json.loads(pathlib.Path(chemin or SURETE_PATH).read_text(encoding="utf-8"))


def _json(nom):
    return json.loads((DATA / nom).read_text(encoding="utf-8"))


def _date(valeur):
    try:
        return dt.date.fromisoformat(valeur)
    except (TypeError, ValueError):
        return None


def _pct(v):
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100


def valider(data, candidats=None, instituts=None, commanditaires=None):
    """Lève ValueError (toutes les anomalies d'un coup) si le fichier est invalide.

    Chaque clé de `candidats` (et d'`omis`) doit exister comme id dans
    data/candidats.json ; les vagues sont triées par terrain_fin croissant ;
    `effectifs_utiles` peut être null."""
    candidats = _json("candidats.json") if candidats is None else candidats
    instituts = _json("instituts.json") if instituts is None else instituts
    commanditaires = _json("commanditaires.json") if commanditaires is None else commanditaires
    err = []
    for cle in ("question", "items", "base", "vagues"):
        if cle not in data:
            err.append(f"clé « {cle} » absente")
    vagues = data.get("vagues")
    if not isinstance(vagues, list) or not vagues:
        err.append("« vagues » doit être une liste non vide")
        raise ValueError("; ".join(err))

    ids, precedente = set(), None
    for i, v in enumerate(vagues):
        nom = v.get("id", f"vague #{i + 1}")
        manquants = [c for c in CHAMPS_VAGUE if c not in v]
        if manquants:
            err.append(f"{nom} : champs absents {manquants}")
            continue
        if v["id"] in ids:
            err.append(f"{nom} : id en double")
        ids.add(v["id"])
        debut, fin, pub = _date(v["terrain_debut"]), _date(v["terrain_fin"]), _date(v["publiee_le"])
        if not (debut and fin and pub):
            err.append(f"{nom} : date illisible")
        elif not debut <= fin <= pub:
            err.append(f"{nom} : il faut terrain_debut ≤ terrain_fin ≤ publiee_le")
        if fin and precedente and fin <= precedente:
            err.append(f"{nom} : vagues à trier par terrain_fin croissant "
                       f"({fin} ne suit pas {precedente})")
        precedente = fin or precedente
        if v["institut"] not in instituts:
            err.append(f"{nom} : institut inconnu « {v['institut']} »")
        for c in v["commanditaires"]:
            if c not in commanditaires:
                err.append(f"{nom} : commanditaire inconnu « {c} »")
        for c in list(v["candidats"]) + list(v["omis"]):
            if c not in candidats:
                err.append(f"{nom} : « {c} » n'est pas un id de data/candidats.json")
        for c in set(v["candidats"]) & set(v["omis"]):
            err.append(f"{nom} : « {c} » à la fois mesuré et omis")
        if not v["candidats"]:
            err.append(f"{nom} : aucun candidat")
        for c, val in v["candidats"].items():
            if not _pct(val):
                err.append(f"{nom} : valeur invalide pour {c} ({val!r}), entier 0-100 attendu")
        if not _pct(v["ensemble"]):
            err.append(f"{nom} : ensemble invalide ({v['ensemble']!r})")
        eff = v["effectifs_utiles"]
        if eff is not None and not (isinstance(eff, int) and not isinstance(eff, bool) and eff > 0):
            err.append(f"{nom} : effectifs_utiles doit être null ou un entier positif")
        if not (isinstance(v["echantillon"], int) and v["echantillon"] > 0):
            err.append(f"{nom} : echantillon invalide")
    if err:
        raise ValueError("; ".join(err))
    return True


# ---------------------------------------------------------------------------
# Calculs
# ---------------------------------------------------------------------------

def evolutions(vagues):
    """Pour chaque vague, {candidat: écart en points ou None, "ensemble": ...}.

    L'écart se calcule contre la vague précédente de la MÊME configuration. Un
    candidat absent de cette vague précédente n'a pas d'évolution (None), pas une
    évolution de zéro ; la première vague d'une configuration n'en a aucune."""
    resultats, vues = [], []
    for v in vagues:
        prec = next((p for p in reversed(vues)
                     if p["configuration"] == v["configuration"]), None)
        ev = {}
        for cid, val in v["candidats"].items():
            ev[cid] = (val - prec["candidats"][cid]
                       if prec is not None and cid in prec["candidats"] else None)
        ev["ensemble"] = v["ensemble"] - prec["ensemble"] if prec is not None else None
        resultats.append(ev)
        vues.append(v)
    return resultats


def precedente_meme_configuration(vagues, indice):
    v = vagues[indice]
    return next((p for p in reversed(vagues[:indice])
                 if p["configuration"] == v["configuration"]), None)


def est_perimee(data, aujourdhui=None):
    """Vrai si la vague la plus récente date de plus de dix semaines (terrain_fin)."""
    aujourdhui = aujourdhui or dt.date.today()
    derniere = max(_date(v["terrain_fin"]) for v in data["vagues"])
    return (aujourdhui - derniere).days > PEREMPTION_JOURS


def vue(data=None, aujourdhui=None, candidats=None):
    """Ce que les affichages montrent, ou None s'il faut tout masquer.

    {"vague", "precedente", "evolutions", "ensemble_evolution", "lignes"} où
    `lignes` = [(id, part, évolution ou None)] trié par part décroissante (puis
    par nom, pour un ordre stable). Valide le fichier avant de l'utiliser."""
    data = charger() if data is None else data
    candidats = _json("candidats.json") if candidats is None else candidats
    valider(data, candidats)
    if est_perimee(data, aujourdhui):
        return None
    vagues = data["vagues"]
    i = len(vagues) - 1
    v = vagues[i]
    ev = evolutions(vagues)[i]
    lignes = sorted(((c, p, ev[c]) for c, p in v["candidats"].items()),
                    key=lambda t: (-t[1], candidats[t[0]]["nom"]))
    return {"vague": v, "precedente": precedente_meme_configuration(vagues, i),
            "evolutions": ev, "ensemble_evolution": ev["ensemble"], "lignes": lignes,
            "question": data["question"], "base": data["base"]}


# ---------------------------------------------------------------------------
# Formatage (partagé par les fiches et l'accueil)
# ---------------------------------------------------------------------------

def signe(n):
    """+3, −1 (vrai signe moins), 0."""
    return f"+{n}" if n > 0 else f"−{-n}" if n < 0 else "0"


def date_jour_mois(iso):
    d = _date(iso)
    return f"{d.day} {MOIS[d.month - 1]}"


def phrase_evolution(evol, vague, precedente):
    """« +3 en un mois », « stable en un mois », ou « +3 depuis le 16 octobre » si
    l'écart entre les deux vagues n'est pas d'environ un mois. Vide sans évolution."""
    if evol is None or precedente is None:
        return ""
    jours = (_date(vague["terrain_fin"]) - _date(precedente["terrain_fin"])).days
    corps = "stable" if evol == 0 else signe(evol)
    if jours in UN_MOIS:
        return f"{corps} en un mois"
    return f"{corps} depuis le {date_jour_mois(precedente['terrain_fin'])}"


def phrase_fiche(genre, part, evol, vague, precedente):
    """La ligne de la fiche candidat. Accord de « le/la » sur le genre du candidat."""
    pronom = "la" if genre == "f" else "le"
    suite = phrase_evolution(evol, vague, precedente)
    suite = f" ({suite})" if suite else ""
    return (f"Parmi les électeurs qui {pronom} placent en tête au 1er tour, "
            f"{part} % se disent sûrs de leur choix{suite}.")


def ligne_fiche(vue, cid, genre="m"):
    """Ligne de la fiche candidat, ou chaîne vide : affichage masqué (vue None) ou
    candidat absent de la dernière vague. Un candidat non mesuré n'est pas un
    candidat à 0 % : ni ligne, ni tiret, ni zéro."""
    if vue is None:
        return ""
    ligne = next((l for l in vue["lignes"] if l[0] == cid), None)
    if ligne is None:
        return ""
    _, part, evol = ligne
    return phrase_fiche(genre, part, evol, vue["vague"], vue["precedente"])


def _nombre(n):
    return f"{n:,}".replace(",", " ")


def libelle_commanditaires(vague, table=None):
    table = _json("commanditaires.json") if table is None else table
    noms = [table[c] for c in vague["commanditaires"]]
    return " et ".join([", ".join(noms[:-1]), noms[-1]] if len(noms) > 1 else noms)


def source_courte(vague, table=None):
    """« Sondage Elabe pour BFMTV et La Tribune Dimanche » : à lire dans le bloc."""
    return f"Sondage Elabe pour {libelle_commanditaires(vague, table)}"


def mentions_html(vague, base, prefix=""):
    """Mentions obligatoires sous tout affichage : institut et commanditaires, dates de
    terrain, base, configuration testée, périmètre de la ventilation."""
    from pages_second_tour import terrain_court
    from instituts import charger_referentiel, lien_institut
    esc = html_mod.escape
    institut = lien_institut(charger_referentiel()[vague["institut"]]["nom"],
                             charger_referentiel(), prefix)
    echant = f"{_nombre(vague['echantillon'])} personnes, dont {_nombre(vague['dont_inscrits'])} inscrites sur les listes électorales"
    if vague["effectifs_utiles"]:
        echant += f" ; {_nombre(vague['effectifs_utiles'])} effectifs utiles à cette question"
    mesures = len(vague["candidats"])
    total = mesures + len(vague["omis"])
    sur_n = (f"La ventilation ne porte que sur {mesures} candidats sur {total}, "
             f"les autres étant écartés pour {esc(vague['omis_motif'])}, "
             f"et sur une seule des {NB_CONFIGURATIONS_T1} configurations de 1er tour ; "
             f"aucune pour le 2nd tour.")
    return (
        f'<p><strong>{institut}</strong> pour {esc(libelle_commanditaires(vague))}, '
        f'terrain du {terrain_court(vague["terrain_debut"], vague["terrain_fin"])}, '
        f'{echant}. Source unique&nbsp;: ces chiffres sont ceux d’Elabe, '
        f'pas une moyenne Sondax.</p>'
        f'<p>Base&nbsp;: {esc(base[0].lower() + base[1:])}. '
        f'Configuration testée&nbsp;: {esc(vague["configuration_libelle"])} '
        f'({esc(vague["configuration_note"])}). {sur_n} '
        f'Ne pas confondre avec la certitude d’aller voter, qui est une autre mesure.</p>'
        f'<p><a href="{esc(vague["url_rapport"])}" rel="noopener" target="_blank">Rapport Elabe</a>, '
        f'page&nbsp;{vague["page_pdf"]} · '
        f'<a href="{prefix}methodologie.html#surete-choix">Méthode et limites</a></p>'
    )


def main():
    data = charger()
    valider(data)
    vagues = data["vagues"]
    for v, ev in zip(vagues, evolutions(vagues)):
        print(v["id"], "ensemble", v["ensemble"], signe(ev["ensemble"]) if ev["ensemble"] is not None else "—")
        for c, p in v["candidats"].items():
            print(f"  {c:12} {p:3}  {signe(ev[c]) if ev[c] is not None else '—'}")
    print("périmée" if est_perimee(data) else "affichée")


if __name__ == "__main__":
    main()
