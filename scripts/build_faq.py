#!/usr/bin/env python3
"""Bloc « Questions fréquentes » : questions propres à chaque type de page, réponses
régénérées à chaque build depuis les mêmes fonctions et les mêmes données que les
blocs de la page.

Mécanique commune
- Une fonction par type de page (`faq_accueil`, …) : elle reçoit les données de la
  page et renvoie la liste des `QR` (question, réponse en HTML). Une question dont
  une donnée manque n'est pas renvoyée ; sans question, il n'y a pas de bloc.
- `bloc_faq(complement, qr)` produit le bloc, identique sur toutes les pages : section
  `bloc-faq`, H2 « Questions fréquentes » + complément, un <details> fermé par
  question (question dans le <summary>, réponse en <p> dans le HTML statique) et le
  JSON-LD schema.org/FAQPage tiré des mêmes chaînes. Aucune réponse ne dépend de
  JavaScript.
- Veille électorale (loi du 19 juillet 1977, `veille.py`) : sur les pages 2027, le
  bloc disparaît tout entier.
- `--verifier` contrôle le site construit : structure du bloc, JSON-LD identique au
  HTML, aucune question en double entre deux pages (ni dans une page).

Accueil : le bloc est réécrit entre <!-- BEGIN:bloc-faq --> et <!-- END:bloc-faq -->,
l'entrée « Questions » de la sous-navigation entre <!-- BEGIN:nav-faq --> et
<!-- END:nav-faq -->, retirée avec le bloc.

Autres pages : le bloc est construit par `bloc_page(type, complement, données)` appelé par
le générateur de la page (build_pages_candidats.py, build_pages_elections.py,
pages_second_tour.py), en bas de page, sans entrée dans la navigation. Les pages 2027
(candidat, duel) ouvrent chaque réponse sur « Au {date de build}, … » et perdent leur bloc
en veille ; les présidentielles passées (résultats arrêtés) sont hors veille.

À lancer après build_modele.py et build_dates.py (accueil), avant
build_header.py --injecter ; `--verifier` une fois toutes les pages générées.
"""

import collections, datetime, functools, html as html_mod, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
INDEX_PATH = SITE / "index.html"

sys.path.insert(0, str(ROOT / "scripts"))
import veille
from balise_time import time_tag
from build_dates import compute_dates
from build_header import candidate_full_name, load_all_sondages
from build_index_premier_tour import (
    CANDIDATS_PATH, SERIES_PATH, enumeration_fr, faits_premier_tour, fmt_ech,
    fmt_pct, load_json, scores_tries, sondage_affiche,
)
from build_index_second_tour import (
    duels_du_bloc, genre, meneur_des_duels, nombre_lettres, pair, sorted_duel_slugs,
)
import generer
from instituts import charger_referentiel, compter_instituts, lien_institut
from pages_second_tour import (
    SEUIL, fmt_pct as fmt_pct_t2, fmt_score, jour_mois, load_duels, nom_court,
    phrase_dernier_sondage as phrase_duel, terrain_court,
)

NBSP = " "
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

BEGIN_FAQ, END_FAQ = "<!-- BEGIN:bloc-faq -->", "<!-- END:bloc-faq -->"
BEGIN_NAV, END_NAV = "<!-- BEGIN:nav-faq -->", "<!-- END:nav-faq -->"
ENTREE_NAV = '  <a href="#bloc-faq">Questions</a>'


class QR(collections.namedtuple("QR", "question reponse")):
    """Une question et sa réponse (HTML : balises <time> et <a> seulement)."""


# ---------------------------------------------------------------------------
# Mise en forme commune
# ---------------------------------------------------------------------------

def e(s):
    return html_mod.escape(s, quote=False)


def date_lettres(iso):
    """'2026-10-18' → '18 octobre 2026', balisée <time>."""
    y, m, d = iso.split("-")
    jour = "1er" if int(d) == 1 else str(int(d))
    return time_tag(iso, f"{jour}{NBSP}{MOIS[int(m) - 1]}{NBSP}{y}")


