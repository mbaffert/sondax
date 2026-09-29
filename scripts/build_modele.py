#!/usr/bin/env python3
"""Page « Le modèle Sondax » et bloc d'accueil (SPEC §14.14).

Lit data/derived/modele.json (scripts/modele.py) et data/modele_history.json,
et écrit :
- site/modele-sondax.html ;
- le bloc #modele-sondax de site/index.html, entre <!-- BEGIN:bloc-modele --> et
  <!-- END:bloc-modele --> ;
- le bloc « Et si on votait dimanche ? » des fiches candidat (site/<slug>.html) ;
- le bloc du modèle des pages duel (site/second-tour/<a>-<b>.html).
À lancer après build_pages_candidats.py et pages_second_tour.py.

Tout le texte est rendu au build. Échoue si un mot réservé à la page Méthode
apparaît dans le texte rendu (§14.3).
"""

import datetime, html, json, pathlib, re, sys
from zoneinfo import ZoneInfo

from site_template import render_page
import courbes_modele as C
import textes_modele as T

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MODELE_PATH = ROOT / "data" / "derived" / "modele.json"
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
BIOS_PATH = ROOT / "scripts" / "bios.json"
HISTORY_PATH = ROOT / "data" / "modele_history.json"
PARTAGE_PATH = SITE / "partage" / "modele.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
INDEX_PATH = SITE / "index.html"
PAGE_PATH = SITE / "modele-sondax.html"
PAGE_URL = "https://sondax.fr/modele-sondax.html"

BEGIN_MARKER = "<!-- BEGIN:bloc-modele -->"
END_MARKER = "<!-- END:bloc-modele -->"

# Mots réservés à la page Méthode (§14.3), cherchés en début de mot.
# Libellés demandés tels quels, retirés du texte avant le contrôle (décision du
# 29 septembre 2026 : le lien de l'accueil vers la méthode dit « probabilités »).
EXCEPTIONS_VOCABULAIRE = ["Comment ces probabilités sont-elles calculées"]
MOTS_INTERDITS = ["simulation", "probabilit", "tirage", "configuration", "échantillon",
                  "calibration", "dirichlet", "variance", "distribution"]

VERDICTS = {
    "quasi_sur": ("Quasi sûr d’y être", "Quasi sûre d’y être"),
    "bien_place": ("Bien placé", "Bien placée"),
    "rien_nest_joue": ("Rien n’est joué", "Rien n’est joué"),
    "surprise": ("Il faudrait une surprise", "Il faudrait une surprise"),
    "tres_improbable": ("Très improbable aujourd’hui", "Très improbable aujourd’hui"),
}

# Couleur d'un duel : celle du challenger, le moins bien placé des deux
# (décision du 28 septembre 2026, après essai de palettes neutres jugées
# illisibles). Gris pour les autres scénarios.
DUEL_COULEUR_AUTRES = "#D5D9DE"
COURBES_DEFAUT = 4                                   # candidats cochés (§14.14.2)
COURBES_SEUIL = 1          # candidats proposés : au moins 1 sur 100 dans l'historique
SECOND_TOUR_FREQUENT_MIN = 8                         # fiches candidat (§14.14.3)
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

CANDIDATS_REF = {}   # candidats.json, renseigné par main()
INDEX = {}   # index des sondages, renseigné par main() (attribution des évolutions)


def evolution_ligne(modele, valeur, chance):
    """Évolution d'une ligne de liste, attribuée au sondage quand un seul est
    entré (règle unique, §5.11) ; rien pour « stable » sous 1 sur 100."""
    evo = T.evolution(modele, valeur, index=INDEX)
    if chance < 1 and evo == "stable":
        return None
    return evo


def ligne_candidat(candidats, pages, slug, v, modele, p="", detail=True, bascule=True):
    q = v["qualification_exacte"]
    evo = evolution_ligne(modele, v.get("evolution_7j"), q)
    infos = [e(verdict_texte(candidats, slug, v["verdict"]))] if detail else []
    if evo:
        infos.append(f'<span class="mo-evo">{evo}</span>')
    bas = T.bascule_courte(v) if bascule else None
    ligne_bascule = (f'<div class="mo-bascule" title="{T.bascule_explication(v)}">{bas}</div>'
                     if bas else "")
    nom_html = e(nom_complet(candidats, slug))
    if slug in pages:
        nom_html = f'<a href="{p}{slug}.html">{nom_html}</a>'
    largeur = max(q, 0.6)
    return f'''<li class="mo-ligne">
      {portrait(candidats, slug, p)}
      <div class="mo-corps">
        <div class="mo-tete"><span class="mo-nom">{nom_html}</span><span class="mo-chance">{sur_100(q)}</span></div>
        <div class="mo-barre" aria-hidden="true"><span style="width:{largeur:.1f}%;background:{candidats[slug]['couleur']}"></span></div>
        {f'<div class="mo-verdict">{" · ".join(infos)}</div>' if infos else ''}
        {ligne_bascule}
      </div>
    </li>'''


def accroche_html(modele, balise="p", candidats=None):
    """Accroche ; avec `candidats`, version développée (point de bascule)."""
    a = modele["accroche"]
    suite = ""
    une = T.bascule_a_la_une(modele) if candidats else None
    if une:
        c, v = une
        suite = (f' {e(nom(candidats, c))} est à environ '
                 f'{T.points(T.bascule_affichee(v["delta_bascule"]))} du basculement.')
    return (f'<{balise} class="mo-accroche"><strong>{e(a["titre"])}</strong> '
            f'{e(a["detail"])}{suite}</{balise}>')


