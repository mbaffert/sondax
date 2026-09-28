#!/usr/bin/env python3
"""Section « Comment fonctionne le modèle Sondax ? » de la page Méthode (§14.19).

Tous les chiffres viennent de data/derived/calibration.json,
data/derived/backtest.json et data/config.json ; aucun n'est écrit ici.
Injecte la section dans site/methodologie.html entre
<!-- BEGIN:methode-modele --> et <!-- END:methode-modele -->, avant </main>.
"""

import html, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CALIBRATION_PATH = ROOT / "data" / "derived" / "calibration.json"
BACKTEST_PATH = ROOT / "data" / "derived" / "backtest.json"
CONFIG_PATH = ROOT / "data" / "config.json"
HISTORIQUE_PATH = ROOT / "data" / "historique.json"
PAGE_PATH = ROOT / "site" / "methodologie.html"

BEGIN, END = "<!-- BEGIN:methode-modele -->", "<!-- END:methode-modele -->"
JEUX = {"presidentielles": "Présidentielles", "europeennes": "Européennes", "ensemble": "Ensemble"}
TRANCHES = {"plus_20": "plus de 20 %", "10_20": "10 à 20 %", "moins_10": "moins de 10 %"}

e = html.escape


def fr(x, d=2):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def entier(n):
    return f"{n:,}".replace(",", " ")


def noms_candidats():
    """Noms des candidats historiques, par élection."""
    try:
        el = json.loads(HISTORIQUE_PATH.read_text())["elections"]
    except FileNotFoundError:
        return {}
    return {a: {c: v["nom"] for c, v in e_["candidats"].items()} for a, e_ in el.items()}


def nom(noms, annee, slug):
    return noms.get(annee, {}).get(slug, slug)


