# Modèle Sondax — brief de développement

Complète `SPEC.md`.
Pour le calcul de la moyenne, la page Méthode actuelle du site fait foi
(configuration de référence « Attal + Philippe », pas de pondération par échantillon).

## 1. Objectif du produit

Les sondages donnent des scores et un classement.
Ils disent beaucoup moins clairement si ce classement est solide.
Deux candidats séparés par un point peuvent en réalité avoir des chances très proches d’accéder au second tour. À l’inverse, un écart apparemment faible peut parfois correspondre à une situation beaucoup plus stable.
Sondax ajoute donc une nouvelle lecture des sondages :
Le modèle Sondax
Sa question centrale est :
Et si on votait dimanche ?
Avec les sondages disponibles aujourd’hui, qui a réellement ses chances d’être au second tour, et à quel point ?
Le modèle Sondax ne cherche pas à prévoir le résultat de l’élection présidentielle d’avril 2027.
Il mesure la solidité du rapport de forces observé aujourd’hui.
Trois produits doivent rester clairement distingués :

* Sondages : ce que mesurent actuellement les enquêtes.
* Modèle Sondax : ce que ces sondages permettent de dire aujourd’hui de la course au second tour.
* Marchés : ce qu’anticipent les participants des marchés prédictifs.

Le modèle doit permettre de répondre à quatre questions :

1. Qui a aujourd’hui ses chances d’être au second tour ?
2. Quels seconds tours restent réellement possibles ?
3. Qui gagne ou perd des chances de qualification ?
4. À quelle distance la situation se trouve-t-elle d’un basculement ?

## 2. Architecture du site

Le produit est réparti sur trois niveaux.

### Niveau 1 — Home page

La home donne une synthèse immédiate.
Elle doit être comprise en moins de dix secondes et donner envie d’ouvrir la page dédiée.
Elle ne cherche pas à présenter toutes les données du modèle.

### Niveau 2 — Page « Le modèle Sondax »

C’est la page produit principale.
Elle permet d’explorer :

* les chances de qualification ;
* leur évolution ;
* les différents seconds tours possibles ;
* les points de bascule ;
* le classement détaillé ;
* ce qui vient de changer.

### Niveau 3 — Page « Méthode »

Elle explique :

* les données utilisées ;
* la calibration historique ;
* la loi statistique ;
* les 50 000 tirages ;
* les backtests ;
* les limites du modèle.

L’architecture principale devient :
Sondages | Modèle Sondax | Marchés | Méthode
Élections passées, Instituts, Tous les sondages et Explorer un sondage restent accessibles là où ils sont aujourd’hui (header et pied de page). Seule la sous-navigation de la home gagne une entrée « Modèle ».
URL recommandée :

```text
/modele-sondax
```

## 3. Règle générale de ton

Le site s’adresse à quelqu’un qui regarde les sondages comme il regarde la météo.
Le produit doit donc être compréhensible sans connaissances statistiques.
Sur la home et la page Modèle, éviter :

* simulation ;
* probabilité ;
* tirage ;
* configuration ;
* échantillon ;
* calibration ;
* Dirichlet ;
* variance ;
* distribution.

Utiliser :

* chances ;
* sur 100 ;
* une chance sur trois ;
* dimanche ;
* duel ;
* second tour ;
* y être ;
* basculer ;
* se rapprocher ;
* s’éloigner ;
* gagner des chances ;
* perdre des chances.

Le terme « Modèle Sondax » peut être utilisé comme nom du produit.
Les termes techniques expliquant son fonctionnement restent réservés à la page Méthode.

## 4. Home page — synthèse

La home ne présente qu’une version condensée du modèle.

### 4.1 Titre

Et si on votait dimanche ?
Sous-titre :
Qui serait au second tour, d’après les sondages d’aujourd’hui ?

### 4.2 Accroche

L’accroche est générée à chaque mise à jour.
Exemple :
Le Pen – Mélenchon reste aujourd’hui le second tour le plus plausible.
Philippe a 38 chances sur 100 d’y être, contre 27 il y a une semaine.
Ou :
La course à la deuxième place se resserre.
Mélenchon et Philippe ont désormais des chances très proches d’accéder au second tour.
Ou :
Le second tour se stabilise.
Les deux premiers disposent aujourd’hui d’une nette avance sur leurs poursuivants.
L’objectif est de raconter ce qu’il faut retenir aujourd’hui.

