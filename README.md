# sirs-postgre

## Objectif

sirs-postgre est un projet Python autonome qui organise la migration progressive
de SIRS Digues V2 depuis CouchDB vers PostgreSQL/PostGIS.

PostgreSQL/PostGIS constitue le futur modèle métier. QGIS est l'interface
principale prévue pour consulter et éditer les données. Le projet avance de façon
itérative : chaque brique métier est inspectée dans la source, modélisée, migrée,
validée puis intégrée à QGIS avant d'élargir le périmètre.

## Architecture générale

- CouchDB reste actuellement la source de migration.
- PostgreSQL 16 et PostGIS portent le modèle cible dans le schéma `public`.
- La CLI Python contrôle l'infrastructure, crée le schéma et exécute les migrations.
- QGIS charge directement les tables PostgreSQL pour l'exploitation et l'édition.

La base PostgreSQL cible est encore considérée comme jetable pendant le
développement. Le cycle normal consiste à la recréer, initialiser son schéma puis
relancer la migration depuis la source.

## État actuel

Le noyau métier, les ouvrages, les aménagements hydrauliques et la végétation
sont opérationnels. Ils couvrent :

- les tables métier `systemes`, `digues`, `troncons`, `desordres`,
  `observations` et `photos` ;
- le noyau de repérage linéaire `systemes_reperage`, `bornes_reperage`,
  `link_troncons_bornes` et `link_systemes_reperage_bornes`, avec système par
  défaut facultatif sur un tronçon ;
- la relation N-N `link_desordres_troncons` ;
- les référentiels `ref_categories_desordre`, `ref_types_desordre` et
  `ref_urgences` ;
- les tables `ouvrages_hydrauliques`, `equipements_mesure`, `cheminements`,
  `mobilier` et `reseaux_techniques`, ainsi que leurs cinq référentiels de types
  indépendants ;
- les relations explicites N-N `link_cheminements_troncons` et
  `link_cheminements_desordres` ;
- `amenagements_hydrauliques`, son référentiel minimal et la relation explicite
  N-N `link_amenagements_troncons` ;
- les plans, parcelles de gestion et objets physiques de végétation, avec
  `link_parcelles_gestion_troncons` ;
- les observations généralisées et les photos exclusivement rattachées à une
  observation ;
- le diagnostic de couverture CouchDB généré dans `audits/bilan.md` ;
- le registre persistant des anomalies dans `audits/anomalies.json` et
  `audits/anomalies.csv`, avec distinction `DATA`, `COVERAGE` et
  `MIGRATION_DECISION` ;
- la détection du CRS global SIRS depuis le document CouchDB `$sirs`, avec
  reprojection réelle vers `EPSG:3950` lorsque le CRS source diffère.

Les objets métier provenant de CouchDB conservent leurs UUID historiques. Les
insertions réalisées directement dans PostgreSQL ou QGIS peuvent omettre l'ID :
les PK UUID simples, y compris l'ID technique de la table de liaison, utilisent
`DEFAULT gen_random_uuid()`.

Les référentiels du noyau conservent littéralement leurs identifiants CouchDB en
PK `TEXT`, par exemple `RefTypeDesordre:57` ou `RefUrgence:1`. Les cinq nouveaux
référentiels Ouvrages utilisent au contraire une abréviation métier stable comme
PK (`PIE`, `ECH`, `VAN`, etc.) ; les anciens IDs `RefOuvrage...` servent
uniquement au mapping de migration.

## Installation

Le projet nécessite Python 3.11 ou plus récent ainsi qu'un serveur PostgreSQL
compatible disposant de PostGIS et de `pgcrypto`. Le développement courant est
validé sur PostgreSQL 16.