def section(cal, bt, reglages, noms):
    jeux = cal["jeux"]
    ref = jeux.get(reglages["N_eff_source"]) or jeux["presidentielles"]
    pres = jeux["presidentielles"]
    faux = [a for a, ok in pres["qualifies_annonces_justes"].items() if not ok]

    lignes_jeux = "".join(
        f'<tr><td>{JEUX.get(k, k)}</td><td>{", ".join(j["elections"])}</td>'
        f'<td class="n">{j["n_comparaisons"]}</td><td class="n">{fr(j["erreur_absolue_moyenne"])}</td>'
        f'<td class="n">{fr(j["ecart_type"])}</td><td class="n">{fr(j["N_eff"], 0)}</td></tr>'
        for k, j in jeux.items())
    lignes_tranches = "".join(
        f'<tr><td>{TRANCHES[k]}</td><td class="n">{t["n"]}</td>'
        f'<td class="n">{fr(t["erreur_absolue_moyenne"])}</td><td class="n">{fr(t["ecart_type"])}</td></tr>'
        for k, t in pres["par_tranche"].items())
    lignes_erreurs = "".join(
        f'<tr><td>{p["election"]}</td><td>{e(nom(noms, p["election"], p["candidat"]))}</td>'
        f'<td class="n">{fr(p["moyenne"], 1)}</td><td class="n">{fr(p["resultat"], 1)}</td>'
        f'<td class="n">{"+" if p["erreur"] > 0 else "−"}{fr(abs(p["erreur"]), 1)}</td></tr>'
        for p in pres["principales_erreurs"][:6])
    maxi = max(h["n"] for h in pres["histogramme"])
    histo = "".join(
        f'<div class="h" title="{fr(h["de"], 1)} à {fr(h["a"], 1)} point : {h["n"]}">'
        f'<span style="height:{100 * h["n"] / maxi:.0f}%"></span></div>'
        for h in pres["histogramme"])
    h_de, h_a = pres["histogramme"][0]["de"], pres["histogramme"][-1]["a"]

    # Backtest
    runs = bt["runs"]
    lignes_bt = []
    for r in runs:
        for l in r["candidats"][:4]:
            lignes_bt.append(
                f'<tr><td>{r["election"]}</td><td>{e(l["nom"])}</td><td class="n">{fr(l["moyenne"], 1)}</td>'
                f'<td class="n">{fr(l["qualification"], 1)}</td><td class="n">{fr(l["resultat"], 1)}</td>'
                f'<td>{"qualifié" if l["qualifie"] else ""}</td></tr>')
    lignes_duels = "".join(
        f'<tr><td>{r["election"]}</td>'
        f'<td>{" – ".join(e(nom(noms, r["election"], c)) for c in r["duel_principal"]["candidats"])}</td>'
        f'<td class="n">{fr(r["duel_principal"]["chance"], 1)}</td>'
        f'<td>{" – ".join(e(nom(noms, r["election"], c)) for c in r["duel_reel"]["candidats"])}</td>'
        f'<td class="n">{fr(r["duel_reel"]["chance"], 1)}</td></tr>'
        for r in runs)
    fia = bt["fiabilite"]
    lignes_fia = "".join(
        f'<tr><td>{t["de"]} à {t["a"]:.0f}</td><td class="n">{t["n"]}</td>'
        f'<td class="n">{fr(t["annonce"], 1) if t["annonce"] is not None else "—"}</td>'
        f'<td class="n">{fr(t["observe"], 1) if t["observe"] is not None else "—"}</td></tr>'
        for t in fia["table"])

    loi = bt["loi"]
    niv = loi["par_niveau"]
    lignes_loi = "".join(
        f'<tr><td>{TRANCHES[k]}</td><td class="n">{t["n"]}</td><td class="n">{fr(t["ecart_type_observe"])}</td>'
        f'<td class="n">{fr(t["ecart_type_attendu"])}</td><td class="n">{fr(t["rapport_variance"])}</td></tr>'
        for k, t in niv.items() if t["n"])
    q2, q3 = loi["queues"]["au_dela_2_ecarts_types"], loi["queues"]["au_dela_3_ecarts_types"]
    cor = loi["correlations"]
    ratio_10_20 = niv["10_20"]["rapport_variance"]
    ratio_20 = niv["plus_20"]["rapport_variance"]

    tirages = entier(reglages["tirages"])
    return f'''<section id="modele" class="methode-modele">
<h2>Comment fonctionne le modèle Sondax&nbsp;?</h2>

<p>Le modèle Sondax répond à une question&nbsp;: <em>si on votait dimanche</em>, avec les
sondages d'aujourd'hui, qui a réellement ses chances d'être au second tour&nbsp;? Il mesure
la solidité du classement observé aujourd'hui. <strong>Il ne prédit pas le résultat de
l'élection d'avril 2027.</strong></p>

<h3>1. Point de départ</h3>
<p>Le calcul part de la moyenne Sondax du jour, celle de la courbe de tendance décrite plus
haut, pour chaque candidat de la configuration de référence (celle qui contient à la fois
Gabriel Attal et Édouard Philippe&nbsp;; quand les instituts testent plusieurs variantes, la
liste de candidats la plus fréquente sur 30 jours). Ces moyennes sont ramenées à 100&nbsp;%
proportionnellement&nbsp;; la colonne «&nbsp;Autre&nbsp;» n'entre pas dans le calcul. Un
candidat absent de cette configuration n'a pas de chiffre de qualification. Le point de
départ diffère donc de quelques dixièmes de la moyenne affichée sur les courbes.</p>

<h3>2. Les erreurs historiques des sondages</h3>
<p>Pour chaque élection passée, nous comparons la moyenne simple des sondages dont le
terrain s'achève dans les sept jours précédant le scrutin au résultat officiel.
Sur les présidentielles de {pres["elections"][0]} à {pres["elections"][-1]}&nbsp;:
<strong>{pres["n_comparaisons"]} comparaisons</strong>, erreur absolue moyenne de
<strong>{fr(pres["erreur_absolue_moyenne"])} point</strong>, écart-type de
<strong>{fr(pres["ecart_type"])} point</strong>.
{("En " + ", ".join(faux) + ", les deux premiers des sondages n'étaient pas les deux qualifiés ; c'est la seule fois." if len(faux) == 1 else "")}</p>
<table class="mm"><tr><th>Jeu</th><th>Élections</th><th class="n">Comparaisons</th><th class="n">Erreur absolue moyenne</th><th class="n">Écart-type</th><th class="n">N<sub>eff</sub> estimé</th></tr>{lignes_jeux}</table>
<p class="mm-legende">Répartition des erreurs (moyenne des sondages − résultat), par tranche de 0,5 point, de {fr(h_de, 1)} à {fr(h_a, 1)} point&nbsp;:</p>
<div class="mm-histo" aria-hidden="true">{histo}</div>
<table class="mm"><tr><th>Niveau du candidat</th><th class="n">Cas</th><th class="n">Erreur absolue moyenne</th><th class="n">Écart-type</th></tr>{lignes_tranches}</table>
<table class="mm"><tr><th>Élection</th><th>Candidat</th><th class="n">Moyenne</th><th class="n">Résultat</th><th class="n">Erreur</th></tr>{lignes_erreurs}</table>

<h3>3. {tirages} premiers tours</h3>
<p>À partir de la moyenne du jour, nous tirons {tirages} premiers tours selon une loi de
Dirichlet centrée sur les intentions de vote. Cette loi a deux propriétés utiles&nbsp;:
chaque premier tour tiré totalise 100&nbsp;%, et l'ampleur possible de l'erreur dépend du
niveau du candidat (plus large à 25&nbsp;% qu'à 2&nbsp;%). Son paramètre, N<sub>eff</sub>,
règle l'ampleur des erreurs&nbsp;; il est calibré sur les erreurs historiques. La graine du
tirage est fixe&nbsp;: d'un jour à l'autre, les écarts ne viennent que des sondages.</p>

<h3>4. Calibration</h3>
<p>Pour une loi de Dirichlet de paramètre N<sub>eff</sub>·p, la variance de la part d'un
candidat vaut p(1−p)/(N<sub>eff</sub>+1). D'où l'estimateur, par la méthode des
moments&nbsp;: <code>N_eff = Σ p(1−p) / Σ erreur² − 1</code>. Estimation sur le jeu retenu&nbsp;:
{fr(ref["N_eff"], 1)}. <strong>Valeur utilisée&nbsp;: {reglages["N_eff"]}</strong>
(jeu «&nbsp;{JEUX.get(reglages["N_eff_source"], reglages["N_eff_source"])}&nbsp;», arrondie à la
dizaine). L'estimation ne change la valeur utilisée qu'après examen du backtest.</p>

<h3>5. Comptage</h3>
<p>Dans chaque premier tour tiré, les candidats sont classés. Un candidat est qualifié
s'il finit premier ou deuxième&nbsp;; ses chances de qualification sont le nombre de
qualifications divisé par {tirages}. Même comptage pour les rangs et pour les duels
(les deux premiers de chaque tirage). Les chiffres sont arrondis à l'entier&nbsp;; sous 1, nous
écrivons «&nbsp;moins de 1 sur 100&nbsp;», au-dessus de 99, «&nbsp;plus de 99 sur 100&nbsp;».</p>

<h3>6. Point de bascule</h3>
<p>Pour les principaux candidats sous 50 chances sur 100, nous cherchons par dichotomie le
score qui leur donnerait environ une chance sur deux. Le point ajouté au candidat est pris
à tous les autres proportionnellement à leur score, le choix le plus neutre. Le chiffre
publié est arrondi au demi-point et n'est affiché qu'à 4 points ou moins&nbsp;: c'est un
ordre de grandeur.</p>

<h3>7. Backtest&nbsp;: qu'aurait affiché Sondax avant les présidentielles passées&nbsp;?</h3>
<p>Pour chaque présidentielle, nous calibrons N<sub>eff</sub> sur les quatre autres
(<em>leave-one-out</em>), calculons la moyenne Sondax avec les seuls sondages disponibles
{bt["horizon_jours"]} jours avant le scrutin, puis appliquons exactement le moteur actuel.</p>
<table class="mm"><tr><th>Élection</th><th>Candidat</th><th class="n">Moyenne</th><th class="n">Chances de qualification</th><th class="n">Résultat</th><th></th></tr>{"".join(lignes_bt)}</table>
<table class="mm"><tr><th>Élection</th><th>Duel principal Sondax</th><th class="n">Chances</th><th>Duel réel</th><th class="n">Chances du duel réel</th></tr>{lignes_duels}</table>
<p>Fiabilité&nbsp;: dans chaque tranche de chances annoncées, la part de candidats
effectivement qualifiés (score de Brier&nbsp;: {fr(fia["brier"], 3)} sur {fia["n"]} cas).</p>
<table class="mm"><tr><th>Chances annoncées</th><th class="n">Cas</th><th class="n">Moyenne annoncée</th><th class="n">Qualifiés observés (%)</th></tr>{lignes_fia}</table>
<p><strong>Deux réserves.</strong> Cinq élections, c'est peu&nbsp;: toute conclusion reste
prudente. Et l'horizon du backtest (sondages disponibles à J−{bt["horizon_jours"]}) est plus
dur que celui de la calibration (sondages de la dernière semaine), ce qui pénalise un peu le
modèle.</p>

<h3>8. Limites de la loi utilisée</h3>
<p>Nous avons confronté la loi calibrée ({loi["N_eff"]}) aux erreurs historiques. Au global,
l'écart-type observé ({fr(loi["global"]["ecart_type_observe"])}) est celui de la loi
({fr(loi["global"]["ecart_type_attendu"])}). Les grandes erreurs ne sont pas plus
fréquentes que prévu&nbsp;: {q2["observe"]} au-delà de deux écarts-types pour {fr(q2["attendu"], 1)}
attendues, {q3["observe"]} au-delà de trois pour {fr(q3["attendu"], 1)}.</p>
<table class="mm"><tr><th>Niveau du candidat</th><th class="n">Cas</th><th class="n">Écart-type observé</th><th class="n">Écart-type de la loi</th><th class="n">Rapport des variances</th></tr>{lignes_loi}</table>
<p><strong>La loi se trompe selon le niveau du candidat.</strong> Pour les candidats entre 10
et 20&nbsp;%, les erreurs réelles ont été {fr(ratio_10_20, 1)} fois plus dispersées (en
variance) que ce que la loi prévoit&nbsp;; au-dessus de 20&nbsp;%, {fr(ratio_20, 2)} fois
seulement. Le modèle est donc probablement <strong>trop sûr de lui pour les candidats
situés entre 10 et 20&nbsp;%</strong>, souvent ceux qui se disputent la deuxième place,
et trop prudent pour les premiers. Le backtest le montre&nbsp;: les qualifications
surprises de 2002 et la remontée de 2022 y étaient jugées très improbables. Côté
corrélations, la loi n'impose que des corrélations négatives et faibles entre candidats&nbsp;;
sur {cor["paires"]} paires de candidats de tête, {cor["meme_sens"]} erreurs vont dans le même
sens, et la covariance moyenne observée ({fr(cor["covariance_moyenne_observee"])}) est proche
de celle de la loi ({fr(cor["covariance_moyenne_attendue"])}).</p>
<p>Nous documentons ces limites sans complexifier le moteur&nbsp;: modèle simple, backtest,
transparence. Un changement de loi serait une décision explicite, annoncée ici.</p>

<h3>9. Ce que le modèle ne fait pas</h3>
<p>Aucune correction discrétionnaire (biais supposés des petits candidats, dynamique
supposée, biais par institut)&nbsp;; aucune pondération par institut&nbsp;; aucune prévision de
l'évolution des intentions de vote&nbsp;; aucune prise en compte des campagnes, débats,
retraits ou événements futurs. <strong>Le modèle Sondax mesure la solidité du classement
observé aujourd'hui. Il ne prédit pas le résultat de l'élection d'avril 2027.</strong></p>
<p>Historique&nbsp;: les chances publiées sont enregistrées à chaque mise à jour. Les points
antérieurs à la mise en ligne du modèle ont été recalculés après coup, avec les sondages
publiés à chaque date.</p>
</section>
<style>
.methode-modele h2 {{ margin-top: 40px; }}
.methode-modele table.mm {{ margin: 12px 0 18px; font-size: 13.5px; }}
.methode-modele table.mm .n {{ text-align: right; white-space: nowrap; }}
.methode-modele code {{ font-family: var(--mono, monospace); font-size: 13px; background: #F2F3F0; padding: 1px 5px; border-radius: 4px; }}
.methode-modele .mm-legende {{ font-size: 13px; color: var(--gris); margin-bottom: 4px; }}
.methode-modele .mm-histo {{ display: flex; align-items: flex-end; gap: 2px; height: 90px; margin-bottom: 16px; max-width: 520px; }}
.methode-modele .mm-histo .h {{ flex: 1; height: 100%; display: flex; align-items: flex-end; }}
.methode-modele .mm-histo span {{ display: block; width: 100%; background: #0C6CF2; border-radius: 2px 2px 0 0; }}
</style>'''


def main():
    if not CALIBRATION_PATH.exists() or not BACKTEST_PATH.exists():
        sys.exit("build_methode_modele : lancer calibration.py et backtest.py d'abord")
    cal = json.loads(CALIBRATION_PATH.read_text())
    bt = json.loads(BACKTEST_PATH.read_text())
    reglages = json.loads(CONFIG_PATH.read_text())["modele"]
    bloc = section(cal, bt, reglages, noms_candidats())

    contenu = PAGE_PATH.read_text(encoding="utf-8")
    if BEGIN not in contenu:
        i = contenu.index("</main>")
        contenu = contenu[:i] + f"{BEGIN}\n{END}\n" + contenu[i:]
    i, j = contenu.index(BEGIN), contenu.index(END)
    contenu = contenu[:i] + BEGIN + "\n" + bloc + "\n" + contenu[j:]
    PAGE_PATH.write_text(contenu, encoding="utf-8")
    print(f"Section #modele écrite dans {PAGE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
