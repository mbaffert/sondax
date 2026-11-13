#!/usr/bin/env python3
"""Génère site/llms.txt et site/.well-known/ard.json (manifeste pour agents IA).

llms.txt suit le format llmstxt.org : titre H1, résumé en blockquote, puis des
sections de liens, chacun avec une ligne de description. ard.json est le
manifeste ARD : {"entries": [...]}, une entrée par ressource utile à un agent
(llms.txt et le CSV des sondages).

Rien de codé en dur côté données : les candidats viennent de scripts/bios.json
(fiches existantes), les instituts de data/instituts.json, les élections passées
des fichiers presidentielle-*.html, et la description de chaque page est la
<meta name="description"> de la page elle-même. À lancer après la génération des
pages (build_sitemap.py) et avant validate_urls.py, qui vérifie que le lien
<link rel="ard"> du <head> pointe vers un fichier existant.
"""

import datetime
import html as html_mod
import json
import pathlib
import re
import sys
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = ROOT / "data"
BASE = "https://sondax.fr"

sys.path.insert(0, str(ROOT / "scripts"))
from build_donnees import NOM_CSV
from build_index_premier_tour import sondage_affiche
from instituts import charger_referentiel
from sondages_io import charger as charger_sondages

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

# Pages principales : (fichier, libellé). Les descriptions sont lues dans les pages.
PAGES_PRINCIPALES = [
    ("index.html", "Accueil"),
    ("sondages.html", "Tous les sondages"),
    ("modele-sondax.html", "Modèle Sondax"),
    ("methodologie.html", "Méthode"),
    ("precedentes-elections.html", "Élections passées"),
    ("instituts.html", "Instituts"),
    ("donnees.html", "Données"),
    ("a-propos.html", "À propos"),
]

LICENCE = "CC BY-SA 4.0"
URL_LICENCE = "https://creativecommons.org/licenses/by-sa/4.0/deed.fr"
MENTION = "Sondax, d'après Wikipédia"

RE_IDENTIFIANT = re.compile(r"^urn:air:[a-zA-Z0-9.-]+(:[a-zA-Z0-9._-]+)+$")


