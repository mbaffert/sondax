# Sondax — spécification

Agrégateur public des données quantitatives sur l'élection présidentielle française de 2027 :
sondages d'opinion et probabilités implicites issues des marchés de prédiction.

Ce fichier fait autorité. En cas de doute sur une structure de données ou une règle de
méthode, s'y référer plutôt que d'improviser. Toute évolution des règles ci-dessous se
décide explicitement et se répercute ici.

---

## 1. Périmètre v1

Une page d'accueil à sections nommées et ancrées :

1. **Bandeau d'en-tête.** Dernier sondage, compte à rebours, navigation (voir
   `scripts/build_header.py`).
2. **Sondages du premier tour** (`#bloc-sondages`). Titre : « Sondages du premier
   tour de la présidentielle 2027 ». Chapeau généré au build (leader, volume,
   delta 3 mois), bloc « Dernier sondage publié » (`#dernier-sondage`) avec
   l'hypothèse sélectionnée, courbe de tendance par candidat, tableau des derniers
   sondages agrégés. Généré par `scripts/build_index_premier_tour.py`.
   En cas d'égalité de `terrain_fin`, le sondage avec le plus grand échantillon
   est retenu.
3. **Second tour** (`#second-tour`). Repères factuels, chapeau généré au build,
   tableau de tous les duels mesurés, sélecteur de détail par duel (voir §7).
4. **Cotes des marchés de prédiction** (`#bloc-polymarket`). Évolution des
   probabilités implicites par candidat, deux onglets : accession au second tour
   et victoire. Les titres ne nomment pas Polymarket, la source est citée dans
   le corps du bloc et en pied de page.
5. **Fiche technique.** Sélection d'une configuration puis d'un sondage, et affichage
   de ses caractéristiques et de ses marges d'erreur (voir §5).

**Contrainte générale de rendu** : tout le contenu textuel des sections est rendu au
build et présent dans le HTML servi par le serveur. Le JavaScript ne sert qu'à
l'interaction (sélecteurs, graphiques, onglets).

**Hors périmètre v1**, à ne pas implémenter sans décision explicite : correction des
*house effects*, base de données, comptes utilisateurs, back-office d'édition,
intentions de vote par catégorie sociologique, sondages autres que présidentiels.

Décision prise : pas de back-office. La validation se fait par page de revue statique
et pull request (§8). À réexaminer seulement si la validation doit être déléguée à
quelqu'un d'autre que l'auteur.

---

## 2. Sources

### 2.1 Sondages — Wikipédia

Page : `Liste de sondages sur l'élection présidentielle française de 2027` (fr.wikipedia.org).

Accès par l'API MediaWiki, en récupérant le **wikitexte**, jamais le HTML rendu :

```
GET https://fr.wikipedia.org/w/api.php
    ?action=parse&page=Liste_de_sondages_sur_l'élection_présidentielle_française_de_2027
    &prop=wikitext|revid&format=json
```

Le `revid` de chaque extraction est conservé.

Licence CC BY-SA : attribution obligatoire et partage à l'identique. Le site affiche en
pied de page un lien vers la page source et la mention de licence.

### 2.2 Cotes — Polymarket

Deux API publiques, sans authentification. Deux événements suivis :

| Clé | Slug | Event id | Objet |
|-----|------|----------|-------|
| `victoire` | `next-french-presidential-election` | 79987 | Probabilité de remporter l'élection |
| `second_tour` | `next-french-presidential-election-who-will-advance-to-the-2nd-round` | 531333 | Probabilité d'accéder au second tour (deux places, somme ~200 %) |

Découverte des marchés :

```
GET https://gamma-api.polymarket.com/events?slug={event_slug}
```

Chaque événement contient un marché binaire par candidat. Pour chaque marché :
`conditionId`, `outcomePrices`, et `clobTokenIds` dont le **premier élément est le
token « Yes »**.

Historique quotidien :

```
GET https://clob.polymarket.com/prices-history?market={token_yes}&interval=max&fidelity=1440
```

Retourne `{"history": [{"t": unix_ts, "p": prix}, ...]}`. La série victoire remonte
à novembre 2025, celle du second tour à juin 2026.

Le mapping vers le référentiel candidats se fait sur le **`conditionId` du marché**,
stable et unique par construction. Le `conditionId` est renseigné à la main dans
`candidats.json`, jamais déduit automatiquement (les slugs Polymarket contiennent des
accents corrompus, cf. §11).

---

## 3. Modèle de données

Trois fichiers dans `/data` pour 2027, plus `historique.json` pour les élections
2002-2022 (§12). Les snapshots de wikitexte vont dans `/data/snapshots`
et ne sont jamais modifiés.

### 3.1 `candidats.json` — référentiel, édité à la main

