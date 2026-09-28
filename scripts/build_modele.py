#!/usr/bin/env python3
"""Page « Le modèle Sondax » et bloc d'accueil (SPEC §14.14).

Lit data/derived/modele.json (scripts/modele.py) et écrit :
- site/modele-sondax.html ;
- le bloc #bloc-modele de site/index.html, entre <!-- BEGIN:bloc-modele --> et
  <!-- END:bloc-modele -->.

Tout le texte est rendu au build. Échoue si un mot réservé à la page Méthode
apparaît dans le texte rendu (§14.3).
"""

import datetime, html, json, pathlib, re, sys
from zoneinfo import ZoneInfo

from site_template import render_page

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MODELE_PATH = ROOT / "data" / "derived" / "modele.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
BIOS_PATH = ROOT / "scripts" / "bios.json"
INDEX_PATH = SITE / "index.html"
PAGE_PATH = SITE / "modele-sondax.html"
PAGE_URL = "https://sondax.fr/modele-sondax.html"

BEGIN_MARKER = "<!-- BEGIN:bloc-modele -->"
END_MARKER = "<!-- END:bloc-modele -->"

# Mots réservés à la page Méthode (§14.3), cherchés en début de mot.
MOTS_INTERDITS = ["simulation", "probabilit", "tirage", "configuration", "échantillon",
                  "calibration", "dirichlet", "variance", "distribution"]

VERDICTS = {
    "quasi_sur": ("Quasi sûr d’y être", "Quasi sûre d’y être"),
    "bien_place": ("Bien placé", "Bien placée"),
    "rien_nest_joue": ("Rien n’est joué", "Rien n’est joué"),
    "surprise": ("Il faudrait une surprise", "Il faudrait une surprise"),
    "tres_improbable": ("Très improbable aujourd’hui", "Très improbable aujourd’hui"),
}

ACCUEIL_MIN, ACCUEIL_MAX, ACCUEIL_SEUIL = 2, 4, 5   # §14.14.1
DUELS_AFFICHES = 3                                   # §14.14.2

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

e = html.escape


# ------------------------------------------------------------------ formats

def sur_100(v):
    """« 38 sur 100 », « moins de 1 sur 100 », « plus de 99 sur 100 »."""
    if v < 0.5:
        return "moins de 1&nbsp;sur&nbsp;100"
    if v > 99.5:
        return "plus de 99&nbsp;sur&nbsp;100"
    return f"{round(v)}&nbsp;sur&nbsp;100"


def date_longue(iso_utc):
    d = datetime.datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    d = d.astimezone(ZoneInfo("Europe/Paris"))
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS[d.month - 1]} {d.year}"


def nom(candidats, slug):
    return candidats[slug]["nom"]


def nom_complet(candidats, slug):
    c = candidats[slug]
    return f"{c['prenom']} {c['nom']}" if c.get("prenom") else c["nom"]


def verdict_texte(candidats, slug, cle):
    feminin = candidats[slug].get("genre") == "f"
    return VERDICTS[cle][1 if feminin else 0]


def ordre_modele(modele):
    return list(modele["candidats"])


def libelle_duel(candidats, paire, ordre):
    a, b = sorted(paire, key=ordre.index)
    return f"{nom(candidats, a)} – {nom(candidats, b)}"


def couleur_duel(candidats, paire, ordre):
    """Couleur du moins bien placé des deux : c'est lui qui distingue le duel."""
    return candidats[max(paire, key=ordre.index)]["couleur"]


def portrait(candidats, slug, p=""):
    photo = SITE / "photos" / f"{slug}.jpg"
    couleur = candidats[slug]["couleur"]
    if photo.exists():
        return (f'<img class="mo-photo" src="{p}photos/{slug}.jpg" alt="" width="40" '
                f'height="40" loading="lazy" style="--c:{couleur}">')
    initiales = "".join(m[0] for m in nom_complet(candidats, slug).split()[:2])
    return f'<span class="mo-photo mo-initiales" style="--c:{couleur}">{e(initiales)}</span>'