def date_lettres(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def url_de(rel):
    """URL publique d'un fichier de site/ (index.html → racine)."""
    return f"{BASE}/{rel.removesuffix('index.html')}"


def description_page(rel, defaut):
    """<meta name="description"> de la page, sur une ligne ; `defaut` à défaut."""
    chemin = SITE / rel
    if chemin.exists():
        m = re.search(r'<meta name="description" content="([^"]*)"', chemin.read_text(encoding="utf-8"))
        if m:
            return re.sub(r"\s+", " ", html_mod.unescape(m.group(1))).strip()
    return defaut


def lien(libelle, rel, defaut):
    return f"- [{libelle}]({url_de(rel)}): {description_page(rel, defaut)}"


def dernier_sondage(sondages):
    """Dernier sondage mis en avant sur l'accueil, à défaut le plus récent."""
    candidats = json.loads((DATA / "candidats.json").read_text(encoding="utf-8"))
    choix = sondage_affiche(sondages, candidats)
    return choix[0] if choix else max(sondages, key=lambda s: s["terrain_fin"])


def construire():
    sondages = charger_sondages(DATA / "sondages.json")
    if not sondages:
        sys.exit("ERREUR build_llms : aucun sondage")
    auj = datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    maj_iso = auj.isoformat()
    dernier = dernier_sondage(sondages)
    bios = json.loads((ROOT / "scripts" / "bios.json").read_text(encoding="utf-8"))
    referentiel = charger_referentiel()
    url_csv = f"{BASE}/donnees/{NOM_CSV}"
    if not (SITE / "donnees" / NOM_CSV).exists():
        sys.exit(f"ERREUR build_llms : site/donnees/{NOM_CSV} absent (lancer build_donnees.py avant)")

    # ---------- llms.txt ----------
    L = ["# Sondax", "",
         "> Sondax agrège les sondages de la présidentielle française de 2027 : moyenne des "
         "sondages par candidat, duels de second tour, modèle de probabilités et données "
         "ouvertes. Mise à jour quotidienne.", "",
         f"Mise à jour : {date_lettres(maj_iso)}.",
         f"Dernier sondage intégré : {dernier['institut']}, "
         f"terrain terminé le {date_lettres(dernier['terrain_fin'])}.", "",
         "## Pages principales", ""]
    for rel, libelle in PAGES_PRINCIPALES:
        L.append(lien(libelle, rel, libelle))
    if (SITE / "second-tour" / "index.html").exists():
        L.append(lien("Second tour", "second-tour/index.html", "Duels de second tour"))

    L += ["", "## Candidats", ""]
    for slug, fiche in bios.items():
        rel = f"{slug}.html"
        if (SITE / rel).exists():
            L.append(lien(fiche["nom"], rel, f"Sondages {fiche['nom']} pour la présidentielle 2027"))

    L += ["", "## Données ouvertes", "",
          f"- [Sondages de la présidentielle 2027 (CSV)]({url_csv}): une ligne par sondage, "
          f"par configuration testée et par candidat, mise à jour chaque jour. "
          f"Licence {LICENCE} ({URL_LICENCE}) ; mention à reprendre : « {MENTION} », "
          f"avec un lien vers sondax.fr.",
          lien("Documentation du jeu de données", "donnees.html", "Colonnes, sources et conditions de réutilisation")]

    L += ["", "## Optional", ""]
    elections = sorted(p.name for p in SITE.glob("presidentielle-*.html"))
    for rel in elections:
        an = rel.removeprefix("presidentielle-").removesuffix(".html")
        L.append(lien(f"Présidentielle {an}", rel, f"Résultats et sondages de la présidentielle {an}"))
    for slug, inst in referentiel.items():
        rel = f"instituts/{slug}.html"
        if (SITE / rel).exists():
            L.append(lien(inst["nom"], rel, f"Sondages publiés par {inst['nom']}"))
    llms = "\n".join(L) + "\n"

    # ---------- ard.json ----------
    maj = datetime.datetime.combine(auj, datetime.time(0, 0), tzinfo=ZoneInfo("Europe/Paris")).isoformat()
    ard = {"entries": [
        {
            "identifier": "urn:air:sondax.fr:docs:llms-txt",
            "displayName": "Sondax : plan du site pour les agents (llms.txt)",
            "type": "text/markdown",
            "url": f"{BASE}/llms.txt",
            "description": "Résumé de Sondax au format llms.txt : pages principales, fiches candidat, "
                           "données ouvertes, date de mise à jour et dernier sondage intégré.",
            "representativeQueries": [
                "Quel est le plan du site Sondax ?",
                "Où trouver la moyenne des sondages de la présidentielle 2027 ?",
                "Quelles pages Sondax présentent les candidats à la présidentielle 2027 ?",
            ],
            "tags": ["sondages", "presidentielle-2027", "france", "elections"],
            "updatedAt": maj,
        },
        {
            "identifier": "urn:air:sondax.fr:data:sondages-presidentielle-2027",
            "displayName": "Sondages de la présidentielle 2027 (CSV)",
            "type": "text/csv",
            "url": url_csv,
            "description": "Tous les sondages d'intention de vote de la présidentielle française de 2027, "
                           "une ligne par sondage, configuration testée et candidat. "
                           f"Licence {LICENCE}, mention : « {MENTION} ».",
            "representativeQueries": [
                "Télécharger les sondages de la présidentielle 2027 en CSV",
                "Jeu de données ouvert des intentions de vote pour 2027",
                "Historique des sondages par candidat et par institut",
                "Sous quelle licence réutiliser les sondages de Sondax ?",
            ],
            "tags": ["sondages", "presidentielle-2027", "open-data", "csv", "cc-by-sa"],
            "updatedAt": maj,
        },
    ]}
    for e in ard["entries"]:
        if not RE_IDENTIFIANT.match(e["identifier"]):
            sys.exit(f"ERREUR build_llms : identifiant ARD invalide {e['identifier']}")
        if not 2 <= len(e["representativeQueries"]) <= 5:
            sys.exit(f"ERREUR build_llms : 2 à 5 representativeQueries attendues ({e['identifier']})")
    return llms, ard


def main():
    llms, ard = construire()
    (SITE / "llms.txt").write_text(llms, encoding="utf-8")
    dossier = SITE / ".well-known"
    dossier.mkdir(exist_ok=True)
    (dossier / "ard.json").write_text(json.dumps(ard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = sum(1 for l in llms.splitlines() if l.startswith("- ["))
    print(f"  OK  llms.txt ({n} liens), .well-known/ard.json ({len(ard['entries'])} entrées)")


if __name__ == "__main__":
    main()