def phrase_duel_principal(modele, candidats, historique):
    """Phrase unique de l'accueil : le duel le plus fréquent, « reste » s'il
    l'était déjà à la référence de 7 jours, « est » sinon."""
    ordre = ordre_modele(modele)
    duel = modele["duels"][0]
    ref = entree_avant(historique, _instant(modele), 7)
    reste = ref is not None and ref["duels"] and max(ref["duels"], key=ref["duels"].get) == "+".join(sorted(duel["candidats"]))
    verbe = "reste" if reste else "est"
    return (f"{e(libelle_duel(candidats, duel['candidats'], ordre))} {verbe}, au vu des "
            f"sondages les plus récents, le second tour le plus plausible.")


def bloc_accueil(modele, candidats, historique):
    """Bloc d'accueil (§14.14.1) : surtitre, titre, phrase du duel principal,
    gaufre et liste des duels (variante « accueil » du composant de la page
    Modèle), lien vers la méthode."""
    return f'''<div class="bloc" id="modele-sondax">
  <div class="section-label">Modèle Sondax</div>
  <h2>Qui serait au second tour si on votait dimanche prochain&nbsp;?</h2>
  <p class="mo-phrase">{phrase_duel_principal(modele, candidats, historique)}</p>
  {composant_duels(modele, candidats, historique=historique, variante="accueil")}
  <p class="mo-lien-accueil"><a href="modele-sondax.html#{ANCRE_EXPLICATION}">Comment ces probabilités sont-elles calculées&nbsp;? →</a></p>
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


def couleurs_duels(candidats, duels, ordre):
    """Couleur de chaque duel : le challenger ; si elle est déjà prise par un
    duel mieux classé, celle de l'autre candidat ; à défaut, gris foncé."""
    prises, couleurs = set(), []
    for d in duels:
        challenger, favori = sorted(d["candidats"], key=ordre.index, reverse=True)
        couleur = next((candidats[c]["couleur"] for c in (challenger, favori)
                        if candidats[c]["couleur"] not in prises), "#66707D")
        prises.add(couleur)
        couleurs.append(couleur)
    return couleurs


def date_reference_7j(modele):
    """Date de référence de la variation : J−7 par rapport à la mise à jour, à
    l'heure de Paris (21/9 pour une mise à jour du 28/9). La valeur comparée est
    celle en vigueur ce jour-là : la dernière entrée d'historique datée de J−7 ou
    avant (§14.9), qui peut être plus ancienne quand aucun sondage n'est entré."""
    d = datetime.datetime.fromisoformat(modele["date"].replace("Z", "+00:00"))
    return d.astimezone(ZoneInfo("Europe/Paris")).date() - datetime.timedelta(days=7)


def evolution_depuis(valeur, date_ref):
    """Variante accueil : « +13 depuis le 21/9 », « stable » si l'écart est nul."""
    if valeur is None or date_ref is None:
        return None
    if valeur == 0:
        return "stable"
    return f"{T.signe(valeur)} depuis le {date_ref.day}/{date_ref.month}"


def chances_sur_100(v):
    """« 71 chances sur 100 », « 1 chance sur 100 », « moins de 1 chance sur
    100 », « plus de 99 chances sur 100 »."""
    if v < 0.5:
        return "moins de 1&nbsp;chance sur&nbsp;100"
    if v > 99.5:
        return "plus de 99&nbsp;chances sur&nbsp;100"
    n = round(v)
    return f"{n}&nbsp;chance{'s' if n > 1 else ''} sur&nbsp;100"


def ligne_duel(modele, candidats, d, couleur, ordre, date_ref=None, variante="page"):
    if variante == "accueil":
        evo = evolution_depuis(d.get("evolution_7j"), date_ref)
        return (f'<li><span class="mo-pastille" style="background:{couleur}"></span>'
                f'<span class="mo-duel-nom">{e(libelle_duel(candidats, d["candidats"], ordre))}</span>'
                f'<span class="mo-duel-chance">{chances_sur_100(d["chance_exacte"])}</span>'
                + (f'<span class="mo-duel-var">{evo}</span>' if evo else '<span></span>') + '</li>')
    evo = evolution_ligne(modele, d.get("evolution_7j"), d["chance_exacte"])
    return (f'<li><span class="mo-pastille" style="background:{couleur}"></span>'
            f'<span class="mo-duel-nom">{e(libelle_duel(candidats, d["candidats"], ordre))}</span>'
            f'<span class="mo-duel-chance">{sur_100(d["chance_exacte"])}</span>'
            + (f'<span class="mo-duel-evo">{evo}</span>' if evo else '') + '</li>')


def composant_duels(modele, candidats, titre="h2", historique=None, variante="page"):
    """« Les seconds tours possibles » (§5.6 du brief) : 100 carrés et liste des
    duels avec leur évolution. Un seul composant, pour la page Modèle et
    l'accueil. Variante « accueil » : ni titre ni phrase d'explication,
    variation datée (« +13 depuis le 21/9 »), « Autres scénarios » en ligne
    grisée sans variation."""
    ordre = ordre_modele(modele)
    duels = modele["duels"]
    principaux, autres = duels[:DUELS_AFFICHES], duels[DUELS_AFFICHES:]
    reste = max(0.0, 100 - sum(d["chance_exacte"] for d in principaux))

    lignes, parts = [], []
    # Variation datée seulement s'il existe un état en vigueur à J−7
    date_ref = None
    if variante == "accueil" and entree_avant(historique or [], _instant(modele), 7) is not None:
        date_ref = date_reference_7j(modele)
    for d, couleur in zip(principaux, couleurs_duels(candidats, principaux, ordre)):
        parts.append((d["candidats"], d["chance_exacte"], couleur))
        lignes.append(ligne_duel(modele, candidats, d, couleur, ordre, date_ref, variante))
    parts.append(("autres", reste, DUEL_COULEUR_AUTRES))

    if variante == "accueil":
        if autres or reste >= 0.5:
            lignes.append(f'<li class="mo-duel-autres"><span class="mo-pastille" '
                          f'style="background:{DUEL_COULEUR_AUTRES}"></span>'
                          f'<span class="mo-duel-nom">Autres scénarios · {chances_sur_100(reste)}</span></li>')
        return f'''<div class="mo-seconds-tours mo-seconds-accueil">
    <div class="mo-duels">
      {grille_100(parts)}
      <ul class="mo-duels-liste">{"".join(lignes)}</ul>
    </div>
  </div>'''

    details = ""
    if autres:
        sous = "".join(ligne_duel(modele, candidats, d, "transparent", ordre) for d in autres)
        details = f'''<details class="mo-repli">
        <summary><span class="mo-pastille" style="background:{DUEL_COULEUR_AUTRES}"></span>Autres scénarios · {sur_100(reste)}</summary>
        <ul class="mo-duels-liste mo-duels-autres">{sous}</ul>
      </details>'''

    return f'''<div class="mo-seconds-tours">
    <{titre} class="mo-seconds-titre">Les seconds tours possibles</{titre}>
    <p class="subtitle">Sur 100 premiers tours refaits à partir des sondages d’aujourd’hui, voici combien de fois chaque duel sort.</p>
    <div class="mo-duels">
      {grille_100(parts)}
      <div>
        <ul class="mo-duels-liste">{"".join(lignes)}</ul>
        {details}
      </div>
    </div>
  </div>'''


def section_duels(modele, candidats):
    return f'''<section class="bloc" id="seconds-tours">
    {composant_duels(modele, candidats)}
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


