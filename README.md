# Digues App

## Présentation

**Digues App** est une application expérimentale de gestion des systèmes d'endiguement reposant sur **PostgreSQL/PostGIS**.

Le projet comprend :

- une application web métier ;
- un modèle de données PostgreSQL/PostGIS ;
- des outils de migration depuis **SIRS Digues V2 / CouchDB** ;
- une intégration **QGIS** complémentaire pour les usages SIG avancés.

L'application web constitue l'interface principale du projet. Elle associe un frontend HTML/CSS/JavaScript avec Leaflet à un backend Python/FastAPI. PostgreSQL/PostGIS reste l'autorité métier et spatiale.

Le schéma historique SIRS Digues/CouchDB reste la **référence métier, technique et historique** pour la migration. PostgreSQL est une transposition relationnelle destinée à préserver cette information tout en permettant des améliorations ciblées du modèle. Tout écart volontaire par rapport au modèle SIRS doit être identifié, argumenté et documenté.

Le projet ne constitue pas une implémentation officielle de SIRS Digues ni une réponse contractuelle à un marché.

---

# Application web

## Architecture

```text
                         ┌─────────────────────┐
                         │     Navigateur      │
                         │ HTML / JS / Leaflet │
                         └──────────┬──────────┘
                                    │ HTTPS / API
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │  backend Digues App │
                         └──────────┬──────────┘
                                    │ SQL
                                    ▼
                         ┌─────────────────────┐
                         │ PostgreSQL / PostGIS│
                         │   modèle métier     │
                         └──────────┬──────────┘
                                    │
                       ┌────────────┴────────────┐
                       │                         │
                       ▼                         ▼
                 migration                   QGIS
                       ▲
                       │
                 SIRS Digues V2
                    CouchDB
```

Le frontend reste volontairement simple : pas de React, Vue, Node ou chaîne de build obligatoire pour l'application métier. Les géométries sont exposées en GeoJSON `EPSG:4326`. PostGIS conserve les géométries métier en `EPSG:3950` et réalise les transformations ainsi que les règles spatiales et de repérage.

Le navigateur ne se connecte jamais directement à PostgreSQL. Le backend utilise le modèle et la configuration de cible fournis par le paquet `digues-app`.

Leaflet, Leaflet.Editable et les tuiles OpenStreetMap sont actuellement chargés depuis des services externes. Ces dépendances devront être embarquées pour un déploiement intranet ou hors ligne.

## Fonctions disponibles

L'application web permet notamment :

- la navigation `Système d'endiguement → Digue → Tronçon` ;
- la consultation des tronçons et des désordres sur une carte ;
- la consultation, la création et l'édition limitée des désordres Point, LineString et Polygon ;
- la localisation par coordonnées `EPSG:3950` ;
- la localisation par longitude/latitude `EPSG:4326` ;
- le déplacement graphique d'un objet ;
- le repérage par borne ;
- l'édition graphique des LineString avec conservation des sommets intermédiaires ;
- la consultation des observations ;
- la consultation des métadonnées de photos ;
- la relecture systématique des valeurs réellement persistées par PostgreSQL.

La création et les modifications restent contrôlées par les contraintes, vues, fonctions et triggers du modèle PostgreSQL.

Le stockage et le service du contenu binaire des médias restent à finaliser.

## Assistant IA

L'application intègre un assistant texte basé sur l'API Mistral.

L'assistant reçoit un contexte de schéma construit côté serveur depuis `pg_catalog`. L'introspection est limitée au schéma `public` et aux tables et vues déclarées par le modèle SIRS versionné, puis mise en cache en mémoire pendant cinq minutes.

Seules les métadonnées de structure sont utilisées pour construire ce contexte : aucune ligne métier n'est envoyée à Mistral par cette étape d'introspection.

L'assistant peut ensuite consulter les données SIRS via l'outil serveur `query_sirs_database`. Il peut produire des requêtes de lecture, mais aucune fonction d'écriture n'est exposée à l'IA.

Toute modification persistante reste une action humaine explicite.

Les réponses de l'assistant prennent en charge un sous-ensemble Markdown rendu par liste blanche, sans injection de HTML arbitraire. Les blocs de code peuvent être copiés, mais ils ne peuvent être ni exécutés ni transférés automatiquement vers la vue Requêtes. Une requête de mutation éventuellement proposée dans un bloc reste du texte sous la responsabilité de l'utilisateur.

