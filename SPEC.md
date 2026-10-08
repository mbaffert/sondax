# Sondax — spécification

Agrégateur public des données quantitatives sur l'élection présidentielle française de 2027 :
sondages d'opinion et probabilités implicites issues des marchés de prédiction.

Ce fichier fait autorité. En cas de doute sur une structure de données ou une règle de
méthode, s'y référer plutôt que d'improviser. Toute évolution des règles ci-dessous se
décide explicitement et se répercute ici.

---

## 1. Périmètre v1

Un site statique multi-pages : page d'accueil à sections ancrées, pages par
candidat, pages par sondage, pages par institut de sondage et page de référence
des instituts, pages par duel de second tour, pages d'élections passées, page de
données, page de méthodologie, tableau complet des sondages et page du modèle Sondax
(`/modele-sondax`, §14).

Page d'accueil à sections nommées et ancrées, dans cet ordre (décision du
29 septembre 2026) :

1. **Bandeau d'en-tête.** Dernier sondage, compte à rebours, navigation (voir
   `scripts/build_header.py`).
2. **Dernier sondage publié** (`#dernier-sondage`), carte compacte avec l'hypothèse
   sélectionnée. En cas d'égalité de `terrain_fin`, le sondage avec le plus grand
   échantillon est retenu. Juste dessous, un simple lien « Voir tous les sondages »
   vers `sondages.html`, sans titre ni texte (écrit dans le gabarit). Le tableau des
   derniers sondages agrégés a été retiré de l'accueil.
3. **Sondages du premier tour** (`#bloc-sondages`). Titre : « Sondages du premier
   tour de la présidentielle 2027 ». Chapeau généré au build (leader, volume,
   delta 3 mois), sélecteur de période, courbe de tendance par candidat. Généré par
   `scripts/build_index_premier_tour.py` (qui produit aussi la carte du point 2).
4. **Sondages par candidat** (`#bloc-candidats`) : vignettes vers les fiches.
5. **Modèle Sondax** (`#modele-sondax`). Généré par `scripts/build_modele.py`
   (§14.14.1).
6. **Second tour** (`#second-tour`). Repères factuels, chapeau généré au build, duel
   principal seul (le plus récemment mesuré, règle inchangée), puis un lien « Voir les
   autres duels » (`<details>` natif, replié par défaut, contenu présent dans le HTML
   servi) qui déplie le tableau des autres duels testés et celui des duels testés avec
   Jordan Bardella avec sa phrase d'explication. Sélecteur « Explorer un duel » en fin
   de bloc (voir §7).
7. **Cotes des marchés de prédiction** (`#bloc-polymarket`). Évolution des
   probabilités implicites par candidat, deux onglets : accession au second tour
   et victoire. Les titres ne nomment pas Polymarket, la source est citée dans
   le corps du bloc et en pied de page.

La sous-navigation de l'accueil suit le même ordre : Premier tour, Modèle, Second
tour, Prédictions.

La page `sondages.html` (titre : « Les N sondages de la présidentielle 2027, un par un », N injecté au build) porte
en tête le module **« Explorer les sondages »** (`#bloc-fiche`) : sélection d'un
sondage puis d'une configuration, et affichage de ses scores et de ses marges
d'erreur (voir §5). Viennent ensuite le filtre par institut et le tableau de tous
les sondages. L'ancienne ancre `index.html#bloc-fiche` redirige vers
`sondages.html#bloc-fiche`.

**Contrainte générale de rendu** : tout le contenu textuel des sections est rendu au
build et présent dans le HTML servi par le serveur. Le JavaScript ne sert qu'à
l'interaction (sélecteurs, graphiques, onglets).

**Repères factuels.** Chaque section porte les repères de son propre tour : le texte
du premier tour dans la section premier tour, celui du second tour dans la section
second tour. Ces textes sont écrits en dur dans `build_header.py` (`REPERES_T1`,
`REPERES_T2`) et sont datés : ils devront être révisés à la publication du décret de
convocation, à la clôture des parrainages (12 mars 2027) et le jour du scrutin. Le
JSON-LD `Event` est scindé de la même façon (un événement par section). Le booléen
`officielles` de `config.json` est conservé pour basculer la formulation si les dates
devaient changer.

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

Trois fichiers dans `/data` pour 2027, deux référentiels des instituts
(`instituts.json`, `commanditaires.json`, §3.5), plus `historique.json` pour les
élections 2002-2022 (§12). Les snapshots de wikitexte vont dans `/data/snapshots`
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

- `id` déterministe : `slug(institut)-terrain_fin`. **L'identifiant est figé à la
  première collecte** et ne doit jamais être recalculé, même si `terrain_fin` est
  corrigé sur Wikipédia : l'URL `/sondages/<id>.html` ne doit pas changer, car
  GitHub Pages ne gère pas les redirections et une URL modifiée casse les liens
  entrants.
- **Commanditaire.** Il n'est pas une colonne de la page Wikipédia et n'est pas
  collecté. Il est déduit au build du nom de fichier de la notice de la commission
  des sondages (`url_source`) : `10260-pres-iv-opinionway-cnews-11-septembre.pdf`
  → `cnews`, soit le segment qui suit le nom de l'institut (`notice` dans
  `instituts.json`), numéro de notice et date de publication retirés. Le slug est
  traduit en nom affiché par `commanditaires.json` (§3.5). Le résultat va dans
  `/data/derived/commanditaires.json`, jamais dans `sondages.json`. Pas de
  commanditaire affiché quand l'URL n'est pas une notice (article de presse, site
  de l'institut), quand le nom de fichier n'en porte pas, ou quand le slug est
  absent de la table ; ce dernier cas est signalé sur la page de revue (§8), sans
  faire échouer le run.
  Une collision d'identifiant (même institut, même date de fin) est une erreur
  bloquante, jamais un écrasement silencieux.
- **`sondages.json` est la référence ; Wikipédia n'est qu'une source d'entrée.**
  La collecte charge le fichier existant et y fusionne le résultat par `id` :
  `id` nouveau → ajouté ; `id` connu → mis à jour si les valeurs ont changé (le
  `revid` n'est alors mis à jour qu'avec elles) ; `id` absent de Wikipédia →
  conservé tel quel, **jamais supprimé automatiquement**. Même logique pour les
  hypothèses d'un sondage : une hypothèse que Wikipédia ne renvoie plus est
  conservée. Un `id` nouveau qui désigne en fait un sondage déjà connu dont la
  date de terrain a bougé (même institut, `terrain_fin` à ±2 jours, mêmes
  valeurs d'hypothèses) met à jour l'entrée existante, qui garde son `id`.
  Chaque run écrit dans son log les sondages absents de Wikipédia et, pour
  chaque sondage modifié, un diff « ancienne valeur → nouvelle valeur ».
- **Retrait volontaire.** Seule voie de suppression : `retire: true`, avec
  `retire_motif` (texte) et `retire_le` (date ISO), posés à la main dans
  `sondages.json`. L'entrée reste dans le fichier (et la collecte ne touche
  jamais à ces trois champs) mais est exclue de tous les calculs et de toutes
  les pages : les scripts lisent le fichier via `scripts/sondages_io.py`
  (`charger`), jamais directement. La validation (§8) bloque si un `id`
  précédent disparaît du fichier ou si le total baisse.
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

### 3.5 `instituts.json` et `commanditaires.json` — référentiels, édités à la main

```json
{
  "toluna-harris-interactive": {
    "nom": "Harris",
    "nom_complet": "Toluna Harris Interactive",
    "alias": ["Harris", "Harris Interactive", "Toluna Harris Interactive"],
    "notice": ["toluna-harris-interactive", "harris-interactive"],
    "mode_recueil": "en ligne",
    "site": "https://harris-interactive.fr/",
    "logo": "logos/toluna-harris-interactive.png",
    "logo_source": "commons:Harris Toluna Company logo.png"
  }
}
```

- La clé est le **slug** de la page `/instituts/<slug>.html`. Comme l'identifiant
  d'un sondage, il ne change plus une fois publié.
- `nom` : nom court, celui du champ `institut` de `sondages.json` et des tableaux.
  `alias` : autres graphies résolues vers la même entrée.
- `nom_complet` : nom sous lequel le public cherche l'institut ; sert au titre et au
  H1 de sa page.
- `notice` : graphies de l'institut dans les noms de fichier des notices (§3.2).
- `mode_recueil` : `en ligne`, `téléphone` ou `mixte` ; `null` si non vérifié.
- `site` : page d'accueil de l'institut. `logo` : chemin relatif à `site/`.
  `logo_source` : origine du logo (`commons:<fichier>`, `fr:<fichier>` ou URL),
  lue par `scripts/logos.py` (§13.7).

Un institut absent du référentiel ne fait pas échouer le run : son nom n'est pas
lié, il n'a pas de page, et il est signalé sur la page de revue.

`commanditaires.json` : table `slug → nom affiché` (`"les-echos": "Les Echos"`).

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
les autres restent accessibles dans le module « Explorer les sondages »
(`sondages.html#bloc-fiche`).

La règle ne s'applique pas au tour 2 : tous les duels sont également valides.

**Sélection du dernier sondage publié.** Une fonction unique
(`select_latest_sondage` dans `build_header.py`) sert au bandeau et à la fiche du
dernier sondage. Règle de départage :

1. `terrain_fin` la plus récente ;
2. en cas d'égalité, le plus grand `echantillon` total ;
3. en cas d'égalité encore, l'ordre d'apparition dans `sondages.json`.

Le bandeau affiche les quatre premiers scores. Le bloc « Dernier sondage » de
l'accueil (`#dernier-sondage`) affiche le même sondage ; le module « Explorer les
sondages » de `sondages.html` s'ouvre sur ce sondage et affiche l'intégralité des
scores de l'hypothèse retenue.

**Sélection de l'hypothèse.** Parmi les hypothèses T1 du sondage retenu, la sélection
suit trois niveaux :

1. Retenir celle qui contient le plus de **candidats officiellement déclarés** —
   c'est-à-dire ceux dont `declare_le` est non nul et ≤ `terrain_fin` du sondage.
2. En cas d'égalité, retenir l'hypothèse dont `echantillon` (au niveau hypothèse) est
   le plus grand ; si nul, considérer l'échantillon du sondage.
3. En cas d'égalité persistante, retenir la première dans l'ordre du fichier.

Tant que tous les `declare_le` sont `null`, la règle dégénère en « hypothèse avec le
plus de candidats testés, puis échantillon le plus grand » — équivalent au fallback des
courbes, et le résultat est cohérent.

**Chapeau de la moyenne** : placé dans la section premier tour, il décrit la moyenne
pondérée (leader, top 3, volume, instituts nommés, delta 3 mois). C'est un contenu
distinct du dernier sondage — les deux peuvent diverger et c'est normal.

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
(3 mois, 6 mois, tout) ou par date libre. **Le site ouvre sur 6 mois par défaut** :
c'est la période la mieux fournie en sondages, et le réglage reste pertinent à mesure
que leur fréquence augmente, contrairement à une date fixe. Le champ de date libre est
borné : `min` = `terrain_fin` du sondage le plus ancien, `max` = date du jour. Ces
bornes sont calculées depuis les données, jamais écrites en dur. Le bloc Polymarket
a son propre sélecteur de période, avec ses propres bornes calculées sur
`polymarket.json`.

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

## 5. Sélection d'une configuration (module « Explorer les sondages »)

Le module est en tête de `sondages.html` (`#bloc-fiche`). État initial rendu au build
par `scripts/build_sondages_page.py` (dernier sondage publié, hypothèse principale),
interaction dans `site/assets/explorer-sondages.js`. Tableau à trois colonnes :
Candidat / Score / Marge d'erreur. Un clic sur une ligne du tableau des sondages de
la même page charge ce sondage dans le module, sans rechargement, et remonte au
module ; la date de la ligne reste un lien vers la fiche `/sondages/<id>.html`.

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
reconstructible, ajouté au `.gitignore`).

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
est généré par `scripts/build_sitemap.py` (§13.5).

