"""Injecte le bloc #second-tour statique dans site/index.html.

Lit data/sondages.json, data/candidats.json et data/config.json,
génère le HTML du bloc et le remplace entre les marqueurs
<!-- BEGIN:second-tour --> et <!-- END:second-tour -->.
"""

import json, pathlib, sys, html as html_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "site" / "index.html"
CONFIG_PATH = ROOT / "data" / "config.json"

sys.path.insert(0, str(ROOT / "scripts"))
from pages_second_tour import (
    load_duels, nom_court, fmt_date, fmt_pct, find_pair_from_slug, SEUIL,
)

BEGIN_MARKER = "<!-- BEGIN:second-tour -->"
END_MARKER = "<!-- END:second-tour -->"

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def date_longue(iso):
    """'2027-04-18' → '18 avril 2027'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def pair(slug, candidats):
    """Découpe un slug en (cid_a, cid_b) via find_pair_from_slug."""
    return find_pair_from_slug(slug, candidats)


# ---------------------------------------------------------------------------
# Texte factuel (dates + règle de qualification)
# ---------------------------------------------------------------------------

def generate_factual_text(config):
    election = config.get("election", {})
    t1 = election.get("premier_tour", "2027-04-18")
    t2 = election.get("second_tour", "2027-05-02")
    officielles = election.get("officielles", False)

    t1_long = date_longue(t1)
    t2_long = date_longue(t2)

    verbe = "aura lieu" if officielles else "devrait avoir lieu"

    text = (
        f'<p class="subtitle">'
        f'Le premier tour {verbe} le '
        f'<time datetime="{t1}">{t1_long}</time>, '
        f'le second tour le '
        f'<time datetime="{t2}">{t2_long}</time>. '
        f'Les deux candidats arrivés en tête au premier tour s\u2019affrontent '
        f'au second, sauf si l\u2019un obtient la majorité absolue dès le '
        f'premier tour.'
        f'</p>'
    )

    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Event",
                "name": "Élection présidentielle française 2027 \u2014 premier tour",
                "startDate": t1,
                "location": {"@type": "Country", "name": "France"},
            },
            {
                "@type": "Event",
                "name": "Élection présidentielle française 2027 \u2014 second tour",
                "startDate": t2,
                "location": {"@type": "Country", "name": "France"},
            },
        ],
    }
    ld = json.dumps(schema, ensure_ascii=False)
    text += f'\n    <script type="application/ld+json">{ld}</script>'

    return text


# ---------------------------------------------------------------------------
# Chapeau généré au build
# ---------------------------------------------------------------------------

def generate_chapeau(duels, candidats):
    if not duels:
        return (
            '<p class="subtitle">'
            'Aucun duel de second tour n\u2019a été testé par les instituts.'
            '</p>'
        )

    n_duels = len(duels)
    n_mesures = sum(len(e) for e in duels.values())

    # Qui arrive en tête dans la dernière mesure de chaque duel ?
    wins = {}
    for slug, entries in duels.items():
        cid_a, cid_b = pair(slug, candidats)
        latest = entries[0]["scores"]
        leader = cid_a if latest.get(cid_a, 0) >= latest.get(cid_b, 0) else cid_b
        wins[leader] = wins.get(leader, 0) + 1

    # Duel le plus serré
    tightest_slug = None
    min_ecart = float("inf")
    for slug, entries in duels.items():
        cid_a, cid_b = pair(slug, candidats)
        latest = entries[0]["scores"]
        ecart = abs(latest.get(cid_a, 0) - latest.get(cid_b, 0))
        if ecart < min_ecart:
            min_ecart = ecart
            tightest_slug = slug

    # Inversions
    reversals = []
    for slug, entries in duels.items():
        if len(entries) < 2:
            continue
        cid_a, cid_b = pair(slug, candidats)
        first = entries[-1]["scores"]
        last = entries[0]["scores"]
        first_leader = cid_a if first.get(cid_a, 0) >= first.get(cid_b, 0) else cid_b
        last_leader = cid_a if last.get(cid_a, 0) >= last.get(cid_b, 0) else cid_b
        if first_leader != last_leader:
            reversals.append(slug)

    phrases = []

    # Phrase 1 : volume
    if n_duels == 1:
        slug = list(duels.keys())[0]
        cid_a, cid_b = pair(slug, candidats)
        nom_a = nom_court(cid_a, candidats)
        nom_b = nom_court(cid_b, candidats)
        mes = "mesure" if n_mesures == 1 else "mesures"
        phrases.append(
            f"Un seul duel a été testé\u00a0: {nom_a} contre {nom_b}, "
            f"avec {n_mesures}\u00a0{mes}."
        )
    else:
        phrases.append(
            f"{n_duels}\u00a0duels de second tour testés par les instituts, "
            f"pour un total de {n_mesures}\u00a0mesures."
        )

    # Phrase 2 : leader
    if wins and n_duels > 1:
        leader_cid = max(wins, key=lambda c: wins[c])
        nom = nom_court(leader_cid, candidats)
        nw = wins[leader_cid]
        if nw == n_duels:
            phrases.append(f"{nom} arrive en tête dans tous les duels mesurés.")
        elif nw > 1:
            phrases.append(f"{nom} arrive en tête dans {nw}\u00a0d\u2019entre eux.")

    # Phrase 3 : inversion ou duel le plus serré
    if reversals and n_duels > 1:
        cid_a, cid_b = pair(reversals[0], candidats)
        nom_a = nom_court(cid_a, candidats)
        nom_b = nom_court(cid_b, candidats)
        phrases.append(
            f"Le duel {nom_a}\u00a0\u2013\u00a0{nom_b} a changé de sens "
            f"depuis sa première mesure."
        )
    elif tightest_slug and n_duels > 1:
        cid_a, cid_b = pair(tightest_slug, candidats)
        nom_a = nom_court(cid_a, candidats)
        nom_b = nom_court(cid_b, candidats)
        ecart_fmt = f"{min_ecart:.1f}".replace(".", ",")
        pts = "point" if min_ecart < 1.5 else "points"
        phrases.append(
            f"Le duel le plus serré oppose {nom_a} à {nom_b} "
            f"({ecart_fmt}\u00a0{pts} d\u2019écart)."
        )

    return f'<p class="subtitle">{" ".join(phrases)}</p>'


# ---------------------------------------------------------------------------
# Tableau des duels
# ---------------------------------------------------------------------------

def generate_table(duels, candidats):
    if not duels:
        return ""

    # Tri : mesures DESC, date DESC
    sorted_slugs = sorted(
        duels.keys(),
        key=lambda s: (-len(duels[s]), duels[s][0]["terrain_fin"]),
        reverse=False,
    )
    # La date est en ISO, on veut DESC → inverser le tri secondaire.
    # Comme le tri primaire est -len (déjà négatif), on peut trier en deux passes.
    sorted_slugs = sorted(duels.keys(), key=lambda s: duels[s][0]["terrain_fin"], reverse=True)
    sorted_slugs = sorted(sorted_slugs, key=lambda s: -len(duels[s]))

    rows = []
    for slug in sorted_slugs:
        entries = duels[slug]
        cid_a, cid_b = pair(slug, candidats)
        nom_a = html_mod.escape(nom_court(cid_a, candidats))
        nom_b = html_mod.escape(nom_court(cid_b, candidats))
        n = len(entries)
        latest = entries[0]
        date_str = fmt_date(latest["terrain_fin"])
        institut = html_mod.escape(latest["institut"])

        score_a = latest["scores"].get(cid_a, 0)
        score_b = latest["scores"].get(cid_b, 0)
        score_str = f'{fmt_pct(score_a)} \u2013 {fmt_pct(score_b)}'

        if n >= SEUIL:
            duel_label = (
                f'<a href="second-tour/{slug}.html">'
                f'{nom_a}\u00a0\u2013\u00a0{nom_b}</a>'
            )
        else:
            duel_label = f'{nom_a}\u00a0\u2013\u00a0{nom_b}'

        rows.append(
            f'      <tr>'
            f'<td>{duel_label}</td>'
            f'<td>{n}</td>'
            f'<td>{date_str} ({institut})</td>'
            f'<td style="font-variant-numeric:tabular-nums;">{score_str}</td>'
            f'</tr>'
        )

    return (
        '    <table class="t2-table">\n'
        '      <tr><th>Duel</th><th>Mesures</th>'
        '<th>Dernière mesure</th><th>Score</th></tr>\n'
        + "\n".join(rows) + "\n"
        '    </table>'
    )


# ---------------------------------------------------------------------------
# Sélecteur de détail (hydraté par JS)
# ---------------------------------------------------------------------------

def generate_selector_html():
    return (
        '    <div class="t2-selector" style="margin-top:18px;">\n'
        '      <h3 style="font-family:var(--titre);font-size:18px;'
        'font-weight:600;margin-bottom:12px;">Explorer un duel</h3>\n'
        '      <div class="duel-select">\n'
        '        <span style="color:var(--gris);">Candidat\u00a0:</span>\n'
        '        <select id="duel-cand1"></select>\n'
        '        <span style="color:var(--gris);">contre\u00a0:</span>\n'
        '        <select id="duel-cand2"></select>\n'
        '      </div>\n'
        '      <div id="t2-content"></div>\n'
        '    </div>'
    )


# ---------------------------------------------------------------------------
# Assemblage et injection
# ---------------------------------------------------------------------------

def generate_bloc(config, duels, candidats):
    factual = generate_factual_text(config)
    chapeau = generate_chapeau(duels, candidats)
    table = generate_table(duels, candidats)
    selector = generate_selector_html()

    return (
        '  <div class="bloc" id="second-tour">\n'
        '    <div class="section-label">Second tour</div>\n'
        '    <h2>Second tour de l\u2019élection présidentielle 2027</h2>\n'
        f'    {factual}\n'
        f'    {chapeau}\n'
        f'{table}\n'
        f'{selector}\n'
        '  </div>'
    )


def inject_into_index(html_bloc):
    content = INDEX_PATH.read_text(encoding="utf-8")
    try:
        i_begin = content.index(BEGIN_MARKER)
        i_end = content.index(END_MARKER) + len(END_MARKER)
    except ValueError:
        raise ValueError(
            f"Marqueurs {BEGIN_MARKER} / {END_MARKER} introuvables "
            f"dans {INDEX_PATH}"
        )
    new_content = (
        content[:i_begin]
        + BEGIN_MARKER + "\n"
        + html_bloc + "\n"
        + END_MARKER
        + content[i_end:]
    )
    INDEX_PATH.write_text(new_content, encoding="utf-8")


def main():
    config = load_config()
    duels, candidats = load_duels()
    html_bloc = generate_bloc(config, duels, candidats)
    inject_into_index(html_bloc)

    n = len(duels)
    m = sum(len(e) for e in duels.values())
    print(f"Bloc second-tour injecté : {n} duels, {m} mesures")


if __name__ == "__main__":
    main()
