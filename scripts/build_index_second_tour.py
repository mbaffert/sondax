"""Injecte le bloc #second-tour statique dans site/index.html.

Lit data/sondages.json, data/candidats.json et data/config.json,
génère le HTML du bloc et le remplace entre les marqueurs
<!-- BEGIN:second-tour --> et <!-- END:second-tour -->.

Tout le contenu est rendu au build et présent dans le HTML servi.
Le JavaScript ne sert qu'à l'interaction (sélecteur de duel).
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

NOMBRES_LETTRES = {
    1: "un", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq",
    6: "six", 7: "sept", 8: "huit", 9: "neuf", 10: "dix",
    11: "onze", 12: "douze",
}


def date_longue(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def pair(slug, candidats):
    return find_pair_from_slug(slug, candidats)


def nombre_lettres(n):
    return NOMBRES_LETTRES.get(n, str(n))


def genre(cid, candidats):
    """Retourne 'm' ou 'f' pour l'accord grammatical."""
    c = candidats.get(cid, {})
    return c.get("genre", "m")


# ---------------------------------------------------------------------------
# Texte factuel
# ---------------------------------------------------------------------------

def generate_factual_text(config):
    election = config.get("election", {})
    t1 = election.get("premier_tour", "2027-04-18")
    t2 = election.get("second_tour", "2027-05-02")
    officielles = election.get("officielles", False)

    verbe = "aura lieu" if officielles else "devrait avoir lieu"

    text = (
        f'<p class="subtitle">'
        f'Le premier tour {verbe} le '
        f'<time datetime="{t1}">{date_longue(t1)}</time>, '
        f'le second tour le '
        f'<time datetime="{t2}">{date_longue(t2)}</time>. '
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
                "name": f"Élection présidentielle française 2027 \u2014 premier tour",
                "startDate": t1,
                "location": {"@type": "Country", "name": "France"},
            },
            {
                "@type": "Event",
                "name": f"Élection présidentielle française 2027 \u2014 second tour",
                "startDate": t2,
                "location": {"@type": "Country", "name": "France"},
            },
        ],
    }
    ld = json.dumps(schema, ensure_ascii=False)
    text += f'\n    <script type="application/ld+json">{ld}</script>'
    return text