```json
{
  "le-pen": {
    "nom": "Marine Le Pen",
    "parti": "RN",
    "type": "personne",
    "couleur": "#0D378A",
    "alias_wikipedia": ["Le Pen", "Marine Le Pen"],
    "condition_polymarket": {
      "victoire": "0x8126317d621047fb13d508a2651eecc8d38305904671822a62309c5aabd353aa",
      "second_tour": "0x4de07f3b6b1220c2406e5807d30588fc6cbd5b938310835524106d05d20a9b4a"
    }
  },
  "candidat-ps": {
    "nom": "Candidat PS",
    "parti": "PS",
    "type": "parti",
    "couleur": "#FF8080",
    "alias_wikipedia": ["Candidat PS"],
    "condition_polymarket": {
      "victoire": null,
      "second_tour": null
    }
  }
}
```

`condition_polymarket` : renseigné à la main, jamais déduit automatiquement. Un candidat
sans marché sur un événement a `null` pour cette clé — ce n'est pas une erreur bloquante.

`declare_le` : date ISO (`"2026-06-12"`) à laquelle le candidat s'est officiellement
déclaré, ou `null` s'il ne l'est pas (encore). Renseigné à la main. Un candidat compte
comme déclaré **pour un sondage donné** si `declare_le` est non nul et antérieur ou égal
au `terrain_fin` du sondage. Ce champ sert au bandeau d'en-tête (§4) et non aux courbes
de tendance.

Aucune création automatique d'entrée : un candidat inconnu fait échouer le run (§8).

Les identifiants sont des **slugs simples** (`le-pen`, `attal`). En cas d'homonymie
future, l'entrée est désambiguïsée à la main (`le-pen-marine`) et l'ancien alias reste
dans `alias_wikipedia`.

**Résolution des noms.** Le parser lit un nom court dans le wikitexte et ne l'écrit
jamais tel quel : il le résout via `alias_wikipedia` vers un identifiant du référentiel.
Un nom sans correspondance est une erreur bloquante (§8, règle 2), jamais une entrée
créée à la volée.

`prenom` : prénom usuel du candidat, utilisé pour construire le nom complet
(`prenom` + ` ` + `nom`) dans le bandeau d'en-tête. Vide pour les entrées
`type: parti`.

**`type`** est obligatoire sur chaque entrée et vaut `personne` par défaut, ou `parti` lorsque le sondage teste un candidat non
désigné (« Candidat PS », « Candidat LR »). Ces entrées sont des candidats comme les
autres pour le parser, la validation et les fiches techniques : aucune exception ne doit
se propager dans le code. Seul l'affichage les distingue (voir §4).

### 3.2 `sondages.json`

```json
[
  {
    "id": "ifop-2026-09-03",
    "institut": "Ifop",
    "terrain_debut": "2026-09-01",
    "terrain_fin": "2026-09-03",
    "echantillon": 1512,
    "population": "certains_daller_voter",
    "url_source": "https://...",
    "revid": 219847362,
    "hypotheses": [
      {
        "tour": 1,
        "libelle": "Attal / Le Pen / Glucksmann",
        "echantillon": 1204,
        "principale": true,
        "scores": {
          "le-pen-marine": 33.5,
          "attal-gabriel": 21.0,
          "glucksmann-raphael": 14.5
        }
      },
      {
        "tour": 2,
        "libelle": "Le Pen / Attal",
        "echantillon": null,
        "principale": false,
        "scores": { "le-pen-marine": 52.0, "attal-gabriel": 48.0 }
      }
    ]
  }
]
```

Règles :

- `id` déterministe : `slug(institut)-terrain_fin`. Le commanditaire n'est pas une
  colonne de la page et n'est pas collecté. Une collision d'identifiant (même institut,
  même date de fin) est une erreur bloquante, jamais un écrasement silencieux.
- Un candidat **absent d'une hypothèse est absent de `scores`**. Ne jamais écrire `0`.
- `echantillon` au niveau de l'hypothèse est la base de calcul réelle de la marge
  d'erreur ; il vaut `null` s'il n'est pas publié, et on retombe alors sur l'échantillon
  total en le signalant à l'affichage.
- Les scores restent **par hypothèse**, jamais aplatis en une valeur par candidat.

### 3.3 `sondages_manuels.json` — saisie manuelle, édité à la main

Tout sondage d'intentions de vote ayant fait l'objet d'un dépôt de notice auprès
de la commission des sondages et absent du wikitexte peut être saisi manuellement
dans ce fichier.

Le schéma est identique à celui de `sondages.json`, avec trois champs
supplémentaires :

- `source`: `"manuel"` (obligatoire).
- `url_notice`: URL de la notice de la commission des sondages (obligatoire).
- `saisi_le`: date de saisie au format ISO (obligatoire).
- `revid`: toujours `null`.

Le pipeline concatène ce fichier à la liste issue du wikitexte **avant** la
validation. Tous les contrôles du §8 s'appliquent à l'identique.

En cas de collision d'identifiant avec une entrée issue du wikitexte, le run
échoue avec un message indiquant que le sondage est désormais présent sur
Wikipédia et que l'entrée manuelle doit être supprimée. Jamais d'écrasement
silencieux (§3.2).

