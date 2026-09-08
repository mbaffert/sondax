"""Collecte des cotes Polymarket pour l'élection présidentielle 2027.

Lit candidats.json pour le mapping slug_polymarket → identifiant candidat,
interroge l'API Polymarket, et écrit data/polymarket.json.
"""

import json, sys, time, datetime, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
OUTPUT_PATH = ROOT / "data" / "polymarket.json"

EVENT_SLUG = "next-french-presidential-election"
SEUIL_PROBA = 0.01  # Probabilité minimale pour conserver un marché (spec §11)
GAMMA_URL = f"https://gamma-api.polymarket.com/events?slug={EVENT_SLUG}"
CLOB_URL = "https://clob.polymarket.com/prices-history?market={token}&interval=max&fidelity=1440"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sondax/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    candidats = json.loads(CANDIDATS_PATH.read_text())

    # Mapping inverse : slug_polymarket → clé candidat
    slug_to_id = {}
    for cid, info in candidats.items():
        slug = info.get("slug_polymarket")
        if slug:
            slug_to_id[slug] = cid

    # Récupération de l'événement
    events = fetch_json(GAMMA_URL)
    if not events:
        print("Erreur : aucun événement trouvé pour le slug", EVENT_SLUG, file=sys.stderr)
        sys.exit(1)

    event = events[0]
    markets = event.get("markets", [])
    print(f"{len(markets)} marchés trouvés sur Polymarket")

    result = {}
    matched, skipped = 0, 0

    for market in markets:
        slug = market.get("slug", "")
        if slug not in slug_to_id:
            skipped += 1
            continue

        cid = slug_to_id[slug]
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
            "slug": slug,
            "token_yes": token_yes,
            "prix_actuel": prix_actuel,
            "historique": historique,
        }
        matched += 1
        print(f"  {cid}: {len(historique)} points, prix actuel {prix_actuel}")

    output = {
        "maj": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "polymarket",
        "event_slug": EVENT_SLUG,
        "candidats": result,
    }

    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n")
    print(f"\n{matched} candidats collectés, {skipped} marchés sans correspondance dans candidats.json")
    print(f"Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
