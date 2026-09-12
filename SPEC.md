# Sondax — spécification

Agrégateur public des données quantitatives sur l'élection présidentielle française de 2027 :
sondages d'opinion et probabilités implicites issues des marchés de prédiction.

Ce fichier fait autorité. En cas de doute sur une structure de données ou une règle de
méthode, s'y référer plutôt que d'improviser. Toute évolution des règles ci-dessous se
décide explicitement et se répercute ici.

---

## 1. Périmètre v1

Un site d'une seule page, trois blocs :

1. **Tendance des sondages, premier tour.** Une courbe par candidat, semaine après semaine.
2. **Cotes Polymarket.** Évolution des probabilités implicites par candidat.
3. **Fiche technique.** Sélection d'une configuration puis d'un sondage, et affichage
   de ses caractéristiques et de ses marges d'erreur (voir §5).

S'y ajoute un sélecteur de duel de second tour (voir §7).

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

Deux API publiques, sans authentification.

Découverte des marchés :

```
GET https://gamma-api.polymarket.com/events?slug=next-french-presidential-election
```

L'événement (id `79987`) contient un marché binaire par candidat. Pour chaque marché :
`slug`, `question`, `outcomePrices`, et `clobTokenIds` dont le **premier élément est le
token « Yes »**.

Historique quotidien :

```
GET https://clob.polymarket.com/prices-history?market={token_yes}&interval=max&fidelity=1440
```

Retourne `{"history": [{"t": unix_ts, "p": prix}, ...]}`. La série remonte à novembre 2025.

Le mapping vers le référentiel candidats se fait sur le **`slug` du marché**, stable,
jamais sur la question en anglais.

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
    "slug_polymarket": "will-marine-le-pen-win-the-2027-french-presidential-election"
  },
  "candidat-ps": {
    "nom": "Candidat PS",
    "parti": "PS",
    "type": "parti",
    "couleur": "#FF8080",
    "alias_wikipedia": ["Candidat PS"],
    "slug_polymarket": null
  }
}
```

Aucune création automatique d'entrée : un candidat inconnu fait échouer le run (§8).

Les identifiants sont des **slugs simples** (`le-pen`, `attal`). En cas d'homonymie
future, l'entrée est désambiguïsée à la main (`le-pen-marine`) et l'ancien alias reste
dans `alias_wikipedia`.

**Résolution des noms.** Le parser lit un nom court dans le wikitexte et ne l'écrit
jamais tel quel : il le résout via `alias_wikipedia` vers un identifiant du référentiel.
Un nom sans correspondance est une erreur bloquante (§8, règle 2), jamais une entrée
créée à la volée.

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
  "candidats": {
    "le-pen-marine": {
      "market_id": "679018",
      "token_yes": "55764212211467781322980371912612507865974994976253196346176314491480419639168",
      "prix_actuel": 0.355,
      "historique": [{ "d": "2026-09-06", "p": 0.352 }]
    }
  }
}
```

---

## 4. Traitement des sondages

**Sélection de l'hypothèse (tour 1) — par candidat, pas par sondage.** Pour chaque
candidat et chaque sondage, on retient l'hypothèse qui contient ce candidat et compte le
plus de candidats testés. **En cas d'égalité, on moyenne les hypothèses concernées.**

Exemple constaté : Elabe du 27/03/2026 teste Le Pen à 31,5 dans une hypothèse à
11 candidats et à 34,0 dans une autre à 11 candidats également. La valeur retenue pour
ce sondage est 32,75.

Deux règles antérieures ont été écartées en développant le front, chacune pour une
raison précise :

- *Le plus de candidats officiellement déclarés* : Wikipédia ne publie pas cet état et
  l'entretenir à la main serait une charge permanente.
- *Une seule hypothèse principale par sondage* : elle faisait alterner Le Pen et
  Bardella au gré des sondages et hachait les deux courbes. Un sondage de mars 2026 peut
  tester six hypothèses, quatre avec Bardella et deux avec Le Pen — retenir la seule
  hypothèse « principale » jetait les mesures de l'autre candidat, pourtant réelles.

Conséquence à assumer et à afficher sur le site : **les courbes ne s'additionnent pas à
100 %**, chaque candidat étant mesuré dans l'hypothèse qui lui est la plus favorable en
nombre de candidats testés. Le graphe montre des trajectoires individuelles, pas une
répartition. Les courbes de tendance n'utilisent que les
hypothèses principales ; les autres restent accessibles dans le bloc fiche technique.

La règle ne s'applique pas au tour 2 : tous les duels sont également valides.

**Courbe de tendance.**

- Fenêtre glissante de **30 jours**, pas de fenêtre en nombre de sondages. Cette fenêtre
  n'est pas le paramètre de lissage : elle ne sert qu'à écarter les sondages de poids
  négligeable. C'est la demi-vie ci-dessous qui règle la réactivité de la courbe.
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

Le bloc Polymarket dispose de **son propre sélecteur, indépendant** de celui des
sondages. Les deux historiques n'ont pas la même profondeur (les cotes remontent à
novembre 2025) et les deux graphes ne mesurent pas la même chose (§11).

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

Un duel est une hypothèse avec `tour: 2` et exactement deux candidats. Sélecteur à deux
noms dans l'interface.

**En dessous de 5 mesures pour un duel donné, afficher un tableau des sondages, pas une
courbe.** Trois points sur dix mois ne constituent pas une tendance.

---

## 8. Validation

Le script de collecte **ne commite rien** si un contrôle échoue. Il s'arrête et signale.

1. La somme des scores d'une hypothèse, **colonne « Autre » incluse**, est comprise
   entre 95 et 105 au tour 1, entre 99 et 101 au tour 2. « Autre » entre dans le
   contrôle mais reste exclu des courbes et des fiches candidat.
2. Tous les candidats rencontrés existent dans `candidats.json`.
3. Le nombre total de sondages n'a pas diminué par rapport au run précédent.

Ne pas ajouter de contrôle supplémentaire par anticipation. On en ajoutera au vu de cas
réels.

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
  polymarket.json
  historique.json                 2002-2022, produit une fois (§12)
  /snapshots                     wikitexte brut, immuable
  /snapshots/historique           wikitexte anglais, immuable
  /derived                       séries précalculées, jetable
/scripts
  collecte_wikipedia.py          dérivé du prototype parse_wikipedia.py
  collecte_polymarket.py
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
corrompu (`will-jean-luc-mlenchon-...`, accent perdu à la création). Le champ
`slug_polymarket` reste éditable à la main dans `candidats.json`.
- Les marchés Polymarket sont en `negRisk` : les prix d'un même événement sont couplés
  et se normalisent d'eux-mêmes. **Ne pas renormaliser.** Afficher les prix bruts.
- L'événement compte 128 marchés. Filtrer à l'affichage (probabilité actuelle > 1 %
  ou volume minimum).
- Sondages et cotes ne mesurent pas la même chose : parts de voix au premier tour d'un
  côté, probabilité de victoire de l'autre. Ne jamais les superposer sur un même graphe.

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
