# SIRS — schéma conceptuel PostgreSQL/PostGIS

Version : **0.6 — 1er septembre 2026**  
Source : schéma conceptuel v0.5 + validation de l'autorité par opération,
du rattachement 0/1/N tronçons et des tronçons composites ordinaires

## Objet de cette version

La v0.6 corrige le modèle cible sans maintenir de migration entre les bases
PostgreSQL de prototype. Une base existante doit être recréée depuis CouchDB.

Les décisions structurantes sont :

```text
0 tronçon
→ géométrie seule

1 tronçon
→ géométrie + repérage longitudinal possible

N tronçons, N >= 2
→ géométrie + rattachement N:N
→ aucun repérage longitudinal
```

Un tronçon composite est un tronçon ordinaire, indépendant, dans `troncons`.
Il n'existe ni table d'agrégats, ni relation de composition, ni union dynamique.

Le modèle opérationnel ne conserve plus les valeurs dont la seule fonction
était d'expliquer la migration CouchDB. Ces valeurs et les diagnostics de
conversion appartiennent aux artefacts JSON/CSV de migration.

## 1. Autorité de la géométrie et du repérage

L'autorité n'est pas un état permanent de l'objet. Elle dépend de l'opération.

### 1.1 Édition cartographique ou par coordonnées

La géométrie saisie fait foi :

1. elle est conservée exactement ;
2. elle n'est pas rabattue sur le tronçon ;
3. avec exactement un tronçon, le point ou les extrémités de la ligne sont
   projetés sur ce tronçon et le repérage est recalculé ;
4. avec zéro ou plusieurs tronçons, aucun repérage n'est conservé.

Un point hors axe reste hors axe. Une ligne libre conserve tous ses sommets.
Pour la vue ponctuelle, géométrie, X/Y et longitude/latitude constituent trois
familles d'entrée exclusives par `INSERT` ou `UPDATE`. La famille fournie est
seule autoritaire ; plusieurs familles ou un couple de coordonnées incomplet
sont refusés avant toute écriture.

### 1.2 Édition explicite borne, distance et sens

Cette opération exige exactement un tronçon associé. Le choix de borne de
l'utilisateur est conservé, même si une autre borne donnerait une
représentation équivalente.

- pour un Point, `borne_offset_vers_xy` replace le point sur le tronçon ;
- pour une LineString, les repérages de début et de fin déterminent une portion
  du tronçon par `ST_LineSubstring` ; les sommets intermédiaires du tronçon sont
  conservés et le sens début→fin est respecté.

Le recalage d'une ligne est volontaire et destructif : il remplace sa forme
libre antérieure. Il ne doit jamais être déclenché par une simple modification
cartographique.

## 2. Désordres et rattachement aux tronçons

`desordres.geometry` porte la représentation physique réelle en EPSG:3950.
Les types simples Point, LineString et Polygon sont admis. Les géométries
multi-parties ne sont pas introduites dans cette version.

La relation reste :

```text
desordres
N:N
link_desordres_troncons
N:1
troncons
```

Le nombre de lignes de `link_desordres_troncons` détermine automatiquement la
disponibilité du repérage. Aucun champ `mode_localisation` n'est ajouté.

### 2.1 Zéro tronçon

La géométrie est éditable. Aucune ligne ne doit exister dans
`desordre_localisations_reperage`.

### 2.2 Un tronçon

Point et LineString possèdent au plus une localisation de repérage, calculée
exclusivement avec le `troncon_id` lié. Les recherches spatiales ne choisissent
jamais un autre tronçon, même s'il est superposé ou plus proche.

### 2.3 Plusieurs tronçons

Les liens expriment seulement les tronçons concernés. Toute localisation de
repérage est supprimée ; aucun PR global et aucun recalage ne sont définis.

Il est interdit de combiner plusieurs liens avec un tronçon de référence
supplémentaire. Un objet utilisant un tronçon composite doit être lié uniquement
à ce dernier.

## 3. Tronçons composites

Un tronçon composite possède, comme tout tronçon :

- une LineString propre ;
- une digue ;
- ses systèmes de repérage ;
- ses bornes ;
- éventuellement un système par défaut.

Il peut recouvrir des tronçons plus courts ou parallèles. Cette superposition
n'introduit aucune ambiguïté dans le moteur car les trois fonctions de
conversion exigent toujours un `troncon_id` et un `systeme_reperage_id`
explicites.

Modifier les tronçons courts ne modifie pas le composite, et réciproquement.

## 4. Bornes et PR

Le corpus audité contient 104 tronçons et 208 associations tronçon–borne : les
104 tronçons ont chacun exactement deux bornes, placées aux extrémités. Cette
observation ne devient pas une contrainte générique du moteur, qui continue à
supporter des bornes intermédiaires.

L'ordre CouchDB n'est pas stocké dans le modèle opérationnel. Les rôles sont
calculés spatialement :

```text
abscisse 0                 → Début du tronçon
abscisse longueur tronçon  → Fin du tronçon
autre abscisse             → borne intermédiaire
```

`valeur_pr` qualifie l'association système–borne. Les PR croissants et
décroissants sont acceptés. L'abscisse géométrique et le PR restent deux
notions distinctes.

Une inversion contrôlée d'un tronçon :

1. applique `ST_Reverse` à sa géométrie ;
2. ne modifie aucune géométrie de désordre ;
3. recalcule les repérages des désordres liés uniquement à ce tronçon depuis
   leur géométrie ;
