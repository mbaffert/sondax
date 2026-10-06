#!/usr/bin/env python3
"""Graphique du premier tour à reprendre : « linkable asset » (page, images, bloc).

Même mécanisme que partage_modele.py : images PNG tracées avec Pillow dans
site/partage/ (dossier ignoré par git, produit au build), une image datée pour
og:image (les caches Facebook, LinkedIn et X ne la rechargent pas sous la même
URL) et une image à l'URL stable pour le code HTML à copier.

Produit, à partir de data/derived/series-t1.json, data/sondages.json et
data/candidats.json :
- site/partage/premier-tour.png            URL stable, toujours la dernière version
- site/partage/premier-tour-AAAA-MM-JJ.png 1200 × 630, seule la dernière est gardée
- site/partage/premier-tour.html           page à l'URL stable, avec le bloc déplié

Le bloc « Partager / Reprendre » (source_html) est aussi injecté sous le graphique
de l'accueil par build_index_premier_tour.py. En veille électorale (loi de 1977),
rien n'est produit, comme pour le modèle, et l'accueil n'affiche plus le bloc.
"""

import datetime, html as html_mod, json, pathlib, sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from balise_time import time_tag  # noqa: E402
from courbes_modele import MOIS_COURTS  # noqa: E402
from partage_modele import police  # noqa: E402

SORTIE = ROOT / "site" / "partage"
SERIES_PATH = ROOT / "data" / "derived" / "series-t1.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"

BASE = "https://sondax.fr"
URL_PAGE = f"{BASE}/partage/premier-tour.html"   # stable : ne jamais la changer
URL_IMAGE = f"{BASE}/partage/premier-tour.png"   # stable : toujours la dernière version
TAILLE = (1200, 630)
JOURS = 90          # fenêtre des courbes
NB_COURBES = 5      # candidats tracés (les mieux placés), pour rester lisible en petit

FOND, TEXTE, GRIS, BLEU, RAIL = "#F7F8F5", "#202632", "#66707D", "#0C6CF2", "#E6E8E3"

# Mention à reprendre : celle de la section « Licence et citation » de /donnees
# (build_donnees.py). La licence elle-même vient de build_jsonld_dataset.py.
MENTION = "Sondax, d’après Wikipédia"

# Texte de remplacement du code à copier : la même image sert tous les jours,
# il ne doit donc citer aucun chiffre.
ALT_CODE = ("Courbes des intentions de vote au premier tour de la présidentielle 2027, "
            "moyenne des sondages")


# ---------- données ----------

def faits():
    """Tout ce que les trois sorties affichent, lu dans data/ (aucun chiffre en dur)."""
    from build_index_premier_tour import (  # import tardif : ce module est aussi importé par lui
        candidates_in_window, derniers_scores, sondages_dans_fenetre, date_lettres, fmt_pct)
    from build_header import candidate_full_name

    series_data = json.loads(SERIES_PATH.read_text(encoding="utf-8"))
    sondages = json.loads(SONDAGES_PATH.read_text(encoding="utf-8"))
    candidats = json.loads(CANDIDATS_PATH.read_text(encoding="utf-8"))

    derniers = sorted(derniers_scores(series_data).items(), key=lambda kv: -kv[1])
    if len(derniers) < 2:
        return None
    debut_fenetre, dans_fenetre = sondages_dans_fenetre(series_data, sondages)
    jour = series_data["date_fin"]
    return {
        "jour": jour, "jour_lettres": date_lettres(jour),
        "debut_fenetre": debut_fenetre, "debut_fenetre_lettres": date_lettres(debut_fenetre),
        "n_sondages": len(dans_fenetre),
        "classement": derniers, "series": series_data["series"], "candidats": candidats,
        "nom_complet": lambda cid: candidate_full_name(cid, candidats),
        "pct": fmt_pct,
    }


def pluriel_points(ecart):
    return "point" if ecart < 2 else "points"


