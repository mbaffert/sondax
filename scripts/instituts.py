"""Référentiel des instituts (data/instituts.json) et commanditaires.

Module partagé par les scripts de build :
- résolution du nom court d'un sondage (`institut`) vers le slug du référentiel ;
- lien HTML vers la page de l'institut ;
- extraction du commanditaire depuis le nom de fichier de la notice.

Le commanditaire n'est pas collecté (SPEC §3.2) : il est déduit du nom de
fichier de la notice de la commission des sondages, par exemple
`10260-pres-iv-opinionway-cnews-11-septembre.pdf` → `cnews` → « CNews ».
Le passage du slug au nom affiché se fait par la table éditée à la main
`data/commanditaires.json`. Un slug absent de la table n'est pas affiché et
est signalé sur la page de revue.
"""

import html as html_mod
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"

MOIS_NOTICE = (
    "janvier|fevrier|mars|avril|mai|juin|juillet|aout|"
    "septembre|octobre|novembre|decembre"
)
PREFIXE_NOTICE = "commission-des-sondages.fr/notices/files/notices/"


def charger_referentiel():
    return json.loads((DATA / "instituts.json").read_text(encoding="utf-8"))


def charger_table_commanditaires():
    return json.loads((DATA / "commanditaires.json").read_text(encoding="utf-8"))


def _cle(nom):
    nfkd = unicodedata.normalize("NFKD", nom)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def index_alias(referentiel):
    """{alias normalisé → slug} ; le nom court compte comme alias."""
    idx = {}
    for slug, inst in referentiel.items():
        for a in [inst["nom"], *inst.get("alias", [])]:
            idx[_cle(a)] = slug
    return idx


def slug_institut(nom, referentiel):
    return index_alias(referentiel).get(_cle(nom))


def lien_institut(nom, referentiel, prefix=""):
    """Nom de l'institut, en lien vers sa page s'il est dans le référentiel."""
    esc = html_mod.escape(nom)
    slug = slug_institut(nom, referentiel)
    if not slug:
        return esc
    return f'<a href="{prefix}instituts/{slug}.html">{esc}</a>'


def logo_disponible(inst):
    """Chemin du logo relatif à site/, ou None si le fichier n'existe pas."""
    chemin = inst.get("logo")
    if chemin and (SITE / chemin).is_file():
        return chemin
    return None


# ---------------------------------------------------------------------------
# Commanditaires
# ---------------------------------------------------------------------------

def slug_commanditaire(url, inst):
    """Extrait le slug du commanditaire du nom de fichier de la notice.

    Retourne (statut, slug) avec statut parmi :
    - "hors_notice" : l'URL n'est pas un fichier de notice nommé ;
    - "institut_introuvable" : le nom de l'institut n'apparaît pas dans le fichier ;
    - "absent" : aucun commanditaire après le nom de l'institut ;
    - "trouve" : slug extrait (reconnu ou non, voir `commanditaire`).
    """
    if not url or PREFIXE_NOTICE not in url or not url.lower().endswith(".pdf"):
        return "hors_notice", None
    nom = url.rsplit("/", 1)[-1][:-4].lower()
    nom = re.sub(r"^\d+-", "", nom)
    nom = re.sub(rf"-\d{{1,2}}(er)?-({MOIS_NOTICE})$", "", nom)
    # Slugs de l'institut, du plus long au plus court (ipsos-bva avant ipsos)
    for s in sorted(inst.get("notice", []), key=len, reverse=True):
        m = re.search(rf"(^|-){re.escape(s)}(-|$)", nom)
        if m:
            reste = nom[m.end():].strip("-")
            return ("trouve", reste) if reste else ("absent", None)
    return "institut_introuvable", None


def commanditaire(sondage, referentiel, table):
    """Résultat d'extraction pour un sondage, sérialisable en JSON."""
    slug_inst = slug_institut(sondage["institut"], referentiel)
    res = {"institut": slug_inst, "statut": None, "slug": None, "nom": None}
    if not slug_inst:
        res["statut"] = "institut_inconnu"
        return res
    statut, slug = slug_commanditaire(sondage.get("url_source"), referentiel[slug_inst])
    res["slug"] = slug
    if statut == "trouve":
        if slug in table:
            res["statut"] = "reconnu"
            res["nom"] = table[slug]
        else:
            res["statut"] = "non_reconnu"
    else:
        res["statut"] = statut
    return res


def calculer_commanditaires(sondages, referentiel=None, table=None):
    referentiel = referentiel or charger_referentiel()
    table = table or charger_table_commanditaires()
    return {s["id"]: commanditaire(s, referentiel, table) for s in sondages}


def main():
    sondages = json.loads((DATA / "sondages.json").read_text(encoding="utf-8"))
    resultat = calculer_commanditaires(sondages)
    out = DATA / "derived" / "commanditaires.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")

    par_statut = {}
    for sid, r in resultat.items():
        par_statut.setdefault(r["statut"], []).append(sid)
    print(f"Commanditaires : {len(par_statut.get('reconnu', []))} reconnus sur {len(resultat)} sondages")
    for sid in par_statut.get("non_reconnu", []):
        print(f"  non reconnu  {sid} : {resultat[sid]['slug']}")
    for sid in par_statut.get("institut_inconnu", []):
        print(f"  institut absent du référentiel  {sid}")


if __name__ == "__main__":
    main()