```bash
cd /home/julien/Projects/sirs-postgre
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

## Configuration

Créer la configuration locale depuis le modèle versionné :

```bash
cp config.example.env config.env
# éditer config.env
```

La CLI charge automatiquement le fichier optionnel `config.env` situé à la
racine du projet. Les variables déjà exportées dans le shell restent prioritaires
car le chargement n'écrase pas l'environnement existant.

`config.example.env` est uniquement un modèle : la CLI ne le charge jamais et
n'y écrit jamais de secrets. `config.env` contient la configuration locale et
n'est pas versionné.

La connexion PostgreSQL peut être définie par les paramètres séparés
`SIRS_POSTGRE_HOST`, `SIRS_POSTGRE_PORT`, `SIRS_POSTGRE_DATABASE`,
`SIRS_POSTGRE_USER` et `SIRS_POSTGRE_PASSWORD`, ou par
`SIRS_POSTGRE_DSN`, prioritaire. La base d'administration utilisée par
`recreate` est configurable avec `SIRS_POSTGRE_ADMIN_DATABASE` et vaut
`postgres` par défaut.

### Gestion des systèmes de coordonnées

SIRS Digues stocke le CRS global de chaque base CouchDB dans le document
`$sirs`, notamment dans `epsgCode`. Le migrateur utilise cette valeur comme
autorité, vérifie que le code est résolvable par PostGIS, puis standardise les
géométries dans le CRS cible fixe `EPSG:3950`.

Si le CRS source est déjà `EPSG:3950`, le WKT est inséré avec ce SRID sans
reprojection. Si le CRS source diffère, le migrateur construit d'abord la
géométrie dans son vrai CRS puis applique `ST_Transform(..., 3950)`. Affecter
simplement le SRID 3950 à des coordonnées exprimées dans un autre CRS donnerait
une localisation fausse et n'est jamais utilisé comme transformation.

Lorsque `$sirs.epsgCode` manque ou n'est pas exploitable, un fallback explicite
peut être configuré :

```bash
SIRS_SOURCE_SRID=2154
```

La variable accepte aussi la forme `EPSG:2154`. Elle est normalement inutile
pour une base SIRS correctement renseignée. Le fallback n'autorise jamais à
masquer une contradiction : si `$sirs.epsgCode`, `crsWkt`, `proj4` ou
`SIRS_SOURCE_SRID` apportent des informations incompatibles, la migration est
bloquée. Le champ objet historique `crsName` sert uniquement de contrôle de
cohérence : il n'est jamais utilisé pour choisir le CRS source et son absence
n'est pas une anomalie.

## Commandes principales

Cycle complet actuel :

```bash
cd /home/julien/Projects/sirs-postgre
source .venv/bin/activate

