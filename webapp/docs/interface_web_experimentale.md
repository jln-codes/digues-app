# Interface web cartographique expérimentale

Ce composant est un prototype local. Il permet la création et une édition
circonscrite des désordres Point, LineString et Polygon. Il ne constitue pas
l’interface définitive de SIRS.

## Architecture

- `webapp/backend/digues_webapp/` : API FastAPI et requêtes PostgreSQL ;
- `webapp/frontend/` : page HTML, styles et JavaScript Leaflet ;
- PostgreSQL/PostGIS : source de vérité, sans modification du schéma ni des
  géométries persistées.

Le navigateur conserve les UUID nécessaires aux appels et relations, mais leur
affichage métier est masqué par défaut. FastAPI utilise la même
configuration `SIRS_POSTGRE_*` et le même pilote psycopg que les commandes de
migration. Les valeurs de `config.env` sont chargées sans remplacer les
variables déjà définies dans l’environnement.

Les tronçons sont lus dans `public.troncons`. Les désordres Point, LineString et Polygon
sont lus dans `public.desordres`, avec le libellé de type provenant de
`public.ref_types_desordre`. PostGIS transforme explicitement les géométries
EPSG:3950 vers EPSG:4326 uniquement dans les réponses GeoJSON.

La navigation patrimoniale utilise les relations existantes :

```text
public.systemes.id
→ public.digues.systeme_endiguement_id
→ public.troncons.digue_id
```

`GET /api/systemes-endiguement` renvoie l’arbre complet en une seule lecture :

```json
{
  "systemes": [
    {
      "id": "…",
      "libelle": "SE A",
      "valid": true,
      "digues": [
        {
          "id": "…",
          "systeme_endiguement_id": "…",
          "libelle": "Digue 1",
          "valid": true,
          "troncons": [
            {
              "id": "…",
              "digue_id": "…",
              "systeme_reperage_defaut_id": "…",
              "libelle": "Tronçon 1",
              "valid": true
            }
          ]
        }
      ]
    }
  ]
}
```

Cette réponse ne contient aucune géométrie. Pour le zoom explicite, le frontend
retrouve le tronçon par son identifiant dans la FeatureCollection déjà chargée
depuis `/api/troncons`. Les digues sans système d’endiguement ne figurent pas
dans cet arbre centré sur les systèmes.

## Création des objets patrimoniaux

Le bouton de barre principale `+ Nouvel objet` propose
`Système d'endiguement`, `Digue`, `Tronçon` et `Désordre`. Le choix réutilise le panneau
droit existant. Celui-ci porte un état simple `mode = create | edit` et un
`objectType` ; aucune modale ni infrastructure de formulaire séparée n'est
introduite. Les types Observation, Photo, Végétation et Ouvrage particulier ne
sont pas créables.

En mode `create`, le formulaire et, pour un tronçon, la couche Leaflet.Editable
sont des brouillons exclusivement locaux. `Annuler` les détruit sans appel à
l'API. L'annulation du seul dessin conserve une copie GeoJSON locale qui peut
être restaurée et rééditée. Le premier appel d'écriture est le `POST` déclenché
par `Créer`. Une erreur conserve les champs et la géométrie provisoire. Après un
succès, la réponse relue en transaction depuis PostgreSQL devient l'état
autoritaire : la fiche passe en lecture, l'arbre est complété localement et le
nouveau tronçon est ajouté à la couche cartographique et à l'index Leaflet.

Le contexte de l'arbre est seulement un préremplissage : un système sélectionné
préremplit le parent d'une nouvelle digue et une digue sélectionnée préremplit
le parent d'un nouveau tronçon. Le sélecteur reste modifiable avant `Créer`.

### Audit des champs et relations

Le schéma cible n'impose aucune unicité de libellé et aucun trigger n'est attaché
directement à ces trois tables. Les identifiants UUID sont générés en base et ne
sont donc jamais demandés au navigateur.