def lecture(f):
    """Deux ou trois phrases de lecture : leader, écart, volume et date."""
    (a, va), (b, vb) = f["classement"][:2]
    nom_a, nom_b = f["nom_complet"](a), f["nom_complet"](b)
    en_tete = ("est en tête des sondages du premier tour" if f["candidats"].get(a, {}).get("type") == "parti"
               else "arrive en tête des sondages du premier tour de la présidentielle 2027")
    jour = time_tag(f["jour"], f["jour_lettres"])
    ecart = va - vb
    ecart_fmt = f"{ecart:.1f}".replace(".", ",")
    depuis = time_tag(f["debut_fenetre"], f["debut_fenetre_lettres"])
    if f["n_sondages"] == 1:
        base = f"d’un seul sondage publié depuis le {depuis}"
    else:
        base = f"des {f['n_sondages']} sondages publiés depuis le {depuis}"
    return [
        f"{nom_a} {en_tete} avec {f['pct'](va)} des intentions de vote au {jour}, "
        f"devant {nom_b} ({f['pct'](vb)}).",
        f"L’écart entre les deux est de {ecart_fmt} {pluriel_points(ecart)}.",
        f"Ces chiffres sont ceux de la moyenne pondérée {base}, mise à jour le {jour}.",
    ]


def texte_source(f):
    """« Source : Sondax, agrégation de N sondages » (brut, sans balise)."""
    n = f["n_sondages"]
    return f"Source : Sondax, agrégation de {n} sondage{'s' if n > 1 else ''}"


# ---------- bloc « Partager / Reprendre » ----------

ICONE = ('<svg class="pt-partage-icone" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" '
         'focusable="false" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
         'stroke-linejoin="round"><circle cx="4" cy="8" r="2"/><circle cx="12" cy="3.5" r="2"/>'
         '<circle cx="12" cy="12.5" r="2"/><path d="M5.8 7l4.4-2.5M5.8 9l4.4 2.5"/></svg>')


def code_html():
    return (f'<figure><a href="{URL_PAGE}"><img src="{URL_IMAGE}" alt="{ALT_CODE}"></a>'
            f'<figcaption>Source : <a href="{BASE}/">Sondax</a>, agrégation de sondages</figcaption></figure>')


def bloc_partage(prefix, ouvert=False, lien_page=True):
    """Bloc <details> natif. Tout le texte est dans le HTML statique ; le seul JS
    (assets/partage-premier-tour.js) fait apparaître et brancher les boutons de copie.
    `prefix` : chemin relatif vers la racine du site (« » ou « ../ »)."""
    page = (f'\n      <a class="pt-bouton" href="{prefix}partage/premier-tour.html">Page de partage</a>'
            if lien_page else "")
    return f'''<link rel="stylesheet" href="{prefix}assets/partage-premier-tour.css?v=1">
<details class="pt-partage" id="partage-premier-tour"{" open" if ouvert else ""}>
  <summary>{ICONE}Partager / Reprendre</summary>
  <div class="pt-partage-corps">
    <p>Reprenez ce graphique dans un article ou sur un site : l’image est mise à jour automatiquement et le lien renvoie vers Sondax.</p>
    <div class="pt-actions">
      <button type="button" class="pt-bouton" data-copier="{URL_PAGE}" hidden>Copier le lien</button>
      <a class="pt-bouton" href="{prefix}partage/premier-tour.png" download="sondax-premier-tour.png">Image</a>{page}
    </div>
    <label class="pt-etiquette" for="pt-code">Code HTML à copier</label>
    <textarea id="pt-code" class="pt-code" readonly rows="6" spellcheck="false">{html_mod.escape(code_html(), quote=False)}</textarea>
    <div class="pt-actions">
      <button type="button" class="pt-bouton" data-copier-cible="pt-code" hidden>Copier le code</button>
      <span class="pt-etat" role="status" aria-live="polite"></span>
    </div>
  </div>
</details>
<script src="{prefix}assets/partage-premier-tour.js?v=2" defer></script>'''