sirs-postgre check
sirs-postgre recreate
sirs-postgre init-schema
sirs-postgre migrate-core
sirs-postgre check --target-only
sirs-postgre diagnose
sirs-postgre qgis-project --output qgis/sirs_postgre.qgz
```

### `check`

```bash
sirs-postgre check
```

La commande diagnostique les connexions CouchDB et PostgreSQL, les versions de
PostgreSQL, PostGIS et `pgcrypto`, ainsi que la présence des tables attendues.
Elle indique aussi si l'authentification est configurée sans jamais afficher les
mots de passe. L'absence de credentials n'est pas une erreur si la connexion
locale réussit.

Le diagnostic ne modifie aucune base. La partie CouchDB n'effectue que des
lectures et la partie PostgreSQL uniquement des `SELECT`.

Options disponibles :

```bash
sirs-postgre check --source-only
sirs-postgre check --target-only
sirs-postgre check --profile secure
sirs-postgre check --source-database autre_base
```

### `recreate`

```bash
sirs-postgre recreate
```

> **Attention — opération destructive :** `sirs-postgre recreate` exécute un
> `DROP DATABASE` sur la base cible configurée. Toute donnée créée directement
> dans PostgreSQL ou QGIS depuis la dernière migration est supprimée.

La commande ferme les connexions actives vers la seule base cible, la supprime,
la recrée puis active les extensions PostGIS et `pgcrypto`. Les bases protégées
`postgres`, `template0`, `template1`, la base d'administration configurée et
les noms dangereux sont explicitement refusés.

QGIS peut conserver en cache l'ancienne définition des couches après une
recréation. Pendant cette phase de développement, un rafraîchissement de la
source de données ou une réimportation des couches peut être nécessaire.

### `init-schema`

```bash
sirs-postgre init-schema
```

La commande vérifie les extensions puis crée transactionnellement le schéma
courant dans `public`. Les instructions utilisent `CREATE TABLE IF NOT EXISTS` :
l'initialisation est réexécutable et vérifie la présence de toutes les tables
avant de valider la transaction. Cette commande crée uniquement la structure ;
la lecture de CouchDB relève de `migrate-core`.

### `migrate-core`

```bash
sirs-postgre migrate-core
```

La commande migre le noyau, 118 objets Ouvrages, les aménagements hydrauliques,
les plans/parcelles de gestion et les objets végétation depuis CouchDB dans
l'ordre imposé par les relations. L'unique
`OuvrageAssocieAmenagementHydraulique` rejoint désormais
`ouvrages_hydrauliques` avec son parent explicitement stocké. Les ponts,
escaliers d'accès, voies sur digue, voies d'accès et chemins d'accès techniques
sont réunis dans `cheminements`. Les huit `CheminAccesDependance` sont migrés
même sans parent ni tronçon : aucune relation obligatoire vers un aménagement
hydraulique n'est supposée et aucun rattachement spatial n'est inféré. L'unique
`PrestationAmenagementHydraulique` reste également différée jusqu'au modèle
général des prestations.
Les anciennes photos directement portées par un objet sont regroupées par objet
et date sous des observations synthétiques déterministes. Après une migration
réussie, le bilan de couverture est automatiquement régénéré ; une erreur du
diagnostic rend la commande explicitement incomplète.
Les insertions et validations s'exécutent dans une transaction PostgreSQL unique :
une erreur bloquante entraîne un rollback complet. Le CRS source est résolu une
seule fois pour l'exécution puis partagé par les modules de migration ; les
géométries ne sont reprojetées que si ce CRS diffère de `EPSG:3950`.

La migration refuse une cible contenant déjà des données et n'effectue aucun
UPSERT. Il faut alors rejouer le cycle `recreate`, `init-schema`,
`migrate-core`.

### `diagnose`

```bash
sirs-postgre diagnose
```

Cette commande indépendante lit les documents CouchDB et génère
`audits/bilan.md`, `audits/anomalies.json` et `audits/anomalies.csv`. Elle
découvre les valeurs `@class` et les clés JSON réelles, les compare au registre
de couverture et distingue `MIGREE`, `PARTIELLE`, `NON_MIGREE`,
`TECHNIQUE_IGNORE` et `REFERENTIEL_IGNORE`. Une classe ou un champ inconnu dans
une autre base apparaît donc automatiquement dans le bilan et, lorsqu'il est
actionnable, dans le registre des anomalies.

Le bilan contient aussi une synthèse CRS : CRS source détecté, origine de cette
détection, CRS cible et nécessité éventuelle d'une transformation. Les codes
EPSG sont validés contre PostGIS avant d'être utilisés pour une migration
géométrique.

### Génération du projet QGIS

```bash
sirs-postgre qgis-project --output qgis/sirs_postgre.qgz
```

La commande génère entièrement le QGZ depuis le code et la configuration
PostgreSQL existante. Elle nécessite PyQGIS 3.38 ou plus récent et doit être
lancée avec le Python fourni par QGIS/OSGeo4W ; son absence produit une erreur
explicite sans affecter les autres commandes. Le projet contient les couches,
groupes, relations et formulaires du prototype de repérage des désordres,
ainsi qu'un unique fond XYZ OpenStreetMap connecté placé derrière les couches
métier. Ce fond ne couvre pas l'utilisation hors connexion de QField.

Le mot de passe PostgreSQL n'est jamais écrit dans le QGZ. Une configuration
d'authentification QGIS locale peut être référencée avec `--authcfg ID`, ou
QGIS peut utiliser `.pgpass`/une saisie interactive. Le code générateur est
versionné ; `qgis/sirs_postgre.qgz` reste un artifact local ignoré par Git. La
procédure Windows détaillée figure dans
`docs/generation_projet_qgis.md`.

## Diagnostic et registre des anomalies

Les trois livrables ont des usages distincts :

- `bilan.md` synthétise la couverture globale des classes, champs et relations ;
- `anomalies.json` est le registre structuré et persistant destiné au suivi ;
- `anomalies.csv` expose le même registre aux tableurs, à QGIS et aux autres
  outils d'analyse.

Chaque entrée reçoit un `anomaly_id` déterministe calculé depuis la base source,
la classe, une clé de sujet interne stable, la catégorie et le champ concernés.
Cette clé interne n'est pas exportée. `source_document_id` conserve exactement
le `_id` du document CouchDB à ouvrir ; `source_object_id` conserve exactement
l'identifiant d'un sous-objet uniquement lorsque celui-ci est le sujet réel du
constat. Un constat portant directement sur le document laisse donc
`source_object_id` à NULL. Le message n'entre pas dans l'identité : il peut
évoluer sans casser le suivi. Une
régénération préserve le statut, le commentaire de résolution et la première
date de détection. Une anomalie disparue reste dans l'historique avec
`active=false`; si elle réapparaît, elle retrouve le même ID et redevient active.
`active` décrit uniquement la présence du constat dans le dernier diagnostic,
tandis que `status` enregistre une décision humaine. Le diagnostic ne transforme
donc jamais automatiquement un statut `OPEN` en statut résolu :

- `active=true`, `status=OPEN` : problème actuel non traité ;
- `active=false`, `status=OPEN` : problème absent du dernier diagnostic, sans
  décision humaine enregistrée ;
- `active=true`, `status=ACCEPTED_AS_IS` : problème encore présent mais accepté ;
- `active=false`, `status=RESOLVED_IN_COUCHDB` : correction enregistrée et
  constat désormais absent.

Les statuts disponibles sont `OPEN`, `RESOLVED_IN_COUCHDB`,
`RESOLVED_IN_POSTGRES`, `RESOLVED_BY_MIGRATOR`, `ACCEPTED_AS_IS` et `IGNORED`.
`correction_location` indique si l'action relève de `COUCHDB`, `POSTGRESQL`, du
`MIGRATOR`, des deux (`EITHER`), d'une revue manuelle ou n'est pas applicable.
La sévérité (`INFO`, `WARNING`, `ERROR`, `BLOCKING`) est choisie explicitement
selon l'impact et non déduite mécaniquement de la catégorie.

L'affichage regroupe en outre les constats en trois familles internes : `DATA`
pour les géométries, références, relations, médias et revues manuelles ;
`COVERAGE` pour les classes/champs inconnus, partiels ou différés ;
`MIGRATION_DECISION` pour les overrides explicites. Cette séparation évite
d'interpréter chaque lacune de couverture comme une corruption de données.

Consultation :

```bash
sirs-postgre anomalies
sirs-postgre anomalies --open
sirs-postgre anomalies --actionable
sirs-postgre anomalies --category INVALID_GEOMETRY
sirs-postgre anomalies --source-document-id <id-couchdb-exact>
sirs-postgre anomalies --source-object-id <id-sous-objet-exact>
```

La vue générale distingue les anomalies actives et inactives, puis les statuts
des seules anomalies actives. `--open` conserve toutes les catégories actives
encore ouvertes. `--actionable` se limite aux anomalies `DATA` actives et
ouvertes ; il exclut notamment les classes partiellement migrées, les
fonctionnalités différées et les décisions `SOURCE_OVERRIDE`.

Enregistrement d'une décision locale :

```bash
sirs-postgre anomalies resolve <anomaly_id> \
  --status RESOLVED_IN_COUCHDB \
  --comment "Géométrie corrigée et validée dans la source"