def lien(href, texte):
    return f'<a href="{href}">{texte}</a>'


def texte_brut(fragment):
    """Texte d'un fragment HTML (balises retirées, entités décodées)."""
    return html_mod.unescape(re.sub(r"<[^>]+>", "", fragment))


def jsonld_faq(qr):
    """FAQPage schema.org construit sur les mêmes chaînes que le HTML."""
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q.question,
             "acceptedAnswer": {"@type": "Answer", "text": texte_brut(q.reponse)}}
            for q in qr
        ],
    }
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def bloc_faq(complement, qr):
    """Bloc « Questions fréquentes {complement} », ou "" sans question."""
    if not qr:
        return ""
    lignes = ['  <section class="bloc bloc-faq" id="bloc-faq">',
              f'    <h2>Questions fréquentes {e(complement)}</h2>']
    for q in qr:
        lignes += ["    <details>",
                   f"      <summary>{e(q.question)}</summary>",
                   f"      <p>{q.reponse}</p>",
                   "    </details>"]
    lignes += [f'    <script type="application/ld+json">{jsonld_faq(qr)}</script>',
               "  </section>"]
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Accueil
# ---------------------------------------------------------------------------

def phrase_terrain(debut, fin):
    """« le 24 septembre 2026 », « du 14 au 16 octobre 2026 », « du 28 août au
    3 septembre 2026 » ; chaque borne dans une balise <time>."""
    fin_t = time_tag(fin, jour_mois(fin))
    if not debut or debut == fin:
        return f"le {fin_t}"
    if debut[:4] != fin[:4]:
        texte_debut = jour_mois(debut)
    elif debut[:7] != fin[:7]:
        texte_debut = jour_mois(debut, annee=False)
    else:
        texte_debut = jour_mois(debut).split(" ")[0]
    return f"du {time_tag(debut, texte_debut)} au {fin_t}"


