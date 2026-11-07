"""Notification IndexNow (Bing, Yandex, Seznam…) des pages récemment modifiées.

Lancé par pages.yml après le déploiement, sur les seuls déploiements
déclenchés par un push (merge d'une collecte), pas sur le cron de 0 h 05 :
on ne renotifie pas chaque nuit des pages inchangées.

Les pages retenues sont celles dont le <lastmod> du sitemap date de moins de
JOURS jours. La fenêtre est large parce qu'une fiche sondage est datée de la
fin du terrain, souvent un ou deux jours avant sa mise en ligne.

Usage : python scripts/indexnow.py _site/sitemap.xml
"""
import datetime
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

HOTE = "sondax.fr"
CLE = "53ccbb713b82097d7d5f59998def2bef"  # publique par construction : site/<CLE>.txt
JOURS = 3
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def urls_recentes(sitemap):
    seuil = (datetime.date.today() - datetime.timedelta(days=JOURS)).isoformat()
    racine = ET.parse(sitemap).getroot()
    return [u.findtext("s:loc", namespaces=NS)
            for u in racine.findall("s:url", NS)
            if (u.findtext("s:lastmod", default="", namespaces=NS))[:10] >= seuil]


def notifier(urls):
    corps = json.dumps({
        "host": HOTE,
        "key": CLE,
        "keyLocation": f"https://{HOTE}/{CLE}.txt",
        "urlList": urls,
    }).encode()
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow", data=corps,
        headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as rep:
        return rep.status


def main():
    urls = urls_recentes(sys.argv[1])
    if not urls:
        print("IndexNow : aucune page modifiée récemment")
        return
    statut = notifier(urls)
    print(f"IndexNow : {len(urls)} URL notifiées, réponse HTTP {statut}")
    for u in urls:
        print("  ", u)


if __name__ == "__main__":
    main()