```

La commande `anomalies resolve` ne contacte et ne modifie ni CouchDB ni
PostgreSQL. Elle met uniquement à jour `audits/anomalies.json` et son export CSV;
la prochaine exécution de `diagnose` préservera cette décision.

Une correction réalisée uniquement dans PostgreSQL est perdue au prochain
`recreate`. Elle peut servir à vérifier une solution ou corriger temporairement
la cible, mais une correction reproductible doit ensuite être appliquée dans
CouchDB ou codée dans le migrateur/`source_overrides.py`.

## Modèle PostgreSQL actuel

```text
systemes
  └── 1-N → digues
               └── 1-N → troncons

troncons
├── 1-N → systemes_reperage
│          └── N-N ↔ link_systemes_reperage_bornes ↔ bornes_reperage
└── N-N ↔ link_troncons_bornes ↔ bornes_reperage

desordres
  └── N-N ↔ link_desordres_troncons ↔ troncons

desordres / troncons / familles d'ouvrages / amenagements_hydrauliques / vegetation
  └── 1-N → observations
                  └── 1-N → photos

ref_categories_desordre
  └── 1-N → ref_types_desordre
                  └── 1-N → desordres.type_desordre_id

ref_urgences
  └── 1-N → observations.urgence_id

ref_types_amenagement_hydraulique
  └── 1-N → amenagements_hydrauliques
                  └── N-N ↔ link_amenagements_troncons ↔ troncons

amenagements_hydrauliques
  └── 1-N → ouvrages_hydrauliques.amenagement_hydraulique_id