### 3.4 `polymarket.json`

```json
{
  "maj": "2026-09-07T18:00:00Z",
  "marches": {
    "second_tour": {
      "event_slug": "next-french-presidential-election-who-will-advance-to-the-2nd-round",
      "candidats": {
        "le-pen": {
          "market_id": "2371045",
          "token_yes": "68877280424127404550238129876288207007515294835359870585560693961915529618517",
          "prix_actuel": 0.885,
          "historique": [{ "d": "2026-06-01", "p": 0.82 }]
        }
      }
    },
    "victoire": {
      "event_slug": "next-french-presidential-election",
      "candidats": {
        "le-pen": {
          "market_id": "679018",
          "token_yes": "55764212211467781322980371912612507865974994976253196346176314491480419639168",
          "prix_actuel": 0.355,
          "historique": [{ "d": "2026-09-06", "p": 0.352 }]
        }
      }
    }
  }
}
```

---

## 4. Traitement des sondages

**Sélection de l'hypothèse (tour 1) — par candidat, pas par sondage.** Pour chaque
candidat et chaque sondage, la sélection suit deux niveaux :

1. **Configuration de référence.** Parmi les hypothèses T1 contenant le candidat, on
   privilégie celles qui contiennent à la fois Attal **et** Philippe — c'est-à-dire le
   bloc central au complet. Quand elles existent, elles seules sont considérées.
2. **Fallback.** Si aucune hypothèse de référence n'existe pour ce sondage (cas des
   sondages antérieurs à mai 2026, ou des instituts qui ne testent pas les deux), on
   retient les hypothèses comptant **le plus de candidats testés**.

En cas d'égalité dans l'un ou l'autre niveau, on **moyenne les hypothèses ex æquo**.

**Motivation.** Le score d'un candidat du centre (Attal, Philippe, Glucksmann) dépend
fortement de la présence de l'autre dans l'hypothèse. Sur les données de 2026, Attal
passe de 8 % avec Philippe à 14 % sans lui — même sondage, même jour. La règle « max
de candidats » alternait entre les deux valeurs au gré des configurations disponibles,
produisant un bimodal artificiel. La configuration de référence stabilise les courbes
en mesurant toujours la même chose : le bloc central au complet.

Conséquence à assumer et à afficher sur le site : **les courbes ne s'additionnent pas à
100 %**, chaque candidat étant mesuré dans la configuration qui reflète le mieux la
concurrence réelle. Le graphe montre des trajectoires individuelles, pas une
répartition. Les courbes de tendance n'utilisent que les hypothèses sélectionnées ;
les autres restent accessibles dans le bloc fiche technique.

La règle ne s'applique pas au tour 2 : tous les duels sont également valides.

**Sélection de l'hypothèse pour le bandeau d'en-tête.** Le bandeau affiche un seul
sondage (le plus récent par `terrain_fin`) et une seule hypothèse de tour 1 de ce
sondage. La règle de sélection est différente de celle des courbes :

1. Parmi les hypothèses T1 du sondage, retenir celle qui contient le plus de
   **candidats officiellement déclarés** — c'est-à-dire ceux dont `declare_le` est
   non nul et ≤ `terrain_fin` du sondage.
2. En cas d'égalité, retenir l'hypothèse dont `echantillon` (au niveau hypothèse) est
   le plus grand ; si nul, considérer l'échantillon du sondage.
3. En cas d'égalité persistante, retenir la première dans l'ordre du fichier.

Tant que tous les `declare_le` sont `null`, la règle dégénère en « hypothèse avec le
plus de candidats testés, puis échantillon le plus grand » — équivalent au fallback des
courbes, et le résultat est cohérent.

Le libellé de l'hypothèse choisie apparaît dans le `<h2>` du bandeau sous la forme :
« Ifop · terrain 3 septembre 2026 · hyp. Attal / Le Pen / Glucksmann ».

**Courbe de tendance.**

- **Fenêtre glissante extensible.** La fenêtre de base est de **30 jours**. Si un
  candidat y est testé dans moins de **3 sondages**, la fenêtre s'étend vers le passé
  jusqu'à en trouver 3, avec une **borne à 90 jours**. Au-delà de 90 jours sans
  3 sondages, la courbe s'interrompt (`v = null`). L'extension se calcule **par
  candidat** : un candidat testé partout garde 30 jours, un candidat rarement testé
  voit sa fenêtre s'étendre. La demi-vie (ci-dessous) reste calculée globalement sur
  la fenêtre fixe de 30 jours — seule la sélection des sondages est étendue.
- Pondération de chaque sondage par sa seule récence : `poids = 2^(-age_jours / T)`,
  où `age_jours` est l'écart entre `terrain_fin` et la date du point calculé et `T` la
  demi-vie retenue pour ce point.