## Moteur SQL de lecture

Le module serveur `readonly_sql.py` fournit un moteur commun à l'assistant IA et à la future vue Requêtes.

Il n'est pas exposé par une route SQL publique.

Il accepte une instruction unique `SELECT` ou `WITH … SELECT`, y compris les jointures, agrégations et fonctions PostgreSQL/PostGIS.

Il refuse notamment :

- `INSERT` ;
- `UPDATE` ;
- `DELETE` ;
- `MERGE` ;
- `CREATE` ;
- `ALTER` ;
- `DROP` ;
- `GRANT` ;
- `REVOKE` ;
- une liste prudente de fonctions à effet de bord connu.

Chaque requête est exécutée dans une transaction PostgreSQL explicitement `READ ONLY`, avec un `statement_timeout` local de 30 secondes.

En production, la connexion de ce moteur doit employer un rôle PostgreSQL dédié ne possédant que les droits de lecture nécessaires sur les objets SIRS. Le rôle utilisé en développement et dans certains tests d'intégration peut disposer de droits d'écriture et ne constitue donc pas le rôle cible.

Une fonction appelée depuis un `SELECT` peut avoir des effets de bord : l'analyse lexicale ne remplace ni la transaction en lecture seule ni les permissions du rôle PostgreSQL.

Le SQL n'est pas réécrit et aucun `LIMIT` n'est ajouté automatiquement. Un curseur serveur ne matérialise au plus que 1 000 lignes et environ 1 Mo de JSON ; `truncated=true` signale que le transport a été coupé, sans modifier l'agrégation calculée par PostgreSQL.

Les valeurs non JSON sont normalisées en texte. Pour les géométries, une requête peut demander explicitement `ST_AsText` ou `ST_AsGeoJSON` lorsqu'un format précis est nécessaire.

Une demande utilisateur peut déclencher au maximum cinq appels d'outil avant qu'un dernier appel Mistral sans outil ne soit imposé afin de produire la réponse à partir des résultats déjà obtenus.

## Limites actuelles de l'application web

L'application reste expérimentale.

Elle n'est pas encore :

- une PWA complète ;
- une application à synchronisation hors ligne ;
- un système complet de gestion documentaire ;
- un gestionnaire complet de médias binaires ;
- une interface couvrant tous les objets métier du modèle historique SIRS.

La documentation fonctionnelle et la procédure de recette complètes se trouvent dans :

```text
docs/interface_web_experimentale.md
```

---

# Installation

## Prérequis

Le projet nécessite au minimum :

- Python 3.11 ou plus récent ;
- `venv` ;
- PostgreSQL 16 ou compatible ;
- PostGIS ;
- l'extension PostgreSQL `pgcrypto`.

L'import web d'un territoire administratif depuis GeoPackage ou Shapefile ZIP
nécessite aussi GDAL/OGR et ses bindings Python `osgeo`. En Docker, l'image les
installe explicitement à partir des paquets système GDAL et de bindings Python
alignés sur `gdal-config --version`. En développement local, installer GDAL côté
système puis les bindings Python correspondant exactement à la version native.

Pour la génération du projet QGIS uniquement :

- QGIS ;
- PyQGIS 3.38 ou plus récent.

**PyQGIS n'est pas requis pour utiliser l'application web ni pour lancer le migrateur.**

## Linux

Sous Ubuntu/Debian :

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

Créer ensuite l'environnement virtuel depuis la racine du projet :

```bash
cd digues-app

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e . -e webapp
```

Activation facultative :

```bash
source .venv/bin/activate
```

Le venv n'a pas besoin d'être activé si les commandes utilisent explicitement `.venv/bin/python`.

### PostgreSQL/PostGIS local sous Ubuntu/Debian

Si PostgreSQL doit être installé sur la même machine :

```bash
sudo apt install postgresql postgresql-contrib postgis
```

Si la base PostgreSQL est hébergée sur un autre serveur, seuls l'accès réseau et la configuration de connexion sont nécessaires.

## Windows

Depuis la racine du projet :

```cmd
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e . -e webapp
```

Activation sous `cmd.exe` :

```cmd
.venv\Scripts\activate.bat
```

Sous Git Bash :

```bash
source .venv/Scripts/activate
```

L'activation reste facultative si les commandes utilisent `.venv\Scripts\python.exe`.

