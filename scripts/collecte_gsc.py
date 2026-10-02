"""Collecte Google Search Console (API Search Analytics) pour sondax.fr.

Authentification : compte de service dont la clé JSON est lue dans la variable
d'environnement GSC_SERVICE_ACCOUNT (secret GitHub). La clé n'est jamais écrite
sur disque ni affichée.

Usage :
  python scripts/collecte_gsc.py --sites   # liste les propriétés accessibles
  python scripts/collecte_gsc.py           # collecte des 90 derniers jours

Pour chaque jeu de dimensions, un CSV dans data/gsc/. Les dates présentes dans
la réponse remplacent intégralement les lignes de ces dates dans le fichier
(Google révise les derniers jours après coup). Toute erreur ou réponse vide fait
échouer le script sans rien écrire.
"""

import csv, datetime, json, os, pathlib, sys, time
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "gsc"

# Identifiant de la propriété, tel que renvoyé par sites.list.
SITE_URL = "sc-domain:sondax.fr"

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
API = "https://www.googleapis.com/webmasters/v3"
JOURS = 90
ROW_LIMIT = 25000

JEUX = {
    "gsc-date.csv": ["date"],
    "gsc-date-query.csv": ["date", "query"],
    "gsc-date-page.csv": ["date", "page"],
    "gsc-date-device.csv": ["date", "device"],
}
METRIQUES = ["clicks", "impressions", "ctr", "position"]


def erreur(message):
    print(f"Erreur GSC : {message}", file=sys.stderr)
    sys.exit(1)


def session():
    brut = os.environ.get("GSC_SERVICE_ACCOUNT", "").strip()
    if not brut:
        erreur("variable d'environnement GSC_SERVICE_ACCOUNT absente ou vide")
    # Messages volontairement génériques : rien du contenu de la clé ne doit
    # pouvoir se retrouver dans les logs.
    try:
        info = json.loads(brut)
    except ValueError:
        erreur("GSC_SERVICE_ACCOUNT n'est pas un JSON valide")
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        erreur("impossible de charger la clé du compte de service")
    return AuthorizedSession(creds)


def appel(sess, methode, url, corps=None):
    """Appel API avec quelques reprises sur 429/5xx. Échoue sinon."""
    for tentative in range(4):
        try:
            resp = sess.request(methode, url, json=corps, timeout=60)
        except Exception as e:
            statut, detail = None, type(e).__name__
        else:
            if resp.status_code == 200:
                return resp.json()
            statut = resp.status_code
            try:
                detail = resp.json()["error"]["message"]
            except Exception:
                detail = resp.text[:300]
        if statut is not None and statut not in (429, 500, 502, 503, 504):
            break
        if tentative < 3:
            time.sleep(2 ** (tentative + 1))
    erreur(f"{methode} {url} → HTTP {statut} : {detail}")


def lister_sites(sess):
    entrees = appel(sess, "GET", f"{API}/sites").get("siteEntry", [])
    if not entrees:
        erreur("sites.list ne renvoie aucune propriété : l'autorisation du compte "
               "de service dans Search Console n'a pas pris")
    return entrees


def requete(sess, debut, fin, dimensions):
    """searchanalytics.query paginé jusqu'à épuisement."""
    url = f"{API}/sites/{quote(SITE_URL, safe='')}/searchAnalytics/query"
    lignes, start = [], 0
    while True:
        rep = appel(sess, "POST", url, {
            "startDate": debut,
            "endDate": fin,
            "dimensions": dimensions,
            "rowLimit": ROW_LIMIT,
            "startRow": start,
        })
        lot = rep.get("rows", [])
        lignes.extend(lot)
        if len(lot) < ROW_LIMIT:
            return lignes
        start += ROW_LIMIT


def nombre(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def fusionner(chemin, dimensions, lignes_api):
    """Retire du fichier existant toutes les dates présentes dans la réponse,
    puis y ajoute la réponse. Renvoie (entête, lignes triées, dates remplacées)."""
    entete = dimensions + METRIQUES
    nouvelles = []
    for r in lignes_api:
        cles = r["keys"]
        if len(cles) != len(dimensions):
            erreur(f"{chemin.name} : ligne inattendue {cles!r}")
        nouvelles.append(cles + [nombre(r[m]) for m in METRIQUES])
    dates = {l[0] for l in nouvelles}

    anciennes = []
    if chemin.exists():
        with chemin.open(newline="", encoding="utf-8") as f:
            lecteur = csv.reader(f)
            if next(lecteur, None) != entete:
                erreur(f"{chemin.name} : entête inattendue, fichier non modifié")
            anciennes = [l for l in lecteur if l and l[0] not in dates]

    toutes = anciennes + nouvelles
    toutes.sort(key=lambda l: l[:len(dimensions)])
    cles_vues = set()
    for l in toutes:
        k = tuple(l[:len(dimensions)])
        if k in cles_vues:
            erreur(f"{chemin.name} : doublon {k!r}")
        cles_vues.add(k)
    return entete, toutes, dates


def ecrire(chemin, entete, lignes):
    tmp = chemin.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(entete)
        w.writerows(lignes)
    os.replace(tmp, chemin)


def main():
    sess = session()
    sites = lister_sites(sess)
    print("Propriétés accessibles :")
    for s in sites:
        print(f"  {s['siteUrl']}  ({s.get('permissionLevel', '?')})")

    if "--sites" in sys.argv:
        return

    if not SITE_URL:
        erreur("SITE_URL n'est pas renseigné dans le script")
    if SITE_URL not in {s["siteUrl"] for s in sites}:
        erreur(f"la propriété {SITE_URL} n'est pas accessible au compte de service")

    fin = datetime.date.today()
    debut = fin - datetime.timedelta(days=JOURS - 1)
    print(f"Période : {debut} → {fin}")

    # Tout est récupéré et fusionné en mémoire avant la moindre écriture :
    # une erreur sur un jeu n'en laisse aucun à moitié mis à jour.
    resultats = []
    for nom, dimensions in JEUX.items():
        lignes_api = requete(sess, debut.isoformat(), fin.isoformat(), dimensions)
        if not lignes_api:
            erreur(f"réponse vide pour {dimensions} : aucun fichier modifié")
        entete, lignes, dates = fusionner(OUTPUT_DIR / nom, dimensions, lignes_api)
        print(f"  {nom} : {len(lignes_api)} lignes reçues, {len(dates)} dates "
              f"({min(dates)} → {max(dates)}), {len(lignes)} lignes au total")
        resultats.append((OUTPUT_DIR / nom, entete, lignes))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for chemin, entete, lignes in resultats:
        ecrire(chemin, entete, lignes)


if __name__ == "__main__":
    main()
