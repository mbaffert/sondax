#!/usr/bin/env python3
"""Génère site/sitemap.xml au build, après la génération de toutes les pages.

Pages : énumération de tous les fichiers HTML présents sous site/. Aucune liste
d'URLs ni de slugs : une page générée est dans le sitemap, sauf si elle n'est
pas publiable :
- redirection (<meta http-equiv="refresh">) ;
- noindex (<meta name="robots" content="…noindex…">) ;
- canonical pointant vers une autre URL (doublon).
Une page sans canonical fait échouer le build.

lastmod : date du dernier changement des données affichées par la page, jamais
la date du build. Une page qui ne relève d'aucune règle fait échouer le build.
- fiche sondage : fin de terrain du sondage (ou date de saisie si postérieure) ;
- page institut : dernier sondage de l'institut ;
- fiche candidat : dernier sondage où figure le candidat, dernier sondage
  utilisé par le modèle Sondax si la fiche affiche son bloc, dernier commit de
  scripts/bios.json ;
- page duel : dernier sondage testant ce duel, dernier sondage du modèle si la
  page affiche son bloc ;
- graphique à reprendre (partage/premier-tour.html) : date de fin de la série
  de moyennes du premier tour ;
- pages de liste (sondages, instituts, candidats, second tour, données) :
  dernier sondage qu'elles listent ;
- accueil : dernier sondage, modèle, dernière collecte Polymarket ;
- pages rédigées à la main : dernier commit de leur fichier et des données
  qu'elles affichent (git log ; le dépôt ne doit pas être un clone superficiel).
"""

import json, pathlib, re, subprocess, sys
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = ROOT / "data"
BASE = "https://sondax.fr"

sys.path.insert(0, str(ROOT / "scripts"))
from instituts import charger_referentiel, slug_institut
from pages_second_tour import find_pair_from_slug
from sondages_io import charger as charger_sondages

RE_REFRESH = re.compile(r'<meta\s[^>]*http-equiv=["\']refresh["\']', re.I)
RE_NOINDEX = re.compile(r'<meta\s[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', re.I)
RE_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"')

# Pages rédigées à la main : fichiers dont le dernier commit date la page
SOURCES_GIT = {
    "a-propos.html": ["site/a-propos.html"],
    "precedentes-elections.html": ["site/precedentes-elections.html"],
    "methodologie.html": ["site/methodologie.html", "data/historique.json",
                          "data/historique_europeennes.json", "data/config.json"],
    **{f"presidentielle-{a}.html": [f"site/presidentielle-{a}.html", "data/historique.json"]
       for a in (2002, 2007, 2012, 2017, 2022)},
}


class ErreurSitemap(Exception):
    pass


# ---------- énumération ----------

def url_de(rel):
    """URL publique d'un fichier de site/ (index.html → répertoire)."""
    return f"{BASE}/{rel.removesuffix('index.html')}"


def classer(rel):
    """Retourne None si la page est publiable, sinon la raison de son exclusion."""
    html = (SITE / rel).read_text(encoding="utf-8")
    if RE_REFRESH.search(html):
        return "redirection"
    if RE_NOINDEX.search(html):
        return "noindex"
    m = RE_CANONICAL.search(html)
    if not m:
        raise ErreurSitemap(f"{rel} : pas de <link rel=\"canonical\">")
    if m.group(1) != url_de(rel):
        return f"canonical vers {m.group(1)}"
    return None


def enumerer_pages():
    """Tous les fichiers HTML de site/ : (publiables, {rel: raison d'exclusion})."""
    publiables, exclues = [], {}
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        raison = classer(rel)
        if raison:
            exclues[rel] = raison
        else:
            publiables.append(rel)
    return publiables, exclues


# ---------- dates des données ----------

def date_sondage(s):
    """Date à laquelle le sondage est entré dans les données du site."""
    return max(s["terrain_fin"], s.get("saisi_le") or "")


@lru_cache(maxsize=None)
def donnees():
    sondages = charger_sondages(DATA / "sondages.json")
    candidats = json.loads((DATA / "candidats.json").read_text(encoding="utf-8"))
    polymarket = json.loads((DATA / "polymarket.json").read_text(encoding="utf-8"))
    chemin_modele = DATA / "derived" / "modele.json"
    modele = json.loads(chemin_modele.read_text(encoding="utf-8")) if chemin_modele.exists() else None
    return sondages, candidats, polymarket, modele