---

# Configuration

Créer la configuration locale à partir du modèle :

```bash
cp config.example.env config.env
```

Sous Windows, copier le fichier manuellement ou avec la commande disponible dans le shell utilisé.

La CLI et la webapp peuvent charger le fichier optionnel `config.env` situé à la racine du projet. Les variables déjà définies dans l'environnement restent prioritaires.

`config.example.env` est uniquement un modèle et ne doit contenir aucun secret.

`config.env` contient la configuration locale et n'est pas versionné.

## Connexion PostgreSQL

La connexion PostgreSQL peut être définie directement par :

```text
DATABASE_URL
```

Exemple :

```text
DATABASE_URL=postgresql://user:password@host:5432/database
```

Le projet conserve également les variables historiques séparées :

```text
SIRS_POSTGRE_HOST
SIRS_POSTGRE_PORT
SIRS_POSTGRE_DATABASE
SIRS_POSTGRE_USER
SIRS_POSTGRE_PASSWORD
```

`DATABASE_URL` est prioritaire lorsqu'elle est définie.

La base d'administration utilisée par `recreate` est configurable avec :

```text
SIRS_POSTGRE_ADMIN_DATABASE
```

et vaut `postgres` par défaut.

## Assistant Mistral

L'assistant utilise :

```text
MISTRAL_API_KEY
```

Cette clé doit être définie dans l'environnement du serveur ou dans le fichier local non versionné `config.env`.

Elle n'est jamais envoyée au navigateur.

## Options de la webapp

```text
SIRS_WEB_SHOW_UUID=false
```

masque les UUID dans l'interface.

```text
SIRS_WEB_SHOW_UUID=true
```

les affiche.

---

# Lancement local de l'application web

Depuis la racine du dépôt :

```bash
.venv/bin/python -m uvicorn --app-dir webapp/backend digues_webapp.app:app --reload
```

Sous Windows :

```cmd
.venv\Scripts\python.exe -m uvicorn --app-dir webapp\backend digues_webapp.app:app --reload
```

Sous Git Bash :

```bash
.venv/Scripts/python.exe -m uvicorn --app-dir webapp/backend digues_webapp.app:app --reload
```

Ouvrir ensuite :

```text
http://127.0.0.1:8000/
```

L'option `--reload` redémarre le serveur lorsque le code Python est modifié.

---

# Docker

L'application web peut être construite et exécutée sous forme d'image Docker standard.

Depuis la racine du dépôt :

```bash
docker build -t digues-app-web .
```

Puis démarrer le conteneur avec une base PostgreSQL/PostGIS SIRS déjà créée et conforme au schéma attendu :

```bash
docker run --rm \
  -p 8000:8000 \
  -e DATABASE_URL='postgresql://...' \
  digues-app-web
```

Ouvrir ensuite :

```text
http://127.0.0.1:8000/
```

Le conteneur sert la webapp FastAPI et les assets frontend.

Il embarque GDAL/OGR pour l'import serveur des contours administratifs
GeoPackage et Shapefile ZIP. Les bindings Python GDAL sont installés avec la
même version que la bibliothèque native fournie par l'image.

Il ne crée pas, ne migre pas et n'administre pas automatiquement la base de données.

Les endpoints métier qui interrogent PostgreSQL nécessitent une base PostgreSQL/PostGIS conforme. Sans base disponible, les pages et assets statiques restent servis mais les routes `/api/...` dépendantes de PostgreSQL échouent selon le comportement serveur existant.

L'image Docker est conçue pour rester portable entre les environnements compatibles Docker.

---

# Architecture métier générale

## Principes

- PostgreSQL/PostGIS constitue l'autorité métier et spatiale de la cible.
- Les calculs spatiaux et les règles de repérage restent côté PostgreSQL/PostGIS.
- L'application web est l'interface principale du projet.
- QGIS reste disponible comme interface SIG complémentaire.
- CouchDB reste la source de migration tant que la bascule depuis SIRS Digues V2 n'est pas achevée.
- La base PostgreSQL de développement reste recréable à partir de CouchDB lorsque ce mode de travail est utilisé.

---

# Migrateur CouchDB → PostgreSQL/PostGIS

## Principe général

Le migrateur reconstruit PostgreSQL/PostGIS à partir d'une base CouchDB SIRS.