def entree_avant(historique, instant, jours):
    limite = (instant - datetime.timedelta(days=jours)).date()
    avant = [h for h in historique if h["date"][:10] <= limite.isoformat()]
    return avant[-1] if avant else None


def entree_precedente(historique, modele):
    avant = [h for h in historique if h["date"] < modele["date"]]
    return avant[-1] if avant else None


def section_changement(modele, candidats, historique, index):
    ordre = ordre_modele(modele)
    texte = T.changement(modele, candidats, index, ordre)
    if texte is None:
        return ""
    instant = _instant(modele)
    reperes = [("Aujourd’hui", {c: v["qualification_exacte"] for c, v in modele["candidats"].items()}),
               ("Mise à jour précédente", (entree_precedente(historique, modele) or {}).get("qualification")),
               ("Il y a 7 jours", (entree_avant(historique, instant, 7) or {}).get("qualification"))]
    reperes = [(lib, q) for lib, q in reperes if q]
    tete = "".join(f'<th class="mo-num">{lib}</th>' for lib, _ in reperes)
    lignes = []
    for c in ordre[:4]:
        cellules = "".join(f'<td class="mo-num">{T.chances(q[c]) if c in q else "—"}</td>'
                           for _, q in reperes)
        lignes.append(f'<tr><td>{e(nom(candidats, c))}</td>{cellules}</tr>')
    return f'''<section class="bloc" id="ce-qui-a-change">
    <h2>Ce qui a changé</h2>
    <p class="mo-accroche"><strong>{texte[0]}</strong> {texte[1]}</p>
    <table class="mo-table mo-table-rangs"><tr><th>Chances sur 100</th>{tete}</tr>{"".join(lignes)}</table>
  </section>'''


def _instant(modele):
    """Fin des courbes : la fin du jour du calcul (UTC), pour qu'une page ne
    change pas d'un déploiement à l'autre quand aucun sondage n'est entré."""
    d = datetime.datetime.fromisoformat(modele["date"].replace("Z", "+00:00"))
    return d.replace(hour=23, minute=59, second=0, microsecond=0)


def candidats_courbes(modele, historique):
    """Candidats proposés (au moins 1 sur 100 à un moment) et cochés par défaut."""
    ordre = ordre_modele(modele)
    maxi = {}
    for h in historique:
        for c, q in h["qualification"].items():
            maxi[c] = max(maxi.get(c, 0), q)
    proposes = [c for c in ordre if maxi.get(c, 0) >= COURBES_SEUIL]
    proposes += sorted(c for c in maxi if maxi[c] >= COURBES_SEUIL and c not in proposes)
    # Candidats remplacés (Bardella, remplacé par Le Pen) : masqués à l'affichage,
    # l'historique n'est pas modifié.
    remplaces = {v.get("succede_a") for v in CANDIDATS_REF.values() if v.get("succede_a")}
    proposes = [c for c in proposes if c not in remplaces]
    return proposes, set(ordre[:COURBES_DEFAUT])