### 4.3 Les seconds tours possibles (composant de §5.6)

Le bloc « Les seconds tours possibles » de la page Modèle (§5.6), identique : même composant, mêmes données. 100 carrés et liste des duels, avec leur évolution et, le cas échéant, le sondage déclencheur (§5.11).
Les barres par candidat restent uniquement sur la page Modèle (§5.2).

### 4.4 Principal mouvement

Mettre en évidence une seule information.
Exemple :
Philippe se rapproche : +11 chances en une semaine.
ou :
Mélenchon repasse devant Philippe.
ou :
Peu de changement depuis une semaine.

### 4.5 Point de bascule

Lorsque l’information est particulièrement pertinente, afficher :
Philippe est à environ 1 point du basculement.
Tooltip ou texte secondaire :
Avec environ un point supplémentaire dans les sondages actuels, ses chances d’accéder au second tour seraient proches d’une sur deux.
Ne pas afficher le point de bascule systématiquement sur la home.

### 4.6 CTA

Bouton principal :
Voir le modèle Sondax →
Lien vers :

```text
/modele-sondax
```

Sous le bouton, éventuellement :
Chances de qualification, seconds tours possibles et évolution de la course.

### 4.7 Ligne de contexte

En pied de bloc :
Si on votait dimanche · Calculé sur [n] sondages · Mis à jour le [date].
Puis :
Ne prédit pas ce qui se passera d’ici avril.

## 5. Page « Le modèle Sondax »

C’est le cœur du produit.
Titre :
Le modèle Sondax
Sous-titre :
Et si on votait dimanche ?
Texte d’introduction :
À partir des sondages disponibles aujourd’hui, Sondax mesure à quel point chaque candidat a réellement ses chances d’accéder au second tour.
Ajouter :
Ce n’est pas une prévision d’avril 2027 : c’est une photographie de la course aujourd’hui.

### 5.1 Accroche du jour

Reprendre l’accroche de la home, éventuellement plus développée.
Exemple :
Le Pen – Mélenchon reste le second tour le plus plausible.
Mais la deuxième place est loin d’être acquise : Philippe a désormais 38 chances sur 100 d’y être, contre 27 il y a une semaine.
Il est à environ un point du basculement.

### 5.2 Chances de qualification

Afficher tous les candidats inclus dans le calcul.
Pour chaque candidat :

* photo ;
* nom ;
* barre ;
* chances sur 100 ;
* évolution sur 7 jours ;
* verdict ;
* point de bascule lorsque pertinent.

Exemple :

```text
Marine Le Pen
> 99 sur 100
Quasi sûre d’y être
Stable


Jean-Luc Mélenchon
46 sur 100
Rien n’est joué
−5 en 7 jours


Édouard Philippe
38 sur 100
Rien n’est joué
+11 en 7 jours
À environ 1 point du basculement


Raphaël Glucksmann
12 sur 100
Il faudrait une surprise
−2 en 7 jours


Gabriel Attal
4 sur 100
Très improbable aujourd’hui


Bruno Retailleau
3 sur 100
Très improbable aujourd’hui
```

### 5.3 Verdicts

Utiliser les seuils suivants.

* > 90 : Quasi sûr(e) d’y être
* 60 à 90 : Bien placé(e)
* 25 à 60 : Rien n’est joué
* 8 à 25 : Il faudrait une surprise
* < 8 : Très improbable aujourd’hui

Ne pas utiliser :
Hors course.
Un événement à 5 ou 7 chances sur 100 reste possible.

### 5.4 Évolution sur 7 jours

Afficher pour chaque candidat :
+11 en 7 jours
−5 en 7 jours
stable
L’évolution porte sur les chances de qualification, pas sur le score dans les sondages.
Stocker également :

```text
evolution_1j
evolution_7j
evolution_30j
```

La page utilise par défaut 7 jours.

### 5.5 Historique

Sur la page Modèle, permettre de visualiser l’évolution des chances de qualification.
Exemple :
Chances d’être au second tour
Sélecteur :
7 jours | 30 jours | Depuis le début
Courbe simple par candidat.
Ne pas afficher nécessairement tous les candidats simultanément.
Par défaut :

* les trois ou quatre principaux candidats ;
* possibilité d’en ajouter ou retirer.

