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

À lancer après build_modele.py et build_dates.py (accueil), avant
build_header.py --injecter ; `--verifier` une fois toutes les pages générées.
"""

import collections, datetime, html as html_mod, json, pathlib, re, sys

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
    duels_du_bloc, pair, phrases_synthese, sorted_duel_slugs,
)
from instituts import charger_referentiel, lien_institut
from pages_second_tour import fmt_pct as fmt_pct_t2, jour_mois, load_duels, nom_court

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
            s1 += f" auprès de {fmt_ech(latest['echantillon'])}{NBSP}personnes interrogées"
        s2 = "Il mesure " + enumeration_fr(
            [f"{e(nom(c))} à {fmt_pct(v)}" for c, v in scores]) + "."
        qr.append(QR(f"Quel est le dernier sondage sur la présidentielle 2027{NBSP}?",
                     f"{s1}. {s2} "
                     + lien(f"sondages/{latest['id']}.html", "Voir la fiche du sondage")))

    # 3. Second tour : duel principal du bloc, puis synthèse sur l'ensemble des duels
    duels = duels_du_bloc(d["duels"], candidats)
    if duels:
        slug = sorted_duel_slugs(duels)[0]
        entries = duels[slug]
        cid_a, cid_b = pair(slug, candidats)
        dernier = entries[0]
        sa, sb = dernier["scores"].get(cid_a, 0), dernier["scores"].get(cid_b, 0)
        if sb > sa:                                  # le tableau met le meneur en premier
            cid_a, cid_b, sa, sb = cid_b, cid_a, sb, sa
        institut = lien_institut(dernier["institut"], charger_referentiel())
        s1 = (f"Au {maj}, le duel de second tour le plus récemment mesuré oppose "
              f"{e(nom(cid_a))} ({fmt_pct_t2(sa)}) à {e(nom(cid_b))} ({fmt_pct_t2(sb)}), "
              f"selon la dernière mesure ({institut}, "
              f"{time_tag(dernier['terrain_fin'], texte_date(dernier['terrain_fin']))}) "
              f"parmi {len(entries)}{NBSP}sondages testant ce duel")
        vus = {cid_a, cid_b}

        def nom_t2(cid):                             # prénom + nom à la première mention
            if cid in vus:
                return nom_court(cid, candidats)
            vus.add(cid)
            return e(nom(cid))
        synthese = phrases_synthese(duels, candidats, nom=nom_t2)
        qr.append(QR(f"Qui gagnerait au second tour d’après les sondages{NBSP}?",
                     " ".join([f"{s1}."] + synthese) + " "
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


# Un type de page → sa fonction de questions. Les autres types s'ajoutent ici.
TYPES = {"accueil": faq_accueil}


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
        if not re.search(r"</section>\s*(?:<!--.*?-->\s*)*</main>\s*<footer", contenu, re.S):
            erreurs.append(f"{rel} : le bloc n'est pas le dernier avant le pied de page")
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
            if "<time" not in r:
                erreurs.append(f"{rel} : « {texte_brut(q)} » sans date balisée")
            if not re.search(r"<a href=\"[^\"]+\">[^<]+</a>\s*$", r):
                erreurs.append(f"{rel} : « {texte_brut(q)} » ne finit pas par un lien")
            cle = normaliser(q)
            if cle in vues:
                erreurs.append(f"question en double : « {texte_brut(q)} » "
                               f"({vues[cle]} et {rel})")
            vues.setdefault(cle, rel)
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