Le modèle historique CouchDB est considéré comme la référence. Une propriété source ne doit pas être abandonnée simplement parce qu'elle paraît inutilisée dans une base particulière.

Pour chaque évolution du modèle cible, il faut pouvoir documenter :

```text
source CouchDB
→ cible PostgreSQL
→ transformation éventuelle
→ justification
→ impact sur la donnée historique
```

Les écarts structurels restent possibles lorsqu'ils améliorent la cohérence du modèle relationnel, mais ils doivent être explicites et traçables.

## Cycle courant de migration

```bash
cd ~/Projects/digues-app

digues-app check
digues-app recreate
digues-app init-schema
digues-app migrate-core
digues-app check --target-only
digues-app diagnose
digues-app qgis-project --output qgis/digues_app.qgz
```

Pendant le développement, la base cible peut être considérée comme recréable. Le cycle normal consiste à la supprimer, recréer le schéma puis relancer la migration depuis CouchDB.

---

# Commandes principales du migrateur

## `check`

```bash
digues-app check
```

Cette commande diagnostique les connexions CouchDB et PostgreSQL, les versions de PostgreSQL, PostGIS et `pgcrypto`, ainsi que la présence des tables attendues.

Elle ne modifie aucune base.

Options :

```bash
digues-app check --source-only
digues-app check --target-only
digues-app check --profile secure
digues-app check --source-database autre_base
```

## `recreate`

```bash
digues-app recreate
```

> **Attention — opération destructive :** cette commande exécute un `DROP DATABASE` sur la base PostgreSQL cible configurée.

Toute donnée créée directement dans PostgreSQL ou QGIS depuis la dernière migration est supprimée.

La commande :

- ferme les connexions vers la seule base cible ;
- supprime cette base ;
- la recrée ;
- active PostGIS et `pgcrypto`.

Les bases protégées `postgres`, `template0`, `template1`, la base d'administration et les noms dangereux sont refusés.

## `init-schema`

```bash
digues-app init-schema
```

Cette commande crée transactionnellement le schéma PostgreSQL courant dans `public`.

Les instructions utilisent `CREATE TABLE IF NOT EXISTS`.

Cette commande ne lit pas CouchDB.

## `migrate-core`

```bash
digues-app migrate-core
```

La reconstruction sur le tronçon des désordres linéaires est activée par défaut, avec une tolérance métrique de `0.0001` m, soit 0,1 mm.

Elle peut être désactivée ou réglée explicitement :

```bash
digues-app migrate-core --no-reproject-on-troncon
digues-app migrate-core --on-troncon-tolerance 0.001
```

La tolérance doit être un nombre positif ou nul et s'exprime en mètres dans le CRS cible `EPSG:3950`.

La commande migre actuellement le noyau SIRS, les ouvrages, les aménagements hydrauliques, les plans/parcelles de gestion et la végétation.

Le noyau couvre notamment :

- `systemes` ;
- `digues` ;
- `troncons` ;
- `desordres` ;
- `observations` ;
- `photos` ;
- les systèmes et bornes de repérage ;
- les référentiels associés.

Les anciennes photos directement portées par un objet sont regroupées sous des observations synthétiques déterministes.

Les insertions et validations s'exécutent dans une transaction PostgreSQL unique. Une erreur bloquante entraîne un rollback complet.

La migration refuse actuellement une cible contenant déjà des données et ne réalise pas d'UPSERT.

Il faut alors rejouer :

```text
recreate
→ init-schema
→ migrate-core
```

## `generate-model-manifest`

```bash
digues-app generate-model-manifest
```

Cette commande régénère le manifeste structurel du modèle historique SIRS Digues 2.55 à partir de la référence versionnée dans :

```text
docs/reference/sirs-2.55/sirs.ecore
docs/reference/sirs-2.55/labels/*.properties
```

Le manifeste produit est :

```text
docs/reference/sirs-2.55/sirs_model_manifest.json
```

Il décrit les classes Ecore, attributs, références, cardinalités, super-types et champs effectifs après héritage, enrichis lorsque possible avec leurs libellés métier.

Le fichier est généré de manière déterministe et ne doit pas être édité manuellement.

La provenance et les empreintes de la référence historique sont documentées dans :

```text
docs/reference/sirs-2.55/README.md
```

## `diagnose`

```bash
digues-app diagnose
```