| Objet | Champs de création retenus | Relation et contrôles |
| --- | --- | --- |
| Système d'endiguement | `libelle` obligatoire, `valid` par défaut à `true` | aucune relation parente |
| Digue | `libelle`, `valid`, `systeme_endiguement_id` | le système parent doit exister et être actif pour une nouvelle création |
| Tronçon | `libelle`, `valid`, `digue_id`, `geometry` | la digue doit exister et être active ; la LineString est obligatoire dans ce parcours |

La colonne PostgreSQL `digues.systeme_endiguement_id` reste nullable pour les
données historiques, mais le nouveau parcours métier exige un parent. La
colonne `troncons.geometry` est également nullable dans le schéma général ; le
formulaire de création exige néanmoins une géométrie exploitable. Le système de
repérage par défaut, les systèmes de repérage et les bornes ne sont pas inventés
pendant cette création : ils restent configurables par les mécanismes métier
prévus ailleurs.

L'audit du corpus CouchDB disponible donne les écarts suivants :

- les 9 systèmes portent tous `libelle` et `valid`; `populationProtegee` et les
  métadonnées d'auteur/date n'ont pas de colonne opérationnelle correspondante ;
- les 26 digues portent toutes `libelle` et `valid`, mais 7 n'ont pas de système
  parent historique ; le rare champ `designation` n'est pas repris par la table
  cible ;
- les 104 tronçons portent `digueId`, `libelle`, `valid` et une géométrie. Les
  références historiques `typeRiveId`, `systemeRepDefautId`, `borneIds` et les
  métadonnées annexes ne sont pas déduites ni créées implicitement par ce
  formulaire.

### Endpoints et payloads

`POST /api/systemes-endiguement` :

```json
{"libelle": "SE nouveau", "valid": true}
```

`POST /api/digues` :

```json
{
  "libelle": "Digue nouvelle",
  "valid": true,
  "systeme_endiguement_id": "00000000-0000-0000-0000-000000000000"
}
```

`POST /api/troncons` :

```json
{
  "libelle": "Tronçon nouveau",
  "valid": true,
  "digue_id": "00000000-0000-0000-0000-000000000000",
  "geometry": {
    "type": "LineString",
    "coordinates": [[2.10, 48.50], [2.11, 48.52], [2.13, 48.51]]
  }
}
```

Les modèles refusent les champs supplémentaires et les libellés vides. Le
GeoJSON est toujours EPSG:4326 côté client. Le serveur contrôle son type, au
moins deux sommets, les domaines longitude/latitude, sa non-vacuité et sa
longueur non nulle. PostGIS effectue seul `ST_Transform(..., 3950)`. Tous les
sommets sont conservés. L'insertion et la relecture ont lieu dans une même
transaction ; un refus de parent ou de géométrie ne laisse aucun objet partiel.

## Création d'un désordre

### Audit et choix métier

`public.desordres` exige seulement `id` et `valid` au niveau SQL. L'identifiant
UUID est généré par PostgreSQL. `type_desordre_id`, `designation`, `commentaire`,
`date_debut`, `date_fin` et `geometry` sont nullable afin d'accepter le corpus
migré. Le parcours web rend néanmoins une localisation obligatoire : GeoJSON,
X/Y ou longitude/latitude. Il ne rend pas artificiellement obligatoires le type
ou la désignation, absents de certains documents historiques.

Le formulaire expose le type actif facultatif, la désignation, le commentaire,
les dates, la validité, la liste explicite des tronçons et la géométrie. Les
coordonnées dans l'autre CRS, le point représentatif Polygon, les bornes,
distances, sens et PR sont dérivés par PostgreSQL ; ils ne sont jamais calculés
en JavaScript ou FastAPI.

Le modèle CouchDB historique contient aussi `categorieDesordreId`,
`positionDebut`, `positionFin`, `linearId`, `systemeRepId`, bornes, distances,
PR, `editedGeoCoordinate` et `geometryMode`. La catégorie est déduite du type
dans la cible. Les anciennes positions et données de repérage ne constituent
pas des champs de création indépendants. Le corpus observé contient Point et
LineString, parfois avec plusieurs sommets, mais aucun Polygon :

