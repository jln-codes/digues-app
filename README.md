# sirs-postgre

## Objectif

`sirs-postgre` est un projet Python autonome qui organise la migration progressive
de SIRS Digues V2 depuis CouchDB vers PostgreSQL/PostGIS. Il ne dépend pas de
`sirs-suite` pour fonctionner.

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

Le noyau métier, le premier lot Ouvrages et les aménagements hydrauliques sont
opérationnels. Ils couvrent :

- les tables métier `systemes`, `digues`, `troncons`, `desordres`,
  `observations` et `photos` ;
- la relation N-N `link_desordres_troncons` ;
- les référentiels `ref_categories_desordre`, `ref_types_desordre` et
  `ref_urgences` ;
- les tables `ouvrages_hydrauliques`, `equipements_mesure`,
  `ouvrages_franchissement`, `mobilier` et `reseaux_techniques`, ainsi que leurs
  cinq référentiels de types indépendants ;
- `amenagements_hydrauliques`, son référentiel minimal et la relation explicite
  N-N `link_amenagements_troncons`.

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
disposant de PostGIS et de `pgcrypto`.

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

La commande migre le noyau, 110 objets Ouvrages et les aménagements hydrauliques
depuis CouchDB dans l'ordre imposé par les relations. L'unique
`OuvrageAssocieAmenagementHydraulique` rejoint désormais
`ouvrages_hydrauliques` avec son parent explicitement stocké. Les huit
`CheminAccesDependance` restent différés : leur parent n'est actuellement connu
que par analyse spatiale et par leur désignation. L'unique
`PrestationAmenagementHydraulique` reste également différée jusqu'au modèle
général des prestations.
Les insertions et validations s'exécutent dans une transaction PostgreSQL unique :
une erreur bloquante entraîne un rollback complet.

La migration refuse une cible contenant déjà des données et n'effectue aucun
UPSERT. Il faut alors rejouer le cycle `recreate`, `init-schema`,
`migrate-core`.

## Modèle PostgreSQL actuel

```text
systemes
  └── 1-N → digues
               └── 1-N → troncons

desordres
  └── N-N ↔ link_desordres_troncons ↔ troncons

desordres
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

Une ZEC représente conceptuellement un ensemble hydraulique pouvant associer
une emprise de stockage et un ou plusieurs tronçons ; elle ne se réduit donc pas
au seul polygone de `amenagements_hydrauliques`. Seules les relations présentes
dans `tronconIds` sont migrées. Une intersection spatiale ne crée jamais de FK.

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
| `Desordre` | `desordres` | champs métier, type et géométrie dérivée des positions |
| `Desordre.linearId` | `link_desordres_troncons` | liaison N-N avec ID technique généré |
| `Desordre.observations[]` | `observations` | aplatissement et injection de `desordre_id` |
| `Observation.urgenceId` | `observations.urgence_id` | référence `TEXT` vérifiée ou `NULL` |
| `Observation.designation` | `observations.designation` | texte nullable, `NULL` si absent |
| `Observation.photos[]` | `photos` | aplatissement et injection de `observation_id` |
| `Photo.chemin` | `photos.chemin_source` | valeur conservée, sans déduplication par chemin |

Les observations conservent notamment `designation`, `date`, `evolution`,
`urgenceId` et `valid`. Seules les photos imbriquées sous
`Desordre → Observation → Photo` sont migrées ; les photos directes des tronçons
et les attachments binaires restent hors du périmètre actuel. Les chemins de
photos ne sont pas utilisés pour dédupliquer les lignes.

`Desordre.categorieDesordreId` sert uniquement à contrôler la cohérence avec la
catégorie du type. Une incohérence est signalée, mais la catégorie source n'est
ni corrigée ni stockée dans `desordres`.

Exemple de comptes obtenus lors d'une migration validée de la source live :

| Table | Lignes |
|---|---:|
| `systemes` | 9 |
| `digues` | 26 |
| `troncons` | 104 |
| `desordres` | 1 597 |
| `link_desordres_troncons` | 1 597 |
| `observations` | 3 206 |
| `photos` | 3 458 |
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
validé puis inséré avec le SRID 3950, sans modification ni reprojection.

### Désordres

`desordres.geometry` utilise le type générique `geometry(Geometry, 3950)` afin
d'accepter plusieurs types géométriques. La géométrie cible est actuellement
construite depuis `positionDebut` et `positionFin` :

- positions identiques : `POINT` ;
- positions différentes : `LINESTRING` ;
- positions absentes ou inexploitables : `NULL` avec warning.

Le champ historique `Desordre.geometry` n'est pas considéré comme la géométrie
canonique et n'est pas utilisé pour construire la valeur cible dans cette
itération. Sa présence est seulement comptabilisée dans le rapport de migration.

## Intégration QGIS

Les tables PostgreSQL sont chargées directement dans QGIS. Les clés étrangères
servent aux relations et aux widgets relationnels des formulaires.

Pour exploiter correctement la relation N-N entre désordres et tronçons, la
table `link_desordres_troncons` doit être présente dans le projet QGIS. Cette
table est une structure technique : elle n'est pas destinée à être manipulée
directement par l'utilisateur métier.

Le dossier `qgis/styles/` versionne progressivement les styles QML et les
configurations de couches et de formulaires. Ces éléments existent pour le noyau
actuel, mais leur ergonomie et leur stabilisation se poursuivent au fil des
briques métier.

Après un `recreate`, QGIS peut encore référencer l'ancienne définition PostgreSQL
des couches. Rafraîchir ou réimporter les couches évite d'utiliser ce cache
périmé.

## Tests

Les tests unitaires emploient des doubles de connexion et ne nécessitent pas de
base CouchDB ou PostgreSQL réelle :

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Ils couvrent notamment la configuration, les diagnostics, la protection de
`recreate`, le DDL, les transformations CouchDB, l'atomicité et les validations
de migration.

## Structure du code

```text
sirs_postgre/
├── cli.py                  # commandes check, recreate, init-schema, migrate-core
├── source/
│   └── couchdb.py          # configuration et client CouchDB
├── target/
│   ├── database.py         # diagnostic, recréation et initialisation PostgreSQL
│   └── schema.py           # DDL du noyau courant
└── migration/
    ├── core.py             # lecture, mapping et insertion du noyau
    └── validation.py       # contrôles exécutés avant commit

qgis/
├── sirs_postgre.qgz        # projet QGIS de travail
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
- la végétation ;
- les ouvrages ;
- les aménagements hydrauliques ;
- les intervenants ;
- des vues PostgreSQL et configurations QGIS orientées métier.

Ces briques ne font pas encore partie du schéma ni de `migrate-core`. Leur
modélisation sera définie après audit des données CouchDB et des usages métier,
sans recopier mécaniquement le modèle historique.