Cette commande analyse les documents CouchDB et génère :

```text
audits/bilan.md
audits/anomalies.json
audits/anomalies.csv
```

Elle confronte trois sources distinctes :

- le manifeste structurel SIRS 2.55 généré depuis `sirs.ecore` ;
- le registre de couverture de `migration/coverage.py` ;
- les documents CouchDB effectivement rencontrés.

Le diagnostic ne déduit donc plus l'existence d'un champ de sa présence dans CouchDB.

Un champ du modèle peut être signalé avec zéro occurrence. À l'inverse, une clé observée dans une classe Ecore connue mais absente du manifeste est distinguée par `UNKNOWN_OBSERVED_FIELD`.

Les statuts de couverture des classes comprennent notamment :

```text
MIGREE
PARTIELLE
NON_MIGREE
TECHNIQUE_IGNORE
REFERENTIEL_IGNORE
```

Au niveau champ, le registre distingue :

```text
MIGRATED
MIGRATED_AS_RELATION
MIGRATED_AS_DERIVED
RENAMED
DEFERRED
INTENTIONALLY_NOT_MIGRATED
UNMIGRATED
```

Le diagnostic inclut également la synthèse du CRS source et de la transformation éventuelle vers `EPSG:3950`.

---

# Diagnostic et registre des anomalies

Les trois fichiers produits ont des rôles distincts :

- `bilan.md` : couverture globale des classes, champs et relations ;
- `anomalies.json` : registre structuré et persistant ;
- `anomalies.csv` : export exploitable dans un tableur ou QGIS.

Chaque entrée reçoit un `anomaly_id` déterministe.

Les anomalies distinguent notamment :

- `DATA` : problèmes de données, géométries, références, relations, médias ;
- `COVERAGE` : classes/champs inconnus, partiels ou différés ;
- `MIGRATION_DECISION` : décisions explicites de migration.

Les statuts disponibles sont :

```text
OPEN
RESOLVED_IN_COUCHDB
RESOLVED_IN_POSTGRES
RESOLVED_BY_MIGRATOR
ACCEPTED_AS_IS
IGNORED
```

Consultation :

```bash
digues-app anomalies
digues-app anomalies --open
digues-app anomalies --actionable
digues-app anomalies --category INVALID_GEOMETRY
digues-app anomalies --source-document-id <id-couchdb-exact>
digues-app anomalies --source-object-id <id-sous-objet-exact>
```

Enregistrement d'une décision :

```bash
digues-app anomalies resolve <anomaly_id> \
  --status RESOLVED_IN_COUCHDB \
  --comment "Géométrie corrigée et validée dans la source"
```

Cette commande modifie uniquement le registre local d'anomalies.

Elle ne modifie ni CouchDB ni PostgreSQL.

Une correction effectuée seulement dans PostgreSQL sera perdue lors du prochain `recreate`. Une correction reproductible doit être réalisée dans CouchDB ou codée dans le migrateur.

---

# Gestion des systèmes de coordonnées

SIRS Digues stocke le CRS global de chaque base CouchDB dans le document `$sirs`, notamment via `epsgCode`.

Le migrateur :

1. lit le CRS source ;
2. vérifie qu'il est résolvable par PostGIS ;
3. construit les géométries dans leur vrai CRS ;
4. les standardise en `EPSG:3950`.

Si la source est déjà en `EPSG:3950`, aucune reprojection n'est effectuée.

Si le CRS source diffère, le migrateur applique :

```text
ST_Transform(..., 3950)
```

Affecter arbitrairement le SRID 3950 à des coordonnées exprimées dans un autre CRS n'est jamais considéré comme une transformation valide.

Un fallback explicite peut être configuré :

```bash
SIRS_SOURCE_SRID=2154
```

La forme suivante est également acceptée :

```bash
SIRS_SOURCE_SRID=EPSG:2154
```

Ce fallback ne masque jamais une contradiction entre `$sirs.epsgCode`, `crsWkt`, `proj4` et la configuration locale.

Le champ objet historique `crsName` sert uniquement de contrôle de cohérence.

---

# État actuel du modèle PostgreSQL

Le noyau couvre :

- `systemes`, `digues`, `troncons` ;
- `desordres`, `observations`, `photos` ;
- le repérage linéaire ;
- les principaux référentiels ;
- les ouvrages ;
- les aménagements hydrauliques ;
- la végétation et sa gestion.