> **Polygon est une extension volontaire du modèle web/PostgreSQL par rapport
> aux désordres historiques observés dans SIRS Digues.**

La table cible admettait déjà Polygon. Ce lot n'ajoute donc ni colonne ni type
PostGIS, seulement son parcours de création et sa lecture cartographique.

### Géométrie et transaction

`POST /api/desordres` accepte exactement une autorité de localisation :

- un GeoJSON Point, LineString ou Polygon EPSG:4326 ;
- ou, pour un Point, une paire `coord_x_3950`/`coord_y_3950` ;
- ou une paire `longitude_4326`/`latitude_4326`.

Les Points numériques sont insérés par `view_desordres_points_saisie`, donc par
le trigger `editer_desordre_point()`. Les GeoJSON sont validés puis transformés
par PostGIS avec `ST_Transform(..., 3950)`. LineString exige au moins deux
sommets. Chaque anneau Polygon exige au moins quatre positions et doit être
fermé ; `ST_IsValid`, la non-vacuité et une aire non nulle restent contrôlés par
PostGIS. Tous les sommets sont conservés.

```text
brouillon Leaflet/coordonnées locales
→ Créer
→ POST transactionnel
→ INSERT désordre et liens tronçons choisis
→ triggers PostgreSQL de synchronisation
→ relecture GeoJSON PostgreSQL
→ remplacement du brouillon sur la carte et dans le panneau
```

Une erreur annule toute la transaction et conserve le brouillon. Changer de
type géométrique est bloqué tant qu'un dessin n'a pas été explicitement annulé
ou que des coordonnées numériques n'ont pas été effacées.

### Rattachement et repérage

Le sélecteur de tronçons est contrôlé par l'utilisateur. Si un tronçon est
sélectionné dans l'arbre, il est seulement prérempli ; aucune proximité spatiale
n'est utilisée. Tous les identifiants fournis doivent désigner des tronçons
actifs.

```text
Point : 0..1 tronçon, jamais davantage
LineString : 0..N tronçons
Polygon : 0..N tronçons
1 tronçon       → projection et repérage éditable pour Point/LineString
0 ou 2+         → géométrie seule, sans bornage
Polygon         → repérage éditable indisponible, quel que soit le nombre de liens
```

Le bornage est proposé à la création et à l'édition uniquement avec exactement
un tronçon. Le navigateur envoie borne, distance et sens ; les fonctions et
triggers PostgreSQL construisent la géométrie et relisent le résultat. La
validation FastAPI refuse explicitement Point + plusieurs tronçons, y compris
pour un appel direct ne passant pas par l'interface.

Le choix « Choisissez votre mode d’édition » est exclusif et horizontal :

- Point : Cartographique, X/Y, Longitude/Latitude, et Bornage avec un tronçon ;
- LineString : Cartographique, Coordonnées début/fin, et Bornage avec un tronçon ;
- Polygon : Cartographique uniquement, sans sélecteur de mode superflu.

| Géométrie | 0 tronçon | 1 tronçon exploitable | 2 tronçons ou plus |
| --- | --- | --- | --- |
| Point | Carte, X/Y, lon/lat | Carte, X/Y, lon/lat, bornage | interdit |
| LineString | Carte, coordonnées | Carte, coordonnées, bornage | Carte, coordonnées |
| Polygon | Carte | Carte | Carte |

Pour LineString, le mode Coordonnées conserve un sous-choix explicite X/Y
EPSG:3950 ou longitude/latitude EPSG:4326. La même fonction JavaScript calcule
les capacités de création et d'édition à partir du type, du nombre de tronçons
et de la disponibilité réelle du repérage. Les formulaires conservent des
conteneurs adaptés aux trois géométries, mais partagent le renderer des types et
tronçons, la normalisation des valeurs optionnelles, la matrice des modes et la
même classe visuelle `disorder-form`.