def faq_accueil(d):
    """Questions de l'accueil. `d` : sondages, candidats, series_data, duels (tous
    les duels) et dates (build_dates.compute_dates)."""
    qr = []
    maj = date_lettres(d["dates"]["build_date"])
    candidats = d["candidats"]
    nom = lambda cid: candidate_full_name(cid, candidats)

    # 1. Tête de la moyenne du premier tour (mêmes faits que le chapeau de #bloc-sondages)
    faits = faits_premier_tour(d["series_data"], d["sondages"])
    if faits:
        (cid, v), autres = faits["top"][0], faits["top"][1:]
        s1 = (f"Au {maj}, {e(nom(cid))} est en tête de la moyenne des sondages du premier "
              f"tour de la présidentielle 2027 avec {fmt_pct(v)} des intentions de vote")
        if autres:
            s1 += ", devant " + enumeration_fr(
                [f"{e(nom(c))} ({fmt_pct(x)})" for c, x in autres])
        n, instituts = faits["n_sondages"], faits["instituts"]
        if n == 1:
            s2 = f"Cette moyenne repose sur un seul sondage publié par {e(instituts[0])}."
        else:
            debut = time_tag(faits["debut_fenetre"], texte_date(faits["debut_fenetre"]))
            s2 = (f"Cette moyenne pondère les {n}{NBSP}sondages publiés depuis le {debut} "
                  f"par {len(instituts)}{NBSP}instituts.")
        qr.append(QR(f"Qui est en tête des sondages de la présidentielle 2027{NBSP}?",
                     f"{s1}. {s2} "
                     + lien("#bloc-sondages", "Voir la moyenne du premier tour")))

    # 2. Dernier sondage sorti (celui du bloc « Dernier sondage »)
    choix = sondage_affiche(d["sondages"], candidats)
    scores = scores_tries(choix[1])[:4] if choix else []
    if scores:
        latest = choix[0]
        institut = lien_institut(latest["institut"], charger_referentiel())
        s1 = (f"Au {maj}, le dernier sondage publié sur la présidentielle 2027 est un "
              f"sondage {institut}, réalisé "
              f"{phrase_terrain(latest['terrain_debut'], latest['terrain_fin'])}")
        if latest.get("echantillon"):
            s1 += f" auprès de {fmt_ech(latest['echantillon'])}{NBSP}personnes"
        s2 = "Il mesure " + enumeration_fr(
            [f"{e(nom(c))} à {fmt_pct(v)}" for c, v in scores]) + "."
        qr.append(QR(f"Quel est le dernier sondage sur la présidentielle 2027{NBSP}?",
                     f"{s1}. {s2} "
                     + lien(f"sondages/{latest['id']}.html", "Voir la fiche du sondage")))

    # 3. Second tour : combien de duels le meneur remporte, duel principal du bloc, volume
    duels = duels_du_bloc(d["duels"], candidats)
    if duels:
        phrases = []
        vus = set()

        def nom_t2(cid):                             # prénom + nom à la première mention
            if cid in vus:
                return nom_court(cid, candidats)
            vus.add(cid)
            return e(nom(cid))

        meneur = meneur_des_duels(duels, candidats)
        if meneur:
            cid, nw, na = meneur
            g = genre(cid, candidats)
            pronom, accord = ("elle", "e") if g == "f" else ("il", "")
            if na == 1:
                portee = "le seul duel de second tour"
            elif nw == na:
                portee = f"les {nombre_lettres(na)}{NBSP}duels de second tour"
            else:
                portee = f"{nombre_lettres(nw)} des {nombre_lettres(na)}{NBSP}duels de second tour"
            phrases.append(f"Au {maj}, {nom_t2(cid)} l’emporte dans {portee} où {pronom} est "
                           f"testé{accord}.")
            debut_s2 = ""
        else:
            debut_s2 = f"Au {maj}, "

        # Duel principal du bloc : mesuré le plus récemment ; à date égale, le plus testé
        slug = sorted_duel_slugs(duels)[0]
        entries = duels[slug]
        dernier = entries[0]
        a_egalite = sum(1 for en in duels.values()
                        if en[0]["terrain_fin"] == dernier["terrain_fin"])
        cid_a, cid_b = pair(slug, candidats)
        sa, sb = dernier["scores"].get(cid_a, 0), dernier["scores"].get(cid_b, 0)
        if sb > sa:                                  # le tableau met le meneur en premier
            cid_a, cid_b, sa, sb = cid_b, cid_a, sb, sa
        if a_egalite > 1:
            critere = (f"Parmi les {nombre_lettres(a_egalite)}{NBSP}duels mesurés le plus "
                       f"récemment, le plus testé")
        else:
            critere = "Le duel mesuré le plus récemment"
        institut = lien_institut(dernier["institut"], charger_referentiel())
        phrases.append(
            f"{debut_s2}{critere} oppose {nom_t2(cid_a)} à {nom_t2(cid_b)} "
            f"({len(entries)}{NBSP}sondages){NBSP}: la dernière mesure donne "
            f"{fmt_pct_t2(sa)} à {nom_court(cid_a, candidats)} contre {fmt_pct_t2(sb)} "
            f"à {nom_court(cid_b, candidats)} ({institut}, "
            f"{time_tag(dernier['terrain_fin'], texte_date(dernier['terrain_fin']))}).")

        n_duels = len(duels)
        n_mesures = sum(len(en) for en in duels.values())
        mesures = "mesure" if n_mesures == 1 else "mesures"
        if n_duels == 1:
            phrases.append(f"Au total, les instituts ont testé un seul duel, pour "
                           f"{n_mesures}{NBSP}{mesures}.")
        else:
            phrases.append(f"Au total, les instituts ont testé {n_duels}{NBSP}duels, pour "
                           f"{n_mesures}{NBSP}{mesures}.")
        qr.append(QR(f"Qui gagnerait au second tour d’après les sondages{NBSP}?",
                     " ".join(phrases) + " "
                     + lien("second-tour/", "Voir tous les duels de second tour")))

    # 4. Nombre de sondages (le compteur du H1 ; seule la date du plus ancien est ajoutée)
    n, m = d["dates"]["n_sondages"], d["dates"]["n_instituts"]
    premier = min(s["terrain_fin"] for s in d["sondages"]) if d["sondages"] else None
    if n and premier:
        qr.append(QR(f"Combien de sondages ont été publiés sur la présidentielle 2027{NBSP}?",
                     f"Au {maj}, Sondax intègre {n}{NBSP}sondages publiés sur la présidentielle "
                     f"2027, réalisés par {m}{NBSP}instituts. Le terrain du plus ancien s’est "
                     f"terminé le {date_lettres(premier)}. "
                     + lien("sondages.html", "Voir tous les sondages")))
    return qr


