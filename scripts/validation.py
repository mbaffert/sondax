"""Validation des données collectées (spec §8).

Trois contrôles, tous bloquants :
1. Somme des scores par hypothèse dans [95, 105] (T1) ou [99, 101] (T2).
2. Tous les candidats existent dans candidats.json.
3. Le nombre total de sondages n'a pas diminué par rapport au run précédent.

Produit data/derived/revue.html listant les sondages ajoutés ou modifiés.
"""

import json, sys, pathlib, subprocess, datetime


def fmt_date(iso):
    """'2026-09-03' → '03/09/2026'"""
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATS_PATH = ROOT / "data" / "candidats.json"
SONDAGES_PATH = ROOT / "data" / "sondages.json"
REVUE_PATH = ROOT / "data" / "derived" / "revue.html"
REVUE_MD_PATH = ROOT / "data" / "derived" / "revue.md"


def load_previous_sondages():
    """Charge sondages.json depuis le dernier commit git (HEAD)."""
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:data/sondages.json"],
            cwd=ROOT, stderr=subprocess.DEVNULL
        )
        return json.loads(raw)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def validate(sondages, candidats):
    """Exécute les trois contrôles. Retourne (ok, erreurs)."""
    errors = []
    candidat_ids = set(candidats.keys())

    # Contrôle 1 : sommes des scores
    for s in sondages:
        for i, h in enumerate(s["hypotheses"]):
            total = sum(h["scores"].values())
            lo, hi = (95, 105) if h["tour"] == 1 else (99, 101)
            if not lo <= total <= hi:
                errors.append(
                    f"[somme] {s['id']} hypothèse {i+1} T{h['tour']} : "
                    f"somme={total:.1f} hors [{lo}, {hi}]"
                )

    # Contrôle 2 : candidats connus
    unknown = set()
    for s in sondages:
        for h in s["hypotheses"]:
            for cid in h["scores"]:
                if cid not in candidat_ids:
                    unknown.add(cid)
    if unknown:
        errors.append(f"[candidats] inconnus du référentiel : {sorted(unknown)}")

    # Contrôle 3 : pas de régression du nombre de sondages
    previous = load_previous_sondages()
    if previous and len(sondages) < len(previous):
        errors.append(
            f"[régression] {len(sondages)} sondages contre {len(previous)} au run précédent"
        )

    return len(errors) == 0, errors


def diff_sondages(sondages, previous):
    """Identifie les sondages ajoutés ou modifiés par rapport au run précédent."""
    prev_by_id = {s["id"]: s for s in previous}
    added, modified = [], []
    for s in sondages:
        if s["id"] not in prev_by_id:
            added.append(s)
        elif s != prev_by_id[s["id"]]:
            modified.append(s)
    return added, modified


def _somme_class(total, tour):
    """Classe CSS pour la colonne Somme selon l'écart à 100."""
    lo, hi = (95, 105) if tour == 1 else (99, 101)
    if not lo <= total <= hi:
        return "somme-rouge"
    warn_lo, warn_hi = (98, 102) if tour == 1 else (99.5, 100.5)
    if total < warn_lo or total > warn_hi:
        return "somme-orange"
    return ""


