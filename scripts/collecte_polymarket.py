"""Collecte des cotes Polymarket pour l'élection présidentielle 2027.

Lit candidats.json pour le mapping condition_polymarket → identifiant candidat,
interroge l'API Polymarket pour les deux événements (victoire et second tour),
et écrit data/polymarket.json.
"""

import json, sys, time, datetime, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
OUTPUT_PATH = ROOT / "data" / "polymarket.json"

EVENTS = {
    "victoire": "next-french-presidential-election",
    "second_tour": "next-french-presidential-election-who-will-advance-to-the-2nd-round",
}

SEUIL_PROBA = 0.01  # Probabilité minimale pour conserver un marché (spec §11)
GAMMA_URL = "https://gamma-api.polymarket.com/events?slug={slug}"
CLOB_URL = "https://clob.polymarket.com/prices-history?market={token}&interval=max&fidelity=1440"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sondax/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def collect_event(event_key, event_slug, cond_to_id):
    """Collecte un événement. Retourne dict {candidat_id: {...}}."""
    events = fetch_json(GAMMA_URL.format(slug=event_slug))
    if not events:
        print(f"Erreur : aucun événement trouvé pour {event_slug}", file=sys.stderr)
        sys.exit(1)

    event = events[0]
    markets = event.get("markets", [])
    print(f"[{event_key}] {len(markets)} marchés trouvés")

    result = {}
    matched, skipped = 0, 0

    for market in markets:
        condition_id = market.get("conditionId", "")
        if condition_id not in cond_to_id:
            skipped += 1
            continue

        cid = cond_to_id[condition_id]
        token_ids = json.loads(market.get("clobTokenIds", "[]"))
        if not token_ids:
            print(f"  {cid}: pas de clobTokenIds, ignoré", file=sys.stderr)
            continue

        token_yes = token_ids[0]  # Premier élément = token « Yes » (spec §2.2)
        prices = json.loads(market.get("outcomePrices", "[]"))
        prix_actuel = float(prices[0]) if prices else None

        if prix_actuel is not None and prix_actuel < SEUIL_PROBA:
            skipped += 1
            continue

        # Historique quotidien
        time.sleep(0.2)  # politesse
        try:
            hist_data = fetch_json(CLOB_URL.format(token=token_yes))
        except urllib.error.URLError as e:
            print(f"  {cid}: erreur historique ({e}), ignoré", file=sys.stderr)
            continue

        historique = []
        for point in hist_data.get("history", []):
            d = datetime.datetime.fromtimestamp(point["t"], tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            historique.append({"d": d, "p": round(point["p"], 4)})

        result[cid] = {
            "market_id": market.get("id", ""),
            "token_yes": token_yes,
            "prix_actuel": prix_actuel,
            "historique": historique,
        }
        matched += 1
        print(f"  {cid}: {len(historique)} points, prix actuel {prix_actuel}")

    print(f"  {matched} candidats collectés, {skipped} marchés sans correspondance ou sous seuil")
    return result


def main():
    candidats = json.loads(CANDIDATS_PATH.read_text())

    # Mapping inverse par événement : conditionId → clé candidat
    cond_maps = {}
    for event_key in EVENTS:
        mapping = {}
        for cid, info in candidats.items():
            cp = info.get("condition_polymarket")
            if cp and cp.get(event_key):
                mapping[cp[event_key]] = cid
        cond_maps[event_key] = mapping

    output = {
        "maj": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "marches": {},
    }

    for event_key, event_slug in EVENTS.items():
        cond_to_id = cond_maps[event_key]
        print(f"\n--- {event_key} ({len(cond_to_id)} candidats attendus) ---")
        candidats_result = collect_event(event_key, event_slug, cond_to_id)
        output["marches"][event_key] = {
            "event_slug": event_slug,
            "candidats": candidats_result,
        }

    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n")
    total = sum(len(m["candidats"]) for m in output["marches"].values())
    print(f"\nTotal : {total} séries collectées")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