def source_html(f, prefix="", avec_partage=True):
    """Ligne de source sous le graphique de l'accueil, bloc de partage à droite."""
    jour = time_tag(f["jour"], f["jour_lettres"])
    return (f'<div class="pt-source">\n'
            f'  <p class="subtitle">{texte_source(f)} · mis à jour le {jour} · '
            f'<a href="{prefix}methodologie.html" style="font-weight:500;">méthode</a></p>\n'
            f'{bloc_partage(prefix) if avec_partage else ""}\n</div>')


# ---------- image ----------

def tracer(f):
    w, h = TAILLE
    m = 56
    img = Image.new("RGB", TAILLE, FOND)
    d = ImageDraw.Draw(img)
    sans_insecable = lambda s: s.replace(" ", " ").replace(" ", " ")

    d.text((m, 34), "SONDAX · SONDAGES", font=police("gras", 20), fill=BLEU)
    d.text((m, 62), "Présidentielle 2027 : le premier tour", font=police("titre", 42), fill=TEXTE)
    d.text((m, 118), f"Intentions de vote, moyenne pondérée des sondages, sur {JOURS} jours (en %)",
           font=police("corps", 22), fill=GRIS)

    fin = datetime.date.fromisoformat(f["jour"])
    debut = fin - datetime.timedelta(days=JOURS)
    tracees = [c for c, _ in f["classement"][:NB_COURBES]]
    maxi = max(v for c in tracees for p in f["series"][c] if p["d"] >= debut.isoformat()
               for v in [p["v"]] if v is not None)
    pas = 5 if maxi <= 20 else 10
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
        pts = [(X(datetime.date.fromisoformat(p["d"])), Y(p["v"])) for p in f["series"][cid]
               if p["v"] is not None and p["d"] >= debut.isoformat()]
        if not pts:
            continue
        couleur = f["candidats"][cid]["couleur"]
        d.line(pts, fill=couleur, width=5, joint="curve")
        xe, ye = pts[-1]
        d.ellipse((xe - 7, ye - 7, xe + 7, ye + 7), fill=couleur)
        etiquettes.append([ye, cid, couleur])

    # Étiquettes de fin de courbe, espacées d'au moins 30 px pour ne pas se chevaucher
    etiquettes.sort()
    for i in range(1, len(etiquettes)):
        etiquettes[i][0] = max(etiquettes[i][0], etiquettes[i - 1][0] + 36)
    valeurs = dict(f["classement"])
    fn, fv = police("gras", 27), police("titre", 27)
    for y, cid, couleur in etiquettes:
        x = droite + 16
        d.rounded_rectangle((x, y - 6, x + 6, y + 6), radius=3, fill=couleur)
        d.text((x + 16, y), f["candidats"][cid]["nom"], font=fn, fill=TEXTE, anchor="lm")
        d.text((w - m, y), sans_insecable(f["pct"](valeurs[cid])), font=fv, fill=TEXTE, anchor="rm")

    d.line((m, h - 62, w - m, h - 62), fill=RAIL, width=2)
    d.text((m, h - 32), f"{sans_insecable(texte_source(f))} · mis à jour le {f['jour_lettres']}",
           font=police("corps", 20), fill=GRIS, anchor="lm")
    d.text((w - m, h - 32), "sondax.fr", font=police("titre", 26), fill=BLEU, anchor="rm")
    return img


# ---------- page ----------

def alt_page(f):
    scores = ", ".join(f"{f['candidats'][c]['nom']} {f['pct'](f['classement'][i][1])}"
                       for i, c in enumerate([c for c, _ in f["classement"][:NB_COURBES]]))
    return (f"Courbes des intentions de vote au premier tour de la présidentielle 2027 sur {JOURS} jours, "
            f"moyenne des sondages. Au {f['jour_lettres']} : {scores}.").replace(" ", " ")


def licence_url():
    """Licence affichée sur /donnees (build_jsonld_dataset.py la déclare pour le jeu de données)."""
    from build_jsonld_dataset import compute_dataset
    return compute_dataset()["license"]