Relations principales :

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

objets métier
  └── 1-N → observations
                  └── 1-N → photos
```

Les objets métier provenant de CouchDB conservent leurs UUID historiques.

Les nouvelles lignes PostgreSQL peuvent utiliser `DEFAULT gen_random_uuid()` lorsque l'identifiant n'est pas fourni.

Les référentiels historiques du noyau conservent leurs identifiants CouchDB en PK `TEXT`, par exemple :

```text
RefTypeDesordre:57
RefUrgence:1
```

## Repérage des désordres

La géométrie PostGIS et le repérage linéaire sont deux représentations liées.

Le noyau expose notamment :

```text
xy_vers_reperage
borne_offset_vers_xy
pr_vers_xy
```

Pour les désordres Point/LineString liés à exactement un tronçon :

- une modification géométrique conserve la géométrie saisie et recalcule le repérage ;
- une modification explicite du repérage reconstruit la géométrie sur le tronçon.

`desordre_localisations_reperage` contient au plus une ligne par désordre.

Avec zéro ou plusieurs tronçons, aucun repérage unique n'est imposé et la géométrie reste autoritaire.

---

# Géométries

## Tronçons

`troncons.geometry` utilise :

```text
geometry(LineString, 3950)
```

La géométrie source est interprétée dans le CRS global de la base CouchDB puis reprojetée si nécessaire.

## Désordres

`desordres.geometry` utilise un type générique :

```text
geometry(Geometry, 3950)
```

avec une contrainte autorisant actuellement :

- Point ;
- LineString ;
- Polygon ;
- NULL.

Pour les seuls `Desordre` historiques, `geometry` CouchDB peut être une représentation projetée ou reconstruite par SIRS sur le tronçon.

La migration utilise donc prioritairement `positionDebut` et `positionFin`, qui constituent la meilleure géométrie physique encore disponible :

- des positions identiques produisent toujours un Point ;
- pour des positions différentes, le comportement de base est une LineString directe A-B.

Par défaut, si `linearId` désigne un tronçon migré et si A et B sont chacun à au plus `0.0001` m de sa géométrie canonique PostgreSQL, la migration reconstruit automatiquement la portion de ce tronçon comprise entre A et B.

Son orientation reste A vers B.

Cette reconstruction peut être désactivée avec :

```text
--no-reproject-on-troncon
```

ou son seuil modifié avec :

```text
--on-troncon-tolerance <mètres>
```

Les sommets intermédiaires d'une ancienne géométrie QGIS ont déjà été perdus lors de l'import historique dans SIRS et ne sont pas recréés.

`geometry` n'est utilisée qu'en fallback lorsque les positions sont inexploitables.

Cette règle est propre aux `Desordre` et ne s'applique pas aux autres classes géométriques.

Le tronçon n'est jamais choisi par proximité : seul celui référencé par le `linearId` historique peut servir à la reconstruction.

---

# Migration CouchDB → PostgreSQL : mapping principal

| Source CouchDB | Cible PostgreSQL | Transformation principale |
|---|---|---|
| `RefCategorieDesordre` | `ref_categories_desordre` | `_id` conservé en `TEXT` |
| `RefTypeDesordre` | `ref_types_desordre` | `_id` conservé ; `categorieId` → `categorie_id` |
| `RefUrgence` | `ref_urgences` | `_id` conservé en `TEXT` |
| `SystemeEndiguement` | `systemes` | UUID, `libelle`, `valid` conservés |
| `Digue` | `digues` | `systemeEndiguementId` → `systeme_endiguement_id` |
| `TronconDigue` | `troncons` | `digueId`, libellé, validité et géométrie conservés |
| `TronconDigue.borneIds` | `link_troncons_bornes` | relations explicites |
| `TronconDigue.systemeRepDefautId` | `troncons.systeme_reperage_defaut_id` | FK vers système de repérage |
| `SystemeReperage` | `systemes_reperage` | UUID, `linearId`, libellé, commentaire, validité |
| `BorneDigue` | `bornes_reperage` | Point via le pipeline CRS |
| `SystemeReperage.systemeReperageBornes[]` | `link_systemes_reperage_bornes` | borne, PR et validité |
| `Desordre` | `desordres` | champs métier, type et géométrie complète |
| `Desordre.linearId` | `link_desordres_troncons` | relation N-N |
| `*.observations[]` | `observations` | aplatissement et FK vers parent métier |
| `Observation.urgenceId` | `observations.urgence_id` | référence vérifiée ou `NULL` |
| `Observation.photos[]` | `photos` | aplatissement avec `observation_id` |
| `Objet.photos[]` | `observations` + `photos` | observation synthétique déterministe |
| `Photo.chemin` | `photos.chemin_source` | chemin source conservé |

Le mapping détaillé et exhaustif doit continuer à être audité contre le schéma SIRS historique.

Une absence dans un corpus source particulier ne constitue pas une justification suffisante pour abandonner un champ ou une classe SIRS.

---

# Ouvrages, aménagements et végétation

Le modèle PostgreSQL regroupe plusieurs classes historiques dans des familles relationnelles explicites.

Il couvre notamment :

- `ouvrages_hydrauliques` ;
- `equipements_mesure` ;
- `cheminements` ;
- `mobilier` ;
- `reseaux_techniques` ;
- `amenagements_hydrauliques` ;
- `plans_gestion_vegetation` ;
- `parcelles_gestion_vegetation` ;
- `vegetation`.

Les relations spatiales ne sont jamais déduites automatiquement d'une simple intersection lorsque CouchDB fournit une relation explicite.

Les décisions propres à une base source particulière restent isolées dans :

```text
migration/source_overrides.py
```

et ne doivent jamais devenir implicitement des règles SIRS générales.

---

# Variabilité des bases CouchDB sources

Une base CouchDB donnée ne contient pas nécessairement toutes les classes ni tous les usages possibles du modèle SIRS Digues.

Les valeurs vides peuvent en outre être absentes des documents sérialisés.

Un corpus source particulier ne doit donc pas être traité comme une description exhaustive du schéma.

La référence structurelle locale du modèle historique est le snapshot SIRS 2.55 versionné sous :

```text
docs/reference/sirs-2.55/
```

Son manifeste est régénérable avec :

```bash
digues-app generate-model-manifest
```

Par conséquent :

```text
modèle SIRS 2.55 de référence
≠
contenu d'une base source particulière
```

Toute autre base doit commencer par :

```bash
digues-app diagnose
```

puis par l'analyse des classes et champs non couverts.

---

# Ce qui n'est pas encore migré

Le modèle reste incomplet.

Restent notamment à traiter ou généraliser :

- le modèle général des prestations ;
- `GlobalPrestation` ;
- `PrestationAmenagementHydraulique` ;
- certaines dépendances, dont `DesordreDependance` ;
- certains traitements et planifications de végétation ;
- plusieurs relations autour des prestations ;
- le repérage des autres objets `Positionable`.

La liste exhaustive et actualisée est produite par `digues-app diagnose` dans :

```text
audits/bilan.md
```

Un élément encore non migré n'est pas considéré comme inutile : il reste à analyser par rapport au modèle historique SIRS.

---

# Génération du projet QGIS

```bash
digues-app qgis-project --output qgis/digues_app.qgz
```

Cette commande génère entièrement le projet QGZ depuis le code et la configuration PostgreSQL.

Elle nécessite PyQGIS 3.38 ou plus récent.

Le projet contient notamment :

- les couches PostgreSQL ;
- les groupes ;
- les relations ;
- les formulaires ;
- le prototype de repérage ;
- un fond OpenStreetMap XYZ.

Le mot de passe PostgreSQL n'est jamais écrit dans le QGZ.

Une configuration QGIS locale peut être référencée avec :

```text
--authcfg ID
```

Le fichier généré :

```text
qgis/digues_app.qgz
```

est un artefact local ignoré par Git.

Après un `recreate`, QGIS peut conserver une ancienne définition des couches en cache. Un rafraîchissement ou une réimportation peut alors être nécessaire.

## PyQGIS

PyQGIS ne doit pas être considéré comme un simple paquet `pip`.

### Linux

Pour une installation QGIS fournie par la distribution :

```bash
sudo apt install qgis python3-qgis
```

Si l'on souhaite utiliser PyQGIS depuis le même venv, le plus simple est de créer ce venv avec accès aux paquets Python système :

```bash
python3 -m venv --system-site-packages .venv
```

puis d'y installer le projet :

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e . -e webapp
```