Une option UUID vide n'est jamais envoyée : les listes filtrent `""` et les
valeurs optionnelles deviennent `null`. Sans tronçon, aucun appel à
`reperage-options` n'est effectué. Polygon n'effectue jamais cet appel.

Lors d'un changement de rattachement, l'API compare l'ensemble demandé à
l'ensemble persistant. S'ils diffèrent, elle supprime d'abord la localisation
de repérage dépendante, puis les liens, insère les nouveaux liens et laisse les
triggers recalculer l'état final, le tout dans une transaction unique. La FK
`desordre_localisations_reperage_lien_troncon_fk` n'est jamais désactivée.

```json
{
  "designation": "Affouillement",
  "type_desordre_id": "RefTypeDesordre:1",
  "commentaire": "Diagnostic initial",
  "valid": true,
  "troncon_ids": ["00000000-0000-0000-0000-000000000000"],
  "geometry": {
    "type": "Polygon",
    "coordinates": [[
      [2.10, 50.50], [2.12, 50.50],
      [2.12, 50.52], [2.10, 50.50]
    ]]
  }
}
```

L’édition ponctuelle passe exclusivement par
`public.view_desordres_points_saisie`. Son trigger `editer_desordre_point()`
arbitre la famille X/Y ou longitude/latitude, reconstruit la géométrie métier et
laisse les triggers de `public.desordres` synchroniser le repérage. Le PUT relit
ensuite la vue dans la même transaction et renvoie ce nouvel état au navigateur.

Le déplacement graphique utilise le handler natif de `L.Marker`. Tous les
marqueurs sont immobiles par défaut ; seul le Point sélectionné devient
déplaçable après l’action explicite `Modifier la position sur la carte`. Le drag
reste local au navigateur. Sa validation envoie uniquement :

```json
{"longitude_4326": 2.25, "latitude_4326": 48.75}
```

PostGIS recalcule ensuite la géométrie métier, X/Y et le repérage éventuel. En
cas d’échec, le marqueur reste à sa position provisoire jusqu’à une nouvelle
validation ou à `Annuler le déplacement`.

Sur écran tactile, une fois le mode graphique explicitement activé, un tap sur
la carte déplace également le Point de façon provisoire. Leaflet ne produit pas
ce `click` après un pan : la navigation tactile normale reste donc disponible.
Comme pour le drag desktop, aucune écriture n'a lieu avant `Valider`.

### Localisation d'un Point par bornage

Le mode Bornage écrit directement dans l'objet enfant prévu par le modèle :

```text
public.link_desordres_troncons
→ public.desordre_localisations_reperage
→ desordre_reperage_appliquer_trigger
→ public.appliquer_desordre_reperage()
→ public.borne_offset_vers_xy()
→ public.desordres.geometry
```

Il est proposé uniquement lorsque le Point possède exactement un tronçon
associé et que celui-ci fournit un système de repérage. La liste de bornes vient
de `public.view_systemes_reperage_bornes` et reste filtrée sur ce système.

`PUT /api/desordres/{id}/reperage` accepte uniquement :

```json
{
  "borne_debut_id": "00000000-0000-0000-0000-000000000000",
  "distance_debut_m": 12.5,
  "position_debut_relative": "APRES_BORNE"
}
```

Les sens admis par PostgreSQL sont `AVANT_BORNE`, `SUR_BORNE` et
`APRES_BORNE`. `SUR_BORNE` impose une distance nulle. L'API détermine elle-même
le tronçon et le système depuis les relations en base, écrit la table enfant,
puis relit `view_desordres_points_saisie` avec son repérage dans la même
transaction. La réponse GeoJSON — géométrie, quatre coordonnées et repérage —
remplace entièrement l'état affiché et repositionne le marqueur Leaflet.

### Édition d'une LineString

Les LineString sont lues et écrites dans `public.desordres`. Il n'existe pas de
vue de saisie linéaire équivalente à la vue ponctuelle. Le flux est donc :