def section_courbes(modele, candidats, historique):
    if len(historique) < 2:
        return ""
    instant = _instant(modele)
    proposes, coches = candidats_courbes(modele, historique)
    proposes = [c for c in proposes if c in candidats]
    periodes = [("7j", "7 jours", 7), ("30j", "30 jours", 30), ("tout", "Depuis le début", None)]
    actif = ' class="active"'
    boutons = "".join(f'<button type="button" data-periode="{k}"{actif if k == "30j" else ""}>{lib}</button>'
                      for k, lib, _ in periodes)
    svgs = "".join(f'<div class="mo-periode" data-periode="{k}"{"" if k == "30j" else " hidden"}>'
                   f'{C.svg(historique, candidats, proposes, instant, j, coches)}</div>'
                   for k, _, j in periodes)
    cases = "".join(f'<label style="--c:{candidats[c]["couleur"]}"><input type="checkbox" data-c="{c}"'
                    f'{" checked" if c in coches else ""}> {e(nom(candidats, c))}</label>'
                    for c in proposes)
    return f'''<section class="bloc" id="historique">
    <h2>Évolution des chances d’être au second tour</h2>
    <p class="subtitle">Sur 100. Ce ne sont pas des intentions de vote : ce sont les chances de chacun d’être au second tour, recalculées à chaque nouveau sondage.</p>
    <div class="mo-periodes" role="group" aria-label="Période">{boutons}</div>
    {svgs}
    <div class="mo-cases">{cases}</div>
    <p class="mo-petit">{note_reconstitue(historique)}</p>
  </section>'''


def note_reconstitue(historique):
    reels = [h for h in historique if not h.get("reconstitue")]
    if not reels:
        return "Les points sont recalculés après coup, avec les sondages publiés à chaque date."
    return (f"Avant le {date_longue(reels[0]['date'])}, les points sont recalculés après coup, "
            f"avec les sondages publiés à chaque date.")


JS_COURBES = '''<script>
(function () {
  var s = document.getElementById('historique');
  if (!s) return;
  s.querySelectorAll('.mo-periodes button').forEach(function (b) {
    b.addEventListener('click', function () {
      s.querySelectorAll('.mo-periodes button').forEach(function (x) { x.classList.toggle('active', x === b); });
      s.querySelectorAll('.mo-periode').forEach(function (d) { d.hidden = d.dataset.periode !== b.dataset.periode; });
    });
  });
  s.querySelectorAll('.mo-cases input').forEach(function (i) {
    i.addEventListener('change', function () {
      s.querySelectorAll('path[data-c="' + i.dataset.c + '"]').forEach(function (p) {
        p.classList.toggle('cache', !i.checked);
      });
    });
  });
})();
</script>'''


def notes_bascule(modele, candidats):
    notes = [f'<li><strong>{e(nom(candidats, c))}</strong> : {T.bascule_explication(v)}</li>'
             for c, v in modele["candidats"].items() if T.bascule_explication(v)]
    if not notes:
        return ""
    return (f'<div class="mo-petit mo-notes"><p>« Basculement » : le seuil à partir duquel un '
            f'candidat aurait une chance sur deux d’être au second tour.</p><ul>{"".join(notes)}</ul></div>')


def bouton_partage(partage):
    """Bouton Partager (§14.15) : partage natif, sinon copie ou téléchargement."""
    if not partage:
        return ""
    image = partage["images"]["carre"]
    return f'''<div class="mo-partage" id="partage" data-gabarit="{e(partage["gabarit"])}"
       data-phrase="{e(partage["phrase"])}" data-image="{e(image)}">
    <button type="button" class="mo-bouton" id="partager">Partager</button>
    <div class="mo-partage-menu" hidden>
      <button type="button" data-action="phrase">Copier la phrase</button>
      <button type="button" data-action="lien">Copier le lien</button>
      <a href="{e(image)}" download data-action="image">Télécharger l’image</a>
      <span class="mo-partage-ok" aria-live="polite"></span>
    </div>
  </div>
<script>
(function () {{
  var z = document.getElementById('partage');
  if (!z) return;
  var url = 'https://sondax.fr/modele-sondax.html';
  var phrase = z.dataset.phrase, menu = z.querySelector('.mo-partage-menu');
  var ok = z.querySelector('.mo-partage-ok');
  function compter(m) {{ window.goatcounter?.count({{ path: 'partage/' + z.dataset.gabarit + '/' + m, event: true }}); }}
  function copier(t, m) {{
    navigator.clipboard.writeText(t).then(function () {{ ok.textContent = 'Copié.'; compter(m); }});
  }}
  document.getElementById('partager').addEventListener('click', async function () {{
    if (navigator.share) {{
      var donnees = {{ title: 'Le modèle Sondax', text: phrase, url: url }};
      try {{
        var r = await fetch(z.dataset.image);
        var f = new File([await r.blob()], 'sondax.png', {{ type: 'image/png' }});
        if (navigator.canShare && navigator.canShare({{ files: [f] }})) donnees.files = [f];
      }} catch (err) {{}}
      try {{ await navigator.share(donnees); compter('natif'); return; }} catch (err) {{ if (err.name === 'AbortError') return; }}
    }}
    menu.hidden = !menu.hidden;
  }});
  menu.addEventListener('click', function (ev) {{
    var a = ev.target.dataset.action;
    if (a === 'phrase') copier(phrase + ' ' + url, 'phrase');
    if (a === 'lien') copier(url, 'lien');
    if (a === 'image') compter('image');
  }});
}})();
</script>'''