- **Demi-vie adaptative.** `T` est la plus courte valeur parmi 4, 7 et 14 jours pour
  laquelle le nombre effectif de sondages atteint 4. À défaut, `T = 14`. Le nombre
  effectif se calcule par la formule de Kish, `(Σw)² / Σw²`, qui mesure combien de
  sondages de poids égal produiraient la même précision.

  La fréquence des sondages va fortement augmenter d'ici avril 2027. Une demi-vie fixe
  calibrée sur un sondage par semaine deviendrait trop lente et lisserait des mouvements
  réels. La règle adaptative resserre la courbe à mesure que les données arrivent, sans
  intervention et sans changement de code. Sur les données de septembre 2026, elle
  retient 14 jours ; elle basculera d'elle-même vers 7 puis 4.

  La demi-vie effectivement utilisée à chaque date est conservée dans `/data/derived` et
  affichable, pour que la courbe reste explicable.
- **Pas de pondération par taille d'échantillon** : les instituts français interrogent
  tous entre 1 000 et 1 800 personnes, l'effet serait négligeable pour un paramètre de
  plus à expliquer et à défendre. L'échantillon reste affiché sur chaque fiche et sert
  au calcul des marges d'erreur, mais n'entre pas dans la courbe.

La décroissance temporelle a une raison précise : sans elle, un sondage compte à plein
le trentième jour puis disparaît le trente-et-unième, et la courbe saute alors qu'aucune
donnée nouvelle n'est arrivée. Avec la demi-vie, il ne pèse presque plus rien au moment
où il sort de la fenêtre, et sa sortie ne se voit pas.
- Un sondage compte pour **une seule valeur**, quel que soit son nombre d'hypothèses.
- Les **points bruts sont toujours affichés** derrière la courbe.
- **Aucune interpolation.** Un segment reposant sur un seul sondage est tracé en
  pointillé ; sans aucun sondage dans la fenêtre, la courbe s'interrompt.

  Le seuil était initialement fixé à deux sondages. Avec la fréquence réelle de 2026 —
  23 semaines sans aucun sondage sur 36 — il produisait une courbe absente les deux tiers
  du temps. Une valeur fragile signalée comme telle informe davantage qu'un trou.

**Période affichée.** L'utilisateur choisit la date de début de la courbe, par raccourcis
(3 mois, 6 mois, depuis le 1er janvier, tout) ou par date libre. **Le site ouvre sur
6 mois par défaut** : c'est la période la mieux fournie en sondages, et le réglage reste
pertinent à mesure que leur fréquence augmente, contrairement à une date fixe.

La collecte, elle, n'est jamais limitée dans le temps : le parser conserve tous les
sondages de la page, y compris antérieurs à la période affichée par défaut.

La date de début est un **filtre d'affichage, jamais un filtre de calcul** : la fenêtre
glissante continue d'utiliser les sondages antérieurs à la date choisie. Sans cela, les
premiers points reposent sur une fenêtre incomplète et la courbe démarre par un
soubresaut artificiel qui se résorbe au bout de 30 jours.

Un candidat dont la première mesure est postérieure à la date choisie voit sa courbe
commencer à cette première mesure, et non à la borne gauche du graphe.

Le bloc Polymarket dispose de **son propre sélecteur de période, indépendant** de celui
des sondages. Il conserve sa valeur quand on change d'onglet.

**Affichage du bloc Polymarket :**

- Surtitre : MARCHÉS DE PRÉDICTION.
- Titre variable selon l'onglet actif :
  - Second tour : « Qui va accéder au second tour d'après les parieurs de Polymarket ? »
  - Victoire : « Qui va gagner la présidentielle d'après les parieurs de Polymarket ? »
- Onglets : Second tour · Victoire (même composant que les onglets sondages).
- Sous-titre sur l'onglet second tour uniquement : « Deux places, le total avoisine
  200 %. » Rien sur l'onglet victoire.
- Un seul graphe affiché à la fois. Chaque série démarre à sa première mesure :
  l'historique du second tour ne remonte qu'à juin 2026, celui de la victoire à
  novembre 2025. Filtre d'affichage inchangé (probabilité > 1 % ou volume minimum).

**Candidats non désignés.** Une entrée de `type: parti` s'affiche en pointillé, avec son
libellé explicite (« Candidat PS »). Sa série n'est **jamais recollée automatiquement**
à celle du candidat réel une fois la désignation intervenue : un score obtenu par un
candidat anonyme et un score obtenu par une personne identifiée ne mesurent pas la même
chose, et l'écart entre les deux est en soi une information. Les deux séries restent
distinctes, avec un repère vertical à la date de désignation.

Un raccord visuel explicite reste possible en v2 via un champ optionnel
(`"succede_a": "candidat-ps", "depuis": "2026-11-15"`), à traiter comme un choix
éditorial assumé et non comme un effet de bord du modèle. Hors périmètre v1.

**Marge d'erreur.** Calculée sur l'échantillon de l'hypothèse. Signalée comme
approximative lorsqu'elle est calculée sur l'échantillon total faute de mieux.

---

## 5. Sélection d'une configuration (bloc fiche technique)

