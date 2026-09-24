#!/usr/bin/env python3
"""Récupère et uniformise les logos des instituts (site/logos/).

Script ponctuel, exécuté à la main quand un institut entre dans le
référentiel ou change de logo ; les fichiers produits sont versionnés.
Il ne fait pas partie du build.

Source : champ `logo_source` de data/instituts.json
- "commons:<Nom de fichier>"  fichier de Wikimedia Commons ;
- "fr:<Nom de fichier>"       fichier local de fr.wikipedia.org ;
- "https://…"                  URL directe (site de l'institut) ;
- null                         pas de source connue, logo non traité.

Traitement, identique pour tous :
- SVG conservé en SVG, PNG en PNG sur fond transparent ;
- marges recadrées au plus près du tracé ;
- rendu monochrome gris foncé (#33383F) ; les aplats clairs à l'intérieur du
  logo restent blancs, un fond clair couvrant tout le logo est supprimé ;
- la hauteur d'affichage est fixée par la CSS des pages institut, le
  recadrage garantit que la même hauteur donne la même taille visuelle ;
  en thème sombre, la CSS inverse le gris (filter: invert).

Dépendances (hors build) : pip install svgelements pillow

Usage :
    python scripts/logos.py              tous les instituts
    python scripts/logos.py ifop elabe   instituts choisis
    python scripts/logos.py --local f.svg ifop   traiter un fichier déjà téléchargé
"""

import hashlib
import io
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

GRIS = "#33383F"
GRIS_RGB = (0x33, 0x38, 0x3F)
HAUTEUR_PNG = 120        # px, soit ~4x la hauteur d'affichage
SEUIL_CLAIR = 0.85       # luminance au-delà de laquelle une couleur est « claire »
UA = "Sondax/1.0 (https://sondax.fr ; contact@sondax.fr) logos.py"

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------

def url_source(source):
    """Résout `logo_source` en URL de téléchargement."""
    if source.startswith(("http://", "https://")):
        return source
    wiki, nom = source.split(":", 1)
    nom = nom.strip().replace(" ", "_")
    h = hashlib.md5(nom.encode("utf-8")).hexdigest()
    base = {"commons": "commons", "fr": "fr"}[wiki]
    return (f"https://upload.wikimedia.org/wikipedia/{base}/{h[0]}/{h[:2]}/"
            f"{urllib.parse.quote(nom)}")


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------

def luminance(rgb):
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def parse_couleur(valeur):
    """Couleur CSS → (r, g, b), ou None si non interprétable / sans effet."""
    v = valeur.strip().lower()
    if v in ("", "none", "transparent", "currentcolor", "inherit") or v.startswith("url("):
        return None
    try:
        from PIL import ImageColor
        c = ImageColor.getrgb(v)
        return c[:3]
    except (ValueError, ImportError):
        return None


def recolorer(valeur):
    rgb = parse_couleur(valeur)
    if rgb is None:
        return valeur
    return "#FFFFFF" if luminance(rgb) > SEUIL_CLAIR else GRIS


PROPS_COULEUR = ("fill", "stroke", "stop-color", "color", "flood-color")


def recolorer_style(style):
    def repl(m):
        return f"{m.group(1)}:{recolorer(m.group(2))}"
    motif = r"(" + "|".join(PROPS_COULEUR) + r")\s*:\s*([^;]+)"
    return re.sub(motif, repl, style)


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

def bbox_svg(data):
    """Boîte englobante (x0, y0, x1, y1) des éléments tracés, en unités viewBox."""
    import svgelements as se
    svg = se.SVG.parse(io.BytesIO(data), reify=True)
    boites = []
    for el in svg.elements():
        if isinstance(el, (se.Shape, se.Text)) and not isinstance(el, se.SVG):
            if isinstance(el, se.Shape) and el.fill in (None, "none") and el.stroke in (None, "none"):
                continue
            b = el.bbox(with_stroke=True) if isinstance(el, se.Shape) else el.bbox()
            # Boîte dégénérée (texte vide, point isolé) : ignorée
            if b and all(v is not None for v in b) and (b[2] > b[0] or b[3] > b[1]):
                boites.append(b)
    if not boites:
        return None
    # svgelements applique la transformation viewBox → pixels ; on la défait
    vb = svg.viewbox
    sx = sy = 1.0
    tx = ty = 0.0
    if vb is not None and svg.width and svg.height:
        sx = vb.width / svg.width
        sy = vb.height / svg.height
        tx, ty = vb.x, vb.y
    x0 = min(b[0] for b in boites) * sx + tx
    y0 = min(b[1] for b in boites) * sy + ty
    x1 = max(b[2] for b in boites) * sx + tx
    y1 = max(b[3] for b in boites) * sy + ty
    return x0, y0, x1, y1


def est_fond(el, bbox):
    """Rectangle clair couvrant (presque) tout le logo : un fond à supprimer."""
    if el.tag.split("}")[-1] != "rect":
        return False
    fill = el.get("fill") or ""
    m = re.search(r"fill\s*:\s*([^;]+)", el.get("style") or "")
    if m:
        fill = m.group(1)
    rgb = parse_couleur(fill)
    if rgb is None or luminance(rgb) <= SEUIL_CLAIR:
        return False
    try:
        w = float(el.get("width", "0").rstrip("px%"))
        h = float(el.get("height", "0").rstrip("px%"))
    except ValueError:
        return False
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    return el.get("width", "").endswith("%") or (w >= 0.95 * bw and h >= 0.95 * bh)


