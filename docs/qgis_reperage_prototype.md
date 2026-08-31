# Prototype QGIS/QField — repérage des désordres

Ce lot prépare un formulaire pilote ; il n'a pas été ouvert dans QGIS ou
QField dans l'environnement de développement, où PyQGIS n'est pas disponible.
Les étapes ci-dessous constituent donc une configuration manuelle à valider.

## Ce que voit l'utilisateur

La couche principale reste `desordres`, avec sa géométrie cartographique. Son
formulaire contient un groupe **Localisations** affiché par l'éditeur de relation
natif QGIS. Une fiche enfant montre, dans cet ordre :

1. mode (`Carte/GPS`, `Borne + distance` ou `Import`) ;
2. tronçon ;
3. système de repérage ;
4. borne de début, distance positive et position `avant/sur/après` ;
5. les mêmes champs de fin lorsque le désordre est linéaire ;
6. PR source et PR courant en lecture seule ;
7. un résumé lisible et un indicateur de cohérence.

Les UUID, offsets signés calculés, identifiants source, politique technique,
qualité interne, JSON de trace et diagnostic restent masqués. Pour un polygone,
le repérage est présenté comme une indication métier et non comme une
description de toute l'emprise.

## Couches et relation

Ajouter les tables `desordres`, `desordre_localisations_reperage`, `troncons`,
`systemes_reperage`, `bornes_reperage` et la vue
`view_desordre_localisations_reperage`. Déclarer une relation :

- identifiant : `desordre_localisations_reperage` ;
- parent : `desordres.id` ;
- enfant : `desordre_localisations_reperage.desordre_id`.

Dans le formulaire drag-and-drop de `desordres`, insérer l'éditeur de cette
relation. Le 0..N natif présente alors, par exemple, deux lignes « T12 — B14
32 m après » et « T13 — B01 8 m avant », sans table de lien supplémentaire.

## Widgets en cascade à configurer

- `troncon_id` : Relation Reference vers `troncons`, libellé comme description ;
- `systeme_reperage_id` : Value Relation vers `systemes_reperage`, filtrée sur
  le `troncon_id` de la fiche enfant ; le système par défaut peut uniquement
  préremplir ce champ ;
- `borne_debut_id` et `borne_fin_id` : choix limité aux bornes présentes dans
  `link_systemes_reperage_bornes` pour le système choisi ;
- distances : plage numérique, minimum 0, unité `m` ;
- positions relatives : liste `AVANT_BORNE`, `SUR_BORNE`, `APRES_BORNE`, avec
  libellés humains « avant », « sur la borne », « après ».

La base calcule l'offset signé dans une colonne générée. QGIS ne demande donc
jamais à l'utilisateur de saisir une valeur négative. Les filtres dépendants
tronçon → système → borne doivent encore être vérifiés dans les versions QGIS
et QField réellement déployées.

## Conversions explicites

Le prototype n'ajoute aucun trigger. Deux actions explicites sont à tester dans
le projet pilote :

- **Calculer le repérage depuis la carte**, qui appelle
  `xy_vers_reperage(troncon, systeme, point)` puis présente le résultat avant
  enregistrement ;
- **Placer depuis borne + distance**, qui appelle
  `borne_offset_vers_xy(...)` et propose le point calculé.

Ces actions ne sont pas configurées par ce lot. La géométrie de `desordres`
n'est jamais reconstruite pendant la migration. Pour GPS/carte, la politique
technique proposée est `GEOMETRIE_FIXE`; pour borne-distance,
`REPERAGE_FIXE`; pour l'import historique ambigu, `MANUELLE`. Ce champ doit
rester caché dans le formulaire courant.

## Limites à mesurer sur le terrain

- ergonomie réelle de l'éditeur 1:N sur petit écran ;
- rafraîchissement des listes dépendantes dans QField hors connexion ;
- pertinence d'afficher début et fin pour un point ou un polygone ;
- besoin éventuel d'une vue ou d'un formulaire spécialisé supplémentaire pour
  masquer la structure enfant ;
- comportement des actions explicites sans code Python côté client.

Si ces points rendent la saisie confuse, simplifier le modèle ou séparer les
parcours carte et borne-distance sera un résultat valide du prototype.