# ---------------------------------------------------------------------------
# Chapeau
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
    # Nombre de sondages distincts portant au moins un duel
    sondage_ids = set()
    for entries in duels.values():
        for e in entries:
            sondage_ids.add(e["terrain_fin"] + "|" + e["institut"])
    n_sondages_distincts = len(sondage_ids)

    # Compter, par candidat : dans combien de duels il apparaît, et combien il gagne
    appearances = {}  # cid → nombre de duels
    wins = {}  # cid → nombre de duels gagnés (dernière mesure)
    for slug, entries in duels.items():
        cid_a, cid_b = pair(slug, candidats)
        appearances[cid_a] = appearances.get(cid_a, 0) + 1
        appearances[cid_b] = appearances.get(cid_b, 0) + 1
        latest = entries[0]["scores"]
        sa, sb = latest.get(cid_a, 0), latest.get(cid_b, 0)
        if sa > sb:
            wins[cid_a] = wins.get(cid_a, 0) + 1
        elif sb > sa:
            wins[cid_b] = wins.get(cid_b, 0) + 1

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
            f"{n_duels}\u00a0duels de second tour testés dans "
            f"{n_sondages_distincts}\u00a0sondages, "
            f"pour un total de {n_mesures}\u00a0mesures."
        )

    # Phrase 2 : leader avec dénominateur explicite
    if wins and n_duels > 1:
        leader_cid = max(wins, key=lambda c: wins[c])
        nom = nom_court(leader_cid, candidats)
        nw = wins[leader_cid]
        na = appearances[leader_cid]
        g = genre(leader_cid, candidats)
        e_accord = "e" if g == "f" else ""
        na_lettres = nombre_lettres(na)

        if nw == na:
            if na == 1:
                phrases.append(
                    f"{nom} l\u2019emporte dans le seul duel "
                    f"où {('elle' if g == 'f' else 'il')} est testé{e_accord}."
                )
            else:
                phrases.append(
                    f"{nom} l\u2019emporte dans les {na_lettres}\u00a0duels "
                    f"où {('elle' if g == 'f' else 'il')} est testé{e_accord}."
                )
        else:
            phrases.append(
                f"{nom} l\u2019emporte dans "
                f"{nombre_lettres(nw)} des {na_lettres}\u00a0duels "
                f"où {('elle' if g == 'f' else 'il')} est testé{e_accord}."
            )

    # Phrase 3 : inversion ou duel le plus serré
    if reversals and n_duels > 1:
        cid_a, cid_b = pair(reversals[0], candidats)
        nom_a = nom_court(cid_a, candidats)
        nom_b = nom_court(cid_b, candidats)
        phrases.append(
            f"Le duel {nom_a}\u00a0\u2013\u00a0{nom_b} a changé de sens "
            f"depuis le premier sondage."
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

HEADER_ROW = (
    '      <tr>'
    '<th scope="col">En t\u00eate</th>'
    '<th scope="col" class="t2-score-col" aria-label="Score du candidat en t\u00eate">Score</th>'
    '<th scope="col">Face \u00e0</th>'
    '<th scope="col" class="t2-score-col" aria-label="Score du candidat adverse">Score</th>'
    '<th scope="col">Sondages</th>'
    '<th scope="col">Derni\u00e8re mesure</th>'
    '</tr>'
)


def format_duel_row(slug, entries, candidats):
    """Génère une ligne <tr> pour un duel.

    Colonnes : En tête | Score | Face à | Score | Mesures | Dernière mesure.
    """
    cid_a, cid_b = pair(slug, candidats)
    latest = entries[0]
    sa = latest["scores"].get(cid_a, 0)
    sb = latest["scores"].get(cid_b, 0)

    # Vainqueur en premier (en cas d'égalité, conserver l'ordre de la clé)
    if sb > sa:
        cid_1, s1, cid_2, s2 = cid_b, sb, cid_a, sa
    else:
        cid_1, s1, cid_2, s2 = cid_a, sa, cid_b, sb

    nom_1 = html_mod.escape(nom_court(cid_1, candidats))
    nom_2 = html_mod.escape(nom_court(cid_2, candidats))

    n = len(entries)
    date_str = fmt_date(latest["terrain_fin"])
    institut = html_mod.escape(latest["institut"])

    return (
        f'      <tr>'
        f'<td>{nom_1}</td>'
        f'<td class="t2-score-cell">{fmt_pct(s1)}</td>'
        f'<td>{nom_2}</td>'
        f'<td class="t2-score-cell">{fmt_pct(s2)}</td>'
        f'<td>{n}</td>'
        f'<td>{date_str} ({institut})</td>'
        f'</tr>'
    )


def sorted_duel_slugs(duels):
    """Tri : date DESC, sondages DESC, clé interne ASC (stable)."""
    return sorted(
        duels.keys(),
        key=lambda s: (
            "".join(chr(255 - ord(c)) for c in duels[s][0]["terrain_fin"]),
            -len(duels[s]),
            s,
        ),
    )


def generate_table_section(duels, candidats):
    """Génère le duel le plus récent en aperçu + le reste dans un <details>."""
    if not duels:
        return ""

    slugs = sorted_duel_slugs(duels)
    n_total = len(slugs)

    # Aperçu : le duel le plus récemment mesuré
    first_slug = slugs[0]
    preview_row = format_duel_row(first_slug, duels[first_slug], candidats)

    preview_table = (
        '    <table class="t2-table t2-duels">\n'
        f'{HEADER_ROW}\n'
        f'{preview_row}\n'
        '    </table>'
    )

    # Pli : les autres duels
    if n_total <= 1:
        return preview_table

    rest_rows = []
    for slug in slugs[1:]:
        rest_rows.append(format_duel_row(slug, duels[slug], candidats))

    n_rest = n_total - 1
    if n_rest == 1:
        summary_text = "L\u2019autre duel testé"
    else:
        summary_text = f"Les {nombre_lettres(n_rest)} autres duels testés"

    fold_table = (
        '      <table class="t2-table t2-duels">\n'
        f'  {HEADER_ROW}\n'
        + "\n".join(rest_rows) + "\n"
        '      </table>'
    )

    details = (
        f'    <details class="duels-repli">\n'
        f'      <summary>{summary_text}</summary>\n'
        f'{fold_table}\n'
        f'    </details>'
    )

    return f'{preview_table}\n{details}'


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
    table_section = generate_table_section(duels, candidats)
    selector = generate_selector_html()

    return (
        '  <div class="bloc" id="second-tour">\n'
        '    <div class="section-label">Second tour</div>\n'
        '    <h2>Second tour de l\u2019élection présidentielle 2027</h2>\n'
        f'    {factual}\n'
        f'    {chapeau}\n'
        f'{table_section}\n'
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
    print(f"Bloc second-tour injecté : {n} duels, {m} sondages")


if __name__ == "__main__":
    main()
