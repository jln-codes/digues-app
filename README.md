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

## Indépendance vis-à-vis de sirs-suite

Le projet ne dépend pas de `sirs-suite`, ne modifie pas son `sys.path` et
n'importe aucun de ses modules. Le petit socle HTTP CouchDB a été réimplémenté
localement après inspection de `sirs-suite/sirs/config.py` et
`sirs-suite/sirs/couchdb.py` : profils de configuration, lecture d'un document,
requêtes Mango, pagination de `_all_docs` et traduction des erreurs HTTP.

Les noms de variables `SIRS_PROFILE`, `SIRS_LOCAL_*` et `SIRS_SECURE_*` restent
compatibles avec ceux de `sirs-suite`. Une même configuration de shell peut donc
être réutilisée, sans créer de dépendance entre les projets. Contrairement au
profil local historique de `sirs-suite`, aucun identifiant ni mot de passe n'a
de valeur par défaut dans ce projet.

L'accès aux pièces jointes est disponible via
`CouchDBClient.get_attachment(document_id, attachment_name)`. Il est prévu pour
la tranche Photo ultérieure et n'est pas appelé par la commande de diagnostic.

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
et active PostGIS :

```bash
source .venv/bin/activate
sirs-postgre recreate
```

Cette commande est réservée à une base jetable. Elle ferme uniquement les
connexions actives vers la base cible, exécute `DROP DATABASE` et
`CREATE DATABASE` en autocommit, puis vérifie la connexion et la disponibilité
de PostGIS. Elle ne crée aucune table métier et ne lance aucune migration
CouchDB. Par sécurité, les noms vides, non conventionnels et les bases protégées
`postgres`, `template0`, `template1` ou la base d'administration configurée sont
refusés avant toute opération destructive.

## Initialisation du schéma métier

Après une recréation, initialiser les sept tables du noyau métier avec :

```bash
source .venv/bin/activate
sirs-postgre init-schema
```

Le DDL est exécuté dans une transaction unique dans le schéma `public`. Les
tables sont créées avec `IF NOT EXISTS`, puis leur présence et celle de PostGIS
sont vérifiées avant validation de la transaction. Cette étape ne migre aucune
donnée CouchDB et ne crée ni table de référence, ni prestation, végétation,
ouvrage ou aménagement hydraulique.

Le contrôle suivant affiche ensuite chaque table comme `présente` ou `absente` :

```bash
sirs-postgre check --target-only
```

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
├── migration/core.py       # emplacement réservé à la migration
├── migration/validation.py # emplacement réservé aux contrôles
└── cli.py                  # commandes `check`, `recreate` et `init-schema`
```

Le noyau initial contient uniquement `systeme_endiguement`, `digue`, `troncon`,
`desordre`, `link_desordre_troncon`, `observation` et `photo`.
