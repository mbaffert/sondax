# Sondax

Code et données de [sondax.fr](https://sondax.fr), agrégateur des sondages de l'élection
présidentielle française de 2027.

## Les données

Le fichier à utiliser est le CSV publié sur le site, mis à jour chaque jour :

**https://sondax.fr/donnees/sondages-presidentielle-2027.csv**

Une ligne par sondage, par configuration testée et par candidat. Colonnes, sources et
conditions de réutilisation : [sondax.fr/donnees.html](https://sondax.fr/donnees.html).

Les fichiers JSON de `data/` sont des formats de travail internes, susceptibles de
changer sans préavis. L'historique git de `data/sondages.json` donne l'état des données
à chaque collecte.

## Sources

- Sondages : page Wikipédia
  [Liste de sondages sur l'élection présidentielle française de 2027](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027),
  complétée à la main à partir des notices de la Commission des sondages quand un
  sondage y manque. Le wikitexte brut de chaque version utilisée est conservé dans
  `data/snapshots/`.
- Cotes des marchés de prédiction : Polymarket (affichées sur le site, non incluses dans
  le jeu de données).

## Licence

Données : [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr), héritée
de Wikipédia. Mention à reprendre : « Sondax, d'après Wikipédia », avec un lien vers
sondax.fr.

## Fonctionnement

Une collecte automatique (GitHub Actions) lit le wikitexte de la page Wikipédia deux fois
par jour, valide les données et ouvre une pull request relue avant fusion. Le site est
statique, régénéré à chaque fusion. Règles de méthode et modèle de données : `SPEC.md`.

Erreur dans les chiffres : le mieux est de la corriger sur Wikipédia, la correction
remonte ici à la collecte suivante. Sinon : contact@sondax.fr.