def dernier(dates, quoi):
    dates = [d for d in dates if d]
    if not dates:
        raise ErreurSitemap(f"aucune donnée datée pour {quoi}")
    return max(dates)


@lru_cache(maxsize=None)
def date_git(fichier):
    date = subprocess.run(["git", "log", "-1", "--format=%cs", "--", fichier],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if not date:
        raise ErreurSitemap(f"{fichier} : aucun commit")
    return date


def verifier_historique_git():
    sortie = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    if sortie == "true":
        raise ErreurSitemap("clone git superficiel : les dates des pages rédigées à la main "
                            "seraient fausses (actions/checkout : fetch-depth: 0)")


def duels_sondage(s):
    """Paires (triées) testées en second tour par le sondage."""
    return {"-".join(sorted(h["scores"])) for h in s["hypotheses"]
            if h["tour"] == 2 and len(h["scores"]) == 2}


def date_page(rel):
    """Date du dernier changement des données affichées par la page."""
    sondages, candidats, polymarket, modele = donnees()
    tous = dernier((date_sondage(s) for s in sondages), "les sondages")
    date_modele = modele["jour_moyenne"] if modele else None
    stem = rel.removesuffix(".html")

    if rel in SOURCES_GIT:
        return max(date_git(f) for f in SOURCES_GIT[rel])

    if rel.startswith("sondages/"):
        s = next((s for s in sondages if s["id"] == stem.split("/", 1)[1]), None)
        if s is None:
            raise ErreurSitemap(f"{rel} : sondage absent de data/sondages.json")
        return date_sondage(s)

    if rel.startswith("instituts/"):
        ref = charger_referentiel()
        slug = stem.split("/", 1)[1]
        return dernier((date_sondage(s) for s in sondages
                        if slug_institut(s["institut"], ref) == slug), rel)

    if rel == "second-tour/index.html":
        return dernier((date_sondage(s) for s in sondages if duels_sondage(s)), rel)

    if rel.startswith("second-tour/"):
        paire = "-".join(sorted(find_pair_from_slug(stem.split("/", 1)[1], candidats)))
        dates = [date_sondage(s) for s in sondages if paire in duels_sondage(s)]
        if modele and any("-".join(sorted(d["candidats"])) == paire for d in modele["duels"]):
            dates.append(date_modele)
        return dernier(dates, rel)

    if "/" not in rel and stem in candidats:
        dates = [date_sondage(s) for s in sondages
                 if any(stem in h["scores"] for h in s["hypotheses"])]
        if modele and stem in modele["candidats"]:
            dates.append(date_modele)
        dates.append(date_git("scripts/bios.json"))
        return dernier(dates, rel)

    if rel == "candidats/index.html":
        return dernier((date_sondage(s) for s in sondages
                        if any(h["tour"] == 1 for h in s["hypotheses"])), rel)

    if rel in ("sondages.html", "instituts.html", "donnees.html"):
        return tous

    if rel == "partage/premier-tour.html":
        serie = json.loads((DATA / "derived" / "series-t1.json").read_text(encoding="utf-8"))
        return serie["date_fin"]

    if rel == "modele-sondax.html":
        return date_modele or tous

    if rel == "index.html":
        return max(d for d in (tous, date_modele, polymarket["maj"][:10]) if d)

    raise ErreurSitemap(f"{rel} : aucune règle de datation (à ajouter dans build_sitemap.date_page)")


# ---------- sitemap ----------

def generate_sitemap(pages):
    """pages : liste de (url, lastmod)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod in pages:
        lines.append(f"  <url><loc>{url}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main():
    try:
        verifier_historique_git()
        publiables, exclues = enumerer_pages()
        pages = [(url_de(rel), date_page(rel)) for rel in publiables]
    except ErreurSitemap as e:
        print(f"ERREUR sitemap : {e}")
        sys.exit(1)
    (SITE / "sitemap.xml").write_text(generate_sitemap(pages), encoding="utf-8")
    print(f"sitemap.xml : {len(pages)} URLs, {len(exclues)} page(s) HTML exclue(s)")
    for rel, raison in exclues.items():
        print(f"  - {rel} ({raison})")


if __name__ == "__main__":
    main()