Cette courbe ne remplace pas la courbe d’intentions de vote.
Elle mesure l’évolution des chances de qualification.

### 5.6 Seconds tours possibles

Section :
Les seconds tours possibles
Exemple :

```text
Le Pen – Mélenchon     44 sur 100
Le Pen – Philippe      31 sur 100
Le Pen – Glucksmann     9 sur 100
Autres                 16 sur 100
```

Afficher les trois principaux duels.
Regrouper les autres sous :
Autres scénarios
avec possibilité de développer.
Une visualisation en 100 points ou 100 carrés peut être utilisée.
L’objectif est de faire comprendre immédiatement qu’il peut exister plusieurs seconds tours plausibles.

### 5.7 Évolution des duels

Afficher :

```text
Le Pen – Mélenchon
44 sur 100
−6 en 7 jours

Le Pen – Philippe
31 sur 100
+9 en 7 jours
```

Cela permet de voir directement si un scénario gagne ou perd en plausibilité.

### 5.8 Qui finit où ?

Section ou onglet :
Qui finit où ?
Pour chaque candidat :

```text
                       1er     2e     3e ou moins

Marine Le Pen           84      15        1
Jean-Luc Mélenchon       8      38       54
Édouard Philippe         5      33       62
Raphaël Glucksmann       2      10       88
```

Les chances de qualification correspondent naturellement à :

```text
1er + 2e
```

Cette vue reste secondaire.
Elle ne doit pas prendre le dessus sur les chances de qualification.

### 5.9 Point de bascule

Pour les principaux candidats en compétition pour la deuxième place, calculer le niveau nécessaire pour atteindre environ :
50 chances sur 100 d’être au second tour.
Exemple :
À environ 1 point du basculement
Explication :
Avec environ un point supplémentaire dans les sondages actuels, ses chances de qualification seraient proches d’une sur deux.
Arrondir volontairement :

* 0,5 point ;
* 1 point ;
* 1,5 point ;
* 2 points ;
* etc.

Éviter :
+1,27 point.
Le résultat est un ordre de grandeur.
Ne pas afficher le point de bascule lorsque le candidat est trop éloigné : afficher si `delta_bascule` ≤ 4 points, rien au-delà. Ne pas le calculer pour un candidat déjà à plus de 50 chances sur 100.

### 5.10 Ce qui a changé

Section importante :
Ce qui a changé
Comparer :

* aujourd’hui ;
* dernière mise à jour ;
* J−7.

Exemple :
Philippe se rapproche.
Ses chances de qualification passent de 31 à 38 sur 100. Le Pen–Philippe devient le deuxième second tour le plus fréquent.
Ou :
Mélenchon reprend de l’avance.
Ses chances d’être au second tour progressent de 44 à 51 sur 100, tandis que celles de Philippe reculent.
Ou :
Peu de changement aujourd’hui.
Le dernier sondage reste proche de la moyenne actuelle et modifie peu la course au second tour.
Génération déterministe à partir des données.
Pas besoin de LLM en V1.

### 5.11 Détection des événements importants

Priorité :

1. changement du duel principal ;
2. changement du deuxième candidat le mieux placé ;
3. variation supérieure à 5 chances sur 100 ;
4. franchissement d’un seuil de verdict ;
5. changement important du point de bascule ;
6. sinon : peu de changement.

Quand l’événement résulte d’un seul sondage entré depuis la dernière mise à jour, le texte le nomme :
Le sondage Ifop du 25 septembre rapproche Philippe : +7 chances sur 100.
C’est plus honnête qu’un « Philippe se rapproche » fondé sur une enquête, et plus lisible.
Créer dans `modele.json` un objet décrivant l’événement.
Exemple :

```json
{
  "type": "candidate_gain",
  "candidate": "philippe",
  "delta": 11,
  "sondages_declencheurs": ["ifop-2026-09-25"]
}
```

`sondages_declencheurs` liste les sondages entrés depuis la mise à jour précédente. Le front choisit ensuite le texte correspondant : formulation attribuée si la liste a un seul élément, formulation générale sinon.

### 5.12 Explication courte

Afficher avant le lien Méthode :
Les sondages se trompent toujours un peu. Sondax regarde donc les écarts réellement observés lors des élections précédentes et refait le premier tour 50 000 fois. Nous comptons ensuite combien de fois chaque candidat termine dans les deux premiers.
Puis :
Un point d’écart dans les sondages ne signifie donc pas nécessairement une grande différence de chances d’être au second tour.
CTA :
Comprendre la méthode →

