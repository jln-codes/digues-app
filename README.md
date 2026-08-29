# sirs-postgre

Prototype Python autonome pour préparer et tester progressivement la migration
de SIRS Digues depuis CouchDB vers PostgreSQL/PostGIS.

Cette première tranche ne migre aucune donnée. Elle vérifie les deux connexions,
initialise un premier noyau métier vide et compte les documents CouchDB top-level des
classes suivantes :

- `SystemeEndiguement` ;
- `Digue` ;
- `TronconDigue` ;
- `Desordre`.

`Observation` et `Photo` sont dans le périmètre futur, mais sont imbriquées dans
les documents parents et ne sont donc pas comptées comme documents top-level.

## Installation

```bash
cd /home/julien/Projects/sirs-postgre
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Préparer ensuite la configuration sans versionner les secrets :

```bash
cp config.example.env config.env
# éditer config.env
```

Au démarrage, la CLI charge automatiquement le fichier optionnel `config.env`
situé à la racine du projet. Les variables déjà exportées dans l'environnement
du shell restent prioritaires sur celles de ce fichier. `config.example.env`
reste uniquement le modèle versionné : la CLI ne le charge jamais et n'y écrit
jamais de secrets.

Il est aussi possible de fournir uniquement `SIRS_POSTGRE_DSN` pour PostgreSQL.
Cette variable est prioritaire sur les paramètres séparés.
La base utilisée pour les opérations d'administration est configurable avec
`SIRS_POSTGRE_ADMIN_DATABASE` et vaut `postgres` par défaut.

## Diagnostic des connexions

```bash
source .venv/bin/activate
sirs-postgre check
```

Options utiles :

```bash
.venv/bin/sirs-postgre check --source-only
.venv/bin/sirs-postgre check --target-only
.venv/bin/sirs-postgre check --profile secure
.venv/bin/sirs-postgre check --source-database autre_base
```

La vérification source effectue exclusivement des requêtes `GET` et des requêtes
Mango `POST /_find`, qui sont des lectures CouchDB. La vérification cible exécute
uniquement des `SELECT`, indique la version de PostGIS et contrôle la présence
des tables métier. Elle ne crée ni base, ni extension, ni table.

Le diagnostic indique également si l'authentification CouchDB et PostgreSQL est
configurée. L'absence de credentials reste informative lorsque la connexion
réussit ; en cas d'échec, le message précise leur absence. Aucun mot de passe
n'est jamais affiché.

## Recréation de la base cible

La commande suivante supprime intégralement la base cible configurée, la recrée
et active PostGIS ainsi que `pgcrypto` :

```bash
source .venv/bin/activate
sirs-postgre recreate
```

Cette commande est réservée à une base jetable. Elle ferme uniquement les
connexions actives vers la base cible, exécute `DROP DATABASE` et
`CREATE DATABASE` en autocommit, puis vérifie la connexion et la disponibilité
de PostGIS et `pgcrypto`. Elle ne crée aucune table métier et ne lance aucune migration
CouchDB. Par sécurité, les noms vides, non conventionnels et les bases protégées
`postgres`, `template0`, `template1` ou la base d'administration configurée sont
refusés avant toute opération destructive.

## Initialisation du schéma métier

Après une recréation, initialiser les tables du noyau métier et ses trois
premiers référentiels avec :

```bash
source .venv/bin/activate
sirs-postgre init-schema
```

Le DDL est exécuté dans une transaction unique dans le schéma `public`. Les
tables sont créées avec `IF NOT EXISTS`, puis leur présence et celle de PostGIS
et `pgcrypto` sont vérifiées avant validation de la transaction. Cette étape ne migre aucune
donnée CouchDB et ne crée ni prestation, végétation, ouvrage ou aménagement
hydraulique.

Les tables possédant une PK UUID simple utilisent
`DEFAULT gen_random_uuid()`. PostgreSQL peut ainsi attribuer un identifiant aux
objets créés directement depuis QGIS. `link_desordres_troncons` possède un UUID
technique généré de cette manière et conserve l'unicité métier du couple
`(desordre_id, troncon_id)`. Les migrations fournissent toujours explicitement
les UUID CouchDB des objets métier et ne déclenchent donc pas leur DEFAULT.

Le contrôle suivant affiche ensuite chaque table comme `présente` ou `absente` :

```bash
sirs-postgre check --target-only
```

## Migration du noyau

La première migration réelle se lance uniquement sur des tables métier vides :

```bash
sirs-postgre migrate-core
```

La commande lit les classes métier `SystemeEndiguement`, `Digue`,
`TronconDigue` et `Desordre`, ainsi que `RefCategorieDesordre`,
`RefTypeDesordre` et `RefUrgence`. Elle aplatit exclusivement les observations
de désordre et leurs photos, ignore volontairement les photos directement
rattachées aux tronçons et ne lit aucun attachment binaire.

Mapping établi après inspection de la source `cabbalr` :

| Cible | Source CouchDB | Transformation |
|---|---|---|
| `ref_categories_desordre` | `RefCategorieDesordre` | `_id` conservé littéralement comme PK `TEXT` |
| `ref_types_desordre` | `RefTypeDesordre` | `_id` conservé ; `categorieId` vers `categorie_id` |
| `ref_urgences` | `RefUrgence` | `_id` conservé littéralement comme PK `TEXT` |
| `systemes.id` | `SystemeEndiguement._id` | normalisation UUID, mêmes 128 bits |
| `systemes.libelle/valid` | `libelle`, `valid` | valeurs inchangées |
| `digues.systeme_endiguement_id` | `systemeEndiguementId` | UUID vérifié ou `NULL` si absent |
| `digues.libelle/valid` | `libelle`, `valid` | valeurs inchangées |
| `troncons.digue_id` | `digueId` | UUID vérifié |
| `troncons.geometry` | `geometry` | WKT `LINESTRING`, `ST_GeomFromText(..., 3950)` |
| `desordres.type_desordre_id` | `Desordre.typeDesordreId` | référence `TEXT` vérifiée ou `NULL` |
| `desordres.designation/commentaire` | champs homonymes | textes nullables inchangés |
| `desordres.date_debut/date_fin` | champs homonymes | dates ISO vers `DATE` |
| `desordres.geometry` | `positionDebut`, `positionFin` | Point si égales, LineString sinon, SRID 3950 |
| `link_desordres_troncons` | `Desordre._id`, `linearId` | deux UUID vérifiés, une ligne N-N avec `id` technique généré |
| `observations` | `Desordre.observations[]` | `desordre_id` injecté depuis le parent |
| `observations.urgence_id` | `Observation.urgenceId` | référence `TEXT` vers `ref_urgences`, ou `NULL` |
| `observations.designation` | `Observation.designation` | texte nullable, `NULL` si absent |
| `observations.evolution` | `Observation.evolution` | texte nullable inchangé |
| `photos` | `Observation.photos[]` | `observation_id` injecté depuis le parent |
| `photos.chemin_source` | `Photo.chemin` | valeur inchangée, aucune déduplication |

Le champ `Desordre.geometry` source n'est pas utilisé pour construire la
géométrie cible dans cette itération ; sa présence est seulement comptabilisée
dans le rapport. Tous les `valid=false` sont conservés.

`Desordre.categorieDesordreId` sert uniquement à contrôler la cohérence avec la
catégorie portée par `RefTypeDesordre.categorieId`. Il n'est jamais stocké dans
`desordres` : lorsqu'un type existe, sa catégorie est déduite par la relation
`ref_types_desordre.categorie_id`. Une catégorie source seule produit un warning
et laisse `type_desordre_id` à `NULL`.

La préparation est déterministe par UUID. Les insertions et les validations
dynamiques sont exécutées dans une transaction PostgreSQL unique. Toute
référence invalide, tout compte incohérent, SRID incorrect ou échec d'insertion
annule intégralement la migration. Une cible non vide est refusée sans UPSERT et
le message rappelle la séquence `recreate`, `init-schema`, `migrate-core`.

## Tests

Les tests unitaires utilisent des doubles de connexion et ne nécessitent aucune
base réelle :

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Architecture

```text
sirs_postgre/
├── source/couchdb.py       # configuration et client CouchDB autonomes
├── target/database.py      # configuration, diagnostic et initialisation
├── target/schema.py        # DDL du premier noyau métier
├── migration/core.py       # mapping, transformation et insertion atomique
├── migration/validation.py # contrôles avant commit
└── cli.py                  # commandes de diagnostic, schéma et migration
```

Le noyau contient `systemes`, `digues`, `troncons`, `desordres`,
`link_desordres_troncons`, `observations`, `photos`, ainsi que les référentiels
`ref_categories_desordre`, `ref_types_desordre` et `ref_urgences`.