def ligne_contexte(modele):
    n = modele["n_sondages"]
    return (f'Si on votait dimanche · Calculé sur {n} sondage{"s" if n > 1 else ""} · '
            f'Mis à jour le {date_longue(modele["date"])}.')


# ------------------------------------------------------------------- blocs

def ligne_candidat(candidats, pages, slug, v, p="", detail=True):
    q = v["qualification_exacte"]
    nom_html = e(nom_complet(candidats, slug))
    if slug in pages:
        nom_html = f'<a href="{p}{slug}.html">{nom_html}</a>'
    verdict = verdict_texte(candidats, slug, v["verdict"])
    largeur = max(q, 0.6)
    return f'''<li class="mo-ligne">
      {portrait(candidats, slug, p)}
      <div class="mo-corps">
        <div class="mo-tete"><span class="mo-nom">{nom_html}</span><span class="mo-chance">{sur_100(q)}</span></div>
        <div class="mo-barre" aria-hidden="true"><span style="width:{largeur:.1f}%;background:{candidats[slug]['couleur']}"></span></div>
        {f'<div class="mo-verdict">{e(verdict)}</div>' if detail else ''}
      </div>
    </li>'''


def candidats_accueil(modele):
    tries = list(modele["candidats"].items())
    retenus = [(c, v) for c, v in tries if v["qualification_exacte"] >= ACCUEIL_SEUIL]
    retenus = retenus[:ACCUEIL_MAX]
    if len(retenus) < ACCUEIL_MIN:
        retenus = tries[:ACCUEIL_MIN]
    return retenus


def accroche_html(modele, balise="p"):
    a = modele["accroche"]
    return (f'<{balise} class="mo-accroche"><strong>{e(a["titre"])}</strong> '
            f'{e(a["detail"])}</{balise}>')


def bloc_accueil(modele, candidats, pages):
    lignes = "\n    ".join(ligne_candidat(candidats, pages, c, v)
                           for c, v in candidats_accueil(modele))
    return f'''<div class="bloc" id="bloc-modele">
  <div class="section-label">Modèle Sondax</div>
  <h2>Et si on votait dimanche&nbsp;?</h2>
  <p class="subtitle">Qui serait au second tour, d’après les sondages d’aujourd’hui&nbsp;?</p>
  {accroche_html(modele)}
  <ul class="mo-liste">
    {lignes}
  </ul>
  <div class="mo-cta">
    <a class="mo-bouton" href="modele-sondax.html">Voir le modèle Sondax →</a>
    <span>Chances d’être au second tour, seconds tours possibles et évolution de la course.</span>
  </div>
  <p class="bloc-note">{ligne_contexte(modele)}<br>Ne prédit pas ce qui se passera d’ici avril.</p>
</div>'''


def grille_100(parts):
    """100 carrés répartis par la méthode du plus fort reste. `parts` :
    [(clé, valeur exacte sur 100, couleur)]."""
    entiers = [(k, int(v), v - int(v), c) for k, v, c in parts]
    manque = 100 - sum(n for _, n, _, _ in entiers)
    ordre = sorted(range(len(entiers)), key=lambda i: -entiers[i][2])
    nombres = [n for _, n, _, _ in entiers]
    for i in ordre[:max(manque, 0)]:
        nombres[i] += 1
    cases = []
    for (k, _, _, c), n in zip(entiers, nombres):
        cases += [f'<span style="background:{c}"></span>'] * n
    return f'<div class="mo-grille" aria-hidden="true">{"".join(cases)}</div>'