Une hypothèse n'a pas de nom sur Wikipédia : elle n'existe que comme un ensemble de
candidats testés. Sur les données de 2026, 106 hypothèses de premier tour donnent
48 configurations distinctes, dont 27 testées une seule fois. Un menu listant les
configurations est donc inutilisable.

**Sélection par pivots.** La quasi-totalité des candidats est présente dans toutes les
hypothèses ; la variation tient à un petit nombre de candidats pivots. Sur septembre
2026 : le candidat RN (Le Pen ou Bardella, jamais les deux), le ou les candidats du
bloc central (Philippe, Attal, Villepin, seuls ou combinés), le candidat de la gauche
non insoumise (Glucksmann, Hollande, Faure, Ruffin).

L'interface propose donc **un menu par axe de variation**, pas un menu de configurations.
À chaque sélection, le nombre de sondages correspondants est affiché et les options sans
donnée sont désactivées plutôt que de mener à un résultat vide.

**Les pivots sont calculés, jamais écrits en dur** : est pivot un candidat présent dans
plus de 10 % et moins de 90 % des hypothèses de la période considérée. Les axes évolueront
à mesure que les candidatures se figent, et le calcul doit suivre sans modification du code.

**L'institut est un filtre secondaire**, appliqué après la configuration. Il discrimine
peu (22 sondages pour six à sept instituts) là où la configuration discrimine beaucoup.

Une fois la configuration choisie, les sondages correspondants sont listés par date
décroissante. La sélection d'un sondage affiche sa fiche : institut, dates de terrain,
échantillon, scores, marges d'erreur, lien vers la source.

---

## 6. Retrait, désignation, entrée en lice

Wikipédia n'annonce pas les retraits : un candidat qui se retire cesse simplement
d'apparaître dans les hypothèses. Rien ne le distingue, dans les données, d'un candidat
que les instituts ont cessé de tester. La distinction est éditoriale et se déclare à la
main dans `candidats.json` :

```json
"villepin": { "retrait": { "date": "2026-11-20", "motif": "renoncement annoncé" } }
```

Conséquences, toutes obligatoires :

- **La série s'arrête à la dernière mesure**, pas trente jours plus tard. Sans cette
  règle, la fenêtre glissante fait survivre le candidat un mois de plus en décroissance
  progressive, ce qui est un artefact de calcul et non une mesure.
- **Un repère vertical** marque la date, comme pour une désignation (§4). Un retrait
  redistribue les intentions de vote : les décrochages simultanés sur les autres courbes
  s'expliquent par lui, et doivent être explicables au lecteur.
- **Le candidat disparaît des menus de sélection par défaut** mais reste accessible dès
  que la période affichée couvre ses mesures. Il n'est jamais supprimé du référentiel ni
  des données historiques.
- **Le calcul des pivots exclut les candidats retirés** pour la période courante, faute
  de quoi les menus proposent durablement des options mortes.
- **Côté Polymarket**, le marché correspondant se résout ou se ferme. La série de cotes
  s'arrête à la même date et n'est pas prolongée.

Le cas symétrique — un candidat qui entre en lice en cours de route — ne demande rien de
particulier : sa courbe commence à sa première mesure (§4).

---

## 7. Second tour

Un duel est une hypothèse avec `tour: 2` et exactement deux candidats.

**En dessous de 5 mesures pour un duel donné, afficher un tableau des sondages, pas une
courbe.** Trois points sur dix mois ne constituent pas une tendance.

### 7.0 Section second tour sur la page d'accueil

Section ancrée `id="second-tour"`, placée entre le bloc de tendance du premier tour et
le bloc Polymarket. Composant autonome, réutilisable tel quel sur une page `/second-tour/`
le jour venu.

**Contrainte impérative** : tout le contenu de la section est rendu au build et présent
dans le HTML servi. Le JavaScript ne sert qu'à l'interaction (sélecteur de duel).

**Contenu, dans l'ordre :**

1. **Repères factuels.** Deux phrases en dur : dates attendues des deux tours et règle
   de qualification. Les dates viennent de `data/config.json` ; un booléen `officielles`
   contrôle la formulation (conditionnel ou affirmatif). Balisage `schema.org` de type
   `Event` en JSON-LD.

2. **Chapeau généré au build.** Deux ou trois phrases composées à partir des données :
   nombre de duels et de sondages, leader avec dénominateur explicite (nombre de duels
   où le candidat est testé, pas le total), duel le plus serré, éventuelle inversion
   de sens. Texte grammatical quel que soit l'état (0, 1 ou N duels), avec accord en
   genre (`genre` dans `candidats.json`). Généré par `scripts/build_index_second_tour.py`.