Les pages des élections passées (`precedentes-elections.html` et les cinq
`presidentielle-AAAA.html`) sont entièrement générées au build par
`scripts/build_pages_elections.py` (styles communs : `assets/historique.css`) ; la page `sondages.html` contient l'état
initial du module « Explorer les sondages » et le tableau complet des sondages en
HTML statique (`scripts/build_sondages_page.py`).

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
5. `data/derived/modele.json` existe et les contrôles du moteur passent (§14.18).
6. **Non bloquant**, signalé sur la page de revue uniquement : pour un même candidat,
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
valeur en anomalie est surlignée. Elle signale aussi, sans bloquer, les commanditaires
non reconnus et les instituts absents de `instituts.json` (§3.5).

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
- `hypothese/<tour>/<id-sondage>` : ouverture d'une hypothèse dans le module
  « Explorer les sondages ».

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
  supprimé sans perte. `modele_history.json` n'y est donc pas : il enregistre ce que
  le site a affiché et ne se reconstruit pas (§14.13).

```
/data
  candidats.json
  sondages.json
  instituts.json                  référentiel des instituts (§3.5)
  commanditaires.json             slug de notice → nom affiché (§3.5)
  polymarket.json                 deux marchés : victoire + second tour
  historique.json                 2002-2022, produit une fois (§12)
  historique_europeennes.json     européennes 2019 et 2024, produit une fois (§14.16)
  modele_history.json             historique du modèle Sondax, versionné (§14.13)
  /snapshots                     wikitexte brut, immuable
  /snapshots/historique           wikitexte anglais, immuable
  /derived                       séries précalculées, jetable
/scripts
  collecte_wikipedia.py          dérivé du prototype parse_wikipedia.py
  collecte_polymarket.py         deux événements (victoire + second tour)
  pages_second_tour.py          pages de duel, reconstructible
  validation.py
  instituts.py                   référentiel instituts, commanditaires → /derived
  build_pages_instituts.py       pages institut + instituts.html
  logos.py                       logos des instituts, exécution ponctuelle
  series.py
  series_historique.py           séries 2002-2022 pour le front
  import_historique.py           import unique depuis les snapshots anglais
  wikitable.py                   parseur de wikitables (pages anglaises)
  import_europeennes.py          import unique des européennes (§14.16)
  calibration.py                 erreurs historiques, N_eff → /derived (§14.5)
  modele.py                      moteur du modèle Sondax → /derived/modele.json (§14.6)
  build_retro.py                 bloc Rétro-Sondax de l'accueil → /derived/retro.json (§15) ;
                                 retro.json couvre aussi 2002 et 2027 (page precedentes-elections.html)
  build_pages_elections.py       pages precedentes-elections.html et presidentielle-AAAA.html
  test_modele.py                 tests du moteur, lancés par validation.py (§14.18)
  backtest.py                    backtest leave-one-out → /derived (§14.17)
  build_modele.py                page Modèle, bloc d'accueil, blocs candidat et duel
  partage_modele.py              images de partage (§14.15)
/site
  index.html
  sondages.html
  modele-sondax.html             page du modèle Sondax, générée (§14)
  /partage                       images de partage du modèle, générées (.gitignore)
  methodologie.html
  a-propos.html                  à propos, contact et mentions légales
  donnees.html                   généré par build_donnees.py
  precedentes-elections.html     rubrique « Précédentes élections »
  presidentielle-{2002..2022}.html  une page par élection
  sitemap.xml                    généré par build_sitemap.py
  /sondages                      pages par sondage, reconstructible (.gitignore)
  instituts.html                 page de référence des instituts, générée
  /instituts                     pages par institut, reconstructible (.gitignore)
  /logos                         logos des instituts, versionnés (§13.7)
  /second-tour                   pages de duel, reconstructible (.gitignore)
  /candidats                     index des candidats
  /assets
    historique.js                script partagé des pages d'élection
    explorer-sondages.js         module « Explorer les sondages » (sondages.html)
```

**Mise en ligne.** Le déploiement public n'intervient qu'après accord explicite.
Développement et prévisualisation en local jusque-là.

---

## 10. Obligations

- Mentions légales : page a-propos.html (éditeur, hébergeur, contact). L'adresse de l'éditeur n'est jamais publiée.
- Attribution Wikipédia (CC BY-SA) et mention de Polymarket comme source des cotes, en texte simple, sans lien vers polymarket.com.
- Affichage en pied de page de la date du dernier run réussi et du `revid` utilisé.
- **Loi du 19 juillet 1977** : interdiction de publier ou commenter des sondages la
  veille et le jour du scrutin. Le site doit pouvoir se mettre en veille automatiquement
  sur ces dates en avril 2027. La veille couvre le modèle Sondax (§14.22).

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
   **`colspan` sur une cellule d'en-tête** aussi : en octobre 2026, la colonne
   Glucksmann est passée en colonne double PS-PP, en-tête et cellules de données
   portant `colspan=2`. Compter les colonnes d'en-tête sans tenir compte du
   `colspan` décale d'un cran tout ce qui suit la colonne et fait sortir la
   dernière colonne (« Autre ») du tableau.
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

**Tableau des moyennes mensuelles** (décision du 30 septembre 2026). Sous les
graphique du premier tour, tableau HTML statique écrit par `scripts/build_pages_elections.py`
(dans un bloc replié « Moyennes mensuelles des sondages ») : une ligne par mois (mois de fin de terrain), une
colonne par principal candidat, puis le résultat du premier tour en dernière ligne.
Pas de colonne d'écart. Moyenne simple, sur le mois, du score de chaque sondage de
premier tour du périmètre affiché (début de terrain à partir de la borne, fin de
terrain avant le premier tour), score retenu comme pour la courbe
(`series.score_candidat`) ; « — » quand le candidat n'est pas testé ce mois-là.
Principaux candidats : présents au premier tour, avec 5 % des suffrages exprimés ou
10 % de moyenne mensuelle au moins une fois ; colonnes par résultat décroissant.

**Hors périmètre.** Traitement des rollings, regroupement par famille politique ou par
rang, superposition de plusieurs élections sur un même graphe, élections de 1965 à 1995.

## 13. Pages générées

Toutes les pages ci-dessous sont générées au build depuis `/data`. Aucune n'est
écrite à la main ; chacune possède un canonical correspondant à son URL réelle.

### 13.1 Fiches candidat

URL : `/<slug>.html` (9 candidats définis dans `scripts/bios.json`).
Script : `scripts/build_pages_candidats.py`, qui appelle `scripts/generer.py`.
Contenu : identité, courbe d'évolution, duels de second tour, profil de
l'électorat (croisements Ipsos), liens vers les autres candidats.
CSS scopé sous `.page-candidat` (`site/style-candidat.css`, copie identique de
`scripts/style-candidat.css`).

Sous la courbe de tendance et son texte (décision du 30 septembre 2026) : tableau
HTML des 5 derniers sondages dont l'hypothèse principale du premier tour teste le
candidat (fin de terrain décroissante) — institut (lien vers sa page), dates de
terrain, score, lien vers la fiche Sondax, lien vers la notice — puis un lien
« Voir tous les sondages » vers `sondages.html`. Un prédécesseur (`succede_a`)
n'y est pas repris.

### 13.2 Index des candidats

URL : `/candidats/` (`site/candidats/index.html`).
Script : `scripts/build_candidats_index.py`.
Contenu : tableau de tous les candidats du référentiel, avec dernier score de
l'hypothèse principale, date de dernière mesure, et lien vers la fiche.

### 13.3 Pages par sondage

