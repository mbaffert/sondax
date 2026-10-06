#!/usr/bin/env python3
"""Graphique Polymarket à partager : image du « second tour » et bloc « Partager / Reprendre ».

Même mécanisme que partage_premier_tour.py (mêmes classes CSS et même JS que
le bloc du premier tour), pour le graphique « Qui va accéder au second tour
d'après les marchés de prédiction ? » de l'accueil.

Produit, à partir de data/polymarket.json et data/candidats.json :
- site/partage/polymarket.png   1200 × 630, URL stable, toujours la dernière version
et injecte le bloc « Partager / Reprendre » dans site/index.html, entre les
marqueurs BEGIN/END:partage-polymarket, sous le graphique.

Ce ne sont pas des sondages : la loi de 1977 ne s'applique pas, pas de veille.
Le lien du code à copier renvoie vers l'ancre #bloc-polymarket de l'accueil.
"""

import datetime, html as html_mod, json, pathlib, sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from courbes_modele import MOIS_COURTS  # noqa: E402
from partage_modele import police  # noqa: E402

SORTIE = ROOT / "site" / "partage"
POLY_PATH = ROOT / "data" / "polymarket.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
INDEX_PATH = ROOT / "site" / "index.html"
BEGIN = "<!-- BEGIN:partage-polymarket -->"
END = "<!-- END:partage-polymarket -->"

BASE = "https://sondax.fr"
URL_LIEN = f"{BASE}/#bloc-polymarket"
URL_IMAGE = f"{BASE}/partage/polymarket.png"   # stable : toujours la dernière version
TAILLE = (1200, 630)
JOURS = 90
NB_COURBES = 5

FOND, TEXTE, GRIS, BLEU, RAIL = "#F7F8F5", "#202632", "#66707D", "#0C6CF2", "#E6E8E3"

# Le code à copier sert la même image tous les jours : il ne cite aucun chiffre.
ALT_CODE = ("Courbes des cotes Polymarket pour l’accès au second tour de la présidentielle 2027 : "
            "probabilités de marché, pas des intentions de vote")

ICONE = ('<svg class="pt-partage-icone" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" '
         'focusable="false" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
         'stroke-linejoin="round"><circle cx="4" cy="8" r="2"/><circle cx="12" cy="3.5" r="2"/>'
         '<circle cx="12" cy="12.5" r="2"/><path d="M5.8 7l4.4-2.5M5.8 9l4.4 2.5"/></svg>')


def faits():
    poly = json.loads(POLY_PATH.read_text(encoding="utf-8"))
    candidats = json.loads(CANDIDATS_PATH.read_text(encoding="utf-8"))
    marche = poly["marches"]["second_tour"]["candidats"]
    classement = sorted(((c, v["prix_actuel"]) for c, v in marche.items()
                         if v.get("prix_actuel") is not None and v.get("historique")),
                        key=lambda kv: -kv[1])
    if len(classement) < 2:
        return None
    jour = max(p["d"] for c, _ in classement[:NB_COURBES] for p in marche[c]["historique"])
    return {"jour": jour, "classement": classement, "marche": marche, "candidats": candidats}


def date_lettres(iso):
    from build_index_premier_tour import date_lettres as dl  # import tardif
    return dl(iso)


def pct(p):
    return f"{round(p * 100)} %"