3. **Tableau général des duels.** Le duel le plus récemment mesuré est affiché en
   aperçu ; les autres sont repliés dans un `<details>` / `<summary>` natif (pas de
   JavaScript), avec un libellé portant le nombre de duels restants.

   Six colonnes : En tête | Score | Face à | Score | Sondages | Dernière mesure.
   Noms alignés à gauche, scores alignés à droite en chiffres tabulaires
   (`font-variant-numeric: tabular-nums`), colonnes de score étroites et de largeur
   fixe identique. Les deux en-têtes « Score » portent un `aria-label` distinct pour
   les lecteurs d'écran. L'ordre des noms suit le résultat de la dernière mesure
   (vainqueur en premier), pas la clé interne de regroupement. En cas d'égalité
   parfaite, l'ordre de la clé est conservé. En mobile, défilement horizontal du
   tableau.

   Tri : date de dernière mesure décroissante, puis nombre de sondages décroissant, puis
   clé interne (tri stable).

4. **Sélecteur de détail par duel.** Deux menus déroulants, hydratés par JavaScript.
   Affiche le détail du duel choisi : tableau des sondages (< 5 sondages) ou courbe
   (≥ 5 sondages). Sans JavaScript, le tableau général reste entièrement lisible.

**Sortie ultérieure en page dédiée** : lorsqu'un duel atteint le seuil de la courbe ou
que les volumes de recherche le justifient, le composant pourra être extrait en page
`/second-tour/`. Hors périmètre actuel.

### 7.1 Pages dédiées par duel

Les duels ne vivent pas uniquement dans le sélecteur JS de la page principale : chaque
duel ayant au moins 5 mesures dispose d'une **page statique dédiée**, indexable par les
moteurs de recherche. La recherche se formule par duel (« sondages second tour Le Pen
Philippe ») et doit trouver une page.

**Slug canonique** : les deux clés candidat triées par ordre alphabétique, jointes par
un tiret (ex. `le-pen-philippe`). L'URL canonique est `/second-tour/le-pen-philippe`.

**Redirection** : l'ordre inverse du slug (`philippe-le-pen`) sert une redirection
HTML (`<meta http-equiv="refresh">`) vers l'URL canonique, jamais un duplicat indexable.

**Page d'entrée** : `site/second-tour/index.html` liste **tous** les duels testés.
Ceux au-dessus du seuil de 5 mesures sont des liens vers leur page dédiée ; ceux en
dessous apparaissent sous forme de tableau des sondages directement dans la page d'entrée.

**Contenu d'une page de duel** :
- `<title>` et `<meta name="description">` propres et distincts par duel.
- `<link rel="canonical">` vers l'URL canonique.
- `<h1>` : « Sondages second tour 2027 : Le Pen – Philippe ».
- Courbe (même rendu que le sélecteur actuel) + tableau des sondages (institut, dates
  de terrain, échantillon, scores, lien vers la notice).
- Même header, footer et mentions de licence que les pages existantes.

**Génération** : `scripts/pages_second_tour.py` lit `data/sondages.json` et
`data/candidats.json`, écrit dans `site/second-tour/` (répertoire entièrement
reconstructible, ajouté au `.gitignore`). Le script génère aussi `site/sitemap.xml`.

**Navigation** : le sélecteur de duel de `site/index.html` pointe vers les pages
dédiées, et le header gagne un lien « Second tour ».

---

## 7.2 Contraintes SEO et techniques

Toute page publiée porte :

- un `<h1>` unique, un `<title>` et une meta description propres ;
- les balises Open Graph (`og:title`, `og:description`, `og:image`, `og:url`) et
  `twitter:card` pour l'aperçu lors du partage ;
- un contenu statique (HTML servi, pas construit en JavaScript) suffisant pour
  l'indexation.

`robots.txt` et `sitemap.xml` font partie de la sortie du build. Le `sitemap.xml`
est généré par `scripts/pages_second_tour.py`.

Les pages des élections passées (2002-2022) portent un chapeau rendu au build
(`scripts/build_elections_chapeaux.py`) et la page `sondages.html` contient le
tableau complet des sondages en HTML statique (`scripts/build_sondages_page.py`).

---

## 8. Validation

Le script de collecte **ne commite rien** si un contrôle échoue. Il s'arrête et signale.

1. La somme des scores d'une hypothèse, **colonne « Autre » incluse**, est comprise
   entre 95 et 105 au tour 1, entre 99 et 101 au tour 2. « Autre » entre dans le
   contrôle mais reste exclu des courbes et des fiches candidat.
2. Tous les candidats rencontrés existent dans `candidats.json`.
3. Le nombre total de sondages n'a pas diminué par rapport au run précédent.
4. Aucun `conditionId` de `candidats.json` n'apparaît deux fois, et chaque
   `conditionId` renseigné existe dans l'événement correspondant côté API Polymarket.
5. **Non bloquant**, signalé sur la page de revue uniquement : pour un même candidat,
   P(victoire) ≤ P(second tour). Violation fréquente sur les marchés à faible volume
   (inefficience de marché, pas erreur de collecte).

**Corrections.** Une valeur modifiée sur Wikipédia écrase la valeur existante. Les
snapshots de wikitexte permettent de retrouver l'origine si nécessaire.

