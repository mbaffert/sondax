"""Injecte le bloc #surete-choix dans site/index.html.

Tableau comparatif de la sûreté du choix par candidat (Elabe pour BFMTV et La Tribune
Dimanche), entre les marqueurs <!-- BEGIN:surete-choix --> et <!-- END:surete-choix -->.

Place : après bloc-modele, avant second-tour. Le modèle dit qui serait au second tour,
la sûreté du choix dit à quel point c'est mou : le second éclaire le premier et se lit
après lui.

Quand la règle de péremption masque l'affichage (surete_choix.est_perimee), le bloc ET
ses marqueurs sont retirés : la page retrouve exactement la mise en page qu'elle avait
sans cette rubrique, sans trou. Au retour d'une vague fraîche, les marqueurs sont
réinsérés au même endroit.

La mention « Sondage Elabe pour BFMTV et La Tribune Dimanche » est dans le bloc, pas en
note : sur l'accueil un tableau se lit « Sondax dit », et le faire passer pour un
agrégat Sondax est la seule chose que ce contrat interdit.
"""

import html as html_mod
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "site" / "index.html"
SITE = ROOT / "site"

sys.path.insert(0, str(ROOT / "scripts"))
import surete_choix as sc
from pages_second_tour import terrain_court

BEGIN_MARKER = "<!-- BEGIN:surete-choix -->"
END_MARKER = "<!-- END:surete-choix -->"
APRES = "<!-- END:bloc-modele -->"      # le bloc s'insère juste après celui-ci
AVANT = "<!-- BEGIN:second-tour -->"    # et avant celui-là

CSS = """<style>
  #surete-choix .sc-source { font-size: 14px; margin: 0 0 6px; }
  #surete-choix .sc-def { font-size: 13.5px; color: var(--gris); margin: 0 0 4px; }
  #surete-choix .sc-question { font-size: 13px; color: var(--gris); margin: 0 0 14px; }
  #surete-choix .sc-table { border-collapse: collapse; width: 100%; font-size: 14px; }
  #surete-choix .sc-table caption { text-align: left; font-size: 12.5px; color: var(--gris); padding-bottom: 6px; }
  #surete-choix .sc-table th, #surete-choix .sc-table td { border-bottom: 1px solid #e2e4e0; padding: 7px 8px; text-align: left; vertical-align: middle; }
  #surete-choix .sc-table th { background: #f5f5f3; font-weight: 600; font-size: 12.5px; }
  #surete-choix .sc-num { text-align: right !important; font-variant-numeric: tabular-nums; white-space: nowrap; }
  #surete-choix .sc-table th.sc-num { white-space: normal; }
  #surete-choix .sc-depuis { display: block; font-weight: 400; color: var(--gris); }
  #surete-choix .sc-piste { width: 38%; }
  #surete-choix .sc-barre { display: block; height: 8px; border-radius: 4px; background: #0A62DC; opacity: .75; }
  #surete-choix .sc-ensemble td { background: #f5f5f3; font-weight: 600; }
  #surete-choix .sc-mentions { font-size: 12px; line-height: 1.5; color: var(--gris); margin-top: 12px; }
  #surete-choix .sc-mentions p { margin: 0 0 4px; }
  @media (max-width: 620px) {
    #surete-choix .sc-table { font-size: 13px; }
    #surete-choix .sc-piste { display: none; }
  }
</style>"""


def _json(nom):
    return json.loads((ROOT / "data" / nom).read_text(encoding="utf-8"))