Vérification :

```bash
.venv/bin/python -c "import qgis; print('PyQGIS disponible')"
```

Si le venv standard est conservé sans `--system-site-packages`, utiliser l'environnement Python fourni par QGIS pour la seule génération du projet QGZ.

### Windows

Installer QGIS/OSGeo4W normalement.

La génération du projet QGIS doit être lancée avec l'environnement Python QGIS/OSGeo4W afin que `qgis.core` soit disponible.

Le venv Python normal reste utilisé pour la webapp et le migrateur.

La procédure Windows détaillée est documentée dans :

```text
docs/generation_projet_qgis.md
```

---

# Tests

## Suite principale

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Sous Windows :

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La majorité des tests utilisent des doubles de connexion.

Certains tests d'intégration utilisent réellement PostgreSQL/PostGIS pour vérifier notamment :

- les reprojections ;
- le repérage ;
- les géométries ;
- les triggers ;
- la relecture après écriture.

Les tests PyQGIS peuvent être ignorés lorsque l'environnement QGIS n'est pas disponible.

## Tests de la webapp

Sous Linux :

```bash
PYTHONPATH=webapp/backend .venv/bin/python -m unittest discover -s webapp/tests -v
```

Sous Windows :

```cmd
set PYTHONPATH=webapp\backend&& .venv\Scripts\python.exe -m unittest discover -s webapp\tests -v
```