def generate_revue(sondages, candidats, added, modified):
    """Génère data/derived/revue.html."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    blocks = []
    for label, group in [("Ajouté", added), ("Modifié", modified)]:
        for s in group:
            ech = int(s["echantillon"]) if s.get("echantillon") else "—"
            source = ""
            if s.get("url_source"):
                source = f'<a href="{s["url_source"]}">notice</a>'

            nhyp = len(s["hypotheses"])
            blocks.append(
                f'<tr class="sondage-header">'
                f'<td rowspan="{nhyp + 1}">{label}</td>'
                f"<td colspan=\"4\"><strong>{s['institut']}</strong> — "
                f"{fmt_date(s['terrain_fin'])} — "
                f"n = {ech} — {source}</td>"
                f"</tr>"
            )
            for i, h in enumerate(s["hypotheses"]):
                total = sum(h["scores"].values())
                cls = _somme_class(total, h["tour"])
                td_cls = f' class="{cls}"' if cls else ""
                blocks.append(
                    f"<tr>"
                    f"<td>T{h['tour']} hyp.{i+1}</td>"
                    f"<td>{len(h['scores'])} candidats</td>"
                    f"<td{td_cls}>{total:.1f}</td>"
                    f"<td>{', '.join(sorted(h['scores'].keys()))}</td>"
                    f"</tr>"
                )

    if not blocks:
        print("Rien de neuf, pas de page de revue.")
        return

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Sondax — revue du {now}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; font-size: 0.9em; }}
  th {{ background: #f5f5f5; }}
  tr.sondage-header td {{ background: #f9f9f9; }}
  .somme-orange {{ background: #fff3cd; font-weight: bold; }}
  .somme-rouge {{ background: #f8d7da; font-weight: bold; }}
  .meta {{ color: #666; margin-bottom: 1em; }}
  a {{ color: #0066cc; }}
</style>
</head>
<body>
<h1>Revue de collecte</h1>
<p class="meta">{now} — {len(added)} ajouté(s), {len(modified)} modifié(s)</p>
<table>
<tr>
  <th>Statut</th><th>Hypothèse</th><th>Candidats</th>
  <th>Somme</th><th>Détail</th>
</tr>
{"".join(blocks)}
</table>
</body>
</html>
"""
    REVUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVUE_PATH.write_text(html, encoding="utf-8")
    print(f"Page de revue : {REVUE_PATH}")

    # Markdown pour le corps de la PR
    md = generate_revue_markdown(added, modified)
    REVUE_MD_PATH.write_text(md, encoding="utf-8")
    print(f"Revue markdown : {REVUE_MD_PATH}")


def _somme_flag(total, tour):
    """Marqueur pour le markdown : ⚠️ si orange, 🔴 si rouge."""
    lo, hi = (95, 105) if tour == 1 else (99, 101)
    if not lo <= total <= hi:
        return " **HORS BORNES**"
    warn_lo, warn_hi = (98, 102) if tour == 1 else (99.5, 100.5)
    if total < warn_lo or total > warn_hi:
        return " ⚠"
    return ""


def generate_revue_markdown(added, modified):
    """Génère le résumé markdown de la revue pour le corps de la PR."""
    lines = ["## Revue de collecte\n"]

    for label, group in [("Ajouté", added), ("Modifié", modified)]:
        if not group:
            continue
        lines.append(f"### {label}s ({len(group)})\n")
        lines.append("| Institut | Date | Éch. | Hyp. | Cands | Somme |")
        lines.append("|----------|------|------|------|-------|-------|")
        for s in group:
            ech = str(int(s["echantillon"])) if s.get("echantillon") else "—"
            date = fmt_date(s["terrain_fin"])
            for i, h in enumerate(s["hypotheses"]):
                total = sum(h["scores"].values())
                flag = _somme_flag(total, h["tour"])
                inst = s["institut"] if i == 0 else ""
                d = date if i == 0 else ""
                e = ech if i == 0 else ""
                lines.append(
                    f"| {inst} | {d} | {e} | T{h['tour']} hyp.{i+1} "
                    f"| {len(h['scores'])} | {total:.1f}{flag} |"
                )
        lines.append("")

    if not added and not modified:
        lines.append("Rien de neuf.\n")

    return "\n".join(lines)


def main():
    candidats = json.loads(CANDIDATS_PATH.read_text())
    sondages = json.loads(SONDAGES_PATH.read_text())

    ok, errors = validate(sondages, candidats)

    if not ok:
        print("VALIDATION ÉCHOUÉE :", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    nh = sum(len(s["hypotheses"]) for s in sondages)
    print(f"Validation OK : {len(sondages)} sondages, {nh} hypothèses")

    previous = load_previous_sondages()
    added, modified = diff_sondages(sondages, previous)
    print(f"  {len(added)} ajouté(s), {len(modified)} modifié(s)")

    generate_revue(sondages, candidats, added, modified)


if __name__ == "__main__":
    main()
