"""Injecte le tableau complet des sondages dans site/sondages.html.

Le JavaScript garde le tri et le filtrage ; le HTML statique contient
toutes les données pour l'indexation.
"""

import json, pathlib, html as html_mod

ROOT = pathlib.Path(__file__).resolve().parent.parent
SONDAGES_PATH = ROOT / "data" / "sondages.json"
SONDAGES_HTML = ROOT / "site" / "sondages.html"

BEGIN = "<!-- BEGIN:table-sondages -->"
END = "<!-- END:table-sondages -->"


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def fmt_ech(n):
    return f"{round(n):,}".replace(",", "\u202f")


def main():
    sondages = json.loads(SONDAGES_PATH.read_text(encoding="utf-8"))

    # sondages.json contient déjà les manuels (fusionnés par le collecteur)

    # Tri par terrain_fin décroissant
    sondages.sort(key=lambda s: s["terrain_fin"], reverse=True)

    rows = [
        '<tr><th>Institut</th><th>Date</th>'
        '<th>Échantillon</th><th>Hypothèses</th><th>Source</th></tr>'
    ]
    for s in sondages:
        sid = s.get("id", "")
        institut = html_mod.escape(s["institut"])
        date_str = fmt_date(s["terrain_fin"])
        ech = fmt_ech(s["echantillon"]) if s.get("echantillon") else "\u2014"
        nhyp = len(s.get("hypotheses", []))
        source = (
            f'<a href="{html_mod.escape(s["url_source"])}" target="_blank">Notice</a>'
            if s.get("url_source") else "\u2014"
        )
        inst_link = f'<a href="sondages/{html_mod.escape(sid)}.html">{institut}</a>' if sid else institut
        rows.append(
            f'<tr><td>{inst_link}</td><td>{date_str}</td>'
            f'<td>{ech}</td><td>{nhyp}</td><td>{source}</td></tr>'
        )

    table_html = (
        '  <table class="sondages-table" id="table-sondages">\n'
        + "\n".join(rows) + "\n"
        '  </table>'
    )

    content = SONDAGES_HTML.read_text(encoding="utf-8")
    try:
        i_begin = content.index(BEGIN)
        i_end = content.index(END) + len(END)
    except ValueError:
        raise ValueError(f"Marqueurs {BEGIN} / {END} introuvables dans sondages.html")

    new_content = (
        content[:i_begin] + BEGIN + "\n"
        + table_html + "\n"
        + END + content[i_end:]
    )
    SONDAGES_HTML.write_text(new_content, encoding="utf-8")
    print(f"Table sondages injectée : {len(sondages)} sondages")


if __name__ == "__main__":
    main()