def jsonld(f, titre, description, image_datee):
    from build_jsonld_dataset import compute_dataset
    jeu = compute_dataset()
    org = {"@type": "Organization", "name": "Sondax", "url": f"{BASE}/"}
    return {
        "@context": "https://schema.org", "@type": "ImageObject",
        "name": titre, "description": description,
        "contentUrl": URL_IMAGE, "thumbnailUrl": image_datee,
        "encodingFormat": "image/png", "width": TAILLE[0], "height": TAILLE[1],
        "author": org, "creditText": MENTION,
        "datePublished": f["jour"], "dateModified": f["jour"],
        "license": jeu["license"], "acquireLicensePage": f"{BASE}/donnees.html",
        "isBasedOn": jeu["isBasedOn"], "inLanguage": "fr-FR",
        "mainEntityOfPage": URL_PAGE,
    }


def page(f, image_datee):
    from site_template import render_page
    esc = html_mod.escape
    titre = "Sondages du premier tour 2027 : le graphique à reprendre — Sondax"
    (a, va), (b, vb) = f["classement"][:2]
    description = (f"{f['candidats'][a]['nom']} ({f['pct'](va)}) devant {f['candidats'][b]['nom']} "
                   f"({f['pct'](vb)}) au premier tour de la présidentielle 2027, au {f['jour_lettres']}. "
                   f"Graphique libre de reprise, avec le code à copier.").replace(" ", " ")
    phrases = " ".join(lecture(f))
    body = f'''<main class="pt-page">
  <nav class="fil" aria-label="Fil d’Ariane"><a href="/">Sondax</a> › Graphique à reprendre</nav>
  <h1>Sondages du premier tour de la présidentielle 2027 : le graphique à reprendre</h1>
  <p class="pt-lecture">{phrases}</p>
  <figure class="pt-figure">
    <img src="{image_datee.rsplit("/", 1)[1]}" width="{TAILLE[0]}" height="{TAILLE[1]}" alt="{esc(alt_page(f))}">
    <figcaption>{texte_source(f)} · mis à jour le {time_tag(f["jour"], f["jour_lettres"])}</figcaption>
  </figure>
  {bloc_partage("../", ouvert=True, lien_page=False)}
  <p class="pt-licence">Licence : <a href="{esc(licence_url())}">CC BY-SA 4.0</a>, celle des données sur lesquelles
  repose le graphique. Mention à reprendre : <strong>{MENTION}</strong>, avec un lien vers sondax.fr.
  Détails sur la page <a href="../donnees.html">Données</a>.</p>
  <p><a href="../">Voir le graphique interactif</a> · <a href="../methodologie.html">Méthode</a></p>
</main>'''
    extra = (f'<meta property="og:image:alt" content="{esc(alt_page(f))}">\n'
             f'<link rel="stylesheet" href="../assets/partage-premier-tour.css?v=1">\n'
             f'<script type="application/ld+json">'
             f'{json.dumps(jsonld(f, titre, description, image_datee), ensure_ascii=False)}</script>')
    return render_page(title=esc(titre), meta_description=esc(description), canonical=URL_PAGE,
                       body_content=body, extra_head=extra, depth=1, og_image=image_datee)


# ---------- génération ----------

def main():
    import veille
    SORTIE.mkdir(parents=True, exist_ok=True)
    if veille.en_veille():
        for ancien in SORTIE.glob("premier-tour*"):
            ancien.unlink()
        print("Veille électorale (loi de 1977) : pas de graphique à reprendre")
        return
    f = faits()
    if f is None:
        sys.exit("ERREUR partage premier tour : moins de deux candidats dans la fenêtre")

    nom = f"premier-tour-{f['jour']}.png"
    img = tracer(f)
    for ancien in SORTIE.glob("premier-tour-*.png"):
        ancien.unlink()
    img.save(SORTIE / nom, optimize=True)
    img.save(SORTIE / "premier-tour.png", optimize=True)
    (SORTIE / "premier-tour.html").write_text(page(f, f"{BASE}/partage/{nom}"), encoding="utf-8")
    print(f"Graphique à reprendre : partage/premier-tour.html, premier-tour.png, {nom}")


if __name__ == "__main__":
    main()