```text
GeoJSON LineString EPSG:4326
→ ST_GeomFromGeoJSON
→ ST_Transform(..., 3950)
→ UPDATE public.desordres.geometry
→ desordres_recalcul_reperage_trigger
→ synchroniser_desordre_reperage()
→ relecture GeoJSON EPSG:4326
```

Le trigger existant utilise `ST_StartPoint` et `ST_EndPoint` uniquement pour
calculer le repérage des extrémités. La géométrie persistée conserve tous ses
sommets intermédiaires.

`PUT /api/desordres/{id}/geometry` accepte une LineString ou un Polygon du même
type que l'objet existant. Pour une LineString :

```json
{
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [2.1, 50.5],
      [2.11, 50.51],
      [2.12, 50.52]
    ]
  }
}
```

Chaque position contient une longitude et une latitude finies. Une ligne doit
avoir au moins deux sommets ; PostGIS contrôle également qu'elle n'est ni vide
ni dégénérée avant l'écriture.

Le frontend utilise
[`Leaflet.Editable` 1.2.0](https://github.com/Leaflet/Leaflet.Editable), chargé
depuis unpkg après Leaflet. Leaflet natif ne fournit pas de poignées d'édition
pour les polylignes. Cette bibliothèque minimale expose `enableEdit()` et
`disableEdit()`, déplace les sommets et permet d'en créer depuis les poignées
intermédiaires, sans barre de dessin globale. Elle est distribuée sous licence
WTFPL. Leaflet-Geoman n'a pas été retenu car ses fonctions de dessin, découpe,
rotation et snapping dépassent le besoin de ce lot.

Pendant l'édition, la couche Leaflet porte la géométrie provisoire et
`lastServerFeature` conserve le GeoJSON complet reçu du serveur. `Annuler`
réapplique tous les sommets de cette copie. Aucun appel HTTP n'est effectué par
les événements de déplacement ; le PUT part uniquement avec `Valider la
géométrie`. Après succès, la réponse PostgreSQL remplace la géométrie locale et
le résumé du repérage.

`PUT /api/desordres/{id}/endpoints` accepte deux extrémités et un CRS explicite
(`EPSG:3950` ou `EPSG:4326`). PostgreSQL applique deux `ST_SetPoint` : une ligne
`A → B → C → D → E` devient `A' → B → C → D → E'`. Les sommets
intermédiaires ne sont jamais supprimés silencieusement. Lors d'une création
sans ligne préexistante, PostgreSQL utilise `ST_MakeLine(début, fin)` ; une
ligne à deux sommets est alors le résultat métier attendu.

Le bornage linéaire passe par `PUT /api/desordres/{id}/reperage`. La fonction
`appliquer_desordre_reperage()` convertit séparément début et fin par
`borne_offset_vers_xy()`, puis reconstruit la géométrie avec
`ST_LineSubstring(troncon.geometry, début, fin)`. Le bornage est autoritaire :
la géométrie libre et ses anciens sommets intermédiaires sont volontairement
détruits et remplacés par la portion du tronçon, dont les sommets intermédiaires
sont conservés. Si fin précède début, le résultat est inversé pour respecter
l'ordre saisi.

### Polygon et point représentatif

Le Polygon reste éditable uniquement sur la carte. Après validation, PostGIS
contrôle et persiste le Polygon, puis la fiche relue affiche sous « Point
représentatif » X/Y (EPSG:3950) et longitude/latitude (EPSG:4326) calculés par
`ST_PointOnSurface`. Ces quatre valeurs sont en lecture seule : elles ne sont
ni une famille d'autorité ni un moyen de reconstruire le Polygon.

### Type, identifiants et visibilité des couches

Le type de désordre facultatif est éditable pour les trois géométries. Le
sélecteur utilise uniquement `GET /api/referentiels/types-desordre`; toute
référence renseignée doit être active, puis l'objet est relu après le PUT.

`SIRS_WEB_SHOW_UUID=false` (valeur par défaut) masque centralement les UUID dans
les fiches, propriétés, arbre et observations. `true`, `1`, `yes` ou `on` les
réaffiche pour le diagnostic. Les identifiants restent toujours présents dans
les réponses API et dans l'état interne JavaScript.

La légende en bas à gauche contient les cases de visibilité des tronçons et des
trois géométries de désordre. Elle ajoute ou retire les groupes Leaflet déjà
chargés, sans requête ni rechargement. Le contrôle Leaflet concurrent en haut à
droite n'est plus créé.

La consultation des observations respecte la chaîne relationnelle cible :

```text
public.desordres.id
→ public.observations.desordre_id
→ public.photos.observation_id
```

La liste est triée par date décroissante. Elle expose `designation`, `date`,
`evolution`, `urgence_id`/son libellé, `valid` et le nombre de photos. La fiche
d’une observation renvoie en une seule lecture ses photos enfants (`id`, date,
désignation, validité et nom de fichier).

La table `public.photos` ne contient aucun binaire ni URL exploitable : elle
conserve seulement `chemin_source`, hérité de la source. Aucun répertoire média
serveur n’étant configuré, l’API n’expose ni ce chemin local ni un faux endpoint
de contenu. La visionneuse affiche donc les métadonnées, la navigation
précédent/suivant et un message explicite d’indisponibilité. Elle pourra charger
la pleine résolution à la demande lorsqu’une règle sûre de matérialisation des
médias aura été définie.

## Lancement local

Depuis la racine du dépôt :

```console
python -m pip install -e . -e webapp
python -m uvicorn --app-dir webapp/backend digues_webapp.app:app --reload
```

Ouvrir ensuite <http://127.0.0.1:8000/>. La documentation automatique de l’API
est disponible sur <http://127.0.0.1:8000/docs>.

Routes disponibles :

- `GET /` ;
- `GET /api/config` pour la visibilité des UUID ;
- `GET /api/troncons` ;
- `GET /api/troncons/options` pour tous les choix de rattachement, y compris
  ceux qui ne figurent pas dans l'arbre centré sur les systèmes ;
- `GET /api/troncons/{id}/reperage-options` pour le système et les bornes du
  tronçon explicitement choisi ;
- `GET /api/systemes-endiguement` ;
- `POST /api/systemes-endiguement` pour créer puis relire un système ;
- `POST /api/digues` pour créer puis relire une digue avec son parent ;
- `POST /api/troncons` pour créer puis relire un tronçon GeoJSON ;
- `GET /api/referentiels/types-desordre` pour alimenter le sélecteur contrôlé ;
- `GET /api/desordres` ;
- `POST /api/desordres` pour créer puis relire un Point, LineString ou Polygon ;
- `GET /api/desordres/{id}` pour un désordre Point, LineString ou Polygon ;
- `GET /api/desordres/{id}/observations` pour les observations directement
  liées au désordre ;
- `GET /api/observations/{id}` pour une observation de désordre et les
  métadonnées de ses photos enfants ;
- `PUT /api/desordres/{id}/reperage` pour le bornage d'un Point ou d'une
  LineString liés à exactement un tronçon ;
- `PUT /api/desordres/{id}/geometry` pour l'édition graphique d'une LineString
  ou d'un Polygon existant ;
- `PUT /api/desordres/{id}/endpoints` pour modifier seulement les extrémités
  d'une LineString ;
- `PUT /api/desordres/{id}` pour les informations générales, le type et les
  rattachements, ainsi que les coordonnées d'un Point.

Le PUT accepte les champs texte `designation`, `type_desordre_id` et
`commentaire`, ainsi qu’au plus une des deux familles complètes :

```json
{"coord_x_3950": 123.45, "coord_y_3950": 678.9}
```

ou :

```json
{"longitude_4326": 2.25, "latitude_4326": 48.75}
```

## Vérification manuelle de la création d'un désordre

1. Ouvrir l'arbre, sélectionner un tronçon, puis choisir `+ Nouvel objet` →
   `Désordre`. Vérifier que ce tronçon est préselectionné mais modifiable.
2. Choisir Point et `Placement sur la carte`, placer un marqueur puis le
   déplacer. Contrôler dans le réseau qu'aucun POST n'est envoyé.
3. Annuler le dessin, le restaurer, puis annuler le formulaire complet. Après
   rechargement, vérifier qu'aucun objet n'a été créé.
4. Recommencer et valider. Vérifier la couche, la fiche Point relue, les quatre
   coordonnées et, avec exactement un tronçon doté d'un système, le repérage.
5. Créer deux autres Points, une fois par X/Y EPSG:3950 et une fois par
   longitude/latitude. Vérifier que l'autre famille est relue depuis PostgreSQL.
6. Créer une ligne sinueuse d'au moins quatre sommets, la corriger avant
   validation, puis vérifier tous les sommets après rechargement.
7. Créer un Polygon fermé. Vérifier son affichage, sa fiche en lecture seule et
   son point représentatif calculé, puis sa persistance après rechargement.
8. Associer successivement zéro, un et plusieurs tronçons et vérifier les règles
   de disponibilité du repérage. Aucun tronçon ne doit être choisi par proximité.
9. Essayer un Polygon auto-croisé ou un parent/référentiel devenu invalide : le
   message doit rester exploitable, la saisie et le dessin doivent rester en
   place, et aucun objet partiel ne doit exister en base.
10. Commencer un dessin puis tenter de changer son type : le changement doit
    être refusé jusqu'à l'annulation explicite du dessin.

## Vérification manuelle générale du formulaire

1. Ouvrir <http://127.0.0.1:8000/>.
2. Ouvrir `+ Nouvel objet`, choisir `Système d'endiguement`, saisir un libellé,
   créer et vérifier la fiche relue ainsi que l'apparition dans l'arbre sans
   rechargement de page.
3. Sélectionner ce système dans l'arbre, créer une digue et vérifier que le
   système est prérempli tout en restant modifiable avant validation. Vérifier
   ensuite l'apparition de la digue sous le bon système.
4. Sélectionner la nouvelle digue puis commencer la création d'un tronçon.
   Vérifier que la digue est préremplie, dessiner une ligne à au moins trois
   sommets et déplacer un sommet : aucun `POST` ne doit apparaître dans l'onglet
   réseau.
5. Cliquer sur `Annuler le dessin`, le restaurer et vérifier tous ses sommets.
   Cliquer ensuite sur l'annulation générale du brouillon et contrôler en base
   ou après rechargement qu'aucun tronçon n'a été créé.
6. Recommencer, dessiner plusieurs sommets puis cliquer sur `Créer`. Vérifier la
   nouvelle couche sur la carte, son indexation/zoom depuis l'arbre et la fiche
   relue. Recharger la page et vérifier la persistance du tracé complet.
7. Refaire une tentative avec une LineString dégénérée ou un parent devenu
   invalide : l'erreur doit être explicite et le brouillon doit rester
   corrigeable.
8. Vérifier l’absence des contrôles Leaflet `+` et `−`, puis utiliser la molette
   pour confirmer que la carte reste zoomable.
9. Cliquer sur `Système d'endiguement` et vérifier l’ouverture du panneau gauche.
10. Déplier successivement un système, une digue puis ses tronçons.
11. Cliquer sur les noms des trois niveaux et vérifier leurs propriétés.
12. Sélectionner un tronçon, vérifier sa mise en évidence, puis cliquer sur
   `Zoomer sur ce tronçon`.
13. Laisser le panneau gauche ouvert et cliquer sur un désordre ponctuel rouge ;
   vérifier que le panneau droit s’ouvre sans fermer le panneau gauche.
14. Vérifier que le panneau droit affiche l’identifiant, les champs métier et les
   deux familles de coordonnées relues depuis PostgreSQL.
15. Choisir `Modifier X/Y`, changer les deux valeurs, puis cliquer sur
   `Enregistrer`.
16. Vérifier que le marqueur se déplace et que longitude/latitude sont remplacées
   par les valeurs renvoyées par PostgreSQL.
17. Choisir ensuite `Modifier longitude/latitude`, modifier les deux valeurs et
   enregistrer ; vérifier cette fois la mise à jour de X/Y et du marqueur.
18. Modifier un champ sans enregistrer puis cliquer sur `Annuler` ; le formulaire
   doit revenir au dernier état reçu du serveur.
19. Pour observer un refus sans perdre la saisie, vider une coordonnée de la
   famille sélectionnée puis cliquer sur `Enregistrer`.
20. Cliquer sur `Modifier la position sur la carte`, déplacer le seul marqueur
   sélectionné et vérifier que les lon/lat changent sans requête d’écriture.
21. Cliquer sur `Annuler le déplacement` et vérifier le retour exact à la
    position serveur.
22. Recommencer le déplacement puis cliquer sur `Valider la position` ; vérifier
    le recalage du marqueur ainsi que l’actualisation des quatre coordonnées.
23. Ouvrir l’onglet `Observations`, vérifier l’ordre décroissant des dates, puis
    ouvrir une observation.
24. Vérifier ses propriétés et la section `Photos`, puis cliquer sur une photo.
25. Dans la visionneuse, utiliser précédent/suivant, la fermer, revenir à la
    liste des observations puis à l’onglet `Général`.
26. Vérifier qu’une édition du désordre fonctionne toujours après ce parcours.
27. Sur un Point lié à exactement un tronçon, sélectionner `Modifier le
    bornage`, choisir une borne, une distance et un sens, puis enregistrer.
28. Vérifier que le marqueur, X/Y, longitude/latitude et le PR sont tous remplacés
    par la réponse PostgreSQL ; fermer puis rouvrir le Point pour vérifier la
    persistance.
29. Modifier le bornage puis cliquer sur `Annuler` et vérifier le retour exact au
    dernier état serveur.
30. Ouvrir un Point sans tronçon : le mode Bornage doit être absent. Vérifier
    que son sélecteur simple et un appel API direct refusent un deuxième tronçon.
31. Vérifier enfin que les modes X/Y, lon/lat et déplacement graphique restent
    mutuellement exclusifs avec le bornage.
32. Cliquer sur un désordre LineString et vérifier sa fiche, son nombre de
    sommets et le repérage relu.
33. Cliquer sur `Modifier la géométrie`, déplacer un sommet et éventuellement
    une poignée intermédiaire ; vérifier dans l'onglet réseau qu'aucun PUT ne
    part pendant ces manipulations.
34. Cliquer sur `Annuler` et vérifier le retour exact de tous les sommets.
35. Recommencer avec plusieurs sommets, puis cliquer sur `Valider la géométrie`.
36. Vérifier le recalage de la ligne sur la réponse serveur, fermer et rouvrir la
    fiche, puis confirmer la persistance des sommets intermédiaires.
37. Pendant une nouvelle édition, tenter de sélectionner un autre désordre et
    d'ouvrir les observations : l'interface doit demander de valider ou annuler.
38. Pour une ligne libre à au moins trois sommets, modifier début/fin par
    Coordonnées et vérifier que les sommets intermédiaires sont identiques.
    Appliquer ensuite un Bornage : vérifier au contraire que la géométrie libre
    disparaît et que le résultat suit exactement la portion du tronçon.
39. Modifier le type d'un Point, d'une ligne puis d'un Polygon ; tester aussi
    type → aucun type et une référence inactive par appel direct.
40. Modifier graphiquement un Polygon et vérifier le recalcul des quatre valeurs
    en lecture seule de son point représentatif.
41. Décocher chaque couche dans la légende en bas à gauche et vérifier son retour
    sans rechargement ; confirmer l'absence du contrôle Leaflet en haut à droite.
42. Démarrer une fois avec `SIRS_WEB_SHOW_UUID=false`, puis `true`, et vérifier
    que seul l'affichage change, jamais les sélections ni les appels API.

La base cible doit avoir été créée, initialisée et alimentée par les commandes
habituelles de `digues-app`. L’accès réseau au serveur de fond OpenStreetMap et
au CDN Leaflet est nécessaire pour afficher la carte complète.
