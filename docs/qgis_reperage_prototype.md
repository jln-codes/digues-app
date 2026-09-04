# Prototype QGIS/QField — repérage des désordres

Le formulaire est produit automatiquement par `digues-app qgis-project` à
partir de `digues_app/qgis_project.py`. Il utilise le Drag-and-Drop Designer,
les relations natives et les widgets standards, sans fichier `.ui`, initialiseur
Python ni plugin client obligatoire.

## Règle de disponibilité

Le formulaire ne propose aucun sélecteur de mode. Il déduit le comportement du
nombre de tronçons associés par `link_desordres_troncons` :

```text
0 tronçon       → géométrie et coordonnées seulement
1 tronçon       → géométrie, coordonnées et repérage
2 tronçons ou + → géométrie, coordonnées et liste des tronçons
                  repérage indisponible
```

Le conteneur **Repérage** porte une expression de visibilité qui exige une
relation tronçon unique et une géométrie Point ou LineString. Un message calculé
à la racine indique discrètement pourquoi le repérage est indisponible.

QGIS réévalue cette expression à l'ouverture et au rafraîchissement du
formulaire. Le rafraîchissement instantané après modification d'une relation
enfant n'est pas garanti par les formulaires standards QGIS/QField ; fermer et
rouvrir la fiche force toujours la réévaluation. PostgreSQL applique entre-temps
la règle 0/1/N et protège la base indépendamment de l'état visuel de la fiche.

## Géométrie et coordonnées

Les désordres ponctuels utilisent la vue éditable
`view_desordres_points_saisie`. X/Y (EPSG:3950) et longitude/latitude
(EPSG:4326) sont quatre expressions de vue sur `desordres.geometry` :

- modifier X ou Y réécrit le Point en EPSG:3950 ;
- modifier longitude ou latitude construit un Point 4326 puis le transforme en
  3950 ;
- déplacer le point sur la carte modifie la même géométrie ;
- une paire de coordonnées incomplète est refusée ;
- une insertion accepte exactement une famille parmi géométrie, X/Y et
  longitude/latitude ;
- une modification simultanée de plusieurs de ces familles est refusée.

QGIS/QField n'est pas l'autorité des conversions. La vue et ses triggers
valident la famille saisie, réécrivent `desordres.geometry`, puis PostGIS
recalcule les valeurs dérivées lors de l'écriture. Le formulaire peut donc
nécessiter une relecture après sauvegarde pour afficher les nouvelles valeurs.
Une consigne courte rappelle dans la fiche de n'utiliser qu'une famille de
saisie par opération et d'appliquer puis relire avant d'en commencer une autre.

Le formulaire affiche X/Y à 2 décimales et longitude/latitude à 6 décimales.
La précision de la géométrie en base n'est jamais arrondie.

Pour une LineString, le formulaire affiche en lecture seule les coordonnées de
`ST_StartPoint` et `ST_EndPoint`. La ligne elle-même reste éditable sur la carte
avec tous ses sommets. Pour un Polygon, seule l'édition cartographique est
proposée ; aucun repérage longitudinal éditable n'est affiché.

## Tronçons concernés

Chaque couche de désordres possède une relation native vers la couche privée
`desordre_troncons`, qui représente `link_desordres_troncons`. Son formulaire
utilise une Value Relation vers `troncons` : l'utilisateur sélectionne des
tronçons existants sans saisir d'UUID.

Un tronçon composite est présenté exactement comme un autre tronçon. QGIS ne
connaît ni agrégat ni relation de composition.

## Formulaire de repérage

Lorsqu'un seul tronçon est associé, la fiche enfant présente :

1. Tronçon ;
2. Système de repérage ;
3. Borne de début ;
4. Distance de début (m) ;
5. Position de début ;
6. PR début courant ;
7. les champs de fin pour une LineString.

Les UUID, offsets signés et autres champs techniques restent masqués. Aucun PR
source, diagnostic CouchDB, qualité de migration ou trace source n'existe dans
le formulaire ou la table opérationnelle.

Les distances et PR sont affichés à 2 décimales sans altérer les valeurs en
base.

### Sélections dépendantes

- `troncon_id` : Value Relation vers `troncons` ;
- `systeme_reperage_id` : Value Relation vers `systemes_reperage`, filtrée par
  le tronçon courant ;