URL : `/sondages/<id>.html` (un fichier par entrée de `sondages.json`).
Script : `scripts/build_sondage_pages.py`.
Contenu : h1 « Sondage <institut> du <date de fin de terrain> », puis une ligne
avec la période de terrain, l'institut (lien vers sa page), l'échantillon, la
population et le lien vers la notice. Vient ensuite un chapô rédigé, puis chaque
hypothèse (tour, scores, marge d'erreur). L'hypothèse
principale est affichée en premier, avec l'écart de chaque candidat à la moyenne
pondérée Sondax à la date de fin de terrain. Marge d'erreur calculée sur
l'échantillon de l'hypothèse si disponible, sinon sur l'échantillon total avec
mention « approximative ». Les duels de second tour sont affichés séparément.
L'identifiant est figé (§3.2) ; il sert d'URL et ne doit jamais être recalculé.

**Chapô.** Généré au build, sans appel à un modèle, sur le modèle du chapeau
de l'accueil : chiffres au format français, espace insécable avant « % ».
Dans l'ordre :

1. podium de l'hypothèse principale (trois premiers, noms complets) ;
2. évolution des trois premiers par rapport au précédent sondage du même
   institut, d'hypothèse principale à hypothèse principale : seuls les
   mouvements d'au moins 1 point sont chiffrés, les autres sont dits stables ;
   un candidat absent de l'hypothèse principale précédente est signalé comme
   tel, jamais comparé à une autre configuration. Sans précédent : « C'est le
   premier sondage <institut> de la série. » ;
3. nombre de configurations de premier tour et ce qui les distingue : candidats
   de l'hypothèse principale absents d'au moins une autre (« avec ou sans »,
   limités à ceux qui y pèsent 5 % ou plus, trois au plus), puis candidats
   ajoutés ailleurs (trois au plus) ;
4. s'il y a des duels : leur nombre, le vainqueur et le duel le plus serré.

Une phrase dont la donnée manque est omise, jamais remplacée par un texte
générique. Deux fiches ne peuvent pas avoir le même chapô : le build échoue
sinon. La meta description reprend la première phrase du chapô, plus la
seconde si l'ensemble tient en 155 caractères ; le title reste
« Sondage <institut> du <date> – présidentielle 2027 ».

**Libellé des hypothèses.** « Hypothèse n — avec X, sans Y », calculé par
différence de candidats avec l'hypothèse principale ; « Hypothèse n » seul
si la liste est identique.

**Navigation.** Sondage précédent et suivant dans l'ordre chronologique de
tous les sondages (fin de terrain, puis début de terrain, puis identifiant),
libellés avec l'institut et la date. Sous chaque duel, lien vers la page du
duel (§13.4).

Maillage : dans `sondages.html`, la date de chaque ligne du tableau renvoie vers
la page du sondage, et « Voir la fiche » du module « Explorer les sondages »
pointe vers la page du sondage sélectionné. Sur la page d'accueil, « Voir la
fiche » du bloc « Dernier sondage » pointe vers la page du dernier sondage.

### 13.4 Pages par duel de second tour

URL : `/second-tour/<slug-a>-<slug-b>.html` (slugs dans l'ordre alphabétique).
Script : `scripts/pages_second_tour.py` (`generate_duel_page`).
Contenu : tableau des sondages pour le duel. Graphique Chart.js si ≥ 5 mesures
(SEUIL défini dans le script), tableau seul en dessous. Redirection HTML depuis
le slug inversé.

Sous la ligne « N sondages · Dernier : … », une phrase générée (décision du
30 septembre 2026) : « Dans le dernier sondage (Harris, 22–24 septembre 2026),
Le Pen obtient 57 % contre 43 % pour Philippe. » Vainqueur en premier ; « le seul
sondage publié » quand le duel n'a qu'une mesure ; en cas d'égalité, « X et Y
obtiennent chacun 50 % ». Le bloc du modèle (§14.14.4) vient après cette phrase.

### 13.5 Balisage et SEO

**Canonicals.** Chaque page déclare un `<link rel="canonical">` pointant vers
son URL réelle (`https://sondax.fr/<chemin>`). Vérifié au build par
`scripts/validate_urls.py`.

**Sitemap.** Généré par `scripts/build_sitemap.py` à chaque build, après la
génération de toutes les pages, par énumération des fichiers HTML de `site/` :
aucune liste d'URLs ni de slugs. En sont exclues les pages de redirection
(`<meta http-equiv="refresh">`), les pages `noindex` et celles dont le canonical
pointe vers une autre URL ; une page sans canonical fait échouer le build.
`/second-tour/` et `/candidats/` sont des pages à contenu propre (liste des duels
et tableaux des duels sous le seuil ; tableau des candidats) et y figurent.

`lastmod` est la date du dernier changement des données affichées, jamais la
date du build (une page qui ne relève d'aucune règle fait échouer le build) :

| Page | lastmod |
|---|---|
| `sondages/<id>.html` | fin de terrain du sondage (`saisi_le` si postérieure) |
| `instituts/<slug>.html` | dernier sondage de l'institut |
| fiche candidat | dernier sondage où figure le candidat ; dernier sondage du modèle (`jour_moyenne`) si la fiche porte son bloc ; dernier commit de `scripts/bios.json` |
| page duel | dernier sondage testant le duel ; `jour_moyenne` du modèle si la page porte son bloc |
| `second-tour/`, `candidats/` | dernier sondage de second tour / de premier tour |
| `sondages.html`, `instituts.html`, `donnees.html` | dernier sondage |
| `modele-sondax.html` | `jour_moyenne` du modèle |
| accueil | dernier sondage, modèle, dernière collecte Polymarket (`maj`) |
| pages rédigées à la main (Méthode, À propos, élections passées) | dernier commit du fichier et des données affichées (`historique*.json`, `config.json`) |

Les dates git exigent un clone complet (`fetch-depth: 0` dans `pages.yml`) ;
`build_sitemap.py` échoue sur un clone superficiel.

**JSON-LD Dataset.** Deux jeux de données distincts, injectés par
`scripts/build_jsonld_dataset.py`, chacun sur la page où il est présenté :

- Sondages, sur `donnees.html` (§13.6) : license CC BY-SA 4.0, isBasedOn (page
  Wikipédia), distribution (le CSV public).
- Cotes Polymarket, sur `index.html` : isBasedOn Polymarket, distribution
  (`polymarket.json`), **sans propriété license** — les cotes relèvent des conditions
  d'utilisation de Polymarket, pas de la CC BY-SA.

Jamais fusionnés en un seul jeu de données.

**Dates de build.** Injectées en HTML statique par `scripts/build_dates.py` :
dernier sondage intégré, date de vérification, revid Wikipédia. Affichées en
haut de la page d'accueil et dans le pied de page de toutes les pages (élément
`#footer-run`, présent aussi dans les fiches candidat et les pages
`presidentielle-20XX.html`).

**Balises `<time>`.** Toute date visible rendue au build est placée dans une
balise `<time datetime>` (date ISO, ou `AAAA-MM` pour un mois), sans changement
d'apparence : `scripts/balise_time.py` (`time_tag`, et `baliser_dates` pour les
textes rédigés comme `bios.json`). Une période de terrain porte une balise par
borne. Les dates écrites en JavaScript et les étiquettes des graphiques n'en ont
pas.

**Validation.** `scripts/validate_urls.py` vérifie que chaque canonical et
chaque URL du sitemap correspond à un fichier généré, et que le sitemap contient
exactement les pages HTML publiables de `site/` (même nombre, liste des pages
manquantes ou en trop, lastmod présent et pas dans le futur). Le build échoue
(exit 1) en cas d'écart : rien n'est déployé.

**JSON-LD Organization.** Chaque page institut porte un objet `Organization`
(nom complet, `alternateName` si le nom court diffère, `url` du site de l'institut,
`logo` si le fichier existe, `subjectOf` vers la page), sur le modèle de l'objet
`Person` des fiches candidat.

**JSON-LD de navigation.** Injecté par `scripts/build_jsonld_navigation.py`, après
la génération de toutes les pages : `WebSite` sur `index.html` ; `BreadcrumbList`
sur chaque page qui affiche un fil d'Ariane (élément de classe `fil`), avec les
mêmes étapes que le fil visible. La dernière étape non liée est la page elle-même ;
une étape intermédiaire affichée sans lien (« Candidats ») prend l'URL de la page
correspondante. Un fil d'une seule étape n'est pas balisé.

### 13.6 Jeu de données public

URL : `/donnees.html` ; fichier : `/donnees/sondages-presidentielle-2027.csv`.
Script : `scripts/build_donnees.py`, exécuté au déploiement ; sorties ignorées par git.

Le CSV est le **contrat public** : ses colonnes ne changent pas sans décision explicite,
contrairement aux JSON de `data/`, formats internes. Format long, une ligne par
sondage × configuration × candidat ; un candidat absent d'une configuration n'a pas de
ligne. UTF-8, séparateur virgule, point décimal. Colonnes documentées sur la page.

Contient les mesures publiées, pas la moyenne Sondax, et aucune donnée Polymarket.

Licence CC BY-SA 4.0 imposée par la source. Mention demandée : « Sondax, d'après
Wikipédia », avec lien vers sondax.fr.

Le même fichier est référencé sur data.gouv.fr comme ressource distante (URL ci-dessus),
jamais comme copie figée.

### 13.7 Pages par institut

URL : `/instituts/<slug>.html` (slug de `instituts.json`) et page de référence
`/instituts.html`. Script : `scripts/build_pages_instituts.py`, après
`scripts/instituts.py` (commanditaires) et `series.py`.

Page institut :
- title et H1 « Sondages <nom complet> — présidentielle 2027 », meta description
  propre ;
- logo en tête de page s'il existe, lien simple vers le site de l'institut ;
- chapeau généré : nombre de sondages, période des fins de terrain, intervalle moyen
  entre deux sondages, principaux commanditaires, mode de recueil ;
- graphique d'évolution, si l'institut compte au moins 5 sondages de tour 1 (sinon
  rien, sans message) : même rendu que le graphique de premier tour de l'accueil
  (`site/assets/bloc-chart.js`, partagé), sans sélecteur de période, axe du premier
  au dernier sondage de l'institut. Courbes : scores de l'hypothèse principale du
  tour 1, un point par sondage, reliés par des segments ; un sondage qui ne teste pas
  le candidat interrompt la courbe (aucune interpolation). En fond, trait fin et
  transparent, la moyenne Sondax des mêmes candidats. Cochés par défaut : les 4
  premiers du dernier sondage de l'institut, plus les candidats passés par ce top 4
  et absents du dernier sondage (Bardella avant son remplacement par Le Pen). La meta
  description mentionne alors « évolution des intentions de vote » ;
- liste de tous les sondages, du plus récent au plus ancien : dates de terrain (lien
  vers la fiche), commanditaire, échantillon, lien vers la notice.

Page de référence : chapeau généré (nombre d'instituts, de sondages, période), puis
une ligne par institut avec son logo, le nombre de sondages et la date du dernier.

Maillage : « Instituts » dans le bandeau d'en-tête, après « Tous les sondages ». Le nom de
l'institut est un lien vers sa page dans les tableaux de l'accueil, `sondages.html`
(la date y mène à la fiche), les fiches sondage et les tableaux de second tour ;
jamais de logo dans ces tableaux.

**Logos.** Fichiers versionnés dans `site/logos/`, produits par `scripts/logos.py`
(exécution à la main, hors build) : SVG quand la source est vectorielle, sinon PNG
sur fond transparent ; marges recadrées ; monochrome gris foncé `#33383F`. La hauteur
d'affichage est fixée par la CSS ; en thème sombre, la CSS inverse le gris. Un logo
absent n'empêche pas la génération : la page s'affiche sans.

### 13.8 Page du modèle Sondax

URL : `/modele-sondax` (`site/modele-sondax.html`). Script : `scripts/build_modele.py`,
après `scripts/modele.py`. Contenu et règles : §14.14.2.

---

## 14. Modèle Sondax

### 14.1 Objet

Les sondages donnent des scores et un classement ; ils disent mal si ce classement est
solide. Deux candidats séparés d'un point peuvent avoir des chances très proches
d'accéder au second tour ; un écart apparemment faible peut aussi correspondre à une
situation stable. Le modèle Sondax répond à une seule question :

> **Et si on votait dimanche ?** Avec les sondages disponibles aujourd'hui, qui a
> réellement ses chances d'être au second tour, et à quel point ?

Il **ne prévoit pas** le résultat d'avril 2027 : il mesure la solidité du rapport de
forces observé aujourd'hui. Trois produits restent distincts, sur le site comme dans le
code :

| Produit | Ce qu'il dit |
|---|---|
| Sondages | ce que mesurent les enquêtes |
| Modèle Sondax | ce que ces sondages permettent de dire aujourd'hui de la course au second tour |
| Marchés | ce qu'anticipent les participants des marchés prédictifs |

Jamais sur un même graphe, jamais additionnés (même règle qu'au §11 pour sondages et
cotes).

Quatre questions auxquelles le produit doit répondre :

1. Qui a aujourd'hui ses chances d'être au second tour ?
2. Quels seconds tours restent réellement possibles ?
3. Qui gagne ou perd des chances de qualification ?
4. À quelle distance la situation se trouve-t-elle d'un basculement ? (calculé, non
   affiché depuis le 29 septembre 2026, §14.7)

### 14.2 Architecture et navigation

Trois niveaux de lecture ; la complexité d'un niveau ne remonte jamais au niveau
au-dessus.

| Niveau | Page | Promesse |
|---|---|---|
| 1 | Accueil, bloc `#bloc-modele` | comprendre la situation en moins de dix secondes |
| 2 | `/modele-sondax.html` | explorer et comprendre la course |
| 3 | `/methodologie.html#modele` | vérifier la construction statistique |

- URL de la page produit : `/modele-sondax` ; canonique
  `https://sondax.fr/modele-sondax.html` (fichier `site/modele-sondax.html`), même
  convention que les autres pages, vérifiée par `validate_urls.py`.
- Architecture principale affichée : **Sondages | Modèle Sondax | Marchés | Méthode**.
  Élections passées, Instituts, Tous les sondages et Explorer un sondage restent là où
  ils sont (bandeau et pied de page).
- Seule la sous-navigation de l'accueil change : elle gagne une entrée **« Modèle »**
  vers `#bloc-modele`, entre « Second tour » et « Prédictions ». Le bloc lui-même est
  placé dans la page au même rang, entre `#second-tour` et `#bloc-polymarket`.
- Le bandeau d'en-tête et le pied de page gagnent un lien « Modèle Sondax ».
- La page Méthode reste une seule page : le modèle y est une section ancrée
  (`#modele`), après la méthode de la moyenne.

### 14.3 Règles de ton

Le lecteur regarde les sondages comme il regarde la météo. Aucune connaissance
statistique ne doit être nécessaire.

**Sur l'accueil et la page Modèle, mots interdits** : simulation, probabilité, tirage,
configuration, échantillon, calibration, Dirichlet, variance, distribution.

**Vocabulaire à utiliser** : chances, sur 100, une chance sur trois, dimanche, duel,
second tour, y être, basculer, se rapprocher, s'éloigner, gagner des chances, perdre
des chances.

« Modèle Sondax » est le nom du produit et peut s'employer partout. Les termes qui
décrivent son fonctionnement sont réservés à la page Méthode.

**Contrôle au build.** `build_modele.py` échoue si un mot interdit apparaît dans le
texte rendu du bloc d'accueil ou de `modele-sondax.html`, hors lien vers la Méthode
et hors attributs HTML. La liste des mots est une constante du script, pas un fichier
éditable.

Formats de nombres :

- chances : entier, « 38 sur 100 » ; sous 1 → « moins de 1 sur 100 » ; au-dessus de 99
  → « plus de 99 sur 100 » ;
- évolutions : « +11 en 7 jours », « −5 en 7 jours » (vrai signe moins U+2212),
  « stable » ;

### 14.4 Moyenne d'entrée et configuration du modèle

**La moyenne est celle de la page Méthode, sans exception** : valeur du jour de la
courbe de tendance du §4 (`data/derived/series-t1.json`), c'est-à-dire, par candidat,
l'hypothèse de référence « Attal + Philippe » ou à défaut celle qui compte le plus de
candidats, fenêtre glissante extensible, demi-vie adaptative, **pas de pondération par
échantillon**. Le modèle ne recalcule aucune moyenne à sa façon : il lit la série.

**Configuration du modèle.** Les hypothèses de référence ne portent pas toutes les
mêmes candidats (Glucksmann, Faure ou Hollande à gauche selon l'institut et la date).
La liste des candidats retenus est donc calculée ainsi :

1. prendre les sondages entrant dans la fenêtre de base de 30 jours du jour du calcul ;
2. dans chacun, les hypothèses de tour 1 qui contiennent Attal **et** Philippe ;
3. retenir l'ensemble de candidats le plus fréquent parmi ces hypothèses (« Autre »
   exclu) ; en cas d'égalité, celui de l'hypothèse la plus récente ;
4. retirer tout candidat dont la valeur du jour dans la série est `null` (courbe
   interrompue), et le signaler sur la page de revue.

Sur les données de septembre 2026, cela donne onze candidats : Arthaud, Attal,
Dupont-Aignan, Glucksmann, Le Pen, Mélenchon, Philippe, Retailleau, Roussel, Tondelier,
Zemmour. La liste est écrite dans `modele.json` (`configuration`) ; elle n'est **jamais**
écrite en dur. Si aucune hypothèse de référence n'existe dans la fenêtre, le modèle
n'est pas calculé et le run échoue (§14.18).

**Renormalisation.** Les moyennes des candidats retenus sont ramenées à 100 %
proportionnellement. « Autre » n'entre pas dans le calcul. Un candidat hors
configuration n'a **pas** de chiffre de qualification : ni zéro, ni tiret, rien.

Conséquence à écrire sur la page Méthode : la moyenne affichée sur les courbes
(non normalisée, §4) et le point de départ du modèle (normalisé) diffèrent de quelques
dixièmes. C'est attendu.

### 14.5 Calibration historique — `scripts/calibration.py`

**Question :** de combien la moyenne des sondages de la dernière semaine s'est-elle
trompée, historiquement ?

Pour chaque élection et chaque candidat ayant obtenu un résultat officiel au premier
tour :

- **moyenne** : moyenne simple, sans pondération, des sondages dont le `terrain_fin`
  tombe dans les sept jours précédant le scrutin (J−7 à J−1 inclus) ; un sondage compte
  pour une valeur ; hypothèse retenue : celle qui contient tous les candidats
  officiels, à défaut celle qui en contient le plus ; **rollings compris**, comme au §12
  tant qu'aucune règle n'est décidée ;
- **erreur** : moyenne − résultat officiel, en points.

Élections : présidentielles 2002, 2007, 2012, 2017, 2022 (`data/historique.json`),
européennes 2019 et 2024 (`data/historique_europeennes.json`, §14.16).

Sortie `data/derived/calibration.json`, reconstructible :

```json
{
  "genere_le": "2026-09-28T06:12:00Z",
  "fenetre_jours": 7,
  "jeux": {
    "presidentielles": {
      "elections": ["2002", "2007", "2012", "2017", "2022"],
      "n_comparaisons": 61,
      "erreur_absolue_moyenne": 0.90,
      "ecart_type": 1.40,
      "N_eff": 345.2,
      "par_tranche": {
        "plus_20": { "n": 0, "erreur_absolue_moyenne": 0, "ecart_type": 0 },
        "10_20":   { "n": 0, "erreur_absolue_moyenne": 0, "ecart_type": 0 },
        "moins_10": { "n": 0, "erreur_absolue_moyenne": 0, "ecart_type": 0 }
      },
      "histogramme": [{ "de": -5.0, "a": -4.5, "n": 0 }],
      "principales_erreurs": [
        { "election": "2002", "candidat": "jospin", "moyenne": 0, "resultat": 16.18, "erreur": 0 }
      ],
      "qualifies_annonces_justes": { "2002": false, "2007": true }
    },
    "europeennes": {},
    "ensemble": {}
  }
}
```

(Valeurs nulles de l'exemple : illustratives.) `principales_erreurs` : les dix plus
grandes erreurs absolues. `qualifies_annonces_justes` : les deux premiers de la moyenne
sont-ils les deux qualifiés réels.

**Estimateur de `N_eff`** (méthode des moments, sur les parts normalisées `p`, en
proportion) :

```
N_eff = Σ p(1−p) / Σ erreur² − 1
```

En effet, pour une loi de Dirichlet de paramètre `N_eff · p`,
`Var(Xᵢ) = pᵢ(1−pᵢ)/(N_eff + 1)`.

**Résultat de référence**, reproduit sur `data/historique.json` avec les règles
ci-dessus : 61 comparaisons, erreur absolue moyenne 0,90 point, écart-type 1,40,
`N_eff` ≈ 345. 2002 est la seule année où les deux qualifiés annoncés ne sont pas les
bons. Sans les rollings, on obtient 0,89 / 1,37 / 356 : le choix est documenté, l'écart
est négligeable.

**Deuxième estimation : la moyenne Sondax à J−7** (décision du 28 septembre 2026).
Le moteur part de la moyenne Sondax (§4), pondérée par la récence, pas de la moyenne
simple de la dernière semaine. `calibration.py` estime donc aussi `N_eff` sur les
erreurs de **cette** moyenne, calculée avec les seuls sondages connus sept jours avant
le scrutin (`moyenne_sondax_j7` dans `calibration.json`). C'est cette estimation qui
règle le moteur : on calibre sur ce qu'on publie, à l'horizon de « si on votait
dimanche ». Référence : écart-type 1,86 (présidentielles), 1,56 (européennes), 1,75
(ensemble) ; `N_eff` ≈ 195, 192 et 194. La première version (moyenne simple,
`N_eff` 350) était trop sûre d'elle : voir la comparaison du backtest (§14.17).

**Valeur retenue.** Le script **propose**, il ne décide pas. La valeur utilisée par le
moteur est écrite à la main dans `data/config.json` :

```json
"modele": {
  "N_eff": 190,
  "N_eff_source": "ensemble_sondax_j7",
  "k_melange": 2,
  "tirages": 50000,
  "graine": 20270418
}
```

`N_eff_source` : nom du jeu (`presidentielles`, `europeennes`, `ensemble`), suffixé
`_sondax_j7` quand l'estimation est celle de la moyenne Sondax.

`N_eff` y est arrondi à la dizaine. La page de revue signale (sans bloquer) tout écart
de plus de 20 % entre la valeur retenue et l'estimation du jeu déclaré dans
`N_eff_source`. On ne change de source (`ensemble` après l'import des européennes)
qu'après avoir regardé le backtest (§14.17).

### 14.6 Moteur — `scripts/modele.py`

**Loi.** Chaque premier tour simulé est un vecteur tiré d'une loi de Dirichlet de
paramètre `α = N_eff · p`, où `p` est le vecteur des moyennes normalisées (§14.4). Deux
propriétés justifient ce choix : chaque tirage totalise 100 %, et l'ampleur possible de
l'erreur dépend du niveau du candidat (écart-type ≈ 2,3 points à 25 %, ≈ 0,75 point à
2 % avec `N_eff` = 350).

**Tirages.** 50 000 (`config.json`, `modele.tirages`). Tirage par variables gamma
(`Xᵢ = Gᵢ / ΣG`, `Gᵢ ~ Gamma(αᵢ, 1)`).

**Mélange** (`k_melange`, décision du 28 septembre 2026). Certaines élections, les
sondages se trompent plus que d'autres (2002, 2022). Pour chaque premier tour tiré, le
paramètre n de la Dirichlet est lui-même tiré selon une loi gamma de forme `k` et
d'échelle `N_eff / (k − 1)`, de sorte que `E[1/n] = 1/N_eff` : l'ampleur **moyenne**
des erreurs reste celle qui a été calibrée, seules les queues s'épaississent. `k` = 2,
choisi par leave-one-out sur les présidentielles (perte logarithmique). `null`
désactive le mélange.

**Graine fixe**, la même à chaque run (`config.json`, `modele.graine`) : deux runs sur
les mêmes données donnent exactement le même résultat, et d'un jour à l'autre les
écarts ne viennent que des données, pas du hasard des tirages. Le bruit résiduel de
50 000 tirages est d'environ 0,2 point de chance à 50 sur 100.

**Dépendance.** `numpy` (générateur `numpy.random.default_rng(graine)`). C'est la
première dépendance hors bibliothèque standard ; elle est installée dans les deux
workflows et figée dans un `requirements.txt`. En pur Python, le point de bascule
(plusieurs dizaines de millions de tirages gamma) prendrait plusieurs minutes.

**Comptage**, pour chaque tirage : classer les candidats par part décroissante (égalité
exacte : ordre de la configuration, cas de probabilité nulle en pratique).

- qualification d'un candidat : rang 1 ou 2 ; chance = qualifications / tirages ;
- rangs : 1er, 2e, 3e ou moins ;
- duel : paire non ordonnée des deux premiers, identifiée par les deux slugs dans
  l'ordre alphabétique (même convention que les pages de duel, §7.1).

Toutes les fréquences sont gardées **exactes** (deux décimales) pour les calculs
d'évolution et les tests, et **arrondies à l'entier** pour l'affichage. Une évolution
se calcule sur les valeurs exactes, puis s'arrondit.

### 14.7 Point de bascule

**Calculé, non affiché** (décision du 29 septembre 2026). Le calcul ci-dessous est
conservé : `seuil_bascule` et `delta_bascule` restent dans `modele.json` et
l'historique, et l'événement `bascule_change` reste détecté (§14.10). Mais la notion
n'apparaît plus nulle part sur le site : ni sur la page Modèle, ni sur les fiches
candidat, ni sur la page Méthode, ni dans les textes générés. Les règles d'affichage
qui suivent sont donc en sommeil.

Pour chaque candidat dont la chance de qualification est **inférieure à 50 sur 100**
et qui figure parmi les **quatre premiers** en chances de qualification :

1. faire varier sa part `x` (échelle normalisée) ;
2. rendre ou prendre la différence **proportionnellement à tous les autres** :
   `pⱼ' = pⱼ · (100 − x) / (100 − pᵢ)` — le choix le plus neutre ;
3. relancer le moteur (même graine, donc fonction lisse de `x`) ;
4. chercher par dichotomie le `x` qui donne 50 sur 100, entre `pᵢ` et `pᵢ + 10`,
   tolérance 0,05 point, 20 itérations au plus.

Stocker `seuil_bascule` (= `x`, une décimale) et `delta_bascule` (= `x − pᵢ`, une
décimale). Si 50 sur 100 n'est pas atteint à `pᵢ + 10`, `seuil_bascule` et
`delta_bascule` valent `null`.

**Affichage** : arrondi au demi-point le plus proche, 0,5 minimum (« à environ 1 point »
pour 0,8 ou 1,2 ; jamais « +1,27 point »). Affiché seulement si `delta_bascule` ≤ 4. Jamais
calculé pour un candidat déjà à 50 sur 100 ou plus. Le chiffre public est un ordre de
grandeur, présenté comme tel.

Texte associé : « Avec environ un point de plus dans les sondages actuels, ses chances
d'être au second tour seraient proches d'une sur deux. »

### 14.8 Verdicts

Calculés sur la chance **arrondie affichée**, pour que le mot et le nombre ne se
contredisent jamais :

| Chances | Verdict |
|---|---|
| plus de 90 | Quasi sûr(e) d'y être |
| 60 à 90 | Bien placé(e) |
| 25 à 59 | Rien n'est joué |
| 8 à 24 | Il faudrait une surprise |
| moins de 8 | Très improbable aujourd'hui |

Accord selon `genre` (`candidats.json`) ; entrée `type: parti` au masculin (« le
candidat PS »). **« Hors course » est proscrit** : un événement à 5 ou 7 chances sur 100
reste possible. Les seuils sont des constantes du générateur, ajustables après la
revue de la phase A (§14.21).

### 14.9 Évolutions

Stockées : `evolution_1j`, `evolution_7j`, `evolution_30j`, pour chaque candidat
(qualification) et chaque duel. Définition : valeur exacte du jour − valeur exacte de
la dernière entrée de l'historique datée de J−1, J−7, J−30 ou avant (§14.13). Pas
d'entrée assez ancienne → `null`.

**Affichage** (7 jours par défaut) :

- `« +11 en 7 jours »` / `« −5 en 7 jours »` si |évolution arrondie| ≥ 2 ;
- `« stable »` si |évolution arrondie| ≤ 1.

**Règle unique : l'attribution** (décision du 28 septembre 2026, brief §5.11). Quand un
**seul** sondage est entré dans le calcul depuis 7 jours, l'évolution le nomme :
« +13 en 7 jours, après le sondage Harris du 24 septembre ». Avec deux sondages ou
plus, formulation générale. Un sondage « entré » est un identifiant présent dans
`sondages_utilises` (§14.13) du jour et absent de celui de l'entrée de J−7.
L'ancienne règle des trois sondages (« peu de changement » sous ce seuil) est
supprimée : elle affichait « peu de changement » pour un candidat qui venait de perdre
13 chances à cause d'un seul sondage ; nommer ce sondage est plus honnête.

L'évolution porte sur les **chances**, jamais sur le score dans les sondages : le
libellé le dit (« chances »), et les deux chiffres ne sont jamais juxtaposés sans ce
mot.

### 14.10 Événement du jour — « Ce qui a changé »

Détection déterministe, sans modèle de langue, dans `modele.py`. Deux horizons, dans
l'ordre :

1. **depuis la dernière mise à jour** (`horizon: "maj"`), si au moins un sondage est
   entré depuis ;
2. **sur 7 jours** (`horizon: "7j"`), si au moins un sondage est entré.

Pour chaque horizon, première règle vérifiée dans cet ordre de priorité :

| Priorité | `type` | Condition |
|---|---|---|
| 1 | `duel_principal_change` | le duel le plus fréquent n'est plus le même |
| 2 | `deuxieme_change` | le deuxième candidat en chances de qualification n'est plus le même |
| 3 | `candidate_gain` / `candidate_loss` | variation d'au moins 5 chances pour un candidat (le plus grand écart absolu l'emporte) |
| 4 | `verdict_change` | un candidat change de verdict (§14.8) |
| 5 | `bascule_change` | `delta_bascule` affiché varie d'au moins 1 point |
| 6 | `peu_de_changement` | sinon |

Si aucun sondage n'est entré depuis la dernière mise à jour ni dans les 7 jours :
`type: "aucun_sondage"`.

```json
"changement": {
  "type": "candidate_gain",
  "horizon": "maj",
  "candidate": "philippe",
  "avant": 31.2,
  "apres": 38.4,
  "delta": 7,
  "sondages_declencheurs": ["ifop-2026-09-25"]
}
```

`sondages_declencheurs` : sondages entrés sur l'horizon retenu. Le front choisit la
formulation : **attribuée** si la liste a un élément (« Le sondage Ifop du
25 septembre rapproche Philippe : +7 chances sur 100. »), **générale** sinon
(« Philippe se rapproche. Ses chances d'être au second tour passent de 31 à 38 sur
100. »). L'attribution est plus honnête qu'un « Philippe se rapproche » fondé sur une
seule enquête.

Gabarits (une phrase de titre, une phrase de détail, pas plus) :

| `type` | Titre | Détail |
|---|---|---|
| `duel_principal_change` | « {A} – {B} devient le second tour le plus fréquent. » | chances avant → après |
| `deuxieme_change` | « {X} repasse devant {Y}. » | chances des deux |
| `candidate_gain` | « {X} se rapproche. » | « Ses chances passent de {a} à {b} sur 100. » + conséquence sur les duels si le rang d'un duel change |
| `candidate_loss` | « {X} s'éloigne. » | idem |
| `verdict_change` | « {X} : {verdict}. » | chances avant → après |
| `bascule_change` | aucun texte : événement détecté mais non affiché (§14.7) | — |
| `peu_de_changement` | « Peu de changement aujourd'hui. » | « Le dernier sondage reste proche de la moyenne actuelle et modifie peu la course au second tour. » |
| `aucun_sondage` | « Pas de nouveau sondage depuis la dernière mise à jour. » | — |

« Se rapproche » / « s'éloigne » s'entendent du second tour : ne pas les employer pour
un candidat déjà à plus de 90.

### 14.11 Accroche

Générée à chaque mise à jour, deux phrases au plus, à partir de `modele.json`. Règles
dans l'ordre (`q1 ≥ q2 ≥ q3` : chances de qualification des trois premiers) :

1. **second tour dessiné** — `q2 ≥ 80` et `q3 < 20` : « Le second tour semble se
   dessiner. Les deux premiers ont aujourd'hui une nette avance sur leurs
   poursuivants. » (Phase B : « Le second tour se stabilise. » si, en plus, la règle
   était déjà vérifiée à J−7.)
2. **course serrée** — `q2 − q3 < 15` : « La course à la deuxième place est serrée.
   {X} et {Y} ont des chances très proches d'être au second tour. »
3. **cas général** — « {A} – {B} est aujourd'hui le second tour le plus plausible.
   {C} a {q} chances sur 100 d'y être. » ({C} : le troisième.)

Avec historique (phase B), les formulations de mouvement deviennent possibles, et
**seulement** avec lui : « se resserre » exige que `q2 − q3` ait diminué d'au moins
5 sur 7 jours ; « reste » exige que le duel principal soit le même qu'à J−7 ;
« contre {n} il y a une semaine » exige une entrée d'historique à J−7. Sans
historique, aucun mot ne suppose un changement (« désormais », « reste », « se
resserre » sont exclus en phase A).

### 14.12 Structure de `modele.json`

`data/derived/modele.json`, reconstructible à partir des données et de l'historique.

```json
{
  "date": "2026-09-28T06:12:00Z",
  "revid": 239883627,
  "configuration": ["arthaud", "attal", "dupont-aignan", "glucksmann", "le-pen",
                    "melenchon", "philippe", "retailleau", "roussel", "tondelier", "zemmour"],
  "n_sondages": 12,
  "sondages_utilises": ["harris-2026-09-24", "ipsos-2026-09-09"],
  "N_eff": 350,
  "N_eff_source": "presidentielles",
  "tirages": 50000,
  "graine": 20270418,

  "candidats": {
    "philippe": {
      "moyenne": 17.9,
      "moyenne_normalisee": 18.1,
      "qualification": 38,
      "qualification_exacte": 38.41,
      "verdict": "rien_nest_joue",
      "evolution_1j": 2,
      "evolution_7j": 11,
      "evolution_30j": 15,
      "sondages_entres_7j": 3,
      "rang": { "1": 5, "2": 33, "3plus": 62 },
      "seuil_bascule": 18.5,
      "delta_bascule": 1.0
    }
  },

  "duels": [
    { "candidats": ["le-pen", "melenchon"], "chance": 44, "chance_exacte": 43.87,
      "evolution_1j": -1, "evolution_7j": -6, "evolution_30j": null }
  ],

  "changement": { "type": "candidate_gain", "horizon": "maj", "candidate": "philippe",
                  "avant": 31.2, "apres": 38.4, "delta": 7,
                  "sondages_declencheurs": ["ifop-2026-09-25"] },

  "accroche": { "regle": "general", "titre": "…", "detail": "…" }
}
```

- `n_sondages` : nombre de sondages distincts portant la moyenne du jour ;
  `sondages_utilises` : leurs identifiants (sert à l'attribution, §14.10).
- `duels` : **tous** les duels observés au moins une fois, triés par chance
  décroissante.
- `rang` : entiers arrondis pour l'affichage ; le test de somme (§14.18) porte sur les
  comptes exacts.
- Champs d'évolution et de bascule : absents ou `null` en phase A ; le front les ignore
  alors sans message.

### 14.13 Historisation — `data/modele_history.json`

À chaque run de collecte, une entrée est **ajoutée** :

```json
{
  "date": "2026-09-28T06:12:00Z",
  "reconstitue": false,
  "configuration": ["…"],
  "sondages_utilises": ["…"],
  "moyennes": { "philippe": 18.1 },
  "qualification": { "philippe": 38.41 },
  "rangs": { "philippe": { "1": 5.02, "2": 33.39, "3plus": 61.59 } },
  "duels": { "le-pen+melenchon": 43.87 },
  "delta_bascule": { "philippe": 1.0 }
}
```

**Écart assumé avec la demande initiale** : le fichier est versionné dans `data/`, pas
dans `data/derived/`. `data/derived/` est ignoré par git et supprimable sans perte
(§9) ; un historique de ce que le site a affiché, lui, ne se reconstruit pas. Il est
commité avec les données dans la pull request de collecte. Une PR non fusionnée perd
son entrée : l'historique a alors un trou, et les évolutions prennent la dernière
entrée disponible avant la date cible.

**Amorçage** : une exécution unique (`modele.py --reconstituer`) calcule une entrée
par jour depuis le premier sondage de référence (fin mai 2026), avec les sondages dont
`terrain_fin` ≤ jour, marquées `reconstitue: true`. Elles alimentent la courbe
« Depuis le début » ; la page Méthode signale qu'elles sont recalculées après coup.

Usages : évolutions 1 j / 7 j / 30 j, courbes (§14.14.5), contenus partagés (§14.15),
événement du jour (§14.10).

### 14.14 Pages et blocs

#### 14.14.1 Bloc d'accueil (`#bloc-modele`)

Rendu au build (contrainte générale du §1) par `scripts/build_modele.py`
(`bloc_accueil`). Version simplifiée (décision du 29 septembre 2026), de haut en bas :

1. **Surtitre** « Modèle Sondax ».
2. **Titre** : « Qui serait au second tour si on votait dimanche prochain ? »
3. **Une phrase**, sans gras, générée (`phrase_duel_principal`) : « {duel le plus
   fréquent} reste, au vu des sondages les plus récents, le second tour le plus
   plausible. » ; « est » au lieu de « reste » si ce duel n'était pas le plus fréquent
   à la référence de 7 jours.
4. **Gaufre de 100 carrés et liste des duels** : variante « accueil » du composant de
   la page Modèle (`composant_duels(…, variante="accueil")`, une seule fonction). Ni
   titre ni phrase d'explication. Chaque ligne : pastille, duel, « {n} chances sur
   100 » (« 1 chance sur 100 » au singulier), variation datée « +13 depuis le 21/9 » /
   « −12 depuis le 21/9 » / « stable » si l'écart arrondi est nul. La date affichée
   est J−7 par rapport à la mise à jour, à l'heure de Paris (21/9 pour une mise à
   jour du 28/9), au format j/m sans zéro initial ; la valeur comparée est celle en
   vigueur ce jour-là, c'est-à-dire la dernière entrée d'historique datée de J−7 ou
   avant (§14.9), qui peut être plus ancienne quand aucun sondage n'est entré entre
   les deux. Pas de variation s'il n'existe aucune entrée à J−7. « Autres scénarios ·
   {n} chances sur 100 » en ligne grisée, sans variation. Sous 600 px : gaufre
   au-dessus de la liste, variation sous les chances.
5. **Lien texte** : « Comment ces probabilités sont-elles calculées ? → » vers
   `methodologie.html#modele`. Seule exception à la liste des mots interdits (§14.3),
   déclarée dans `EXCEPTIONS_VOCABULAIRE`.

Plus de bouton, de ligne de contexte, d'accroche développée ni de barres par
candidat sur l'accueil. Le nombre de sondages et la date de mise à jour restent
affichés sur la page Modèle (ligne de contexte). L'accroche du jour (§14.11) reste
calculée : elle sert à la page Modèle, à la meta description et au partage.

#### 14.14.2 Page « Le modèle Sondax » (`/modele-sondax`)

Structure (décision du 29 septembre 2026), dans cet ordre et rien d'autre :

1. **Titre** : « Le modèle Sondax », sans surtitre, suivi d'une ligne discrète
   « Calculé le {date} à partir de {N} sondages » (`date` et `n_sondages` de
   `modele.json`, date du jour à Paris ; décision du 30 septembre 2026).
2. **« Comment fonctionne ce modèle ? »** (ancre `#comment-fonctionne`, cible du
   lien « Comment ces probabilités sont-elles calculées ? » de l'accueil). Texte fourni
   tel quel (`EXPLICATION` dans `build_modele.py`), quatre paragraphes. Le nombre de
   tirages vient de `modele.json` ; le nombre de l'exemple (« 30 000 simulations sur
   50 000 ») en est 60 %, pour rester juste. Les deux premiers paragraphes sont
   visibles, les deux derniers repliés sous « Lire la suite » (`<details>` natif ; le
   lien disparaît une fois le texte déplié). Ce texte est exclu du contrôle des mots
   réservés (§14.3), le reste de la page y reste soumis.
3. **« Chances d'être au second tour »** : tous les candidats de la configuration,
   par chances décroissantes. Par ligne : photo, nom, barre, « {n} sur 100 »,
   verdict, évolution 7 jours (§14.9). Pas de point de bascule (§14.7).
4. **« Évolution des chances d'être au second tour »** : sélecteur 7 jours | 30 jours
   | Depuis le début, une courbe par candidat, les quatre premiers cochés par défaut.
   Les candidats remplacés (`succede_a` dans `candidats.json` : Bardella) ne sont pas
   proposés ; l'historique n'est pas modifié. Titre et axe disent « chances sur
   100 », jamais « % ».

Retirés de la page (le code reste, pour l'accueil ou un usage ultérieur) : sous-titre
et introduction, « Aujourd'hui », « Ce qui a changé », « Les seconds tours
possibles » (composant partagé avec l'accueil, §14.14.1), « Qui finit où ? »,
« Comment lire ces chiffres », bouton Partager. Métadonnées : `<title>` « Qui serait
au second tour si on votait dimanche ? — Modèle Sondax », meta description générée à
partir de l'accroche, `og:image` du jour (§14.15).

#### 14.14.3 Fiches candidat (§13.1)

Sous le score moyen, bloc « Et si on votait dimanche ? » :

- « {n} chances sur 100 d'être au second tour » ;
- verdict ;
- évolution 7 jours (phase B) ;
- « Son second tour le plus fréquent : face à {X}. » — le duel le plus fréquent qui
  contient le candidat ; affiché seulement si ses chances sont d'au moins 8 ;
- petite courbe « Évolution de ses chances de qualification », 7 jours / 30 jours
  (phase B).

Bloc **absent** si le candidat n'est pas dans la configuration.

#### 14.14.4 Pages duel (§7.1, §13.4)

Sur chaque page de duel existante dont le duel figure dans `modele.json` :

```text
Le Pen – Philippe
31 fois sur 100 aujourd'hui
22 il y a une semaine
+9 en 7 jours
```

avec un libellé de rang : 1er → « Le second tour le plus fréquent aujourd'hui » ;
2e → « Le deuxième second tour le plus fréquent », complété de « près d'un second tour
sur {k} » quand `100/k` est à moins de 3 de la valeur pour `k` ∈ {2, 3, 4, 5} ;
moins de 5 → « Peu fréquent aujourd'hui ». Un duel du modèle sans page (moins de
5 sondages, §7) n'en reçoit pas pour autant : il reste listé sur la page Modèle.

Le bloc est visuellement séparé des intentions de vote de second tour : il ne dit rien
du vainqueur du duel (§14.20).

#### 14.14.5 Courbes

Données lues dans `modele_history.json`. Courbes en **SVG rendu au build**
(`scripts/courbes_modele.py`), pas en Chart.js : elles sont présentes dans le HTML
servi (contrainte du §1) et le JavaScript ne fait que changer de période et masquer
ou afficher un candidat. Tracé en marches, sans interpolation : les chances ne
changent qu'à l'entrée d'un sondage. Points reconstitués (§14.13) sans distinction
visuelle, mais signalés sous la courbe et sur la page Méthode.

### 14.15 Partage

Images générées au build par `scripts/partage_modele.py` (Pillow ; polices du site,
Space Grotesk et IBM Plex Sans, embarquées dans `scripts/fonts/` sous licence OFL),
dans `site/partage/` (ignoré par git), nom daté pour contourner les caches
(`modele-2026-09-28-og.png`). `site/partage/modele.json` donne au bouton le gabarit,
la phrase et les chemins ; l'`og:image` de la page Modèle pointe vers l'image du
jour (`render_page(og_image=…)`).

| Format | Taille | Usage |
|---|---|---|
| `og` | 1200 × 630 | OpenGraph, LinkedIn, X (carte large) |
| `carre` | 1080 × 1080 | messageries, réseaux mobiles |

Trois gabarits, choisis par le type d'événement du jour :

1. **duel principal** (défaut) : « Et si on votait dimanche ? » / « Le Pen – Mélenchon »
   / « Le second tour le plus fréquent aujourd'hui. » ;
2. **mouvement** (`candidate_gain`/`candidate_loss` sur 7 jours) : « Philippe gagne
   11 chances d'être au second tour en une semaine. » ;
3. **course serrée** (`deuxieme_change`, ou accroche « course serrée ») : « La course à
   la deuxième place devient indécise. »

Chaque image porte « sondax.fr », la date et « Ne prédit pas avril 2027 ».

**Bouton « Partager »** : `navigator.share` (avec l'image quand
`navigator.canShare({files})` l'accepte) ; sinon menu avec « Copier la phrase »,
« Copier le lien », « Télécharger l'image ». La phrase copiée est le titre de
l'accroche suivi du lien. Aucun bouton tiers ni script de réseau social. Événement
GoatCounter `partage/<gabarit>/<methode>` ajouté à la liste fermée du §8.

### 14.16 Import des européennes — `scripts/import_europeennes.py`

Même démarche que `import_historique.py` (§12) : pages Wikipédia anglaises figées par
`revid`, snapshots dans `data/snapshots/historique/`, sortie unique
`data/historique_europeennes.json` au même schéma que `historique.json` (listes
plutôt que candidats : l'identifiant est le slug du sigle de la colonne,
`type: "liste"`). Élections : 2019, 2024. Uniquement les sondages nationaux.

- **2019** : « Opinion polling for the 2019 European Parliament election in France »
  (revid 1306346350) ; le résultat officiel est la ligne de l'élection en tête du
  tableau.
- **2024** : pas de page de sondages en anglais ; tableau de la section « Opinion
  polling » de « 2024 European Parliament election in France » (revid 1370942182).
  Résultat : voix du modèle `{{Election results}}` du même article, rapportées au
  total des exprimés, avec une correspondance liste → colonne écrite à la main
  (`RESULTATS_2024`). Les listes sondées sans liste correspondante au scrutin (GE,
  PS dissident, NE, DLF) n'ont pas de résultat et n'entrent pas dans les
  comparaisons.
- Une ligne dont le nombre de cellules ne correspond pas à l'en-tête est écartée et
  comptée (18 en 2024, toutes de 2023 : hypothèses de listes d'union) ; une cellule
  fusionnée sur plusieurs listes va dans `scores_groupes`, « <0,5 » dans
  `scores_inferieurs_a`.

Référence au 28 septembre 2026 : européennes seules, 34 comparaisons, erreur absolue
moyenne 0,83, écart-type 1,44, `N_eff` ≈ 227 ; ensemble, 95 comparaisons, 0,88, 1,41,
`N_eff` ≈ 300. Le défaut de la loi entre 10 et 20 % se retrouve (LR 2019 : +4,5 ;
EELV 2019 : −5,7). `N_eff_source` reste `presidentielles` en attendant une
décision.

Précaution : les européennes comptent beaucoup de listes (plus de 30 en 2024) ; les
petites listes non sondées n'entrent pas dans les comparaisons (même règle que la
présidentielle : un candidat non sondé n'a pas de moyenne).

### 14.17 Backtest — `scripts/backtest.py`

**Question :** qu'aurait affiché Sondax avant les présidentielles précédentes ?

Pour chaque présidentielle 2002-2022, **en leave-one-out** : calibrer `N_eff` sur toutes
les autres élections (présidentielles et européennes), avec l'estimateur du moteur
(moyenne Sondax à J−7), puis, pour l'élection testée :

1. ne garder que les sondages dont `terrain_fin` ≤ J−7 ;
2. calculer la moyenne **avec le code de la courbe** (`series_historique.py`, même
   méthode qu'en 2027, §12), valeur à J−7 ;
3. configuration : candidats officiels ayant une moyenne ;
4. appliquer exactement le moteur actuel (même nombre de tirages, même graine) ;
5. chances de qualification, rangs, duels ;
6. comparer au résultat réel.

Sortie `data/derived/backtest.json` et deux tableaux :

```text
Élection | candidat | moyenne | chances de qualification | qualifié ?
Élection | duel principal Sondax | chances | duel réel | chances du duel réel
```

Plus, sur l'ensemble des cinq runs : **score de Brier** et **table de fiabilité** par
tranche de chances (0-10, 10-25, 25-60, 60-90, 90-100 : nombre de cas, moyenne annoncée,
fréquence observée). Un résultat donné à 10 sur 100 doit correspondre à un événement
rare mais possible.

À regarder en priorité : 2002 (chances annoncées pour Le Pen) et 2022.

`backtest.json` contient aussi une **comparaison** avec la méthode de la phase A
(moyenne simple, présidentielles, sans mélange) : Brier, perte logarithmique et
chances données au qualifié le moins attendu de chaque élection. Au 28 septembre
2026 : perte logarithmique 0,159 → 0,125 ; Le Pen 2002 : 1,3 → 4 sur 100.

Deux réserves à écrire telles quelles sur la page Méthode : cinq élections, c'est peu,
toute conclusion reste prudente ; et l'horizon du backtest (sondages à J−7) est plus
dur que celui de la calibration (sondages de la dernière semaine), ce qui pénalise un
peu le modèle.

### 14.18 Tests et validation

`scripts/validation.py` échoue (exit 1, pas de PR) si `modele.json` manque ou si l'un
des contrôles suivants échoue. Tests unitaires dans `scripts/test_modele.py`, lancés par
`validation.py` :

- chaque tirage totalise 1 (tolérance 1e-9) ;
- somme des comptes de qualification = 2 × tirages exactement ;
- pour chaque candidat, somme des comptes de rangs = tirages ;
- somme des comptes de duels = tirages ;
- aucune chance < 0 ni > 100 ;
- deux runs avec la même graine donnent un `modele.json` identique (hors `date`) ;
- vecteur test `[40, 20, 15, 10, 8, 7]`, `N_eff` = 350 : chances du candidat à 40 ≥ 99 ;
- vecteur test `[30, 20, 20, 15, 15]` : les deux candidats à 20 ont des chances égales
  à 1 point près (symétrie) ;
- point de bascule : `seuil_bascule` donne bien 50 ± 1 sur 100 quand on relance le
  moteur avec ce seuil ;
- `configuration` non vide et contenant au moins trois candidats ;
- mélange : chaque tirage totalise 100, même graine même résultat, et la variance de
  chaque part reste celle de `N_eff` à 5 % près.

Pas de test sur les sommes des chiffres **arrondis** : 200 et 100 n'y sont pas garantis,
et ce n'est pas une erreur.

### 14.19 Page Méthode — section `#modele`

Destinée au lecteur qui veut vérifier. Titre de section : « Comment fonctionne le
modèle Sondax ? ». Tous les chiffres viennent de `calibration.json`, `backtest.json` et
`config.json`, injectés au build entre marqueurs (`<!-- BEGIN:methode-modele -->`),
**jamais codés en dur**.

1. **Point de départ** : moyenne du jour, configuration de référence, renormalisation,
   « Autre » exclu, candidats hors configuration sans chiffre (§14.4).
2. **Erreurs historiques** : élections, nombre de comparaisons, erreur absolue moyenne,
   écart-type, histogramme, erreurs par tranche, dix plus grandes erreurs (§14.5).
3. **50 000 premiers tours** : loi de Dirichlet centrée sur les intentions de vote ;
   total de 100 % ; ampleur des erreurs selon le niveau du candidat.
4. **Calibration** : formule de `N_eff`, valeurs par jeu (présidentielles,
   européennes, ensemble), valeur retenue et pourquoi.
5. **Comptage** : qualification, rang, duel ; arrondis.
6. **Backtest** : tableaux et table de fiabilité, réserves (§14.17).
7. **Limites de la loi** (§14.20).
8. **Ce que le modèle ne fait pas** (§14.20), et la phrase centrale : « Le modèle Sondax
   mesure la solidité du classement observé aujourd'hui. Il ne prédit pas le résultat
   de l'élection d'avril 2027. »

### 14.20 Validation de la loi, limites, hors périmètre

**Validation** (dans `backtest.py`, sortie dans `backtest.json`) : comparer, sur les
erreurs historiques, la loi de Dirichlet calibrée à ce qu'on observe :

- variance globale ;
- queues : part des erreurs au-delà de 2 et 3 écarts-types attendus ;
- erreurs selon le niveau : plus de 20 %, 10 à 20 %, moins de 10 % ;
- corrélations entre erreurs des candidats d'une même élection. La Dirichlet n'impose
  que des corrélations **négatives** et faibles ; une sous-estimation commune à deux
  candidats proches (même électorat) ne peut pas y être reproduite.

Les limites constatées sont **documentées** sur la page Méthode. Le moteur n'est pas
complexifié en conséquence sans décision explicite : modèle simple, backtest,
transparence.

**Le modèle ne fait pas** : correction de biais supposés (petits candidats, dynamique,
instituts) ; pondération par institut ; prévision de l'évolution des intentions de
vote ; prise en compte de campagnes, débats, retraits ou événements futurs.

**Hors périmètre v1** : chances de gagner l'élection ; résultat du second tour ;
prédiction d'avril 2027 ; scénarios de retrait ; candidatures hypothétiques ; correction
manuelle des biais ; pondération par institut ; modèle d'événements futurs ; prévision
des intentions de vote.

### 14.21 Tests de compréhension

Avant publication, sur la version de la phase A, faire répondre quelques lecteurs non
spécialistes :

- Que signifie « 38 chances sur 100 » ?
- Sondax dit-il que Philippe fera 38 % ?
- Sondax prédit-il avril 2027 ?
- Que signifie « +11 en une semaine » ?
- Quelle différence entre la courbe des sondages et la courbe du modèle ?

Une confusion importante impose de revoir le wording avant publication. Les réponses
et les changements décidés sont consignés dans la PR correspondante.

### 14.22 Production

- `collecte.yml` : après `series.py`, `modele.py --historiser` (calcul + ajout d'une
  entrée à `modele_history.json`), puis `validation.py --modele` (modele.json présent,
  tests du §14.18) ; `modele_history.json` est ajouté au commit de collecte.
- `pages.yml` : `calibration.py`, `backtest.py`, `modele.py` (sans historiser),
  `partage_modele.py`, `build_modele.py` (après les fiches candidat et les pages duel,
  dans lesquelles il injecte ses blocs), `build_methode_modele.py`, avant
  `build_sitemap.py`. Dépendances : `requirements.txt` (numpy, Pillow).
- `modele.py` recalcule la série en mémoire avec les hypothèses principales
  (`principale.py`), comme au déploiement : la collecte, qui ne lance pas
  `principale.py`, obtient ainsi les mêmes chiffres que le site.
- **Loi du 19 juillet 1977** (§10) : `scripts/veille.py` (dates de `config.json`,
  heure de Paris). En veille, le bloc d'accueil et la page Modèle n'affichent qu'un
  avis, les blocs des fiches candidat et duel sont vidés, aucune image de partage
  n'est produite et aucune entrée n'est ajoutée à l'historique. Le module ne couvre
  encore que le modèle : le reste du site (courbes, derniers sondages) n'a pas de
  veille à ce jour.
- **Point juridique à trancher avant mise en ligne** : un chiffre dérivé de sondages
  est vraisemblablement un « commentaire de sondage » au sens de la loi de 1977 ; les
  mentions obligatoires (§10) doivent être accessibles depuis la page Modèle (lien vers
  la liste des sondages utilisés, avec leurs notices).
- Mise en ligne après accord explicite (§9).

### 14.23 Ordre de développement

**Phase A — voir le produit** (en local, deux sessions ; c'est sur elle que se règlent
le wording et les seuils).

| Étape | Contenu | Critère de fin |
|---|---|---|
| A1 | `calibration.py` sur les présidentielles | 61 comparaisons, 0,90, 1,40, `N_eff` ≈ 345 ; 2002 seule année aux qualifiés faux |
| A2 | `modele.py` → `modele.json` (chances, rangs, duels) ; tests §14.18 hors bascule | tests verts |
| A3 | Page Modèle : §14.14.2 sections 1, 2, 4, 6, 7 ; sans évolution, bascule ni historique | rendu statique, mots interdits contrôlés |
| A4 | Bloc d'accueil : titre, accroche (règles 1 à 3 de §14.11, sans mots de changement), candidats, bouton, ligne de contexte | idem |

Puis revue en local, mobile et desktop ; ajustement des seuils de verdict et du
wording sur les chiffres réels ; tests de compréhension (§14.21).

**Phase B — compléter.**

| Étape | Contenu |
|---|---|
| B1 | Import européennes, recalibration, `N_eff_source` mis à jour si le jeu `ensemble` est retenu |
| B2 | `backtest.py` leave-one-out, `backtest.json`, validation de la loi (§14.20) |
| B3 | `modele_history.json` à chaque run, amorçage ; évolutions 1 j / 7 j / 30 j avec la règle de §14.9 |
| B4 | « Ce qui a changé » (§14.10) avec attribution ; accroches et mouvement de l'accueil |
| B5 | Point de bascule (§14.7), affichage borné |
| B6 | Courbes de la page Modèle |
| B7 | Fiches candidat et pages duel (§14.14.3, §14.14.4) |
| B8 | Partage (§14.15) |
| B9 | Section Méthode (§14.19), chiffres tirés de `calibration.json` et `backtest.json` |
| B10 | Production (§14.22) |

---

## 15. Rétro-Sondax

**Objet.** Un bloc de la page d'accueil répond chaque jour à la question « À J-x de la
présidentielle, qui était en tête des sondages ? » pour 2022, 2017, 2012 et 2007. x est
recalculé à chaque build à partir de la date du premier tour 2027
(`series_historique.TOUR1_2027`, 18 avril 2027). Hors de J-365 à J-1, le bloc n'est pas
rendu.

Pas de résultats électoraux, pas de mention « qualifié » ou « élu ». Uniquement ce que
disaient les sondages à cette date.

**Variante de `precedentes-elections.html`.** Le même calcul sert la page des
présidentielles passées, avec un curseur de J-365 à J-30 et six colonnes : 2027 (point
de comparaison), 2022, 2017, 2012, 2007 et 2002. `retro.json` contient donc aussi 2002 et
2027. Pour 2027, les sondages sont ceux de `data/sondages.json` (hypothèse principale
selon `declare_le`, comme pour la tendance de la home) et seuls les jours déjà écoulés
ont une valeur : au-delà, la colonne affiche « Date à venir ». Le bloc est rendu au
build par `build_retro.rendre_bloc_page()`, puis `assets/bloc-retro.js` le recalcule au
déplacement du curseur.

**Données.** Aucune extraction propre : le calcul lit `data/historique.json` (§12,
en.wikipedia, figé par revid) et, pour les couleurs et les noms courts,
`data/derived/historique.json` (`series_historique.py`). Premier tour uniquement.
Identifiants propres à chaque élection : « Le Pen 2017 » et « Le Pen 2027 » ne partagent
rien.

**Hypothèse principale.** Une seule hypothèse T1 par sondage, désignée par la règle de
`principale.py` (§4) : aucun `declare_le` pour ces élections, donc repli sur l'hypothèse
comptant le plus de candidats, puis la première dans l'ordre de la page. Les autres
hypothèses T1 sont écartées du calcul : un candidat absent de l'hypothèse principale n'a
pas de score dans ce sondage (sans quoi Juppé et Fillon, testés en 2011 à la place de
Sarkozy, entreraient dans le classement 2012).

**Candidats non désignés** (même règle que le site, §3.1 et §4). Tant que le parti n'a
pas désigné son candidat, la personne qu'il présente dans une hypothèse est remplacée
par une entrée `type: parti` (« Candidat LR », « Candidat PS », « Candidat UMP »), qui
garde la personne testée (`teste`). Désignation exclue, comparée au `terrain_fin` :

| Élection | Parti | Désigné le | Personnes rattachées |
|---|---|---|---|
| 2022 | LR | 4 décembre 2021 | Bertrand, Pécresse, Barnier, Baroin, Ciotti, Juvin, Payre, Retailleau, Wauquiez |
| 2017 | LR | 27 novembre 2016 | Juppé, Sarkozy, Fillon, Le Maire, Kosciusko-Morizet, Copé |
| 2017 | PS | 29 janvier 2017 | Hollande, Valls, Montebourg, Hamon, Peillon |
| 2012 | PS | 16 octobre 2011 | Hollande, Aubry, Strauss-Kahn, Royal, Delanoë, Fabius |
| 2007 | PS | 16 novembre 2006 | Royal, Strauss-Kahn, Fabius, Jospin, Lang, Hollande |
| 2007 | UMP | 14 janvier 2007 | Sarkozy, Villepin, Alliot-Marie, Chirac |

Une hypothèse qui teste plusieurs de ces personnes (Sarkozy et Villepin en 2006,
Hollande et Montebourg en 2016) : la première de la liste occupe la place du parti, les
autres restent des candidats à part entière. Guaino (2017) et Mélenchon (2007), testés
en dissidents, ne sont pas rattachés. L'entrée de parti s'efface au premier sondage
postérieur à la désignation : la fenêtre glissante ne la fait pas survivre à côté du
candidat désigné.

**Calcul.** Même fonction que la courbe de la home (`series.calculer_series`, §4),
prolongée jusqu'à la veille du scrutin. Au build, pour chaque élection et chaque J-x de
365 à 1, les quatre premiers et leur valeur. Si la fenêtre de 30 jours contient moins de
2 sondages, on prend l'hypothèse principale du sondage le plus proche de la date (le
plus ancien à égalité) et on marque `approx: true`. `teste` d'une entrée de parti : la
personne de l'hypothèse principale la plus récente à cette date.

Contrôle de somme (§8, règle 1) sur les hypothèses principales de la période, signalé à
l'exécution, non bloquant (données figées, §12).

**Sortie.** `data/derived/retro.json` :

```json
{
  "premier_tour_2027": "2027-04-18",
  "elections": {
    "2017": {
      "premier_tour": "2017-04-23",
      "source": {"url": "https://en.wikipedia.org/w/index.php?oldid=1213598918", "revid": 1213598918},
      "non_designes": [{"id": "candidat-lr", "designation": "2016-11-27"}],
      "candidats": {"candidat-lr": {"nom": "Candidat LR", "nom_court": "Candidat LR",
                                    "couleur": "#2F80ED", "type": "parti"}},
      "jours": {"201": {"date": "2016-10-04", "approx": false,
                        "top": [{"id": "candidat-lr", "v": 22.0, "teste": "juppe"}]}}
    }
  }
}
```

**Rendu.** `scripts/build_retro.py`, entre `<!-- BEGIN:bloc-retro -->` et
`<!-- END:bloc-retro -->` de `site/index.html`, juste après le bloc de la courbe du
premier tour et avant la galerie des candidats. Ancre `#retro-sondax`. CSS :
`site/assets/bloc-retro.css`.

Mise à jour quotidienne. Le bloc statique porte le J-x du jour du build ; `pages.yml`
se relance chaque jour (cron `5 0 * * *`, UTC). En complément, `site/assets/bloc-retro.js`
recalcule au chargement le J-x du compte à rebours du header (`window._joursAvantT1_2027`) ;
s'il diffère de celui du bloc, il charge `data/derived/retro.json` et régénère sous-titre
et grille avec le même HTML que `rendre_bloc()`. Hors de 1 à 365, ou si le JSON ne se
charge pas, le bloc statique reste en place.

Bloc `.bloc` standard :
- titre h2 en Space Grotesk : « Rétro-Sondax » ;
- sous-titre gris : « À J-201 de la présidentielle, qui était en tête des sondages ? »
  (x dynamique) ;
- grille 4 colonnes (2022, 2017, 2012, 2007), 4 lignes. Chaque cellule : nom court en
  Space Grotesk 600, score en gras `tabular-nums`, barre fine de 4 px à la couleur du
  candidat (largeur relative au premier de la colonne), comme dans le bloc « Dernier
  sondage ». Un candidat de `type: parti` s'affiche en gris avec la note « <Nom>
  testé(e) » sous la barre. La hauteur de la note est réservée dans toutes les cellules
  pour que les quatre lignes restent alignées d'une colonne à l'autre ;
- pas de surtitre mono, pas de date sous l'année, pas de note de bas de bloc ;
- mobile : 2 colonnes × 2 (2022 / 2017 puis 2012 / 2007).

Page Méthode : paragraphe `#retro-sondax` (source, règle des candidats non désignés,
fenêtre de 30 jours).