**Circuit.** Le cron quotidien (GitHub Actions) exécute le script et ouvre une **pull
request** avec les données mises à jour. Aucun commit direct sur la branche principale.
La PR est relue et fusionnée à la main.

**Page de revue.** Chaque run produit `/data/derived/revue.html`, page statique jointe à
la PR, listant les sondages ajoutés ou modifiés : institut, dates, échantillon, une ligne
par hypothèse avec sa somme, lien vers la notice de la commission des sondages. Toute
valeur en anomalie est surlignée.

**Notification.** Un mail est envoyé à chaque run, quel que soit le résultat :
nombre de sondages ajoutés en objet, détail (institut, dates de terrain) et lien
vers la PR dans le corps. En cas d'échec, l'objet le signale.

**Corriger une valeur.** Priorité à la correction sur Wikipédia elle-même, qui bénéficie
à tous et disparaît du problème au run suivant. En dernier recours, un fichier
`corrections.json` appliqué après le parsing, avec motif obligatoire pour chaque entrée.
Une erreur récurrente se répare dans le parser, jamais dans les corrections.

**Mesure d'audience.** GoatCounter, hébergé chez GoatCounter (hors du site), sans cookie
ni stockage local, sans donnée personnelle collectée. Le script `count.js` est chargé en
asynchrone et ignoré s'il est bloqué par un adblock (optional chaining, pas de fallback).

Événements envoyés (liste fermée, seuls des identifiants du référentiel ou des données) :

- `duel/<id-a>-<id-b>` : sélection d'un duel de second tour (identifiants triés
  alphabétiquement).
- `periode-sondages/<3m|6m|annee|tout|libre>` : raccourci de période, courbe sondages.
- `periode-cotes/<3m|6m|annee|tout|libre>` : raccourci de période, bloc Polymarket.
- `hypothese/<tour>/<id-sondage>` : ouverture d'une hypothèse dans la fiche technique.

Aucune date libre saisie par l'utilisateur, aucune valeur de champ texte, aucun paramètre
de requête n'est transmis.

---

## 9. Architecture

- Collecte : script Python, exécution quotidienne par GitHub Actions. `collecte_wikipedia.py`
  reprend le parser existant et lui ajoute l'appel à l'API MediaWiki, la conservation du
  `revid` et l'écriture du snapshot dans `/data/snapshots`.
- Données : fichiers JSON versionnés dans le dépôt. L'historique git fait office
  d'historique de données.
- Front : site statique, lecture des JSON au build.
- `/data/derived` est entièrement reconstructible depuis les sources et peut être
  supprimé sans perte.

```
/data
  candidats.json
  sondages.json
  polymarket.json                 deux marchés : victoire + second tour
  historique.json                 2002-2022, produit une fois (§12)
  /snapshots                     wikitexte brut, immuable
  /snapshots/historique           wikitexte anglais, immuable
  /derived                       séries précalculées, jetable
/scripts
  collecte_wikipedia.py          dérivé du prototype parse_wikipedia.py
  collecte_polymarket.py         deux événements (victoire + second tour)
  pages_second_tour.py          pages de duel + sitemap, reconstructible
  validation.py
  series.py
  series_historique.py           séries 2002-2022 pour le front
  import_historique.py           import unique depuis les snapshots anglais
  wikitable.py                   parseur de wikitables (pages anglaises)
/site
  index.html
  sondages.html
  methodologie.html
  precedentes-elections.html     rubrique « Précédentes élections »
  presidentielle-{2002..2022}.html  une page par élection
  sitemap.xml                    généré par pages_second_tour.py
  /second-tour                   pages de duel, reconstructible (.gitignore)
  /assets
    historique.js                script partagé des pages d'élection
```

**Mise en ligne.** Le déploiement public n'intervient qu'après accord explicite.
Développement et prévisualisation en local jusque-là.

---

## 10. Obligations

- Mentions légales : éditeur, hébergeur, contact.
- Attribution Wikipédia (CC BY-SA) et mention de Polymarket comme source des cotes.
- Affichage en pied de page de la date du dernier run réussi et du `revid` utilisé.
- **Loi du 19 juillet 1977** : interdiction de publier ou commenter des sondages la
  veille et le jour du scrutin. Le site doit pouvoir se mettre en veille automatiquement
  sur ces dates en avril 2027.

---

## 11. Pièges du wikitexte (constatés, pas théoriques)

Relevés sur la version de septembre 2026 en développant le parser. Tous ont produit des
données fausses avant correction. À traiter comme une liste de tests de non-régression.

1. **Une cellule peut remplacer le candidat de sa colonne.** Environ 225 occurrences :
   `7,5<br><small>[[François Hollande|Hollande]] (PS)</small>` dans la colonne Glucksmann
   signifie que ce sondage teste Hollande. Piège le plus grave : sans traitement, des
   scores sont attribués au mauvais candidat, de façon parfaitement plausible et donc
   indétectable à l'œil.