def traiter_svg(data):
    """Retourne (svg_bytes, None) ou (None, motif d'échec)."""
    texte = data.decode("utf-8", errors="replace")
    if "<image" in texte:
        return None, "SVG contenant une image matricielle"
    racine = ET.fromstring(data)

    # 1. Supprimer les fonds clairs pleine taille, puis recalculer la boîte
    bbox = bbox_svg(data)
    if bbox is None:
        return None, "aucun tracé détecté"
    for parent in racine.iter():
        for el in list(parent):
            if est_fond(el, bbox):
                parent.remove(el)
    data = ET.tostring(racine, encoding="utf-8")
    bbox = bbox_svg(data)
    if bbox is None:
        return None, "aucun tracé détecté après retrait du fond"

    # 2. Monochrome
    for el in racine.iter():
        for attr in PROPS_COULEUR:
            if el.get(attr) is not None:
                el.set(attr, recolorer(el.get(attr)))
        if el.get("style"):
            el.set("style", recolorer_style(el.get("style")))
        if el.tag.split("}")[-1] == "style" and el.text:
            el.text = re.sub(
                r"(" + "|".join(PROPS_COULEUR) + r")\s*:\s*([^;}]+)",
                lambda m: f"{m.group(1)}:{recolorer(m.group(2))}", el.text)
    if racine.get("fill") is None:
        racine.set("fill", GRIS)   # couleur par défaut (noir implicite)

    # 3. Recadrage : viewBox au plus près, dimensions intrinsèques retirées
    x0, y0, x1, y1 = bbox
    marge = 0.01 * (y1 - y0)
    racine.set("viewBox", f"{x0 - marge:.3f} {y0 - marge:.3f} "
                          f"{x1 - x0 + 2 * marge:.3f} {y1 - y0 + 2 * marge:.3f}")
    for attr in ("width", "height", "x", "y"):
        racine.attrib.pop(attr, None)
    racine.set("preserveAspectRatio", "xMinYMid meet")
    return ET.tostring(racine, encoding="utf-8", xml_declaration=False), None


# ---------------------------------------------------------------------------
# PNG (et autres formats matriciels)
# ---------------------------------------------------------------------------

def traiter_png(data):
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    w, h = img.size
    px = img.load()

    # Couleur de fond : moyenne des coins opaques ; None si le fond est transparent
    coins = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    opaques = [c for c in coins if c[3] > 200]
    fond = None
    if len(opaques) >= 3:
        fond = tuple(sum(c[i] for c in opaques) / len(opaques) for i in range(3))

    # Encre de chaque pixel, normalisée sur le pixel le plus marqué :
    # - fond opaque : écart à la couleur du fond ;
    # - fond transparent : obscurité (les aplats clairs deviennent transparents).
    def brut(c):
        if fond is not None:
            return max(abs(c[0] - fond[0]), abs(c[1] - fond[1]), abs(c[2] - fond[2])) / 255
        return 1 - luminance(c[:3])

    pixels = list(getattr(img, "get_flattened_data", img.getdata)())
    maxi = max((brut(c) for c in pixels if c[3] > 128), default=0)
    if maxi < 0.1:
        return None, "logo sans contraste avec son fond"
    alphas = []
    for c in pixels:
        a = int(c[3] * min(1.0, brut(c) / maxi))
        alphas.append(a if a > 8 else 0)
    sortie = Image.new("RGBA", (w, h))
    sortie.putdata([(*GRIS_RGB, a) for a in alphas])

    boite = sortie.getbbox()
    if not boite:
        return None, "image vide après retrait du fond"
    sortie = sortie.crop(boite)
    cw, ch = sortie.size
    if ch > HAUTEUR_PNG:
        sortie = sortie.resize((round(cw * HAUTEUR_PNG / ch), HAUTEUR_PNG), Image.LANCZOS)
    elif ch < 40:
        return None, f"résolution trop faible ({ch} px de haut après recadrage)"
    buf = io.BytesIO()
    sortie.save(buf, "PNG", optimize=True)
    return buf.getvalue(), None


# ---------------------------------------------------------------------------

def traiter(slug, inst, data):
    dest = SITE / inst["logo"]
    est_svg = data.lstrip()[:5] in (b"<?xml", b"<svg ") or b"<svg" in data[:500]
    if dest.suffix == ".svg" and not est_svg:
        return "attendu SVG, reçu un fichier matriciel (changer `logo` en .png)"
    if dest.suffix == ".png" and est_svg:
        return "reçu un SVG (changer `logo` en .svg)"
    out, erreur = traiter_svg(data) if est_svg else traiter_png(data)
    if erreur:
        return erreur
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out)
    return None


def main(argv):
    referentiel = json.loads((ROOT / "data" / "instituts.json").read_text(encoding="utf-8"))
    local = None
    if argv[:1] == ["--local"]:
        local, argv = pathlib.Path(argv[1]), argv[2:]
    slugs = argv or list(referentiel)

    echecs = []
    for slug in slugs:
        inst = referentiel[slug]
        if local:
            data = local.read_bytes()
        else:
            source = inst.get("logo_source")
            if not source:
                echecs.append((slug, "pas de source connue (logo_source vide)"))
                continue
            try:
                data = telecharger(url_source(source))
            except Exception as e:
                echecs.append((slug, f"téléchargement impossible : {e}"))
                continue
        erreur = traiter(slug, inst, data)
        if erreur:
            echecs.append((slug, erreur))
        else:
            print(f"  ok  {slug} → site/{inst['logo']}")

    for slug, motif in echecs:
        print(f"  ÉCHEC  {slug} : {motif}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