La suite comporte des tests unitaires avec doubles de connexion et des tests d'intégration PostgreSQL/PostGIS conditionnels.

Elle contrôle également la présence et le service des assets frontend.

---

# Structure du dépôt

```text
digues_app/
├── cli.py
├── model_manifest.py
├── qgis_project.py
├── source/
│   └── couchdb.py
├── target/
│   ├── database.py
│   ├── reperage.py
│   ├── desordre_reperage.py
│   └── schema.py
└── migration/
    ├── core.py
    ├── amenagements.py
    ├── anomalies.py
    ├── coverage.py
    ├── crs.py
    ├── media.py
    ├── ouvrages.py
    ├── reperage.py
    ├── vegetation.py
    ├── source_overrides.py
    └── validation.py

webapp/
├── backend/
│   └── digues_webapp/
├── frontend/
├── docs/
└── tests/

docs/
└── reference/
    └── sirs-2.55/
        ├── sirs.ecore
        ├── sirs_model_manifest.json
        └── labels/

qgis/
├── digues_app.qgz
└── styles/

tests/
config.example.env
Dockerfile
```

---

# Principes de développement

- L'application web est l'interface principale du projet.
- PostgreSQL/PostGIS porte l'autorité métier et spatiale de la cible.
- Le schéma SIRS Digues/CouchDB reste la référence métier générale pour la migration.
- La migration vers PostgreSQL doit être fidèle par défaut.
- Tout écart au modèle historique doit être explicite, argumenté et documenté.
- Le manifeste SIRS 2.55 décrit le modèle historique indépendamment des champs effectivement rencontrés dans un corpus CouchDB.
- Une absence dans un corpus source ne signifie pas qu'une structure SIRS est inutile.
- Les UUID historiques sont conservés.
- Les nouvelles lignes peuvent recevoir des UUID générés par PostgreSQL.
- Une relation 1-N simple utilise une FK directe.
- Une relation N-N réelle utilise une table `link_`.
- Les référentiels utilisent le préfixe `ref_`.
- Les vues utilisent le préfixe `view_`.
- Les corrections de migration doivent être reproductibles.
- Les particularités d'une base source restent isolées et documentées.
- Les nouvelles fonctions métier doivent être confrontées au modèle historique SIRS avant toute évolution structurelle de la cible PostgreSQL.

---

# Prochaines briques

Les développements prévus concernent notamment :

- la création de nouveaux objets métier supplémentaires ;
- l'édition des observations et photos ;
- la généralisation des formulaires métier ;
- le stockage et le service des médias ;
- les autres objets `Positionable` ;
- les prestations ;
- les intervenants ;
- la migration du stockage des médias ;
- la préparation éventuelle d'un fonctionnement hors ligne.

Chaque nouvelle brique doit être confrontée au modèle CouchDB historique avant de modifier le modèle PostgreSQL cible.

---

# Licence

Ce projet est distribué sous licence Apache License 2.0.

Voir le fichier [`LICENSE`](LICENSE) et, le cas échéant, [`NOTICE`](NOTICE).