2. **`colspan` sur une cellule de données.** Un candidat de substitution occupe parfois
   plusieurs colonnes fusionnées. Ne pas confondre avec les lignes d'annonce de
   candidature, qui portent un `colspan` couvrant tout le tableau.
3. **Le gras est placé indifféremment dedans ou dehors** : `'''{{blanc|36}}'''` et
   `{{blanc|'''36'''}}` coexistent. Découper sur le `<br>` avant tout nettoyage.
4. **Colonne générique** : le tableau du premier semestre 2026 a une colonne
   « Candidat RN », sans portrait ni sigle, le candidat réel étant précisé dans chaque
   cellule. Identifier les colonnes par leur **position** dans l'en-tête, jamais par leur
   mise en forme.
5. **Colonnes désignant un parti et non une personne** : la page utilise « Candidat PS »,
   « Candidat LR », « Candidat EELV », « Candidat RN ». Aucune occurrence sans candidat
   nommé dans les données de 2026 — toutes les cellules précisent la personne testée —
   mais le cas se présentera avant les primaires. Il se traite par une entrée
   `type: parti` du référentiel (§3.1), pas par une exception dans le parser.
6. **`[[File:` au lieu de `[[Fichier:`** dans deux tableaux. Ne jamais faire reposer une
   détection sur l'orthographe française d'un mot-clé wiki.
7. **Dates sans année** au premier tour (« 2-3 septembre ») : l'année vient du titre de
   section. Certaines chevauchent deux mois (« 31 août - 2 septembre »). Les tableaux de
   second tour, eux, portent l'année.

8. **Balises HTML dans le libellé d'un lien de substitution.** OpinionWay du
   10/09/2026 : `[[Karim Bouamrane|'''<small>Bouamrane</small>''']]`. Le gras
   est à l'intérieur du libellé et enveloppe une balise `<small>`. Si `_une_valeur()`
   ne nettoie que `{{blanc}}` et les apostrophes, le slug devient
   `small-bouamrane-small` au lieu de `bouamrane`. Retirer les balises HTML
   du libellé après extraction du groupe capturé.

Autres irrégularités à prévoir : décimales à la virgule, `{{formatnum:}}`, espaces
insécables, notes en exposant, `—` pour non testé.

**Le mapping Polymarket ne peut pas être automatique** : le marché Mélenchon a un slug
corrompu (`will-jean-luc-mlenchon-...`, accent perdu à la création). Le mapping se fait
sur le `conditionId` (champ `condition_polymarket` de `candidats.json`), renseigné à la
main.
- Deux événements suivis : victoire (128 marchés) et accession au second tour (37 marchés).
  Sur le second tour, la somme des probabilités avoisine 200 % (deux places) — ne pas
  corriger.
- Les marchés Polymarket sont en `negRisk` : les prix d'un même événement sont couplés
  et se normalisent d'eux-mêmes. **Ne pas renormaliser.** Afficher les prix bruts.
- Filtrer à l'affichage (probabilité actuelle > 1 % ou volume minimum).
- Sondages et cotes ne mesurent pas la même chose : parts de voix au premier tour d'un
  côté, probabilités de l'autre. Ne jamais les superposer sur un même graphe.

---

## 12. Précédentes élections (2002-2022)

**Objet.** Comparer 2027 aux présidentielles précédentes, au même nombre de jours avant
le premier tour. Une page d'accueil de rubrique, puis une page par élection avec
premier et second tours.

**Source.** Pages « Opinion polling for the {année} French presidential election »
(en.wikipedia.org, CC BY-SA), figées par revid : 1329460026 (2002), 1341388824 (2007),
1279812574 (2012), 1213598918 (2017), 1363121499 (2022). Les pages françaises sont
écartées : pas d'échantillon pour 2002-2012, couverture plus faible.

**Données.** `data/historique.json`, produit une fois par `scripts/import_historique.py`
depuis `data/snapshots/historique/`. Données figées : ni collecte quotidienne, ni
contrôles du §8. Les sommes hors bornes présentes sur la page sont conservées et
marquées (`somme_hors_bornes`). Rollings, sous-échantillons et sondages hors commission
sont marqués, jamais filtrés à l'import.

**Périmètre affiché.** Sondages commencés à partir du 1er janvier de l'année précédant
l'élection, jusqu'au second tour. Pour la courbe du premier tour, filtre d'affichage et
non de calcul (§4).

**Méthode.** Premier tour : identique à la courbe 2027, même code ; toute évolution de
méthode s'applique aux deux et l'historique est recalculé. Second tour : même règle
qu'au §7. Rollings compris tant qu'aucune règle n'est décidée.

**Affichage.** Axe en dates ; alignement interne en jours avant le premier tour,
repère du jour équivalent pour 2027 et nombre de jours dans l'info-bulle.
Résultats officiels ; points bruts au premier tour.

**Hors périmètre.** Traitement des rollings, regroupement par famille politique ou par
rang, superposition de plusieurs élections sur un même graphe, élections de 1965 à 1995.