def section_duels(modele, candidats):
    ordre = ordre_modele(modele)
    duels = modele["duels"]
    principaux, autres = duels[:DUELS_AFFICHES], duels[DUELS_AFFICHES:]
    reste = max(0.0, 100 - sum(d["chance_exacte"] for d in principaux))

    lignes, parts = [], []
    for d in principaux:
        couleur = couleur_duel(candidats, d["candidats"], ordre)
        parts.append((d["candidats"], d["chance_exacte"], couleur))
        lignes.append(f'<tr><td><span class="mo-pastille" style="background:{couleur}"></span>'
                      f'{e(libelle_duel(candidats, d["candidats"], ordre))}</td>'
                      f'<td class="mo-num">{sur_100(d["chance_exacte"])}</td></tr>')
    parts.append(("autres", reste, "#D5D9DE"))

    details = ""
    if autres:
        sous = "".join(f'<tr><td>{e(libelle_duel(candidats, d["candidats"], ordre))}</td>'
                       f'<td class="mo-num">{sur_100(d["chance_exacte"])}</td></tr>'
                       for d in autres)
        details = f'''<details class="mo-repli">
      <summary><span class="mo-pastille" style="background:#D5D9DE"></span>Autres scénarios · {sur_100(reste)}</summary>
      <table class="mo-table">{sous}</table>
    </details>'''

    return f'''<section class="bloc" id="seconds-tours">
    <h2>Les seconds tours possibles</h2>
    <p class="subtitle">Sur 100 premiers tours refaits à partir des sondages d’aujourd’hui, voici combien de fois chaque duel sort.</p>
    <div class="mo-duels">
      {grille_100(parts)}
      <div>
        <table class="mo-table">{"".join(lignes)}</table>
        {details}
      </div>
    </div>
  </section>'''


def compact(v):
    """Valeur de tableau : « < 1 », « > 99 » ou l'entier."""
    if v < 0.5:
        return "&lt;&nbsp;1"
    if v > 99.5:
        return "&gt;&nbsp;99"
    return str(round(v))


def section_rangs(modele, candidats):
    lignes, restants = [], 0
    for c, v in modele["candidats"].items():
        if v["qualification_exacte"] < 1:
            restants += 1
            continue
        r = v["rang_exact"]
        lignes.append(f'<tr><td>{e(nom_complet(candidats, c))}</td>'
                      f'<td class="mo-num">{compact(r["1"])}</td>'
                      f'<td class="mo-num">{compact(r["2"])}</td>'
                      f'<td class="mo-num">{compact(r["3plus"])}</td></tr>')
    note = ""
    if restants:
        note = (f'<p class="mo-petit">Les {restants} autres candidats finissent troisièmes '
                f'ou au-delà plus de 99 fois sur 100.</p>')
    return f'''<section class="bloc" id="qui-finit-ou">
    <details class="mo-repli mo-rangs" open>
      <summary><h2>Qui finit où&nbsp;?</h2></summary>
      <p class="subtitle">Sur 100, combien de fois chaque candidat termine premier, deuxième, ou plus loin. Premier + deuxième = ses chances d’être au second tour.</p>
      <table class="mo-table mo-table-rangs">
        <tr><th>Candidat</th><th class="mo-num">1<sup>er</sup></th><th class="mo-num">2<sup>e</sup></th><th class="mo-num">3<sup>e</sup> ou&nbsp;moins</th></tr>
        {"".join(lignes)}
      </table>
      {note}
    </details>
  </section>'''


