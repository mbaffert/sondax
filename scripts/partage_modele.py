#!/usr/bin/env python3
"""Images de partage du modèle Sondax (SPEC §14.15).

Lit data/derived/modele.json et écrit dans site/partage/ deux images datées :
modele-<jour>-og.png (1200 × 630 : OpenGraph, LinkedIn, X) et
modele-<jour>-carre.png (1080 × 1080 : messageries). Le gabarit dépend de
l'événement du jour : duel principal, mouvement ou basculement. Écrit aussi
site/partage/modele.json (gabarit, phrase, chemins) pour le bouton Partager.
"""

import datetime, json, pathlib, sys
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import textes_modele as T  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELE_PATH = ROOT / "data" / "derived" / "modele.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
SORTIE = ROOT / "site" / "partage"
POLICES = pathlib.Path(__file__).resolve().parent / "fonts"

FOND, TEXTE, GRIS, BLEU, BLEU_NUIT, RAIL = "#F7F8F5", "#202632", "#66707D", "#0C6CF2", "#0B2E6F", "#E6E8E3"
FORMATS = {"og": (1200, 630), "carre": (1080, 1080)}


def police(nom, taille):
    fichiers = {"titre": "space-grotesk-latin-700-normal.woff",
                "titre2": "space-grotesk-latin-600-normal.woff",
                "corps": "ibm-plex-sans-latin-400-normal.woff",
                "gras": "ibm-plex-sans-latin-600-normal.woff"}
    return ImageFont.truetype(str(POLICES / fichiers[nom]), taille)


def texte_brut(s):
    return s.replace("&nbsp;", " ")


def jour_paris(modele):
    d = datetime.datetime.fromisoformat(modele["date"].replace("Z", "+00:00"))
    return d.astimezone(ZoneInfo("Europe/Paris")).date()


def date_longue(d):
    return f"{'1er' if d.day == 1 else d.day} {T.MOIS[d.month - 1]} {d.year}"


def choisir(modele, candidats, index):
    """(gabarit, titre, sous-titre) de l'image du jour."""
    ordre = list(modele["candidats"])
    ev = modele.get("changement") or {}
    t = ev.get("type")
    if t in ("candidate_gain", "candidate_loss") and ev.get("horizon") == "7j":
        x = T.nom(candidats, ev["candidate"])
        n = abs(ev["delta"])
        verbe = "gagne" if t == "candidate_gain" else "perd"
        sous = "Chances d’être au second tour, si on votait dimanche."
        ids = ev.get("sondages_declencheurs") or []
        if len(ids) in (1, 2):
            qui = T.nommer_sondages(ids, index)
            sous = f"Après {qui[0].lower() + qui[1:]}."
        return ("mouvement", f"{x} {verbe} {n} chances d’être au second tour en une semaine.", sous)
    if t == "deuxieme_change" or modele["accroche"]["regle"] == "serree":
        return ("basculement", "La course à la deuxième place devient indécise.",
                modele["accroche"]["detail"])
    a, b = sorted(modele["duels"][0]["candidats"], key=ordre.index)
    return ("duel", f"{T.nom(candidats, a)} – {T.nom(candidats, b)}",
            "Le second tour le plus fréquent aujourd’hui.")


def couper(draw, texte, fonte, largeur):
    mots, lignes, ligne = texte.split(), [], ""
    for m in mots:
        essai = f"{ligne} {m}".strip()
        if draw.textlength(essai, font=fonte) <= largeur:
            ligne = essai
        else:
            lignes.append(ligne)
            ligne = m
    if ligne:
        lignes.append(ligne)
    return lignes


def dessiner(modele, candidats, gabarit, titre, sous, fmt, jour):
    w, h = FORMATS[fmt]
    carre = fmt == "carre"
    img = Image.new("RGB", (w, h), FOND)
    d = ImageDraw.Draw(img)
    m = 72 if carre else 64
    y = m

    d.text((m, y), "SONDAX · MODÈLE", font=police("gras", 22), fill=BLEU)
    y += 44
    d.text((m, y), "Et si on votait dimanche ?", font=police("titre2", 40 if carre else 34), fill=GRIS)
    y += 70 if carre else 58

    taille = 76 if gabarit == "duel" else (62 if carre else 54)
    ft = police("titre", taille)
    for ligne in couper(d, titre, ft, w - 2 * m):
        d.text((m, y), ligne, font=ft, fill=TEXTE)
        y += int(taille * 1.12)
    y += 10
    fs = police("corps", 30 if carre else 26)
    for ligne in couper(d, texte_brut(sous), fs, w - 2 * m)[:2]:
        d.text((m, y), ligne, font=fs, fill=GRIS)
        y += 40 if carre else 34

    # Trois premiers : barres
    y = max(y + 30, h - (430 if carre else 250))
    fn, fc = police("gras", 30 if carre else 24), police("titre", 34 if carre else 26)
    pas = 96 if carre else 58
    for c, v in list(modele["candidats"].items())[:3]:
        q = v["qualification_exacte"]
        d.text((m, y), candidats[c]["nom"], font=fn, fill=TEXTE)
        lib = f"{T.chances(q)} sur 100"
        d.text((w - m - d.textlength(lib, font=fc), y - 4), lib, font=fc, fill=TEXTE)
        yb = y + (44 if carre else 34)
        d.rounded_rectangle((m, yb, w - m, yb + 12), radius=6, fill=RAIL)
        d.rounded_rectangle((m, yb, m + max(12, (w - 2 * m) * q / 100), yb + 12), radius=6,
                            fill=candidats[c]["couleur"])
        y += pas

    pied = f"sondax.fr · {date_longue(jour)} · Ne prédit pas avril 2027"
    d.text((m, h - m + 8 - (0 if carre else 16)), pied, font=police("corps", 22), fill=GRIS)
    return img


def main():
    import veille
    if veille.en_veille():
        for ancien in SORTIE.glob("modele*"):
            ancien.unlink()
        print("Veille électorale (loi de 1977) : pas d'image de partage")
        return
    modele = json.loads(MODELE_PATH.read_text())
    candidats = json.loads(CANDIDATS_PATH.read_text())
    index = {s["id"]: s for s in json.loads(SONDAGES_PATH.read_text())}
    jour = jour_paris(modele)
    gabarit, titre, sous = choisir(modele, candidats, index)

    SORTIE.mkdir(parents=True, exist_ok=True)
    for ancien in SORTIE.glob("modele-*.png"):
        ancien.unlink()
    chemins = {}
    for fmt in FORMATS:
        nom = f"modele-{jour.isoformat()}-{fmt}.png"
        dessiner(modele, candidats, gabarit, titre, sous, fmt, jour).save(SORTIE / nom, optimize=True)
        chemins[fmt] = f"partage/{nom}"
    phrase = f"{modele['accroche']['titre']} {texte_brut(modele['accroche']['detail'])}"
    (SORTIE / "modele.json").write_text(json.dumps(
        {"gabarit": gabarit, "titre": titre, "phrase": phrase, "images": chemins},
        ensure_ascii=False, indent=1) + "\n")
    print(f"Images de partage ({gabarit}) : {', '.join(chemins.values())}")


if __name__ == "__main__":
    main()
