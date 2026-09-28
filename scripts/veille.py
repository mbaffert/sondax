"""Veille électorale (loi du 19 juillet 1977, SPEC §10) : ni publication ni
commentaire de sondage la veille et le jour de chaque tour. Dates lues dans
data/config.json ; « aujourd'hui » s'entend à l'heure de Paris.
"""

import datetime, json, pathlib
from zoneinfo import ZoneInfo

CONFIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "config.json"


def jours_de_veille():
    el = json.loads(CONFIG_PATH.read_text())["election"]
    jours = set()
    for cle in ("premier_tour", "second_tour"):
        tour = datetime.date.fromisoformat(el[cle])
        jours |= {tour - datetime.timedelta(days=1), tour}
    return jours


def aujourdhui():
    return datetime.datetime.now(ZoneInfo("Europe/Paris")).date()


def en_veille(jour=None):
    return (jour or aujourdhui()) in jours_de_veille()