def page_modele(modele, candidats, pages):
    lignes = "\n      ".join(ligne_candidat(candidats, pages, c, v)
                             for c, v in modele["candidats"].items())
    return f'''<main class="page-modele">
  <div class="fil">Modèle Sondax</div>
  <h1>Le modèle Sondax</h1>
  <p class="mo-sous-titre">Et si on votait dimanche&nbsp;?</p>
  <p class="mo-intro">À partir des sondages disponibles aujourd’hui, Sondax mesure à quel point chaque candidat a réellement ses chances d’accéder au second tour. Ce n’est pas une prévision d’avril 2027&nbsp;: c’est une photographie de la course aujourd’hui.</p>

  <section class="bloc mo-une">
    <div class="section-label">Aujourd’hui</div>
    {accroche_html(modele)}
    <p class="bloc-note">{ligne_contexte(modele)}</p>
  </section>

  <section class="bloc" id="chances">
    <h2>Chances d’être au second tour</h2>
    <p class="subtitle">Pour chaque candidat, sur 100.</p>
    <ul class="mo-liste">
      {lignes}
    </ul>
  </section>

  {section_duels(modele, candidats)}

  {section_rangs(modele, candidats)}

  <section class="bloc" id="comment">
    <h2>Comment lire ces chiffres</h2>
    <p>Les sondages se trompent toujours un peu. Sondax regarde donc les écarts réellement observés lors des élections précédentes et refait le premier tour 50&nbsp;000 fois. Nous comptons ensuite combien de fois chaque candidat termine dans les deux premiers.</p>
    <p>Un point d’écart dans les sondages ne signifie donc pas nécessairement une grande différence de chances d’être au second tour.</p>
    <p class="mo-lien-methode"><a href="methodologie.html#modele">Comprendre la méthode →</a></p>
    <p class="bloc-note">{ligne_contexte(modele)}<br>Ne prédit pas ce qui se passera d’ici avril.</p>
  </section>
</main>'''


CSS = '''
  .mo-liste { list-style: none; display: flex; flex-direction: column; gap: 14px; margin: 6px 0 4px; }
  .mo-ligne { display: flex; gap: 12px; align-items: flex-start; }
  .mo-photo { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex: none;
    border: 2px solid var(--c); background: #F2F3F0; }
  .mo-initiales { display: inline-flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 600; color: var(--c); }
  .mo-corps { flex: 1; min-width: 0; }
  .mo-tete { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0 10px; align-items: baseline; }
  .mo-tete .mo-chance { margin-left: auto; }
  .mo-nom { font-weight: 600; font-size: 15px; }
  .mo-nom a { color: inherit; }
  .mo-chance { font-family: var(--titre); font-weight: 600; font-size: 17px; white-space: nowrap;
    font-variant-numeric: tabular-nums; }
  .mo-barre { height: 10px; background: #F0F1EE; border-radius: 5px; margin: 5px 0 4px; overflow: hidden; }
  .mo-barre span { display: block; height: 100%; border-radius: 5px; }
  .mo-verdict { font-size: 13px; color: var(--gris); }
  .mo-accroche { font-size: 16.5px; line-height: 1.5; margin: 0 0 18px; max-width: 46em; }
  .mo-accroche strong { font-weight: 600; }
  .mo-cta { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; margin-top: 20px; }
  .mo-cta span { font-size: 13px; color: var(--gris); }
  .mo-bouton { display: inline-block; background: var(--bleu-vif); color: #fff; font-weight: 600;
    font-size: 14.5px; padding: 10px 18px; border-radius: 9px; }
  .mo-bouton:hover { background: var(--bleu-nuit); color: #fff; text-decoration: none; }
  .mo-sous-titre { font-family: var(--titre); font-size: 20px; font-weight: 500; margin: -10px 0 10px; }
  .mo-intro { max-width: 46em; color: var(--texte); margin-bottom: 20px; }
  .page-modele .bloc { background: #fff; border: 1px solid #E3E5E0; border-radius: 16px;
    padding: 24px 26px 20px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(32,38,50,0.04); }
  .page-modele .bloc h2 { margin-top: 0; }
  .page-modele .section-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--bleu-vif); margin-bottom: 8px; }
  .page-modele .subtitle { font-size: 13.5px; color: var(--gris); margin-bottom: 16px; }
  .page-modele .bloc-note { margin: 16px 0 0; padding-top: 12px; border-top: 1px solid #EDEEEA;
    font-size: 12px; color: #8A929C; line-height: 1.6; }
  .page-modele .mo-une .mo-accroche { margin-bottom: 0; font-size: 18px; }
  .page-modele #comment p { max-width: 46em; margin-bottom: 10px; }
  .mo-duels { display: grid; grid-template-columns: 220px 1fr; gap: 24px; align-items: start; }
  .mo-grille { display: grid; grid-template-columns: repeat(10, 1fr); gap: 3px; }
  .mo-grille span { aspect-ratio: 1; border-radius: 3px; }
  .mo-table { width: 100%; border-collapse: collapse; font-size: 14.5px; }
  .mo-table td, .mo-table th { padding: 8px 4px; border-bottom: 1px solid #F0F1EE; text-align: left; }
  .mo-table th { font-family: var(--mono); font-size: 10.5px; font-weight: 500; color: var(--gris);
    letter-spacing: .08em; text-transform: uppercase; }
  .mo-table-rangs th.mo-num { text-transform: none; letter-spacing: 0; font-family: var(--corps); font-size: 12.5px; }
  .mo-num { text-align: right !important; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .mo-pastille { display: inline-block; width: 11px; height: 11px; border-radius: 3px;
    margin-right: 8px; vertical-align: -1px; }
  .mo-repli { margin-top: 10px; }
  .mo-repli summary { cursor: pointer; font-size: 14px; color: var(--bleu-vif); padding: 6px 4px;
    list-style: none; }
  .mo-repli summary::-webkit-details-marker { display: none; }
  .mo-rangs > summary { color: var(--texte); padding: 0; }
  .mo-rangs > summary h2 { display: inline; }
  .mo-rangs > summary::after { content: ' ▾'; color: var(--gris); font-size: 14px; }
  .mo-rangs:not([open]) > summary::after { content: ' ▸'; }
  .mo-petit { font-size: 13px; color: var(--gris); margin-top: 10px; }
  .mo-lien-methode a { font-weight: 600; }
  @media (max-width: 640px) {
    .mo-duels { grid-template-columns: 1fr; }
    .mo-grille { max-width: 260px; }
    .page-modele .bloc { padding: 20px 16px 16px; }
    .mo-accroche { font-size: 15.5px; }
    .mo-chance { font-size: 15px; }
  }
'''


