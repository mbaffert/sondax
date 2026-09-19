#!/usr/bin/env python3
"""Télécharge les portraits depuis Wikimedia Commons et les recadre en 240×240."""

import json, os, re, subprocess, tempfile, urllib.request, urllib.parse

UA = "SondaxBot/1.0 (https://sondax.fr; contact@sondax.fr)"
API = "https://commons.wikimedia.org/w/api.php"
OUT = os.path.join(os.path.dirname(__file__), "..", "site", "photos")
DATA = os.path.join(os.path.dirname(__file__), "..", "data", "photos.json")

os.makedirs(OUT, exist_ok=True)

with open(DATA) as f:
    photos = json.load(f)


def filename_from_url(url):
    """Extrait 'File:Xxx.jpg' depuis l'URL Commons."""
    m = re.search(r"wiki/(File:.+)$", url)
    if not m:
        raise ValueError(f"URL inattendue : {url}")
    return urllib.parse.unquote(m.group(1))


def get_thumb_url(file_title):
    """Appelle l'API Commons pour obtenir l'URL du thumbnail 320px."""
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 320,
        "format": "json",
    })
    req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return page["imageinfo"][0]["thumburl"]


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())


def crop_square(src, dest, size=240):
    """Recadre en carré centré horizontalement, calé en haut, via sips."""
    # Lire les dimensions
    out = subprocess.check_output(["sips", "-g", "pixelWidth", "-g", "pixelHeight", src],
                                  text=True)
    w = int(re.search(r"pixelWidth:\s*(\d+)", out).group(1))
    h = int(re.search(r"pixelHeight:\s*(\d+)", out).group(1))

    side = min(w, h)
    x0 = (w - side) // 2
    y0 = 0  # calé vers le haut

    import shutil
    shutil.copy2(src, dest)

    # Positionner l'offset puis recadrer
    subprocess.run(["sips", "--cropOffset", str(y0), str(x0), dest],
                   check=True, capture_output=True)
    subprocess.run(["sips", "-c", str(side), str(side), dest],
                   check=True, capture_output=True)
    # Redimensionner à 240×240
    subprocess.run(["sips", "-z", str(size), str(size), dest],
                   check=True, capture_output=True)
    # Convertir en JPEG qualité 82
    subprocess.run(["sips", "-s", "format", "jpeg",
                     "-s", "formatOptions", "82", dest,
                     "--out", dest], check=True, capture_output=True)


for slug, info in photos.items():
    dest = os.path.join(OUT, f"{slug}.jpg")
    print(f"{slug}...", end=" ", flush=True)
    try:
        title = filename_from_url(info["source"])
        thumb = get_thumb_url(title)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        download(thumb, tmp_path)
        crop_square(tmp_path, dest)
        os.unlink(tmp_path)
        print("OK")
    except Exception as e:
        print(f"ERREUR: {e}")
