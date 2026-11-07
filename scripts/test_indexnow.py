"""Test de indexnow.urls_recentes sur un sitemap factice (aucun appel réseau).

Même convention que test_modele.py : `python scripts/test_indexnow.py`, sortie 1
au premier échec.
"""

import datetime, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import indexnow


def test_urls_recentes():
    aujourdhui = datetime.date.today().isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://sondax.fr/recente</loc><lastmod>{aujourdhui}</lastmod></url>
<url><loc>https://sondax.fr/ancienne</loc><lastmod>2026-09-12</lastmod></url>
<url><loc>https://sondax.fr/sans-date</loc></url>
</urlset>"""
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "sitemap.xml"
        f.write_text(xml, encoding="utf-8")
        assert indexnow.urls_recentes(f) == ["https://sondax.fr/recente"]


if __name__ == "__main__":
    for nom, fn in list(globals().items()):
        if nom.startswith("test_"):
            try:
                fn()
            except AssertionError:
                print(f"ÉCHEC {nom}")
                sys.exit(1)
            print(f"ok {nom}")