## 6. Pages candidat

Sous le score moyen :
Et si on votait dimanche ?
Exemple :
46 chances sur 100 d’être au second tour
Puis :
Rien n’est joué.
Puis :
−5 en 7 jours.
Puis :
Son second tour le plus fréquent : face à Marine Le Pen.
Si pertinent :
À environ 1,5 point du basculement.
Ajouter une petite courbe :
Évolution de ses chances de qualification
7 jours / 30 jours.
Absent si le candidat ne fait pas partie de la configuration calculée.

## 7. Pages duel

Pour chaque duel :
Afficher :

* fréquence actuelle ;
* évolution ;
* rang parmi les différents seconds tours.

Pour le premier :
Le second tour le plus fréquent aujourd’hui
Pour le deuxième :
Près d’un second tour sur trois
Si <5 :
Peu fréquent aujourd’hui
Exemple :

```text
Le Pen – Philippe

31 fois sur 100 aujourd’hui
22 il y a une semaine
+9 en 7 jours
```

## 8. Page Méthode

La page Méthode est séparée de la page Modèle.
Elle est destinée au lecteur qui veut vérifier et comprendre précisément le calcul.
Titre :
Méthode
Section :
Comment fonctionne le modèle Sondax ?

### 8.1 Point de départ

Utiliser la moyenne Sondax du jour pour chaque candidat de la configuration de référence.
Configuration de référence :
celle contenant actuellement Attal et Philippe.
Renormaliser l’ensemble à 100 %.
« Autre » n’entre pas dans le calcul.
Un candidat absent de cette configuration n’a pas de chiffre de qualification.

### 8.2 Erreurs historiques des sondages

Pour chaque élection historique, comparer :

* la moyenne des sondages dont le terrain se termine dans les sept jours précédant le scrutin ;
* le résultat officiel.

Élections utilisées :

* présidentielle 2002 ;
* présidentielle 2007 ;
* présidentielle 2012 ;
* présidentielle 2017 ;
* présidentielle 2022 ;
* européennes 2019 ;
* européennes 2024.

Produire automatiquement :

* nombre de comparaisons ;
* erreur absolue moyenne ;
* écart-type ;
* distribution ;
* principales erreurs historiques.

Les chiffres publiés sur la page Méthode doivent venir du script de calibration.
Ne pas les coder en dur.

### 8.3 Simulation

À partir de la moyenne du jour :
effectuer 50 000 premiers tours.
Utiliser une loi de Dirichlet centrée sur le vecteur des intentions de vote.
Deux propriétés importantes :

* chaque premier tour totalise 100 % ;
* l’ampleur possible des erreurs dépend du niveau du candidat.

Le paramètre est calibré à partir des erreurs historiquement observées.

### 8.4 Calibration

Paramètre principal :

```text
N_eff
```

Estimateur initial :

```text
N_eff = Σ p(1−p) / Σ erreur² − 1
```

Calculer :

* présidentielles seules ;
* européennes seules ;
* ensemble.

Ne pas retenir mécaniquement l’estimation sans validation.

### 8.5 Comptage

Pour chaque premier tour simulé :
classer les candidats.
Qualification :

```text
rang 1 ou rang 2
```

Chance de qualification :

```text
nombre de qualifications / 50 000
```

Même logique pour :

* rang ;
* duel.

Arrondi :

```text
38 sur 100
```

Sous 1 :
moins de 1 sur 100
Au-dessus de 99 :
plus de 99 sur 100.

### 8.6 Point de bascule

Faire varier le score moyen du candidat jusqu’à obtenir environ :

```text
50 chances sur 100
```

Après modification de son score :
renormaliser proportionnellement les autres scores.
Utiliser une recherche par dichotomie.
Stocker :

```text
seuil_bascule
delta_bascule
```

Le chiffre public est arrondi. Le point retiré ou ajouté au candidat est pris ou rendu proportionnellement à tous les autres : c’est le choix le plus neutre.

### 8.7 Ce que le modèle ne fait pas

Pas de correction discrétionnaire :

* biais supposés des petits candidats ;
* dynamique supposée ;
* biais par institut.

Pas de pondération spécifique par institut.
Pas de prévision de l’évolution future des intentions de vote.
Pas de prise en compte :

