#!/usr/bin/env python3
"""Initialise data/lastmod.json (usage ponctuel, après un build complet).

Dates initiales :
- fiche sondage : date de fin de terrain du sondage ;
- accueil, liste des sondages, pages candidat, institut et second tour :
  date du dernier sondage intégré ;
- Méthode, À propos, Données, élections passées : date du dernier commit qui
  a touché leur source (git log -1 --format=%cs -- <fichier>). Le dépôt ne
  doit pas être un clone superficiel.

Les hashes sont ceux du build présent dans site/, calculés comme au build.
"""

import json, pathlib, subprocess, sys

from build_sitemap import ROOT, collect_pages, content_hash, save_lastmod

# Page → fichier source dont le dernier commit date la page
SOURCES = {
    "methodologie.html": "site/methodologie.html",
    "a-propos.html": "site/a-propos.html",
    "donnees.html": "scripts/build_donnees.py",
    "precedentes-elections.html": "site/precedentes-elections.html",
    **{f"presidentielle-{a}.html": f"site/presidentielle-{a}.html"
       for a in (2002, 2007, 2012, 2017, 2022)},
}


def date_commit(fichier):
    date = subprocess.run(["git", "log", "-1", "--format=%cs", "--", fichier],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if not date:
        sys.exit(f"Aucun commit ne touche {fichier}")
    return date


def main():
    if (ROOT / ".git" / "shallow").exists():
        sys.exit("Clone superficiel : lancer d'abord git fetch --unshallow")
    sondages = json.loads((ROOT / "data" / "sondages.json").read_text(encoding="utf-8"))
    fin = {s["id"]: s["terrain_fin"] for s in sondages if s.get("id")}
    dernier = max(fin.values())

    lastmod = {}
    for _, rel in collect_pages():
        if rel in SOURCES:
            date = date_commit(SOURCES[rel])
        elif rel.startswith("sondages/"):
            date = fin[rel.removeprefix("sondages/").removesuffix(".html")]
        else:
            date = dernier
        lastmod[rel] = {"hash": content_hash(rel), "date": date}
    save_lastmod(lastmod)
    print(f"lastmod.json initialisé : {len(lastmod)} pages")


if __name__ == "__main__":
    main()
