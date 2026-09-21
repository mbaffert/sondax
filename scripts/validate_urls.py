#!/usr/bin/env python3
"""Valide que chaque canonical et chaque URL du sitemap correspond à un fichier généré.

Fait échouer le build (exit 1) si une URL n'a pas de fichier correspondant.
"""

import pathlib, re, sys, xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://sondax.fr"


def url_to_path(url):
    """Convertit une URL en chemin relatif dans site/."""
    if not url.startswith(BASE):
        return None
    rel = url[len(BASE):]
    if rel == "" or rel == "/":
        return SITE / "index.html"
    rel = rel.lstrip("/")
    if rel.endswith("/"):
        return SITE / rel / "index.html"
    return SITE / rel


def collect_canonicals():
    """Collecte tous les canonicals déclarés dans les fichiers HTML."""
    canonicals = {}  # url → file_path
    for html_path in SITE.rglob("*.html"):
        content = html_path.read_text(encoding="utf-8")
        # Exclure les pages de redirection
        if len(content) < 500 and "Redirection" in content:
            continue
        m = re.search(r'<link rel="canonical" href="([^"]+)"', content)
        if m:
            canonicals[m.group(1)] = str(html_path)
    return canonicals


def collect_sitemap_urls():
    """Collecte toutes les URLs du sitemap."""
    sitemap_path = SITE / "sitemap.xml"
    if not sitemap_path.exists():
        return []
    tree = ET.parse(sitemap_path)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text for loc in tree.findall(".//sm:loc", ns)]


def main():
    errors = []

    # Vérifier les canonicals
    canonicals = collect_canonicals()
    for url, source in sorted(canonicals.items()):
        target = url_to_path(url)
        if target is None:
            errors.append(f"CANONICAL  {url}  (dans {source}) : URL externe ignorée")
            continue
        if not target.exists():
            errors.append(f"CANONICAL  {url}  (dans {source}) : fichier manquant {target}")

    # Vérifier le sitemap
    sitemap_urls = collect_sitemap_urls()
    for url in sitemap_urls:
        target = url_to_path(url)
        if target is None:
            errors.append(f"SITEMAP    {url} : URL externe")
            continue
        if not target.exists():
            errors.append(f"SITEMAP    {url} : fichier manquant {target}")

    if errors:
        print(f"\n{'='*60}")
        print(f"ERREURS DE VALIDATION ({len(errors)})")
        print(f"{'='*60}")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        n_can = len(canonicals)
        n_sit = len(sitemap_urls)
        print(f"Validation OK : {n_can} canonicals, {n_sit} URLs sitemap")


if __name__ == "__main__":
    main()