* des campagnes futures ;
* des débats futurs ;
* des retraits de candidature futurs ;
* des événements politiques futurs.

Formulation centrale :
Le modèle Sondax mesure la solidité du classement observé aujourd’hui. Il ne prédit pas le résultat de l’élection d’avril 2027.

## 9. Backtest historique

Créer :

```text
/scripts/backtest.py
```

Question :
Qu’aurait affiché Sondax avant les élections précédentes ?
Pour chaque présidentielle :

1. ne prendre que les sondages disponibles à J−7 ;
2. calculer la moyenne ;
3. appliquer exactement le moteur actuel ;
4. calculer les chances de qualification ;
5. calculer les différents duels ;
6. comparer au résultat réel.

Sortie :

```text
Élection | candidat | moyenne | chances qualification | résultat
```

Et :

```text
Élection | duel principal Sondax | chances | duel réel
```

Objectif :
tester la calibration.
Pour que le test ne porte pas sur les données qui ont servi à calibrer, procéder en leave-one-out : pour chaque présidentielle, calibrer `N_eff` sur les quatre autres, puis tester sur celle-là. Cinq runs au lieu d’un ; le tableau de backtest devient honnête.
Un résultat donné à :

```text
10 chances sur 100
```

doit effectivement correspondre à un événement rare mais possible.
Le backtest doit notamment permettre de regarder ce que le modèle aurait produit en 2002 et 2022.
Le faible nombre d’élections impose cependant de rester prudent sur les conclusions.

## 10. Validation de la loi utilisée

Tester si la Dirichlet reproduit raisonnablement :

* variance des erreurs ;
* queues de distribution ;
* erreurs selon le niveau du candidat ;
* erreurs des candidats >20 % ;
* erreurs entre 10 et 20 % ;
* erreurs <10 %.

Examiner également les corrélations historiques entre erreurs des candidats.
Si la Dirichlet présente des limites, les documenter.
Ne pas complexifier automatiquement le moteur.
Principe :
modèle simple + backtest + transparence sur ses limites.

## 11. Données

Déjà présent :

```text
/data/historique.json
```

À ajouter :

```text
/data/historique_europeennes.json
```

2019 + 2024.
Puis :

```text
/data/derived/modele.json
/data/derived/modele_history.json
/data/derived/backtest.json
```

Scripts :

```text
/scripts/import_europeennes.py
/scripts/calibration.py
/scripts/modele.py
/scripts/backtest.py
```

## 12. Structure de modele.json

Exemple :

```json
{
  "date": "2026-09-28T06:12:00Z",
  "revid": 239883627,
  "configuration": ["le-pen", "melenchon", "philippe", "glucksmann", "attal", "retailleau", "tondelier", "roussel"],
  "n_sondages": 12,
  "N_eff": 350,
  "N_eff_source": "presidentielles",

  "candidats": {
    "philippe": {
      "qualification": 38,
      "evolution_1j": 2,
      "evolution_7j": 11,
      "evolution_30j": 15,
      "rang": {
        "1": 5,
        "2": 33,
        "3plus": 62
      },
      "seuil_bascule": 18.5,
      "delta_bascule": 1.0
    }
  },

  "duels": [
    {
      "candidats": ["le-pen", "melenchon"],
      "chance": 44,
      "evolution_7j": -6
    }
  ],

  "changement": {
    "type": "candidate_gain",
    "candidate": "philippe",
    "delta": 11
  }
}
```

## 13. Historisation

Conserver les résultats dans le temps.
À chaque mise à jour :
enregistrer :

* moyenne ;
* qualification ;
* rangs ;
* duels ;
* point de bascule.

Cela permet :

* évolution 1 jour ;
* évolution 7 jours ;
* évolution 30 jours ;
* courbes historiques ;
* génération de contenus sociaux.

## 14. Tests automatiques

Le moteur doit vérifier :

* chaque tirage totalise 100 ;
* les chances de qualification totalisent 200 ;
* les rangs d’un candidat totalisent 100 ;
* tous les duels totalisent 100 ;
* aucune valeur <0 ;
* aucune valeur >100 ;
* deux runs avec la même graine donnent le même résultat ;
* un candidat à 40 % dans une configuration classique est presque toujours qualifié.

`validation.py` doit échouer si ces conditions ne sont pas remplies.

