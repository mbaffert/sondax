#!/usr/bin/env python3
"""Génère le jeu de données public et la page qui le présente.

Sorties (reconstructibles, ignorées par git) :
    site/donnees/sondages-presidentielle-2027.csv
    site/donnees.html

Le CSV est le contrat public : ses colonnes ne changent pas sans décision
explicite, contrairement à data/sondages.json qui reste un format interne.
Une ligne par sondage × configuration testée × candidat. Un candidat absent
d'une configuration n'a pas de ligne (jamais de score à 0).
"""

import csv, json, pathlib, datetime, html

from site_template import render_page

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
NOM_CSV = "sondages-presidentielle-2027.csv"
URL_PAGE = "https://sondax.fr/donnees.html"
WIKI = ("https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_"
        "pr%C3%A9sidentielle_fran%C3%A7aise_de_2027")
MARKER_JSONLD = "<!-- BUILD:jsonld-dataset -->"

# (colonne, description) — l'ordre est celui du fichier
COLONNES = [
    ("sondage_id", "Identifiant du sondage : institut et date de fin de terrain. "
                   "Identique à l’adresse de sa fiche sur sondax.fr/sondages/."),
    ("institut", "Institut de sondage."),
    ("terrain_debut", "Premier jour de terrain (AAAA-MM-JJ)."),
    ("terrain_fin", "Dernier jour de terrain (AAAA-MM-JJ)."),
    ("echantillon", "Nombre total de personnes interrogées."),
    ("tour", "1 ou 2."),
    ("configuration", "Numéro de la configuration testée dans le sondage, dans l’ordre "
                      "de publication. Un même sondage teste souvent plusieurs listes "
                      "de candidats au premier tour et plusieurs duels au second."),
    ("configuration_principale", "Premier tour : 1 si c’est la configuration retenue "
                                 "par Sondax pour sa moyenne, 0 sinon. Vide au second tour."),
    ("echantillon_configuration", "Base de calcul des pourcentages de la configuration "
                                  "(en général les personnes certaines d’aller voter), "
                                  "quand l’institut la publie. Vide sinon."),
    ("candidat_id", "Identifiant stable du candidat."),
    ("candidat", "Prénom et nom."),
    ("parti", "Parti ou mouvement."),
    ("score", "Intention de vote en % des suffrages exprimés, point décimal."),
    ("source", "wikipedia, ou manuel pour un sondage saisi à partir de sa notice "
               "parce qu’il manquait sur Wikipédia."),
    ("wikipedia_revid", "Version de la page Wikipédia dont la ligne est extraite. "
                        "Vide pour une saisie manuelle."),
    ("url_source", "Notice déposée à la Commission des sondages ou, à défaut, "
                   "publication de l’institut."),
]


def nombre(x):
    """Entier si la valeur est entière, sinon décimal ; vide si absent."""
    if x is None:
        return ""
    return str(int(x)) if float(x).is_integer() else str(x)


def lignes(sondages, candidats):
    for s in sorted(sondages, key=lambda s: (s["terrain_fin"], s["id"]), reverse=True):
        manuel = s.get("source") == "manuel"
        for n, h in enumerate(s["hypotheses"], start=1):
            principale = "" if h["tour"] != 1 else ("1" if h.get("principale") else "0")
            for cid, score in sorted(h["scores"].items(), key=lambda kv: -kv[1]):
                c = candidats[cid]
                nom = f'{c.get("prenom", "")} {c["nom"]}'.strip()
                yield {
                    "sondage_id": s["id"],
                    "institut": s["institut"],
                    "terrain_debut": s["terrain_debut"],
                    "terrain_fin": s["terrain_fin"],
                    "echantillon": nombre(s.get("echantillon")),
                    "tour": h["tour"],
                    "configuration": n,
                    "configuration_principale": principale,
                    "echantillon_configuration": nombre(h.get("echantillon")),
                    "candidat_id": cid,
                    "candidat": nom,
                    "parti": c.get("parti") or "",
                    "score": nombre(score),
                    "source": "manuel" if manuel else "wikipedia",
                    "wikipedia_revid": "" if manuel else nombre(s.get("revid")),
                    "url_source": s.get("url_source") or s.get("url_notice") or "",
                }


def ecrire_csv(rows):
    out = SITE / "donnees" / NOM_CSV
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[c for c, _ in COLONNES], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return out


def date_fr(iso):
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}\u00a0{mois[d.month - 1]}\u00a0{d.year}"