EXPLICATION = [
    # Texte fourni tel quel (29 septembre 2026). {n} : nombre de tirages de
    # modele.json ; {n60} : 60 % de ce nombre, pour que l'exemple reste juste.
    "Le modèle Sondax part de la moyenne actuelle des sondages. Il simule ensuite {n} élections fictives selon la méthode dite de Monte-Carlo.\n"
    "Dans chacune de ces simulations, le score de chaque candidat peut être un peu supérieur ou inférieur à celui donné par les derniers sondages. L’ampleur de ces variations est calibrée à partir des écarts observés entre les sondages et les résultats des précédentes élections présidentielles.\n"
    "On obtient ainsi {n} scénarios différents, tous compatibles avec les sondages actuels et avec le niveau d’incertitude observé historiquement.",

    "Pour chaque simulation, Sondax observe quels candidats arrivent en tête et lesquels se qualifient pour le second tour. Imaginons qu’un duel Le Pen – Philippe apparaisse dans {n60} simulations sur {n}. Le modèle affichera alors 60 chances sur 100. Cela signifie que dans 60 % des scénarios simulés à partir des sondages actuels, Le Pen et Philippe arrivent aux deux premières places.",

    "Sondax ne cherche donc pas à prédire qui sera qualifié au second tour dans plusieurs mois.\n"
    "Il répond à une question plus précise : si le rapport de forces mesuré aujourd’hui dans les sondages était celui du jour du vote, quels seraient les classements possibles compte tenu de l’incertitude habituelle des sondages ?\n"
    "Le modèle mesure donc surtout la solidité du classement actuel. Deux candidats peuvent sembler « dans un mouchoir de poche » mais, en réalité, les chances de l’un d’atteindre le second tour à la date du dernier sondage sont statistiquement beaucoup plus élevées.",

    "Le modèle ne prend pas en compte l’avenir, il ne peut pas anticiper les débats, les événements de campagne, les nouvelles candidatures, les retraits ou les déplacements de l’opinion dans les prochains mois.\n"
    "Il ne prétend donc surtout pas prédire le résultat de l’élection.\n"
    "Il transforme simplement les sondages disponibles aujourd’hui et leur marge d’incertitude en une estimation de la solidité des différents scénarios de premier tour.",
]
EXPLICATION_VISIBLES = 2       # paragraphes visibles ; les suivants sont repliés
ANCRE_EXPLICATION = "comment-fonctionne"


def milliers(n):
    """« 50 000 » avec une espace insécable."""
    return f"{n:,}".replace(",", "\u00a0")


def paragraphe(texte, n):
    t = texte.format(n=milliers(n), n60=milliers(round(n * 0.6)))
    t = e(t).replace("\n", "<br>")
    return re.sub(r" ([?:!;»])", "\u00a0\\1", t).replace("« ", "«\u00a0")


def section_explication(modele):
    n = modele["tirages"]
    visibles = "\n    ".join(f"<p>{paragraphe(t, n)}</p>" for t in EXPLICATION[:EXPLICATION_VISIBLES])
    replies = "\n      ".join(f"<p>{paragraphe(t, n)}</p>" for t in EXPLICATION[EXPLICATION_VISIBLES:])
    return f'''<section class="bloc mo-explication">
    <h2 id="{ANCRE_EXPLICATION}">Comment fonctionne ce modèle&nbsp;?</h2>
    {visibles}
    <details class="mo-plus">
      <summary>Lire la suite</summary>
      {replies}
    </details>
  </section>'''