def texte_date(iso):
    """'2026-09-16' → '16 septembre 2026' (sans balise)."""
    y, m, d = iso.split("-")
    return f"{'1er' if int(d) == 1 else int(d)}{NBSP}{MOIS[int(m) - 1]}{NBSP}{y}"


# ---------------------------------------------------------------------------
# Pages candidat
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def date_build():
    return compute_dates()["build_date"]


def faq_candidat(d):
    """Questions d'une page candidat. `d` : slug, fiche (bios), noms, duels (ceux de la
    page), serie, n_sondages, rangs, ecart_devant et derniers (build_pages_candidats)."""
    qr = []
    maj = date_lettres(date_build())
    slug, fiche, noms = d["slug"], d["fiche"], d["noms"]
    nom, fem = fiche["nom"], fiche.get("genre") == "f"
    il = "Elle" if fem else "Il"

    # 1. Moyenne du premier tour (mêmes données que la section « Tendance »)
    if d["serie"]:
        s1 = (f"Au {maj}, {e(nom)} est {'mesurée' if fem else 'mesuré'} à "
              f"{generer.fr(d['serie'][-1][1])}{NBSP}% des intentions de vote au premier tour")
        if d["n_sondages"]:
            s1 += (f", moyenne pondérée de {d['n_sondages']}{NBSP}sondages sur les trente "
                   f"derniers jours")
        phrases = [f"{s1}."]
        if d["rangs"]:
            phrases.append(f"{e(nom)} est {generer.rang_mot(d['rangs'][-1][1], fem)} des "
                           f"intentions de vote au premier tour.")
        if d["ecart_devant"]:
            devant, ecart = d["ecart_devant"]
            phrases.append(f"{il} compte {generer.fr(ecart)}{NBSP}point"
                           f"{'s' if ecart >= 2 else ''} de retard sur {e(devant)}.")
        qr.append(QR(f"Quel est le score de {nom} dans les sondages de la présidentielle "
                     f"2027{NBSP}?",
                     " ".join(phrases) + " " + lien("/#bloc-sondages",
                                                   "Voir la moyenne du premier tour")))

    # 2. Dernier sondage testant le candidat (celui du tableau « Derniers sondages »)
    if d["derniers"]:
        latest, score = d["derniers"][0]
        institut = lien_institut(latest["institut"], charger_referentiel(), "/")
        s1 = (f"Au {maj}, le dernier sondage testant {e(nom)} au premier tour est un sondage "
              f"{institut}, réalisé "
              f"{phrase_terrain(latest.get('terrain_debut'), latest['terrain_fin'])}")
        if latest.get("echantillon"):
            s1 += f" auprès de {fmt_ech(latest['echantillon'])}{NBSP}personnes interrogées"
        s2 = f"{il} y est {'mesurée' if fem else 'mesuré'} à {generer.fr(score)}{NBSP}%."
        qr.append(QR(f"Quel est le dernier sondage de {nom}{NBSP}?",
                     f"{s1}. {s2} "
                     + lien(f"/sondages/{latest['id']}.html", "Voir la fiche du sondage")))

    # 3. Second tour : dernière mesure de chaque duel (celles du bloc « au second tour »)
    mesures = generer.duels_du_candidat(slug, d["duels"])
    if mesures:
        n = len(mesures)
        faits = []
        for adv, v in mesures[:3]:
            der = v[-1]
            faits.append(f"face à {e(noms.get(adv, adv))}, {generer.fr(der['s'][slug], 0)}"
                         f"{NBSP}% contre {generer.fr(der['s'][adv], 0)}{NBSP}% "
                         f"({time_tag(der['d'], texte_date(der['d']))})")
        phrases = [f"Au {maj}, {e(nom)} est {'testée' if fem else 'testé'} dans {n}{NBSP}duel"
                   f"{'s' if n > 1 else ''} de second tour par les instituts.",
                   ("Dernières mesures des trois duels les plus mesurés" if n > 3
                    else "Dernières mesures") + f"{NBSP}: " + f"{NBSP}; ".join(faits) + "."]
        page = generer.page_duel(slug, mesures[0][0])
        cible = (lien(f"/second-tour/{page}.html",
                      f"Voir le duel {e(nom)} – {e(noms.get(mesures[0][0], mesures[0][0]))}")
                 if page else lien("/second-tour/", "Voir tous les duels de second tour"))
        qr.append(QR(f"Que donnent les sondages de second tour pour {nom}{NBSP}?",
                     " ".join(phrases) + " " + cible))
    return qr