```

`categorie_desordre_id` n'est volontairement pas stocké dans `desordres`. Quand
un type est renseigné, sa catégorie est déduite par
`ref_types_desordre.categorie_id`. Cette règle évite de reproduire une donnée
redondante susceptible de devenir incohérente.

Les relations 1-N utilisent des FK directes. La relation entre désordres et
tronçons est réellement N-N : `link_desordres_troncons` possède un ID UUID
technique pour QGIS et garantit l'unicité du couple
`(desordre_id, troncon_id)`.

`observations` possède une FK nullable explicite vers chacune des neuf familles
métier actuellement prises en charge. Une contrainte `num_nonnulls(...) = 1`
garantit qu'une observation a exactement un parent. Ces FK permettent à QGIS de
découvrir les relations sans couple polymorphe `objet_type/objet_id`.

Une ZEC représente conceptuellement un ensemble hydraulique pouvant associer
une emprise de stockage et un ou plusieurs tronçons ; elle ne se réduit donc pas
au seul polygone de `amenagements_hydrauliques`. Seules les relations présentes
dans `tronconIds` sont migrées. Une intersection spatiale ne crée jamais de FK.

La géométrie PostGIS et le repérage linéaire sont deux informations distinctes.
Une borne est autonome et peut appartenir à plusieurs tronçons ou systèmes ;
`valeur_pr` qualifie donc le couple système–borne, jamais la borne seule. L'ordre
de la liste CouchDB est conservé uniquement comme trace non autoritative. Les
localisations des objets `Positionable` (bornes début/fin, distances, sens, PR
et positions) restent explicitement différées au lot suivant.

Le noyau expose trois conversions PostGIS déterministes :
`xy_vers_reperage`, `borne_offset_vers_xy` et `pr_vers_xy`. Chacune exige le
tronçon et le système de repérage explicites ; le système par défaut du tronçon
n'est jamais consulté par le moteur. L'abscisse est une distance géométrique
interne depuis le début du LineString et ne doit pas être confondue avec le PR,
qui est interpolé entre les couples système–borne. Les PR décroissants sont
acceptés ; les systèmes ambigus, incomplets et les valeurs hors domaine sont
signalés par des statuts, sans rabattement ni extrapolation. Aucun trigger ne
synchronise géométrie et repérage : l'appelant choisit explicitement la
conversion. Un prototype volontairement spécialisé conserve désormais le
repérage historique des seuls désordres dans
`desordre_localisations_reperage` (relation 0..N). Il garde la géométrie métier
indépendante, expose une vue lisible pour QGIS et laisse toutes les autres
familles hors périmètre ; le modèle transversal `localisations_reperage` n'est
donc pas encore implémenté.

### Règles génériques et overrides de source

Le transformateur des aménagements ne dépend d'aucun nom, UUID ou nombre
d'objets propre à une base. Un type source connu passe par un mapping explicite ;
un type absent ou inconnu devient `IND` avec warning, sans perte de l'objet. Une
géométrie autre que Polygon bloque la transaction au lieu d'être corrigée.

Les décisions propres à une base sont regroupées dans
`migration/source_overrides.py`, indexées par nom de base CouchDB. Pour la base
auditée `cabbalr` seulement, les six UUID actuels sont provisoirement classés
`ZEC`. Cette configuration n'est pas une règle SIRS universelle : une autre base,
même avec les mêmes désignations, conserve `IND` en l'absence de mapping de type.

## Végétation et gestion de la végétation

Le modèle sépare les objets physiques des structures qui organisent leur
gestion :

- `plans_gestion_vegetation` conserve les plans et leur période ;
- `parcelles_gestion_vegetation` porte les segments de gestion et leur
  géométrie linéaire ;
- `link_parcelles_gestion_troncons` conserve uniquement les relations source
  explicites aux tronçons ;
- `vegetation` regroupe les objets physiques sous les natures structurelles
  `ARB`, `PEU`, `INV` ou `IND`.

Chaque objet physique référence sa parcelle de gestion. Il ne duplique ni le
tronçon, ni la digue, ni le système. La relation 1 parcelle–1 tronçon observée
dans `cabbalr` est historique : la table de lien accepte plusieurs tronçons par
parcelle et aucune intersection spatiale ne crée de relation.

`vegetation.geometry` accepte uniquement Point, LineString, Polygon ou NULL en
EPSG:3950. Le migrateur conserve une géométrie valide, transforme une ligne
d'arbre dégénérée en son Point réellement stocké, ou utilise les positions
début/fin identiques d'un arbre sans géométrie. Une géométrie explicite valide
peut récupérer une source corrompue seulement si elle est compatible. Deux
représentations valides divergentes, ou une corruption sans alternative, donnent
`MANUAL_REVIEW` : la ligne métier est conservée avec une géométrie NULL et un
warning dédié. `ST_MakeValid` n'est jamais appliqué automatiquement.

Les décisions propres au corpus restent dans `migration/source_overrides.py`.
Pour `cabbalr`, seul Bos3 sélectionne explicitement `explicitGeometry` après
audit. Aucun nom tel que « Haie », « Bos1 » ou « Ran1 » n'est utilisé comme règle
générique.

Les traitements embarqués et les tableaux de planification sont différés, car
ils ne contiennent actuellement aucune action opérationnelle. Aucune essence
n'est extraite des commentaires : le texte source est conservé et une future
relation N-N aux essences pourra être étudiée avec le modèle général des
interventions et prestations.

## Migration CouchDB → PostgreSQL

Le mapping actuel est issu de l'inspection des documents CouchDB :

| Source CouchDB | Cible PostgreSQL | Transformation principale |
|---|---|---|
| `RefCategorieDesordre` | `ref_categories_desordre` | `_id` conservé littéralement en `TEXT` |
| `RefTypeDesordre` | `ref_types_desordre` | `_id` conservé ; `categorieId` devient `categorie_id` |
| `RefUrgence` | `ref_urgences` | `_id` conservé littéralement en `TEXT` |
| `SystemeEndiguement` | `systemes` | UUID, `libelle`, `valid` conservés |
| `Digue` | `digues` | `systemeEndiguementId` devient `systeme_endiguement_id`, nullable |
| `TronconDigue` | `troncons` | `digueId`, libellé, validité et WKT conservés |
| `TronconDigue.borneIds` | `link_troncons_bornes` | relations explicites uniquement, sans proximité |
| `TronconDigue.systemeRepDefautId` | `troncons.systeme_reperage_defaut_id` | FK d'existence et validation du même tronçon |
| `SystemeReperage` | `systemes_reperage` | UUID, `linearId`, libellé, commentaire et validité conservés |
| `BorneDigue` | `bornes_reperage` | UUID, Point via le pipeline CRS, attributs et validité conservés |
| `SystemeReperage.systemeReperageBornes[]` | `link_systemes_reperage_bornes` | UUID du sous-objet, borne, `valeurPR` exacte, ordre source et validité |
| `Desordre` | `desordres` | champs métier, type et géométrie dérivée des positions |
| `Desordre.linearId` | `link_desordres_troncons` | liaison N-N avec ID technique généré |
| `*.observations[]` | `observations` | aplatissement et injection de l'unique FK métier |
| `Observation.urgenceId` | `observations.urgence_id` | référence `TEXT` vérifiée ou `NULL` |
| `Observation.designation` | `observations.designation` | texte nullable, `NULL` si absent |
| `Observation.photos[]` | `photos` | aplatissement et injection de `observation_id` |
| `Objet.photos[]` | `observations` + `photos` | regroupement par objet/date sous une observation synthétique stable |
| `Photo.chemin` | `photos.chemin_source` | valeur conservée, sans déduplication par chemin |

Les observations conservent notamment `designation`, `date`, `evolution` et
`valid`. `urgenceId` n'est conservé que pour les observations de désordres. Une
photo métier n'a jamais de FK directe vers un tronçon, un ouvrage ou une
végétation : le modèle impose systématiquement objet → observation → photo. Les
UUID source sont préservés ; seules les observations synthétiques reçoivent un
UUID v5 reproductible. Une date absente reste `NULL` avec warning. Les chemins
de photos ne servent pas à dédupliquer les lignes.

`Desordre.categorieDesordreId` sert uniquement à contrôler la cohérence avec la
catégorie du type. Une incohérence est signalée, mais la catégorie source n'est
ni corrigée ni stockée dans `desordres`.

Exemple de comptes obtenus lors d'une migration validée de la source live :

| Table | Lignes |
|---|---:|
| `systemes` | 9 |
| `digues` | 26 |
| `troncons` | 104 |
| `systemes_reperage` | 104 |
| `bornes_reperage` | 208 |
| `link_troncons_bornes` | 208 |
| `link_systemes_reperage_bornes` | 208 |
| `desordres` | 1 597 |
| `link_desordres_troncons` | 1 597 |
| `observations` | 3 400 |
| `photos` | 3 967 |
| `ref_categories_desordre` | 7 |
| `ref_types_desordre` | 74 |
| `ref_urgences` | 5 |

Ces valeurs décrivent un état observé de la source, pas des constantes métier.
La migration calcule les comptes depuis CouchDB à chaque exécution et les compare
dynamiquement aux comptes PostgreSQL avant le commit.

Les objets `valid=false` sont migrés : cet état historique ne signifie pas une
suppression. Aucune donnée source n'est corrigée silencieusement. Une
incohérence explicitement gérée produit un warning ; une rupture qui compromet
les FK, les identifiants ou les validations annule la migration.

## Géométries

### Tronçons

`troncons.geometry` utilise `geometry(LineString, 3950)`. Le WKT source est
validé, associé au CRS global détecté dans `$sirs`, puis reprojeté vers 3950
uniquement lorsque le CRS source diffère.

### Désordres

`desordres.geometry` utilise le type générique `geometry(Geometry, 3950)` avec
une contrainte limitant les valeurs à Point, LineString, Polygon ou NULL. Pour
les sources ponctuelles/linéaires historiques, la géométrie cible est construite
depuis `positionDebut` et `positionFin` :

- positions identiques : `POINT` ;
- positions différentes : `LINESTRING` ;
- positions absentes ou inexploitables : `NULL` avec warning.

Un Polygon source explicite, compatible et valide est conservé. Aucun Polygon,
MultiPolygon ou MultiLineString n'est fabriqué depuis des données ponctuelles ou
linéaires. Le champ historique `Desordre.geometry` non polygonal n'est pas
considéré comme canonique dans la migration actuelle de `cabbalr`.

## Évolutions du modèle par rapport au schéma initial

- Désordres/tronçons : la relation est N-N via
  `link_desordres_troncons`, car chaque côté peut concerner plusieurs objets.
- Géométries des désordres : Point, LineString et Polygon sont désormais admis.
- Ouvrages : les nombreuses classes SIRS sont normalisées vers
  `ouvrages_hydrauliques`, `equipements_mesure`, `cheminements`, `mobilier` et
  `reseaux_techniques`. Leurs
  référentiels PostgreSQL sont indépendants des anciens IDs SIRS ; les
  abréviations métier pertinentes ont été conservées autant que possible.
- Cheminements : ponts, escaliers d'accès, voies sur digue, voies d'accès et
  chemins d'accès techniques partagent une famille de déplacement, d'accès et
  de franchissement. Le type conserve leur distinction métier. Le rattachement
  à un tronçon est facultatif et passe par `link_cheminements_troncons`; les
  liens vers les désordres explicitement stockés passent par
  `link_cheminements_desordres`. Les données historiques sans parent sont
  acceptées. Ni proximité, ni intersection, ni désignation ne créent de lien.
  Des contraintes métier plus fortes pourront être proposées dans QGIS ou une
  application sans empêcher la conservation de la source historique.
- Aménagements hydrauliques : la table polygonale possède ses liens explicites
  aux tronçons et peut être référencée par un ouvrage hydraulique. Le classement
  provisoire `ZEC` des six objets de `cabbalr` est un override de source, pas une
  vérité universelle SIRS.
- Végétation : les objets biologiques sont séparés des plans et parcelles de
  gestion. La relation parcelle–tronçon est N-N ; le 1-1 observé dans `cabbalr`
  n'est pas une contrainte conceptuelle. Les corruptions géométriques sont
  reconstruites uniquement par règles contrôlées, sinon `MANUAL_REVIEW` conserve
  la ligne avec une géométrie NULL.
- Observations/photos : toute photo passe désormais par une observation, y
  compris quand CouchDB la stockait directement sous l'objet métier.

## Base CouchDB utilisée pendant le développement

Le développement initial s'appuie principalement sur la base CouchDB
`cabbalr`, qui reflète les usages d'une collectivité particulière. Elle ne couvre
pas nécessairement toutes les classes, référentiels, outils et workflows de SIRS
Digues : certains sont absents, rares ou uniquement remplis de valeurs par
défaut.

L'absence d'implémentation d'une classe ne signifie donc pas qu'elle est inutile
dans SIRS, et un override `cabbalr` n'est jamais une règle générale. En bref :

> modèle cible générique ≠ contenu particulier de `cabbalr`

Tout fork utilisant une autre base doit commencer par exécuter
`sirs-postgre diagnose`, puis analyser chaque classe et champ non couvert avant
d'étendre le migrateur.

## Ce qui n'est pas encore migré

Le modèle général des prestations reste à construire, notamment pour
`GlobalPrestation` et `PrestationAmenagementHydraulique`. Certaines dépendances,
dont `DesordreDependance`, ainsi que les traitements/planifications végétation
restent différés. Les relations explicites entre prestations et cheminements
sont également conservées dans le diagnostic en attente de ce futur modèle.
Les localisations de repérage des objets `Positionable` restent elles aussi
différées : ce lot conserve seulement le référentiel systèmes/bornes.
Cette liste
résume les grandes familles connues ; l'inventaire exhaustif et actualisé est
généré dans `audits/bilan.md`.

## Intégration QGIS

Les tables PostgreSQL sont chargées directement dans QGIS. Les clés étrangères
servent aux relations et aux widgets relationnels des formulaires.

Pour exploiter correctement la relation N-N entre désordres et tronçons, la
table `link_desordres_troncons` doit être présente dans le projet QGIS. Cette
table est une structure technique : elle n'est pas destinée à être manipulée
directement par l'utilisateur métier.

Le projet pilote est désormais généré par `sirs-postgre qgis-project`. La table
enfant `desordre_localisations_reperage` est enregistrée comme couche privée
sans géométrie principale : elle reste utilisable par les relations et les
formulaires sans exposer ses deux positions historiques comme couches dans le
panneau. Le dossier `qgis/styles/` conserve les anciens QML comme références,
mais le générateur ne les réutilise pas automatiquement.

Après un `recreate`, QGIS peut encore référencer l'ancienne définition PostgreSQL
des couches. Rafraîchir ou réimporter les couches évite d'utiliser ce cache
périmé.

## Tests

La suite principale s'exécute avec :

```bash
.venv/bin/python -m unittest discover -s tests -v
```

La majorité des tests utilisent des doubles de connexion et ne nécessitent pas
de base CouchDB réelle. Des tests d'intégration utilisent toutefois PostGIS pour
vérifier la reprojection et les conversions de repérage, notamment les PR
croissants, décroissants ou non métriques, les ambiguïtés et les aller-retours.
Lorsque PostgreSQL/PostGIS n'est pas accessible, ces tests peuvent être ignorés ;
dans l'environnement de développement courant, ils sont exécutés.

Les tests couvrent notamment la configuration, les diagnostics, la protection
de `recreate`, le DDL, les transformations CouchDB, l'atomicité, le registre
d'anomalies, la résolution du CRS source et les validations de migration.

## Structure du code

```text
sirs_postgre/
├── cli.py                  # check, migration, diagnose, QGIS, anomalies
├── qgis_project.py         # génération reproductible du projet QGZ
├── source/
│   └── couchdb.py          # configuration et client CouchDB
├── target/
│   ├── database.py         # diagnostic, recréation et initialisation PostgreSQL
│   ├── reperage.py         # fonctions PostGIS de conversion du repérage
│   └── schema.py           # DDL du noyau courant
└── migration/
    ├── core.py             # orchestration transactionnelle du noyau
    ├── amenagements.py     # aménagements hydrauliques
    ├── anomalies.py        # collecte, historique et exports JSON/CSV
    ├── coverage.py         # registre et bilan de couverture CouchDB réel
    ├── crs.py              # détection, validation et reprojection CRS
    ├── media.py            # normalisation objet → observation → photo
    ├── ouvrages.py         # ouvrages et équipements
    ├── reperage.py         # systèmes, bornes et relations explicites
    ├── vegetation.py       # gestion et objets physiques de végétation
    ├── source_overrides.py # décisions isolées propres aux bases sources
    └── validation.py       # contrôles exécutés avant commit