def page_modele(modele, candidats, pages, historique):
    """Page Modèle (décision du 29 septembre 2026) : titre, explication,
    chances d'être au second tour, évolution de ces chances. Rien d'autre."""
    lignes = "\n      ".join(ligne_candidat(candidats, pages, c, v, modele)
                             for c, v in modele["candidats"].items())
    return f'''<main class="page-modele">
  <h1>Le modèle Sondax</h1>

  {section_explication(modele)}

  <section class="bloc" id="chances">
    <h2>Chances d’être au second tour</h2>
    <p class="subtitle">Pour chaque candidat, sur 100.</p>
    <ul class="mo-liste">
      {lignes}
    </ul>
    {notes_bascule(modele, candidats)}
  </section>

  {section_courbes(modele, candidats, historique)}
</main>
{JS_COURBES}'''


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
  .mo-evo { white-space: normal; }
  .mo-partage { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 4px 0 12px; }
  .mo-bouton { border: 0; cursor: pointer; font-family: var(--corps); }
  .mo-partage-menu { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13.5px; }
  .mo-partage-menu button, .mo-partage-menu a { background: #fff; border: 1px solid #DDDFDA; border-radius: 8px;
    padding: 7px 12px; cursor: pointer; font: 500 13.5px var(--corps); color: var(--texte); }
  .mo-partage-ok { color: var(--gris); }
  .mo-table .mo-evo { font-size: 13px; color: var(--gris); }
  .mo-bascule { font-size: 13px; font-weight: 600; color: var(--bleu-nuit); margin-top: 2px; }
  .mo-mouvement { font-size: 14.5px; margin: 14px 0 0; }
  .mo-notes { margin-top: 14px; }
  .mo-notes ul { margin: 4px 0 0 18px; }
  .mo-periodes { display: flex; background: #F2F3F0; border-radius: 9px; padding: 3px; width: fit-content; margin-bottom: 12px; }
  .mo-periodes button { border: 0; cursor: pointer; font: 500 13px var(--corps); padding: 6px 13px;
    border-radius: 7px; background: transparent; color: var(--gris); }
  .mo-periodes button.active { background: #fff; color: var(--texte); box-shadow: 0 1px 2px rgba(32,38,50,.08); }
  .mo-cases { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 10px; font-size: 13.5px; }
  .mo-cases label { display: inline-flex; align-items: center; gap: 5px; cursor: pointer; }
  .mo-cases input { accent-color: var(--c); }
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
  .mo-seconds-tours { margin: 4px 0 6px; }
  .mo-seconds-titre { font-family: var(--titre); font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 4px; }
  h3.mo-seconds-titre { font-size: 18px; }
  .mo-duels { display: grid; grid-template-columns: 220px 1fr; gap: 24px; align-items: start; }
  .mo-duels-liste { list-style: none; margin: 0; padding: 0; }
  .mo-duels-liste li { display: grid; grid-template-columns: 19px 1fr auto; column-gap: 0;
    padding: 9px 0; border-bottom: 1px solid #F0F1EE; font-size: 14.5px; align-items: baseline; }
  .mo-duels-liste .mo-pastille { margin: 0; }
  .mo-duel-nom { font-weight: 600; }
  .mo-duel-chance { white-space: nowrap; font-variant-numeric: tabular-nums; text-align: right; }
  .mo-duel-evo { grid-column: 2 / 4; font-size: 13px; color: var(--gris); margin-top: 1px; }
  .mo-duels-autres li { font-size: 13.5px; }
  #modele-sondax .mo-phrase { font-size: 16.5px; font-weight: 400; line-height: 1.5; margin: 0 0 18px; max-width: 46em; }
  .mo-seconds-accueil .mo-duels-liste li { grid-template-columns: 19px 1fr 11em 10em; }
  .mo-duel-var { font-size: 13.5px; color: var(--gris); white-space: nowrap;
    text-align: right; font-variant-numeric: tabular-nums; }
  .mo-seconds-accueil .mo-duel-autres .mo-duel-nom { font-weight: 400; color: var(--gris); grid-column: 2 / 5; }
  .mo-lien-accueil { margin: 18px 0 0; }
  .mo-lien-accueil a { color: var(--bleu-vif); font-weight: 500; font-size: 15px; }
  .mo-duels-autres .mo-duel-nom { font-weight: 400; }
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
  .mo-explication p { max-width: 46em; margin: 0 0 12px; line-height: 1.6; }
  .mo-explication h2 { scroll-margin-top: 68px; }
  .mo-plus summary { cursor: pointer; list-style: none; color: var(--bleu-vif); font-weight: 500;
    font-size: 15px; margin: 4px 0 12px; }
  .mo-plus summary::-webkit-details-marker { display: none; }
  .mo-plus summary:hover { text-decoration: underline; }
  .mo-plus[open] summary { display: none; }
  @media (max-width: 599px) {
    /* Téléphone : carrés au-dessus de la liste, en 5 rangées de 20 */
    .mo-duels { grid-template-columns: 1fr; gap: 10px; }
    .mo-grille { grid-template-columns: repeat(20, 1fr); gap: 2px; }
    .mo-grille span { border-radius: 2px; }
    .mo-seconds-tours .subtitle { font-size: 13px; margin-bottom: 10px; }
    .mo-seconds-titre { font-size: 19px; }
    h3.mo-seconds-titre { font-size: 17px; }
    .mo-duels-liste li { padding: 6px 0; font-size: 14px; }
    .mo-duel-evo { font-size: 12px; letter-spacing: -0.01em; grid-column: 1 / 4; }
    .mo-table-rangs { font-size: 13px; }
    .mo-table-rangs th { white-space: normal; letter-spacing: 0; }
    #modele-sondax { padding: 18px 16px 14px; }
    #modele-sondax h2 { font-size: 22px; }
    #modele-sondax .mo-accroche { font-size: 15px; }
    #modele-sondax .mo-phrase { font-size: 15px; margin-bottom: 14px; }
    .mo-seconds-accueil .mo-duels-liste li { grid-template-columns: 19px 1fr auto; }
    .mo-duel-var { grid-column: 3; font-size: 12.5px; margin-top: 1px; }
    #modele-sondax .mo-seconds-tours .subtitle { font-size: 12.5px; }
    #modele-sondax .subtitle { margin-bottom: 12px; }
    #modele-sondax .mo-accroche { margin-bottom: 14px; }
    #modele-sondax .mo-cta { margin-top: 14px; }
    #modele-sondax .mo-cta span { display: none; }
    #modele-sondax .bloc-note { margin-top: 12px; padding-top: 8px; font-size: 11.5px; }
    #modele-sondax .mo-repli { margin-top: 4px; }
    #modele-sondax .mo-repli summary { padding: 4px 0; }
  }
  @media (max-width: 640px) {
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
    texte = texte_visible(fragment)
    for exception in EXCEPTIONS_VOCABULAIRE:
        texte = texte.replace(exception, "")
    texte = texte.lower()
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


# --------------------------------------------------- fiches candidat, duels

BEGIN_CANDIDAT, END_CANDIDAT = "<!-- BEGIN:modele-candidat -->", "<!-- END:modele-candidat -->"
BEGIN_DUEL, END_DUEL = "<!-- BEGIN:modele-duel -->", "<!-- END:modele-duel -->"


def duel_le_plus_frequent(modele, slug):
    return next((d for d in modele["duels"] if slug in d["candidats"]), None)


def bloc_candidat(modele, candidats, slug, historique):
    v = modele["candidats"].get(slug)
    if v is None:
        return ""
    lignes = [f'<p class="mc-chance"><b>{T.chances(v["qualification_exacte"])}</b> chances sur 100 '
              f'd’être au second tour</p>',
              f'<p class="mc-verdict">{e(verdict_texte(candidats, slug, v["verdict"]))}.</p>']
    evo = T.evolution(modele, v.get("evolution_7j"), index=INDEX)
    if evo:
        lignes.append(f'<p class="mc-evo">{evo[0].upper() + evo[1:]}.</p>')
    d = duel_le_plus_frequent(modele, slug)
    if d and v["qualification_exacte"] >= SECOND_TOUR_FREQUENT_MIN:
        autre = next(c for c in d["candidats"] if c != slug)
        lignes.append(f'<p>Son second tour le plus fréquent : face à {e(nom_complet(candidats, autre))}.</p>')
    bas = T.bascule_courte(v)
    if bas:
        lignes.append(f'<p class="mc-bascule">{bas}. <span>{T.bascule_explication(v)}</span></p>')
    courbe = ""
    if len(historique) >= 2:
        instant = _instant(modele)
        couleurs = {slug: candidats[slug]}
        courbe = (f'<div class="mc-courbe"><div class="mc-periodes">'
                  f'<button type="button" data-p="7" >7 jours</button>'
                  f'<button type="button" data-p="30" class="active">30 jours</button></div>'
                  f'<div data-p="7" hidden>{C.svg(historique, couleurs, [slug], instant, 7, hauteur=170)}</div>'
                  f'<div data-p="30">{C.svg(historique, couleurs, [slug], instant, 30, hauteur=170)}</div>'
                  f'<div class="mc-sous">Évolution de ses chances d’être au second tour, sur 100</div></div>')
    return f'''<section class="carte modele-candidat"><div class="pad">
  <div class="label">Modèle Sondax</div>
  <h2>Et si on votait dimanche&nbsp;?</h2>
  <div class="txt">{"".join(lignes)}</div>
  {courbe}
  <p class="mc-lien"><a href="/modele-sondax.html">Voir le modèle Sondax →</a> · <span>Ne prédit pas ce qui se passera d’ici avril.</span></p>
</div></section>
<style>{C.CSS}
.modele-candidat .mc-chance {{ font-size: 18px; }}
.modele-candidat .mc-chance b {{ font-family: var(--titre); font-size: 26px; }}
.modele-candidat .txt p {{ margin: 0 0 4px; }}
.modele-candidat .mc-bascule span {{ display: block; font-size: 13px; color: var(--gris); }}
.modele-candidat .mc-periodes {{ display: flex; gap: 4px; margin: 6px 0; }}
.modele-candidat .mc-periodes button {{ border: 1px solid var(--bord); background: #fff; border-radius: 7px;
  padding: 4px 10px; font-size: 12.5px; cursor: pointer; color: var(--gris); }}
.modele-candidat .mc-periodes button.active {{ color: var(--texte); border-color: var(--texte); }}
.modele-candidat .mc-sous, .modele-candidat .mc-lien span {{ font-size: 12.5px; color: var(--gris); }}
.modele-candidat .mc-lien {{ margin: 12px 0 20px; font-size: 14px; }}
</style>
<script>
document.querySelectorAll('.modele-candidat .mc-periodes button').forEach(function (b) {{
  b.addEventListener('click', function () {{
    var s = b.closest('.mc-courbe');
    s.querySelectorAll('button').forEach(function (x) {{ x.classList.toggle('active', x === b); }});
    s.querySelectorAll('div[data-p]').forEach(function (d) {{ d.hidden = d.dataset.p !== b.dataset.p; }});
  }});
}});
</script>'''


def libelle_rang_duel(modele, d):
    """Libellé de rang d'un duel (§14.14.4)."""
    rang = modele["duels"].index(d) + 1
    v = d["chance_exacte"]
    if v < 5:
        return "Peu fréquent aujourd’hui"
    if rang == 1:
        return "Le second tour le plus fréquent aujourd’hui"
    lib = "Le deuxième second tour le plus fréquent" if rang == 2 else f"Le {rang}<sup>e</sup> second tour le plus fréquent"
    for k in (2, 3, 4, 5):
        if abs(100 / k - v) < 3:
            return f"{lib} : près d’un sur {['', '', 'deux', 'trois', 'quatre', 'cinq'][k]}"
    return lib


def bloc_duel(modele, candidats, paire, historique):
    d = next((x for x in modele["duels"] if sorted(x["candidats"]) == sorted(paire)), None)
    if d is None:
        return ""
    ordre = ordre_modele(modele)
    instant = _instant(modele)
    ref = entree_avant(historique, instant, 7)
    lignes = [f'<p class="md-chance"><b>{T.chances(d["chance_exacte"])}</b> fois sur 100 aujourd’hui</p>']
    evo = T.evolution(modele, d.get("evolution_7j"), index=INDEX)
    if ref is not None and evo not in (None, "peu de changement"):
        avant = ref["duels"].get("+".join(sorted(paire)), 0.0)
        lignes.append(f'<p>{T.chances(avant)} il y a une semaine · {evo}</p>')
    elif evo:
        lignes.append(f'<p>{evo[0].upper() + evo[1:]} sur 7 jours</p>')
    return f'''<section class="modele-duel">
  <div class="md-label">Modèle Sondax · Et si on votait dimanche&nbsp;?</div>
  <h2>{e(libelle_duel(candidats, d["candidats"], ordre))}</h2>
  <p class="md-rang">{libelle_rang_duel(modele, d)}</p>
  {"".join(lignes)}
  <p class="md-note">Combien de fois ce duel sortirait au premier tour si on votait dimanche. Cela ne dit rien du vainqueur du second tour. <a href="../modele-sondax.html">Voir le modèle Sondax →</a></p>
</section>
<style>
.modele-duel {{ background: #fff; border: 1px solid #E3E5E0; border-radius: 14px; padding: 16px 20px; margin: 10px 0 22px; }}
.modele-duel h2 {{ margin: 2px 0 2px; font-size: 20px; }}
.modele-duel .md-label {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--bleu-vif); }}
.modele-duel .md-rang {{ font-weight: 600; margin-bottom: 4px; }}
.modele-duel .md-chance b {{ font-family: var(--titre); font-size: 24px; }}
.modele-duel .md-note {{ font-size: 13px; color: var(--gris); margin-top: 8px; }}
</style>'''


def remplacer_entre(contenu, debut, fin, bloc):
    i, j = contenu.index(debut), contenu.index(fin)
    return contenu[:i] + debut + "\n" + bloc + "\n" + contenu[j:]


def injecter_candidats(modele, candidats, pages, historique):
    n = 0
    for slug in sorted(pages):
        chemin = SITE / f"{slug}.html"
        if not chemin.exists():
            continue
        contenu = chemin.read_text(encoding="utf-8")
        bloc = bloc_candidat(modele, candidats, slug, historique)
        if BEGIN_CANDIDAT not in contenu:
            # Après la section « Tendance » (première carte après le portrait)
            i = contenu.index('<div class="label">Tendance</div>')
            j = contenu.index("</section>", i) + len("</section>")
            contenu = contenu[:j] + f"\n{BEGIN_CANDIDAT}\n{END_CANDIDAT}" + contenu[j:]
        verifier_vocabulaire(bloc, f"la fiche {slug}")
        chemin.write_text(remplacer_entre(contenu, BEGIN_CANDIDAT, END_CANDIDAT, bloc), encoding="utf-8")
        n += bool(bloc)
    return n


def injecter_duels(modele, candidats, historique):
    dossier = SITE / "second-tour"
    n = 0
    for d in modele["duels"]:
        chemin = dossier / f"{'-'.join(sorted(d['candidats']))}.html"
        if not chemin.exists():
            continue
        contenu = chemin.read_text(encoding="utf-8")
        if "Redirection" in contenu and len(contenu) < 500:
            continue
        if BEGIN_DUEL not in contenu:
            i = contenu.index("</h1>")
            j = contenu.index("</p>", i) + len("</p>")
            contenu = contenu[:j] + f"\n{BEGIN_DUEL}\n{END_DUEL}" + contenu[j:]
        bloc = bloc_duel(modele, candidats, d["candidats"], historique)
        verifier_vocabulaire(bloc, f"la page duel {chemin.name}")
        chemin.write_text(remplacer_entre(contenu, BEGIN_DUEL, END_DUEL, bloc), encoding="utf-8")
        n += 1
    return n


def charger_index_sondages():
    try:
        return {s["id"]: s for s in json.loads(SONDAGES_PATH.read_text())}
    except FileNotFoundError:
        return {}


VEILLE_TEXTE = ("En application de la loi du 19 juillet 1977, aucun sondage n’est publié ni "
                "commenté la veille et le jour du scrutin. Le modèle Sondax reprendra après le vote.")


def main_veille():
    """Veille électorale : le bloc d'accueil et la page Modèle ne montrent qu'un
    avis ; les blocs des fiches candidat et des pages duel sont vidés."""
    avis = f'<p class="mo-accroche">{VEILLE_TEXTE}</p>'
    bloc = f'''<div class="bloc" id="modele-sondax">
  <div class="section-label">Modèle Sondax</div>
  <h2>Qui serait au second tour si on votait dimanche prochain&nbsp;?</h2>
  {avis}
</div>'''
    corps = f'''<main class="page-modele">
  <h1>Le modèle Sondax</h1><section class="bloc">{avis}</section></main>'''
    PAGE_PATH.write_text(render_page(title="Le modèle Sondax", meta_description=e(VEILLE_TEXTE),
                                     canonical=PAGE_URL, body_content=corps,
                                     extra_head=f"<style>{CSS}</style>"), encoding="utf-8")
    injecter(f"<style>{CSS}</style>\n{bloc}")
    for chemin in list(SITE.glob("*.html")) + list((SITE / "second-tour").glob("*.html")):
        contenu = chemin.read_text(encoding="utf-8")
        for debut, fin in ((BEGIN_CANDIDAT, END_CANDIDAT), (BEGIN_DUEL, END_DUEL)):
            if debut in contenu:
                contenu = remplacer_entre(contenu, debut, fin, "")
        chemin.write_text(contenu, encoding="utf-8")
    print("Veille électorale : modèle Sondax masqué")


def main():
    import veille
    if veille.en_veille():
        return main_veille()
    modele = json.loads(MODELE_PATH.read_text())
    candidats = json.loads(CANDIDATS_PATH.read_text())
    pages = set(json.loads(BIOS_PATH.read_text()))
    historique = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else []
    index = charger_index_sondages()
    INDEX.update(index)

    bloc = bloc_accueil(modele, candidats, historique)
    CANDIDATS_REF.update(candidats)
    partage = json.loads(PARTAGE_PATH.read_text()) if PARTAGE_PATH.exists() else None
    corps = page_modele(modele, candidats, pages, historique)
    verifier_vocabulaire(bloc, "le bloc d'accueil")
    # L'explication est un texte fourni tel quel : hors du contrôle de vocabulaire.
    verifier_vocabulaire(corps.replace(section_explication(modele), ""), "la page Modèle")

    a = modele["accroche"]
    description = f"{a['titre']} {a['detail']} Chances d’être au second tour si on votait dimanche."
    page = render_page(
        title="Qui serait au second tour si on votait dimanche&nbsp;? — Modèle Sondax",
        meta_description=e(description),
        canonical=PAGE_URL,
        body_content=corps,
        extra_head=f"<style>{CSS}{C.CSS}</style>",
        og_image=(f"https://sondax.fr/{partage['images']['og']}" if partage
                  else "https://sondax.fr/assets/og-default.png"),
    )
    PAGE_PATH.write_text(page, encoding="utf-8")
    injecter(f"<style>{CSS}</style>\n{bloc}")
    n_c = injecter_candidats(modele, candidats, pages, historique)
    n_d = injecter_duels(modele, candidats, historique)
    print(f"Écrit {PAGE_PATH.relative_to(ROOT)}, le bloc #modele-sondax de l'accueil, "
          f"{n_c} fiches candidat et {n_d} pages duel")


if __name__ == "__main__":
    main()