# ---------------------------------------------------------------------------
# Pages des présidentielles passées
# ---------------------------------------------------------------------------

def faq_election(d):
    """Questions d'une page « présidentielle {année} ». `d` : e (Election) et elections
    (build_pages_elections.charger). Pas de date de build : les chiffres sont arrêtés."""
    import build_pages_elections as be      # importé ici : ce module importe build_faq
    el, elections = d["e"], d["elections"]
    a = el.annee
    qr = []

    # 1. Vainqueur (comme le titre de la synthèse) et score du second tour
    gagnant = el.vainqueur
    perdant = min(el.t2["candidats"], key=lambda c: c["voix"])
    qr.append(QR(f"Qui a remporté la présidentielle {a}{NBSP}?",
                 f"{be.esc(gagnant['nom'])} a été {be.verbe_election(el, elections)} le "
                 f"{be.date_tag(el.tour2)} avec {be.fmt_pct(gagnant['pct_exprimes'])} des suffrages "
                 f"exprimés au second tour, face à {be.esc(perdant['nom'])} "
                 f"({be.fmt_pct(perdant['pct_exprimes'])}). "
                 + lien(f"presidentielle-{a}.html#resultats-second-tour",
                        "Voir les résultats du second tour")))

    # 2. Trois premiers du premier tour (barres de la synthèse)
    top = el.t1["candidats"][:3]
    suite = enumeration_fr([f"{be.esc(c['nom'])} ({be.fmt_pct(c['pct_exprimes'])})"
                            for c in top[1:]])
    qr.append(QR(f"Quels ont été les résultats du premier tour de la présidentielle {a}{NBSP}?",
                 f"Le {be.date_tag(el.tour1)}, {be.esc(top[0]['nom'])} arrive en tête avec "
                 f"{be.fmt_pct(top[0]['pct_exprimes'])} des suffrages exprimés, devant {suite}. "
                 + lien(f"presidentielle-{a}.html#resultats-premier-tour",
                        "Voir les résultats du premier tour")))

    # 3. Participation (celle de la synthèse, et celle du premier tour)
    p1 = be.pct_exact(el.t1["votants"], el.t1["inscrits"])
    p2 = be.pct_exact(el.t2["votants"], el.t2["inscrits"])
    qr.append(QR(f"Quelle a été la participation à la présidentielle {a}{NBSP}?",
                 f"La participation s’est élevée à {be.fmt_pct(p1)} au premier tour "
                 f"({be.date_tag(el.tour1)}) et à {be.fmt_pct(p2)} au second "
                 f"({be.date_tag(el.tour2)}), soit {be.fmt_entier(el.t2['votants'])}{NBSP}votants "
                 f"sur {be.fmt_entier(el.t2['inscrits'])}{NBSP}inscrits. "
                 + lien(f"presidentielle-{a}.html#resultats-second-tour",
                        "Voir le détail du scrutin")))

    # 4. Nombre de sondages du premier tour (le résumé du graphique)
    der = el.derive
    if der.get("nb_sondages_t1"):
        borne = der["borne"]
        s = (f"{der['nb_sondages_t1']}{NBSP}sondages du premier tour ont été publiés depuis "
             f"{time_tag(borne[:7], f'{be.MOIS[int(borne[5:7]) - 1]} {borne[:4]}')}")
        if der.get("nb_rollings_t1", 0) > 0:
            s += f", dont {der['nb_rollings_t1']}{NBSP}vagues de rolling"
        qr.append(QR(f"Combien de sondages ont été publiés avant la présidentielle {a}{NBSP}?",
                     f"{s}. " + lien(f"presidentielle-{a}.html#sondages-premier-tour",
                                     "Voir l’évolution des sondages")))

    # 5. Dernière moyenne mensuelle comparée au résultat (le tableau des moyennes)
    moyennes = be.moyennes_mensuelles(el.brut, der)
    cands = der["candidats"]
    principaux = sorted((c for c in cands if cands[c].get("resultat") is not None
                         and c in moyennes), key=lambda c: -cands[c]["resultat"])[:3]
    mois = max((m for c in principaux for m in moyennes[c]), default=None)
    lignes = [f"{be.esc(cands[c]['nom'])} à {be.fmt_pct1(moyennes[c][mois])} "
              f"(résultat{NBSP}: {be.fmt_pct(cands[c]['resultat'])})"
              for c in principaux if mois in moyennes[c]]
    if mois and lignes:
        y, m = mois.split("-")
        qr.append(QR(f"Que montraient les sondages avant le premier tour de la présidentielle "
                     f"{a}{NBSP}?",
                     f"En {time_tag(mois, f'{be.MOIS[int(m) - 1]} {y}')}, dernier mois de sondages "
                     f"avant le premier tour, la moyenne des sondages mesurait "
                     + enumeration_fr(lignes) + ". "
                     + lien(f"presidentielle-{a}.html#sondages-premier-tour",
                            "Voir les moyennes mensuelles")))
    return qr