4. recalcule implicitement les rôles début/fin par leur abscisse spatiale.

## 5. Localisation opérationnelle des désordres

`desordre_localisations_reperage` contient uniquement les données nécessaires
au fonctionnement futur :

```text
id
desordre_id                 UNIQUE
troncon_id
systeme_reperage_id
borne_debut_id
distance_debut_m
position_debut_relative
offset_debut_m              généré
pr_debut                    courant
borne_fin_id                nullable pour Point
distance_fin_m              nullable pour Point
position_fin_relative       nullable pour Point
offset_fin_m                généré
pr_fin                      courant
valid
```

Les clés étrangères garantissent que tronçon, système et bornes forment une
chaîne cohérente. La FK vers `(desordre_id, troncon_id)` interdit une
localisation sur un tronçon non associé. `desordre_id UNIQUE` garantit au plus
un repérage, conformément au mode « exactement un tronçon ».

`SUR_BORNE` reste accepté en base pour la compatibilité des données. Le
formulaire propose seulement Amont (`AVANT_BORNE`) et Aval
(`APRES_BORNE`) ; une distance égale à zéro signifie dans les deux cas « sur la
borne ».

## 6. Comportement par type géométrique

### Point

- édition cartographique libre ;
- édition numérique X/Y en EPSG:3950 ;
- édition longitude/latitude en EPSG:4326 avec transformation vers 3950 ;
- projection informative et repérage si un seul tronçon ;
- repositionnement sur le tronçon lors d'une édition explicite du repérage.

X/Y et longitude/latitude sont des vues éditables de la même géométrie, jamais
des colonnes métier indépendantes.

### LineString

- à la migration historique des `Desordre`, `positionDebut` et `positionFin`
  produisent la LineString physique à deux sommets ; `Desordre.geometry`
  CouchDB n'est pas prioritaire car SIRS peut l'avoir projetée ou reconstruite
  sur le tronçon ;
- les sommets intermédiaires d'une ancienne géométrie QGIS, perdus lors de
  l'import historique dans SIRS, ne sont pas recréés ;
- l'édition cartographique conserve la ligne complète ;
- seuls `ST_StartPoint` et `ST_EndPoint` alimentent le repérage ;
- le recalage explicite remplace la ligne par une portion du tronçon.

### Polygon

Les `Desordre` SIRS historiques ne sont pas polygonaux. Un éventuel Polygon
CouchDB valide n'est conservé qu'en fallback de compatibilité lorsque les deux
positions historiques sont inexploitables ; il ne constitue pas un cas métier
historique normal.

Le polygone est éditable uniquement sur la carte. Il ne possède pas de
repérage longitudinal éditable et ne peut jamais être reconstruit depuis une
borne ou un PR. Une future pseudo-localisation par `ST_PointOnSurface` devra
rester strictement informative.

## 7. Données de migration hors modèle métier

Les éléments suivants ne sont pas des colonnes de la table opérationnelle :

```text
pr_debut_source / pr_fin_source
position_debut_source / position_fin_source
systeme_reperage_source_id
mode_saisie_source
politique_autorite
source_document_id
trace_source
diagnostic_conversion
qualite de migration
ordre_source des associations système–borne
```

Le migrateur peut les porter transitoirement en mémoire pour comparer les
conversions historiques et produire `audits/anomalies.json`,
`audits/anomalies.csv` et `audits/bilan.md`. Après validation, la localisation
opérationnelle est recalculée depuis `desordres.geometry`.

Les champs de cheminement nommés `usage_source_id`, `materiau_source_id`, etc.
ne sont pas supprimés mécaniquement : ils portent des attributs métier réels
(usage, matériau, revêtement, position) dont les référentiels cibles ne sont pas
encore modélisés. Leur nom et leur normalisation devront être corrigés avec ces
référentiels, sans perdre entre-temps l'information métier. De même,
`photos.chemin_source` est le chemin opérationnel du fichier, pas une trace de
migration. À l'inverse, `vegetation.type_source_code`, redondant avec la nature
normalisée et seulement explicatif de la classe CouchDB, est retiré.

## 8. Vues et opérations SQL

- `view_desordres_points_saisie` expose les quatre coordonnées dérivées et les
  réécrit atomiquement dans `desordres.geometry`, y compris un `INSERT` par
  longitude/latitude, après arbitrage exclusif de la famille saisie ;
- `view_systemes_reperage_bornes` fournit les rôles et libellés spatiaux des
  bornes ;
- `view_desordre_localisations_reperage` fournit un affichage lisible du
  repérage courant ;
- `synchroniser_desordre_reperage` applique la règle de cardinalité et projette
  depuis la géométrie ;
- `inverser_troncon` constitue l'opération contrôlée d'inversion ;
- les triggers sur géométrie et liens maintiennent l'invariant 0/1/N ;
- le trigger de localisation applique une édition explicite du repérage à la
  géométrie.

## 9. Précision

Les types PostgreSQL/PostGIS ne sont pas arrondis. Seul l'affichage QGIS est
formaté : distances et PR à 2 décimales, X/Y à 2 décimales,
longitude/latitude à 6 décimales environ.

## 10. Extension à d'autres objets

Le choix du tronçon composite est réutilisable sans nouvelle abstraction : un
autre objet métier peut être lié à un tronçon ordinaire long. En revanche, les
triggers et la table de repérage introduits ici restent volontairement propres
aux désordres. Une généralisation future devra préserver la même règle de
cardinalité, sans déduire de rattachement par simple intersection spatiale.