def page(nb_sondages, nb_lignes, poids_ko, dernier, premier):
    dico = "\n".join(
        f"<tr><td><code>{c}</code></td><td>{html.escape(d)}</td></tr>" for c, d in COLONNES)
    aujourdhui = datetime.date.today().isoformat()
    body = f"""<main class="donnees">
<h1>Données des sondages de la présidentielle 2027</h1>

<p>Tous les sondages d’intentions de vote de la présidentielle 2027 recensés par Sondax,
dans un fichier CSV mis à jour chaque jour. Une ligne par candidat, par configuration
testée et par sondage.</p>

<p>Les chiffres viennent de la <a href="{WIKI}">page Wikipédia</a> qui recense ces
sondages, complétée à partir des notices de la Commission des sondages quand un sondage
y manque. Par rapport au tableau de Wikipédia, le fichier sépare chaque configuration
testée, rattache chaque score au candidat réellement testé, y compris quand la cellule
remplace celui de la colonne, et renvoie vers la notice de chaque sondage.</p>

<p class="telechargement"><a href="donnees/{NOM_CSV}" download>{NOM_CSV}</a><br>
<span>{nb_sondages} sondages du {date_fr(premier)} au {date_fr(dernier)} · {nb_lignes}
lignes · {poids_ko}&nbsp;Ko · généré le {date_fr(aujourdhui)}</span></p>

<p>CSV encodé en UTF-8, séparateur virgule, point décimal. Le fichier contient les mesures
publiées par les instituts, pas la moyenne calculée par Sondax
(<a href="methodologie.html">méthode</a>).</p>

<h2>Licence et citation</h2>

<p>Le fichier est diffusé sous licence
<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.fr">CC BY-SA 4.0</a>,
celle de Wikipédia dont il dérive. Vous pouvez le réutiliser librement, y compris à des
fins commerciales, en citant la source et en diffusant sous la même licence les versions
que vous en tirez.</p>

<p>Mention à reprendre&nbsp;: <strong>Sondax, d’après Wikipédia</strong>, avec un lien vers
sondax.fr. Une erreur&nbsp;? Écrivez à <a href="mailto:contact@sondax.fr">contact@sondax.fr</a>
ou corrigez directement Wikipédia&nbsp;: la correction apparaît ici au passage suivant.</p>

<h2>Colonnes</h2>

<div class="table-scroll"><table>
<thead><tr><th>Colonne</th><th>Contenu</th></tr></thead>
<tbody>
{dico}
</tbody>
</table></div>
</main>
{MARKER_JSONLD}"""

    style = """<style>
  main.donnees { max-width: 760px; }
  main.donnees p { margin-bottom: 0.9em; line-height: 1.65; }
  main.donnees .telechargement { background: var(--carte); border: 1px solid var(--bord);
    border-radius: 6px; padding: 14px 18px; margin: 1.4em 0; }
  main.donnees .telechargement a { font-family: var(--mono); font-weight: 500; font-size: 15px; }
  main.donnees .telechargement span { color: var(--gris); font-size: 13px; }
  main.donnees code { font-family: var(--mono); font-size: 12.5px; white-space: nowrap; }
  main.donnees td { vertical-align: top; }
  main.donnees .table-scroll { overflow-x: auto; }
</style>"""
    return render_page(
        title="Données des sondages de la présidentielle 2027 (CSV) — Sondax",
        meta_description=(f"Téléchargez les {nb_sondages} sondages d’intentions de vote de la "
                          "présidentielle 2027 en CSV : une ligne par candidat et par "
                          "configuration testée, mise à jour quotidienne, licence CC BY-SA."),
        canonical=URL_PAGE,
        body_content=body,
        extra_head=style,
    )


def main():
    sondages = json.loads((DATA / "sondages.json").read_text(encoding="utf-8"))
    candidats = json.loads((DATA / "candidats.json").read_text(encoding="utf-8"))
    rows = list(lignes(sondages, candidats))
    out = ecrire_csv(rows)
    fins = [s["terrain_fin"] for s in sondages]
    debuts = [s["terrain_debut"] for s in sondages]
    poids = max(1, round(out.stat().st_size / 1024))
    (SITE / "donnees.html").write_text(
        page(len(sondages), len(rows), poids, max(fins), min(debuts)), encoding="utf-8")
    print(f"  OK  donnees/{NOM_CSV} ({len(rows)} lignes, {len(sondages)} sondages)")
    print("  OK  donnees.html")


if __name__ == "__main__":
    main()