# ---------------------------------------------------------------------------
# Pages de duel
# ---------------------------------------------------------------------------

def faq_duel(d):
    """Questions d'une page de duel. `d` : slug, cid_a, cid_b, entries (mesures du duel,
    la plus récente en premier) et candidats (pages_second_tour.generate_duel_page)."""
    qr = []
    maj = date_lettres(date_build())
    entries, candidats = d["entries"], d["candidats"]
    cid_a, cid_b = d["cid_a"], d["cid_b"]
    nom_a, nom_b = e(nom_court(cid_a, candidats)), e(nom_court(cid_b, candidats))
    duel = f"{nom_a} – {nom_b}"
    if not entries:
        return qr

    # 1. Dernière mesure (la phrase sous le titre de la page)
    phrase = phrase_duel(entries, cid_a, cid_b, candidats)
    qr.append(QR(f"Que donne le dernier sondage du duel {texte_brut(duel)}{NBSP}?",
                 f"Au {maj}, {phrase[0].lower()}{phrase[1:]} "
                 + lien("/second-tour/", "Voir tous les duels de second tour")))

    # 2. Nombre de mesures (le sous-titre de la page) et d'instituts
    n = len(entries)
    ancien, recent = entries[-1]["terrain_fin"], entries[0]["terrain_fin"]
    if n == 1:
        instituts = lien_institut(entries[0]["institut"], charger_referentiel(), "/")
        r = (f"Au {maj}, un seul sondage a testé le duel {duel}\u00a0: celui de {instituts}, "
             f"dont le terrain s’est terminé le {date_lettres(recent)}.")
    else:
        m = compter_instituts(entries, charger_referentiel())
        r = (f"Au {maj}, {n}{NBSP}sondages ont testé le duel {duel}, réalisés par "
             f"{m}{NBSP}institut{'s' if m > 1 else ''}. Le terrain du plus ancien s’est terminé "
             f"le {date_lettres(ancien)}, celui du plus récent le {date_lettres(recent)}.")
    qr.append(QR(f"Combien de sondages ont testé le duel {texte_brut(duel)}{NBSP}?",
                 r + " " + lien("/sondages.html", "Voir tous les sondages")))

    # 3. Étendue des scores (seulement quand la page a son graphique)
    if n >= SEUIL:
        def etendue(cid):
            xs = [x["scores"][cid] for x in entries]
            return f"entre {fmt_score(min(xs))} et {fmt_score(max(xs))}"
        debut = entries[-1]["terrain_fin"]
        pages = json.loads((ROOT / "scripts" / "bios.json").read_text(encoding="utf-8"))
        cible = next((c for c in (cid_a, cid_b) if c in pages), None)
        qr.append(QR(f"Entre quelles valeurs se situent les scores du duel "
                     f"{texte_brut(duel)}{NBSP}?",
                     f"Au {maj}, sur {n}{NBSP}mesures depuis "
                     f"{time_tag(debut[:7], f'{MOIS[int(debut[5:7]) - 1]} {debut[:4]}')}, "
                     f"{nom_a} obtient {etendue(cid_a)} et {nom_b} {etendue(cid_b)}. "
                     + (lien(f"/{cible}.html", f"Voir la page de {e(nom_court(cible, candidats))}")
                        if cible else lien("/second-tour/", "Voir tous les duels de second tour"))))
    return qr


