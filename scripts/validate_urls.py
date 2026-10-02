#!/usr/bin/env python3
"""Valide que chaque canonical, URL du sitemap et lien interne correspond à un fichier,
et que le sitemap couvre exactement les pages HTML publiables présentes dans site/.

Fait échouer le build (exit 1) si une URL n'a pas de fichier correspondant, si
une page publiable manque au sitemap ou s'il en contient une en trop, ou si un
lastmod est absent ou mal formé.
"""

import datetime, pathlib, re, sys, xml.etree.ElementTree as ET

from build_sitemap import enumerer_pages, url_de, ErreurSitemap

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://sondax.fr"

# Préfixes à ignorer dans les liens internes
IGNORE_PREFIXES = (
    "http://", "https://", "mailto:", "#", "javascript:",
    "data:", "//", "${",
)


def url_to_path(url):
    """Convertit une URL absolue en chemin dans site/."""
    if not url.startswith(BASE):
        return None
    rel = url[len(BASE):]
    if rel == "" or rel == "/":
        return SITE / "index.html"
    rel = rel.lstrip("/")
    if rel.endswith("/"):
        return SITE / rel / "index.html"
    return SITE / rel


def href_to_path(href, source_path):
    """Convertit un href relatif ou absolu en chemin dans site/.

    Retourne None si le lien est externe ou un ancre."""
    if not href or any(href.startswith(p) for p in IGNORE_PREFIXES):
        return None

    # Absolu depuis la racine du site
    if href.startswith("/"):
        rel = href.lstrip("/")
        # Retirer le fragment et le query string
        rel = rel.split("#")[0].split("?")[0]
        if not rel or rel.endswith("/"):
            return SITE / (rel or "") / "index.html"
        return SITE / rel

    # Relatif au fichier source
    href_clean = href.split("#")[0].split("?")[0]
    if not href_clean:
        return None
    parent = source_path.parent
    resolved = (parent / href_clean).resolve()
    # Vérifier que ça reste dans site/
    try:
        resolved.relative_to(SITE.resolve())
    except ValueError:
        return None
    if resolved.is_dir() or str(resolved).endswith("/"):
        return resolved / "index.html"
    return resolved


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


def collect_sitemap():
    """Collecte les entrées du sitemap : liste de (loc, lastmod)."""
    sitemap_path = SITE / "sitemap.xml"
    if not sitemap_path.exists():
        return []
    tree = ET.parse(sitemap_path)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [(u.findtext("sm:loc", namespaces=ns), u.findtext("sm:lastmod", namespaces=ns))
            for u in tree.findall("sm:url", ns)]


def check_sitemap_complet(sitemap):
    """Le sitemap contient exactement les pages HTML publiables de site/."""
    errors = []
    try:
        publiables, _ = enumerer_pages()
    except ErreurSitemap as e:
        return [f"SITEMAP    {e}"], 0
    attendues = {url_de(rel) for rel in publiables}
    urls = [loc for loc, _ in sitemap]
    presentes = set(urls)
    for url in sorted(attendues - presentes):
        errors.append(f"SITEMAP    {url} : page publiable absente du sitemap")
    for url in sorted(presentes - attendues):
        errors.append(f"SITEMAP    {url} : dans le sitemap mais pas une page publiable")
    for url in sorted({u for u in urls if urls.count(u) > 1}):
        errors.append(f"SITEMAP    {url} : en double")
    if len(urls) != len(attendues):
        errors.append(f"SITEMAP    {len(urls)} URLs pour {len(attendues)} pages publiables")
    today = datetime.date.today().isoformat()
    for loc, lastmod in sitemap:
        if not lastmod or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod):
            errors.append(f"SITEMAP    {loc} : lastmod absent ou mal formé ({lastmod})")
        elif lastmod > today:
            errors.append(f"SITEMAP    {loc} : lastmod {lastmod} dans le futur")
    return errors, len(attendues)


def strip_scripts(html):
    """Retire le contenu des balises <script> pour ne pas parser les href JS."""
    return re.sub(r'<script[\s>].*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)


def collect_internal_links():
    """Collecte tous les href internes de toutes les pages HTML."""
    links = []  # (href, source_path)
    for html_path in SITE.rglob("*.html"):
        content = html_path.read_text(encoding="utf-8")
        if len(content) < 500 and "Redirection" in content:
            continue
        clean = strip_scripts(content)
        for m in re.finditer(r'href="([^"]*)"', clean):
            href = m.group(1)
            links.append((href, html_path))
    return links


def main():
    errors = []

    # Vérifier les canonicals
    canonicals = collect_canonicals()
    for url, source in sorted(canonicals.items()):
        target = url_to_path(url)
        if target is None:
            continue
        if not target.exists():
            errors.append(f"CANONICAL  {url}  (dans {source}) : fichier manquant")

    # Vérifier le sitemap
    sitemap = collect_sitemap()
    sitemap_urls = [loc for loc, _ in sitemap]
    erreurs_sitemap, n_publiables = check_sitemap_complet(sitemap)
    errors += erreurs_sitemap
    for url in sitemap_urls:
        target = url_to_path(url)
        if target is None:
            continue
        if not target.exists():
            errors.append(f"SITEMAP    {url} : fichier manquant")

    # Vérifier tous les liens internes
    links = collect_internal_links()
    n_links = 0
    seen = set()
    for href, source_path in links:
        target = href_to_path(href, source_path)
        if target is None:
            continue
        n_links += 1
        key = (str(target), str(source_path))
        if key in seen:
            continue
        seen.add(key)
        if not target.exists():
            rel_source = source_path.relative_to(SITE)
            errors.append(f"LIEN       {href}  (dans {rel_source}) : fichier manquant {target}")

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
        print(f"Validation OK : {n_can} canonicals, {n_sit} URLs sitemap "
              f"pour {n_publiables} pages publiables, {n_links} liens internes")


if __name__ == "__main__":
    main()