qgis/
├── sirs_postgre.qgz        # artifact local généré, ignoré par Git
└── styles/                 # styles QML et configurations de formulaires

tests/                      # tests unitaires
config.example.env          # modèle de configuration sans secrets
```

## Principes de développement

- CouchDB reste la source de migration tant que la bascule n'est pas achevée.
- PostgreSQL/PostGIS est le modèle métier cible.
- QGIS fournit l'interface principale d'exploitation et d'édition.
- Les tables métier portent des noms simples au pluriel.
- Les tables de liaison utilisent le préfixe `link_`.
- Les référentiels utilisent le préfixe `ref_`.
- Les futures vues utiliseront le préfixe `view_`.
- Une relation 1-N simple utilise une FK directe.
- Une relation N-N réelle utilise une table `link_` explicite.
- Les UUID historiques sont conservés et les nouvelles lignes reçoivent des UUID
  générés par PostgreSQL.
- La migration ne reproduit pas automatiquement toute la complexité du modèle
  historique SIRS Digues : chaque structure est justifiée par les données et les
  usages cibles.

## Prochaines briques

Le noyau actuel sera progressivement complété par :

- les prestations ;
- les localisations de repérage des objets `Positionable` ;
- les intervenants ;
- des vues PostgreSQL et configurations QGIS orientées métier.

Ces briques seront définies après audit des données CouchDB et des usages
métier, sans recopier mécaniquement le modèle historique.