## 15. Partage

Créer automatiquement des visuels partageables.

Format 1 — duel principal
Et si on votait dimanche ?
Le Pen – Mélenchon
Le second tour le plus fréquent aujourd’hui.

Format 2 — mouvement
Philippe gagne 11 chances de qualification en une semaine.

Format 3 — basculement
La course à la deuxième place devient indécise.

Formats :

* OpenGraph ;
* LinkedIn ;
* X ;
* messageries.

Bouton :
Partager
Copier :

* phrase ;
* lien ;
* visuel lorsque possible.

## 16. Principes UX

Trois niveaux de lecture.

* Niveau 1 — Home : comprendre la situation en moins de 10 secondes.
* Niveau 2 — Modèle Sondax : explorer et comprendre la course.
* Niveau 3 — Méthode : vérifier la construction statistique.

Ne jamais faire remonter la complexité du niveau 3 dans le niveau 1.

## 17. Tests de compréhension utilisateur

Faire tester notamment :

* Que signifie « 38 chances sur 100 » ?
* Est-ce que Sondax dit que Philippe fera 38 % ?
* Est-ce que Sondax prédit avril 2027 ?
* Que signifie « +11 en une semaine » ?
* Que signifie « à un point du basculement » ?
* Quelle différence faites-vous entre la courbe des sondages et la courbe du modèle ?

Si les réponses montrent une confusion importante, revoir le wording avant publication.

## 18. Hors périmètre V1

Ne pas inclure :

* chances de gagner l’élection finale ;
* simulation du résultat du second tour ;
* prédiction d’avril 2027 ;
* scénarios de retrait ;
* variante de candidature hypothétique ;
* correction manuelle des biais ;
* pondération par institut ;
* modèle d’événements politiques futurs ;
* prévision des intentions de vote futures.

## 19. Ordre de développement

Deux phases. La première met le produit sous les yeux avec des chiffres réels, en local, en deux sessions de Claude Code ; c’est sur elle que se règlent le wording et les seuils. La seconde complète.

### Phase A — voir le produit

**A1 — Calibration sur les présidentielles**
`calibration.py` sur `data/historique.json` (déjà dans le dépôt). Résultat attendu : 61 comparaisons, écart absolu moyen 0,90, écart-type 1,40, `N_eff` ≈ 350 par la méthode des moments. 2002 est la seule année où les deux qualifiés annoncés ne sont pas les bons.

**A2 — Moteur**
`modele.py` produit `modele.json` (chances, rangs, duels). Tests de la section 14.

**A3 — Page « Le modèle Sondax »**
Sections 5.1, 5.2, 5.3, 5.6, 5.8, 5.12. Sans évolutions, sans point de bascule, sans historique : les champs sont absents ou vides et la page les ignore.

**A4 — Bloc home**
Sections 4.1, 4.2 (accroche « stabilise » ou « se resserre » seulement), 4.3, 4.6, 4.7.

Revue en local, mobile et desktop. Ajustement des seuils de verdict et du wording sur les chiffres réels. Tests de compréhension (section 17) sur cette version.

### Phase B — compléter

**B1 — Import européennes**
2019 + 2024, recalibration, `N_eff_source` mis à jour si l’estimation globale est retenue.

**B2 — Backtest**
`backtest.py`, leave-one-out, `backtest.json`. Validation de la loi (section 10).

**B3 — Historisation**
`modele_history.json` à chaque run ; évolutions 1 j, 7 j, 30 j avec la règle d’affichage de 5.4.

**B4 — « Ce qui a changé »**
Règles de 5.11, avec attribution au sondage déclencheur. Accroches de mouvement (4.2, 4.4).

**B5 — Point de bascule**
Section 8.6, affichage borné (5.9).

**B6 — Historique sur la page Modèle**
Courbes de 5.5.

**B7 — Pages candidat et pages duel**
Sections 6 et 7.

**B8 — Partage**
Section 15 : image quotidienne et bouton Partager.

**B9 — Page Méthode**
Section 8, chiffres tirés de `calibration.json` et `backtest.json`, jamais codés en dur.

**B10 — Production**
Intégration au run bi-quotidien. `validation.py` échoue si `modele.json` manque ou si un test de la section 14 échoue. Mise en veille les jours couverts par la loi de 1977, comme le reste du site. Mise en ligne après accord explicite.