# Un type de page → sa fonction de questions. Les autres types s'ajoutent ici.
TYPES = {"accueil": faq_accueil, "candidat": faq_candidat, "election": faq_election,
         "duel": faq_duel}

# Types de pages 2027 : soumis à la veille électorale (pas les présidentielles passées).
PAGES_2027 = {"accueil", "candidat", "duel"}


def bloc_page(type_page, complement, d):
    """Bloc FAQ prêt à insérer dans une page générée (hors accueil) : "" en veille
    électorale pour une page 2027, ou quand aucune question n'a de donnée."""
    if type_page in PAGES_2027 and veille.en_veille():
        return ""
    return bloc_faq(complement, TYPES[type_page](d))



def donnees_accueil():
    return {
        "sondages": load_all_sondages(),
        "candidats": load_json(CANDIDATS_PATH),
        "series_data": load_json(SERIES_PATH),
        "duels": load_duels()[0],
        "dates": compute_dates(),
    }


def remplacer_entre(contenu, debut, fin, texte):
    try:
        i, j = contenu.index(debut), contenu.index(fin)
    except ValueError:
        sys.exit(f"build_faq : marqueurs {debut} / {fin} introuvables dans {INDEX_PATH}")
    return contenu[:i] + debut + ("\n" + texte if texte else "") + "\n" + contenu[j:]


def injecter_accueil():
    """Réécrit le bloc et l'entrée de sous-navigation de l'accueil ; renvoie le nombre
    de questions affichées."""
    qr = [] if veille.en_veille() else TYPES["accueil"](donnees_accueil())
    contenu = INDEX_PATH.read_text(encoding="utf-8")
    contenu = remplacer_entre(contenu, BEGIN_FAQ, END_FAQ,
                              bloc_faq("sur la présidentielle 2027", qr))
    contenu = remplacer_entre(contenu, BEGIN_NAV, END_NAV, ENTREE_NAV if qr else "")
    INDEX_PATH.write_text(contenu, encoding="utf-8")
    return len(qr)


# ---------------------------------------------------------------------------
# Vérification du site construit
# ---------------------------------------------------------------------------

SECTION = re.compile(r'<section class="bloc bloc-faq" id="bloc-faq">(.*?)</section>', re.S)
DETAILS = re.compile(r"<details>\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>", re.S)
LDJSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


PASSEE = re.compile(r"presidentielle-\d{4}\.html")        # présidentielles passées
MODELE = re.compile(r"mod[eè]le|prévi|projection|pronostic", re.I)


def normaliser(s):
    s = texte_brut(s).replace("’", "'").lower()
    return " ".join(s.split())