def tracer(f):
    w, h = TAILLE
    m = 56
    img = Image.new("RGB", TAILLE, FOND)
    d = ImageDraw.Draw(img)

    d.text((m, 34), "SONDAX · MARCHÉS DE PRÉDICTION", font=police("gras", 20), fill=BLEU)
    d.text((m, 62), "Présidentielle 2027 : qui au second tour ?", font=police("titre", 42), fill=TEXTE)
    d.text((m, 118), f"Cotes Polymarket sur {JOURS} jours (en %). Deux places : le total avoisine 200 %.",
           font=police("corps", 22), fill=GRIS)

    fin = datetime.date.fromisoformat(f["jour"])
    debut = fin - datetime.timedelta(days=JOURS)
    tracees = [c for c, _ in f["classement"][:NB_COURBES]]
    serie = {c: [(datetime.date.fromisoformat(p["d"]), p["p"] * 100) for p in f["marche"][c]["historique"]
                 if p["d"] >= debut.isoformat()] for c in tracees}
    maxi = max(v for pts in serie.values() for _, v in pts)
    pas = 10 if maxi <= 40 else 20
    haut = max(pas, -(-int(maxi + 0.999) // pas) * pas)

    gauche, droite, sommet, bas = m + 38, w - m - 310, 176, h - 104
    X = lambda dt: gauche + (droite - gauche) * (dt - debut).days / JOURS
    Y = lambda v: bas - (bas - sommet) * v / haut

    fa = police("corps", 22)
    for v in range(0, haut + 1, pas):
        d.line((gauche, Y(v), droite, Y(v)), fill=RAIL, width=2)
        d.text((gauche - 10, Y(v)), str(v), font=fa, fill=GRIS, anchor="rm")
    for k in range(4):
        dt = debut + datetime.timedelta(days=round(JOURS * k / 3))
        d.text((X(dt), bas + 14), f"{dt.day} {MOIS_COURTS[dt.month - 1]}", font=fa, fill=GRIS,
               anchor="la" if k == 0 else "ra" if k == 3 else "ma")

    etiquettes = []
    for cid in tracees:
        pts = [(X(dt), Y(v)) for dt, v in serie[cid]]
        if not pts:
            continue
        couleur = f["candidats"][cid]["couleur"]
        d.line(pts, fill=couleur, width=5, joint="curve")
        xe, ye = pts[-1]
        d.ellipse((xe - 7, ye - 7, xe + 7, ye + 7), fill=couleur)
        etiquettes.append([ye, cid, couleur])

    etiquettes.sort()
    for i in range(1, len(etiquettes)):
        etiquettes[i][0] = max(etiquettes[i][0], etiquettes[i - 1][0] + 36)
    valeurs = dict(f["classement"])
    fn, fv = police("gras", 27), police("titre", 27)
    for y, cid, couleur in etiquettes:
        x = droite + 16
        d.rounded_rectangle((x, y - 6, x + 6, y + 6), radius=3, fill=couleur)
        d.text((x + 16, y), f["candidats"][cid]["nom"], font=fn, fill=TEXTE, anchor="lm")
        d.text((w - m, y), pct(valeurs[cid]), font=fv, fill=TEXTE, anchor="rm")

    d.line((m, h - 62, w - m, h - 62), fill=RAIL, width=2)
    d.text((m, h - 32),
           f"Source : Polymarket, via Sondax · {date_lettres(f['jour'])} · prix de marché, pas des intentions de vote",
           font=police("corps", 20), fill=GRIS, anchor="lm")
    d.text((w - m, h - 32), "sondax.fr", font=police("titre", 26), fill=BLEU, anchor="rm")
    return img


def code_html():
    return (f'<figure><a href="{URL_LIEN}"><img src="{URL_IMAGE}" alt="{ALT_CODE}"></a>'
            f'<figcaption>Source : <a href="{BASE}/">Sondax</a>, d’après Polymarket</figcaption></figure>')


def bloc_partage():
    return f'''<link rel="stylesheet" href="assets/partage-premier-tour.css?v=1">
<details class="pt-partage" id="partage-polymarket">
  <summary>{ICONE}Partager / Reprendre</summary>
  <div class="pt-partage-corps">
    <p>Reprenez ce graphique dans un article ou sur un site : l’image est mise à jour automatiquement et le lien renvoie vers Sondax. Ce sont des prix de marché, pas des intentions de vote.</p>
    <div class="pt-actions">
      <button type="button" class="pt-bouton" data-copier="{URL_LIEN}" hidden>Copier le lien</button>
      <a class="pt-bouton" href="partage/polymarket.png" download="sondax-polymarket.png">Image</a>
    </div>
    <label class="pt-etiquette" for="pm-code">Code HTML à copier</label>
    <textarea id="pm-code" class="pt-code" readonly rows="6" spellcheck="false">{html_mod.escape(code_html(), quote=False)}</textarea>
    <div class="pt-actions">
      <button type="button" class="pt-bouton" data-copier-cible="pm-code" hidden>Copier le code</button>
      <span class="pt-etat" role="status" aria-live="polite"></span>
    </div>
  </div>
</details>
<script src="assets/partage-premier-tour.js?v=2" defer></script>'''


def injecter(html_bloc):
    contenu = INDEX_PATH.read_text(encoding="utf-8")
    try:
        i, j = contenu.index(BEGIN), contenu.index(END)
    except ValueError:
        sys.exit(f"partage_polymarket : marqueurs {BEGIN} / {END} introuvables dans {INDEX_PATH}")
    INDEX_PATH.write_text(contenu[:i] + BEGIN + "\n" + html_bloc + "\n" + contenu[j:], encoding="utf-8")


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    f = faits()
    if f is None:
        sys.exit("ERREUR partage polymarket : moins de deux candidats cotés")
    tracer(f).save(SORTIE / "polymarket.png", optimize=True)
    injecter(bloc_partage())
    print("Graphique Polymarket à reprendre : partage/polymarket.png, bloc injecté dans index.html")


if __name__ == "__main__":
    main()