def generate_bloc(vue, candidats=None):
    """HTML du bloc, ou chaîne vide si `vue` est None (affichage masqué)."""
    if vue is None:
        return ""
    candidats = _json("candidats.json") if candidats is None else candidats
    v, prec = vue["vague"], vue["precedente"]
    esc = html_mod.escape

    avec_evol = prec is not None
    entete_evol = ""
    if avec_evol:
        entete_evol = (f'<th scope="col" class="sc-num">Évolution<span class="sc-depuis">'
                       f'depuis le {sc.date_jour_mois(prec["terrain_fin"])}</span></th>')

    def cellule_evol(evol):
        if not avec_evol:
            return ""
        return f'<td class="sc-num">{sc.signe(evol) if evol is not None else "—"}</td>'

    lignes = []
    for cid, part, evol in vue["lignes"]:
        nom = esc(candidats[cid]["nom"])
        if (SITE / f"{cid}.html").exists():
            nom = f'<a href="{cid}.html">{nom}</a>'
        lignes.append(
            f'      <tr><th scope="row">{nom}</th>'
            f'<td class="sc-piste"><span class="sc-barre" style="width:{part}%" aria-hidden="true"></span></td>'
            f'<td class="sc-num">{part} %</td>{cellule_evol(evol)}</tr>')
    lignes.append(
        '      <tr class="sc-ensemble"><th scope="row">Ensemble des électeurs</th>'
        '<td class="sc-piste"></td>'
        f'<td class="sc-num">{v["ensemble"]} %</td>{cellule_evol(vue["ensemble_evolution"])}</tr>')

    terrain = terrain_court(v["terrain_debut"], v["terrain_fin"])
    return (
        f'  <div class="bloc" id="surete-choix">\n'
        f'    {CSS}\n'
        f'    <div class="section-label">Sûreté du choix</div>\n'
        f'    <h2>Les électeurs de chaque candidat sont-ils sûrs de leur choix ?</h2>\n'
        f'    <p class="sc-source"><strong>{esc(sc.source_courte(v))}</strong>, '
        f'terrain du {terrain}. Ces chiffres sont ceux d’Elabe : '
        f'ce n’est pas une moyenne Sondax.</p>\n'
        f'    <p class="sc-def">Part des électeurs de chaque candidat qui se déclarent sûrs de '
        f'leur choix. Ce n’est pas la certitude d’aller voter, qui est une autre mesure.</p>\n'
        f'    <p class="sc-question">Question posée : « {esc(vue["question"])} »</p>\n'
        f'    <table class="sc-table">\n'
        f'      <caption>Part des électeurs sûrs de leur choix, en % des intentions de vote</caption>\n'
        f'      <thead><tr><th scope="col">Candidat</th><th scope="col" class="sc-piste" aria-label="Part"></th>'
        f'<th scope="col" class="sc-num">Sûrs de leur choix</th>{entete_evol}</tr></thead>\n'
        f'      <tbody>\n' + "\n".join(lignes) + '\n      </tbody>\n'
        f'    </table>\n'
        f'    <div class="sc-mentions">{sc.mentions_html(v, vue["base"])}</div>\n'
        f'  </div>'
    )


def inject(content, bloc):
    """Renvoie `content` (le HTML de index.html) avec le bloc inséré, remplacé, ou
    retiré (bloc vide). Retirer rend la page strictement identique à celle d'avant
    l'insertion."""
    present = BEGIN_MARKER in content and END_MARKER in content
    if not bloc:
        if not present:
            return content
        return re.sub(r"\n\n[ \t]*" + re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER),
                      "", content, count=1, flags=re.S)
    if present:
        i_begin = content.index(BEGIN_MARKER)
        i_end = content.index(END_MARKER) + len(END_MARKER)
        return (content[:i_begin] + BEGIN_MARKER + "\n" + bloc + "\n" + END_MARKER
                + content[i_end:])
    if APRES not in content or AVANT not in content or content.index(APRES) > content.index(AVANT):
        raise ValueError(f"Repères {APRES} / {AVANT} introuvables (ou dans le mauvais ordre) "
                         f"dans index.html")
    i = content.index(APRES) + len(APRES)
    return (content[:i] + "\n\n  " + BEGIN_MARKER + "\n" + bloc + "\n" + END_MARKER
            + content[i:])


def main():
    vue = sc.vue()
    bloc = generate_bloc(vue)
    contenu = INDEX_PATH.read_text(encoding="utf-8")
    INDEX_PATH.write_text(inject(contenu, bloc), encoding="utf-8")
    if vue is None:
        print("Bloc surete-choix masqué : dernière vague de plus de dix semaines")
    else:
        print(f"Bloc surete-choix injecté : {len(vue['lignes'])} candidats, vague {vue['vague']['id']}")


if __name__ == "__main__":
    main()