- `borne_debut_id` et `borne_fin_id` : Value Relation vers
  `view_systemes_reperage_bornes`, filtrée par le système courant.

La valeur stockée pour une borne reste son UUID. La vue affiche selon sa
position : **Début du tronçon**, **Fin du tronçon**, ou son libellé métier pour
une borne intermédiaire. Ces rôles sont indépendants de l'ordre CouchDB et
changent automatiquement après inversion du tronçon.

Le système par défaut peut être choisi par la synchronisation initiale, mais le
moteur reçoit toujours explicitement tronçon, système et borne. Il ne dépend
jamais implicitement du défaut pour convertir une saisie.

### Amont, aval et distance nulle

La Value Map propose seulement :

```text
Amont → AVANT_BORNE
Aval  → APRES_BORNE
```

`SUR_BORNE` reste accepté par PostgreSQL pour la compatibilité, mais n'est pas
un choix utilisateur. Une distance égale à zéro produit un offset nul, que la
valeur affichée soit Amont ou Aval.

## Autorité selon l'opération

Une modification cartographique ou numérique conserve exactement la géométrie.
Le trigger PostgreSQL recalcule le repérage par projection seulement si le
désordre est lié à un tronçon unique.

Une modification explicite de borne, distance ou sens applique le repérage à
la géométrie :

- le Point est repositionné sur le tronçon ;
- la LineString est remplacée par la portion correspondante du tronçon avec
  `ST_LineSubstring`, sommets intermédiaires compris.

Le groupe Repérage contient un avertissement permanent sur le caractère
destructif du recalage d'une ligne. Les widgets standards ne fournissent pas de
boîte de confirmation transactionnelle portable QGIS/QField ; l'avertissement
précède donc l'enregistrement, et PostgreSQL garantit l'application atomique.

Une opération utilisateur doit utiliser une seule famille autoritaire :

```text
géométrie
ou X/Y
ou longitude/latitude
ou repérage
```

Les trois premières familles sont arbitrées dans le trigger de la vue
ponctuelle. Le repérage est une table enfant et une requête distincte : aucune
machinerie transactionnelle cliente n'est ajoutée pour l'interdire avec une
autre famille. L'interface demande donc d'appliquer et relire une opération
avant d'en saisir une autre ; les guards PostgreSQL existants conservent
l'autorité correcte de chaque écriture.

## Cycle d'application et de relecture

Le projet reste volontairement fondé sur les capacités standards communes à
QGIS Desktop et QField, sans initialiseur Python ni plugin :

```text
modifier
→ appliquer ou enregistrer
→ PostGIS arbitre et recalcule
→ rafraîchir ou rouvrir la fiche si elle affiche encore l'ancien état
```

Il n'existe pas dans cette configuration standard de hook portable garantissant
la relecture automatique du formulaire parent après un trigger ou la sauvegarde
d'une relation enfant. Le message de disponibilité et le groupe Repérage sont
corrects dès la réévaluation. Un ajout de deuxième tronçon supprime le repérage
en base ; sa suppression recrée le repérage depuis la géométrie sans la déplacer.

## Mise en page

Le générateur aplatit récursivement tout groupe qui ne contiendrait qu'un seul
champ ou une seule relation. Les groupes conservés ont une fonction réelle :

- **Général** contient plusieurs attributs métier ;
- **Coordonnées** contient quatre coordonnées pour les Points, ou les
  coordonnées début/fin pour les lignes ;
- **Repérage** contient l'avertissement et la relation de localisation.

La relation des tronçons concernés et le message d'état sont placés directement
à la racine. Cette règle est vérifiée pour tous les formulaires générés.

## Limites QField à valider sur appareil

- réévaluation immédiate de la visibilité après ajout ou suppression d'un lien
  tronçon dans une sous-fiche déjà ouverte ;
- rafraîchissement en cascade des Value Relation hors connexion ;
- présentation de l'avertissement de recalage sur petit écran ;
- comportement de la vue ponctuelle éditable avec la version du fournisseur
  PostgreSQL embarquée dans QField.

Le projet généré reste utilisable sans ces raffinements : PostgreSQL impose la
cardinalité et refuse tout repérage incohérent.