# -------------------------------------------------------------- contrôles

def texte_visible(fragment):
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return html.unescape(t)


def verifier_vocabulaire(fragment, nom_bloc):
    texte = texte_visible(fragment).lower()
    trouves = sorted({m for m in MOTS_INTERDITS if re.search(r"\b" + m, texte)})
    if trouves:
        sys.exit(f"build_modele : mot(s) réservé(s) à la page Méthode dans {nom_bloc} : "
                 f"{', '.join(trouves)}")


# ------------------------------------------------------------------- main

def injecter(bloc):
    contenu = INDEX_PATH.read_text(encoding="utf-8")
    try:
        debut = contenu.index(BEGIN_MARKER)
        fin = contenu.index(END_MARKER)
    except ValueError:
        sys.exit(f"build_modele : marqueurs {BEGIN_MARKER} / {END_MARKER} introuvables "
                 f"dans {INDEX_PATH}")
    contenu = contenu[:debut] + BEGIN_MARKER + "\n" + bloc + "\n" + contenu[fin:]
    INDEX_PATH.write_text(contenu, encoding="utf-8")


def main():
    modele = json.loads(MODELE_PATH.read_text())
    candidats = json.loads(CANDIDATS_PATH.read_text())
    pages = set(json.loads(BIOS_PATH.read_text()))

    bloc = bloc_accueil(modele, candidats, pages)
    corps = page_modele(modele, candidats, pages)
    verifier_vocabulaire(bloc, "le bloc d'accueil")
    verifier_vocabulaire(corps, "la page Modèle")

    a = modele["accroche"]
    description = f"{a['titre']} {a['detail']} Chances d’être au second tour si on votait dimanche."
    page = render_page(
        title="Qui serait au second tour si on votait dimanche&nbsp;? — Modèle Sondax",
        meta_description=e(description),
        canonical=PAGE_URL,
        body_content=corps,
        extra_head=f"<style>{CSS}</style>",
    )
    PAGE_PATH.write_text(page, encoding="utf-8")
    injecter(f"<style>{CSS}</style>\n{bloc}")
    print(f"Écrit {PAGE_PATH.relative_to(ROOT)} et le bloc #bloc-modele de l'accueil")


if __name__ == "__main__":
    main()
