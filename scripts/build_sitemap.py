#!/usr/bin/env python3
"""Génère site/sitemap.xml au build, listant toutes les pages publiques.

Parcourt site/ pour les pages statiques, puis ajoute les pages générées
(candidats, sondages, duels, instituts) à partir des données.

Le lastmod de chaque page vient de data/lastmod.json (chemin → {hash, date}) :
on hache le HTML généré, débarrassé des chaînes qui dépendent de la date du
build ; si le hash a changé (ou si la page est nouvelle), la date devient celle
du jour. Les entrées des pages disparues sont supprimées.
"""

import json, pathlib, datetime, hashlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
LASTMOD_PATH = ROOT / "data" / "lastmod.json"
BASE = "https://sondax.fr"

# Chaînes qui changent à chaque build sans que le contenu change
VOLATILES = [
    # Pied de page : « N sondages agrégés · Dernier sondage intégré … · Données vérifiées le … · revid … »
    (re.compile(r'<div id="footer-run">.*?</div>', re.S), '<div id="footer-run"></div>'),
    # Accueil, sous le H1 : « N sondages · M instituts · mis à jour le 29 septembre 2026 »
    (re.compile(r" · mis à jour le (?:<time[^>]*>[^<]*</time>)?[^<]*"), ""),
    # donnees.html : « … · généré le 28 septembre 2026 »
    (re.compile(r" · généré le (?:<time[^>]*>[^<]*</time>)?[^<]*"), ""),
    # donnees.html : JSON-LD Dataset des sondages, dateModified = date du build
    (re.compile(r'(<script type="application/ld\+json" id="jsonld-dataset-sondages">'
                r'[^<]*?"dateModified": )"\d{4}-\d{2}-\d{2}"'),
     r'\1""'),
]


def collect_pages():
    """Collecte toutes les pages publiques : liste de (URL, chemin relatif à site/)."""
    pages = []

    def add(rel):
        pages.append((f"{BASE}/{rel.removesuffix('index.html')}", rel))

    # Pages statiques à la racine de site/
    for f in sorted(SITE.glob("*.html")):
        add(f.name)

    # Pages dans second-tour/ (exclure les redirections)
    st_index = SITE / "second-tour" / "index.html"
    if st_index.exists():
        add("second-tour/index.html")
    for f in sorted((SITE / "second-tour").glob("*.html")):
        if f.name == "index.html":
            continue
        # Exclure les pages de redirection (< 500 octets, contiennent "Redirection")
        content = f.read_text(encoding="utf-8")
        if len(content) < 500 and "Redirection" in content:
            continue
        add(f"second-tour/{f.name}")

    # Pages dans candidats/
    cand_index = SITE / "candidats" / "index.html"
    if cand_index.exists():
        add("candidats/index.html")

    # Pages dans sondages/
    for f in sorted((SITE / "sondages").glob("*.html")):
        if f.name != "index.html":
            add(f"sondages/{f.name}")

    # Pages dans instituts/ (instituts.html est couvert par la racine)
    for f in sorted((SITE / "instituts").glob("*.html")):
        add(f"instituts/{f.name}")

    return pages


def content_hash(rel):
    """SHA-256 du HTML de la page, sans les chaînes dépendant de la date du build."""
    html = (SITE / rel).read_text(encoding="utf-8")
    for motif, remplacement in VOLATILES:
        html = motif.sub(remplacement, html)
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def load_lastmod():
    if LASTMOD_PATH.exists():
        return json.loads(LASTMOD_PATH.read_text(encoding="utf-8"))
    return {}


def save_lastmod(lastmod):
    LASTMOD_PATH.write_text(
        json.dumps(dict(sorted(lastmod.items())), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")


def update_lastmod(pages, today=None):
    """Met à jour data/lastmod.json et le retourne. Retourne aussi les pages modifiées."""
    today = today or datetime.date.today().isoformat()
    ancien = load_lastmod()
    nouveau, modifiees = {}, []
    for _, rel in pages:
        h = content_hash(rel)
        entree = ancien.get(rel)
        if entree and entree["hash"] == h:
            nouveau[rel] = entree
        else:
            nouveau[rel] = {"hash": h, "date": today}
            modifiees.append(rel)
    save_lastmod(nouveau)
    supprimees = sorted(set(ancien) - set(nouveau))
    return nouveau, modifiees, supprimees


def generate_sitemap(pages, lastmod):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url, rel in pages:
        lines.append(f"  <url><loc>{url}</loc><lastmod>{lastmod[rel]['date']}</lastmod></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main():
    pages = collect_pages()
    lastmod, modifiees, supprimees = update_lastmod(pages)
    xml = generate_sitemap(pages, lastmod)
    out = SITE / "sitemap.xml"
    out.write_text(xml, encoding="utf-8")
    print(f"sitemap.xml : {len(pages)} URLs")
    print(f"lastmod.json : {len(modifiees)} page(s) datée(s) du jour, "
          f"{len(supprimees)} entrée(s) supprimée(s)")
    for rel in modifiees:
        print(f"  ~ {rel}")
    for rel in supprimees:
        print(f"  - {rel}")


if __name__ == "__main__":
    main()