def verifier():
    erreurs, vues, n_pages = [], {}, 0
    for chemin in sorted(SITE.rglob("*.html")):
        rel = chemin.relative_to(SITE)
        contenu = chemin.read_text(encoding="utf-8")
        m = SECTION.search(contenu)
        if not m:
            if rel == pathlib.Path("index.html") and 'href="#bloc-faq"' in contenu:
                erreurs.append(f"{rel} : entrée « Questions » sans bloc")
            continue
        n_pages += 1
        corps = m.group(1)
        details = DETAILS.findall(corps)
        if not details or len(details) != corps.count("<details>"):
            erreurs.append(f"{rel} : <details> mal formés (summary + p attendus)")
        if "<h2>Questions fréquentes" not in corps:
            erreurs.append(f"{rel} : titre « Questions fréquentes » absent")
        if rel == pathlib.Path("index.html") and 'href="#bloc-faq"' not in contenu:
            erreurs.append(f"{rel} : bloc sans entrée « Questions » dans la sous-navigation")
        if not re.search(r"</section>\s*(?:<!--.*?-->\s*)*(?:</main>\s*(?:</div>\s*)?)?<footer",
                         contenu, re.S):
            erreurs.append(f"{rel} : le bloc n'est pas le dernier avant le pied de page")
        passee = PASSEE.fullmatch(rel.name) is not None
        if rel != pathlib.Path("index.html") and 'href="#bloc-faq"' in contenu:
            erreurs.append(f"{rel} : entrée « Questions » dans la navigation")
        if not passee and veille.en_veille():
            erreurs.append(f"{rel} : bloc affiché pendant la veille électorale")
        ld = LDJSON.search(corps)
        try:
            data = json.loads(ld.group(1)) if ld else None
        except ValueError:
            data = None
        if not data or data.get("@type") != "FAQPage":
            erreurs.append(f"{rel} : JSON-LD FAQPage absent ou invalide")
            data = {"mainEntity": []}
        entites = data["mainEntity"]
        if len(entites) != len(details):
            erreurs.append(f"{rel} : {len(entites)} questions en JSON-LD, {len(details)} en HTML")
        for (q, r), ent in zip(details, entites):
            if ent.get("name") != texte_brut(q) or ent["acceptedAnswer"]["text"] != texte_brut(r):
                erreurs.append(f"{rel} : JSON-LD différent du HTML pour « {texte_brut(q)} »")
            if not passee and not re.match(r"Au <time ", r):
                erreurs.append(f"{rel} : « {texte_brut(q)} » ne s'ouvre pas sur « Au {{date}} »")
            if MODELE.search(texte_brut(q) + " " + texte_brut(r)):
                erreurs.append(f"{rel} : « {texte_brut(q)} » parle du modèle ou de prévision")
            if "<time" not in r:
                erreurs.append(f"{rel} : « {texte_brut(q)} » sans date balisée")
            if not re.search(r"<a href=\"[^\"]+\">[^<]+</a>\s*$", r):
                erreurs.append(f"{rel} : « {texte_brut(q)} » ne finit pas par un lien")
            cle = normaliser(q)
            if cle in vues:
                erreurs.append(f"question en double : « {texte_brut(q)} » "
                               f"({vues[cle]} et {rel})")
            vues.setdefault(cle, rel)
    for chemin in sorted(SITE.glob("presidentielle-*.html")):   # ces pages ont toujours un bloc
        if PASSEE.fullmatch(chemin.name) and not SECTION.search(chemin.read_text(encoding="utf-8")):
            erreurs.append(f"{chemin.name} : bloc « Questions fréquentes » absent")
    return erreurs, n_pages, len(vues)


def main():
    if "--verifier" in sys.argv[1:]:
        erreurs, n_pages, n_questions = verifier()
        if erreurs:
            print("ECHEC build_faq --verifier :", *erreurs, sep="\n  ", file=sys.stderr)
            sys.exit(1)
        print(f"OK  FAQ : {n_questions} questions sur {n_pages} pages, toutes distinctes")
        return
    n = injecter_accueil()
    print(f"FAQ accueil : {n} questions" if n else "FAQ accueil : aucun bloc")


if __name__ == "__main__":
    main()
