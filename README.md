# sirs-postgre

## Présentation

`sirs-postgre` est un projet Python consacré à la transition de **SIRS Digues V2**
depuis CouchDB vers PostgreSQL/PostGIS.

Le dépôt contient aujourd'hui deux briques principales :

1. une **application web métier** fondée sur FastAPI, Leaflet et
   PostgreSQL/PostGIS ;
2. un **migrateur CouchDB → PostgreSQL/PostGIS** chargé de reconstruire de façon
   reproductible la base cible à partir d'une base SIRS Digues existante.

Un générateur de projet QGIS complète ces deux briques pour les usages SIG
avancés et les contrôles dans QGIS.

Le schéma historique SIRS Digues/CouchDB reste la **référence métier, technique
et historique**. PostgreSQL est une transposition relationnelle destinée à
préserver cette information tout en permettant des améliorations ciblées du
modèle. Tout écart volontaire par rapport au modèle SIRS doit être identifié,
argumenté et documenté.

---

## Architecture générale

```text
                         ┌──────────────────────┐
                         │   SIRS Digues V2     │
                         │      CouchDB         │
                         └──────────┬───────────┘
                                    │
                                    │ migration
                                    ▼
                         ┌──────────────────────┐
                         │ PostgreSQL / PostGIS │
                         │   modèle métier      │
                         └───────┬──────┬───────┘
                                 │      │
                         SQL     │      │ SQL
                                 │      │
                    ┌────────────▼─┐  ┌─▼────────────┐
                    │   FastAPI    │  │     QGIS     │
                    │ API + web    │  │ usage SIG    │
                    └──────┬───────┘  └──────────────┘
                           │ HTTPS/HTTP
                           ▼
                    ┌──────────────┐
                    │  Navigateur  │
                    │   Leaflet    │
                    └──────────────┘
```

### Principes

- CouchDB reste la source de migration tant que la bascule n'est pas achevée.
- PostgreSQL/PostGIS constitue la base cible et l'autorité métier/spatiale de
  l'application web.
- Le navigateur ne se connecte jamais directement à PostgreSQL.
- FastAPI porte les accès applicatifs à PostgreSQL/PostGIS.
- Les calculs spatiaux et les règles de repérage restent côté
  PostgreSQL/PostGIS ; ils ne sont pas réimplémentés en JavaScript.
- QGIS reste disponible comme interface SIG complémentaire.
- La base PostgreSQL de développement reste actuellement recréable à partir de
  CouchDB.

---

# Application web

## Objectif

L'application web constitue un prototype métier léger permettant de consulter
et modifier les données SIRS directement depuis un navigateur.

Architecture :

```text
Navigateur
├── HTML / CSS / JavaScript
├── Leaflet
└── Leaflet.Editable
        ↓
     FastAPI
        ↓
PostgreSQL / PostGIS
```

Le frontend reste volontairement simple : pas de React, Vue, TypeScript, Node
ou chaîne de build obligatoire.

Les géométries sont exposées au navigateur en GeoJSON `EPSG:4326`.
PostGIS conserve les géométries métier en `EPSG:3950` et réalise les
transformations nécessaires.

## Fonctions actuellement disponibles

### Navigation patrimoniale

La barre principale donne accès à la navigation :

```text
Système d'endiguement
  └── Digue
       └── Tronçon
```

Le panneau gauche permet de parcourir les systèmes, digues et tronçons. Les
tronçons peuvent être sélectionnés, mis en évidence et cadrés sur la carte.

### Désordres Point

Un désordre Point peut être ouvert dans le panneau droit et localisé par quatre
modes exclusifs :

- modification X/Y en `EPSG:3950` ;
- modification longitude/latitude en `EPSG:4326` ;
- déplacement graphique du marqueur ;
- repérage par borne, distance et sens lorsqu'exactement un tronçon est associé.

Dans tous les cas, une seule famille de saisie est autoritaire pour
l'opération :

```text
saisie utilisateur
→ PostgreSQL/PostGIS
→ triggers métier
→ géométrie / coordonnées / repérage recalculés
→ relecture serveur
→ rafraîchissement du formulaire et de la carte
```

### Désordres LineString

Les LineString peuvent être ouvertes puis éditées graphiquement avec
Leaflet.Editable.

L'édition :

- conserve tous les sommets de la géométrie ;
- permet de déplacer les sommets existants ;
- permet d'ajouter un sommet via les poignées intermédiaires ;
- reste locale tant que l'utilisateur n'a pas validé ;
- peut être annulée sans écriture en base ;
- envoie la géométrie GeoJSON au serveur uniquement lors de la validation ;
- relit ensuite la géométrie réellement persistée par PostgreSQL.

### Observations et photos

Les observations sont consultables depuis la fiche d'un désordre selon la
relation métier :

```text
Désordre
  └── Observation
       └── Photo
```

Les métadonnées des photos sont disponibles. Le stockage et le service du
contenu binaire des médias restent à finaliser.

## État du prototype web

L'application web est actuellement une interface expérimentale de développement.
Elle n'est pas encore une PWA complète et ne propose pas encore de
synchronisation hors ligne.

La création de nouveaux objets métier, l'édition des observations/photos et
l'extension aux autres familles SIRS sont les prochaines briques prévues.

Leaflet.Editable est actuellement chargé depuis un CDN. Pour un déploiement
intranet ou PWA, cette dépendance devra être embarquée localement afin de ne pas
dépendre d'un accès Internet externe.

---

# Installation et dépendances

## 1. Prérequis

Le projet nécessite au minimum :

- Python 3.11 ou plus récent ;
- `venv` ;
- PostgreSQL 16 ou compatible ;
- PostGIS ;
- l'extension PostgreSQL `pgcrypto`.

Pour l'application web :

- FastAPI ;
- Uvicorn.

Pour la génération du projet QGIS uniquement :

- QGIS ;
- PyQGIS 3.38 ou plus récent.

**PyQGIS n'est pas requis pour lancer le migrateur ou l'application web.**

---

## 2. Linux — environnement Python

Sous Ubuntu/Debian :

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

Créer ensuite l'environnement virtuel depuis la racine du projet :

```bash
cd ~/Projects/sirs-postgre

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install fastapi uvicorn
```

Activation facultative du venv :

```bash
source .venv/bin/activate
```

Le venv n'a pas besoin d'être activé si les commandes utilisent explicitement
`.venv/bin/python`.

### PostgreSQL/PostGIS local sous Ubuntu/Debian

Si PostgreSQL doit être installé sur la même machine :

```bash
sudo apt install postgresql postgresql-contrib postgis
```

Si la base PostgreSQL est hébergée sur un autre serveur, seul l'accès réseau et
la configuration de connexion sont nécessaires.

---

## 3. Windows — environnement Python

Depuis la racine du projet :

```cmd
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m pip install fastapi uvicorn
```

Activation sous `cmd.exe` :

```cmd
.venv\Scripts\activate.bat
```

Sous Git Bash :

```bash
source .venv/Scripts/activate
```

L'activation reste facultative si les commandes utilisent
`.venv\Scripts\python.exe`.

---

## 4. PyQGIS / QGIS

PyQGIS est une dépendance particulière : il ne doit pas être considéré comme un
simple paquet `pip`.

### Linux

Pour une installation QGIS fournie par la distribution :

```bash
sudo apt install qgis python3-qgis
```

Si l'on souhaite utiliser PyQGIS depuis le même venv, le plus simple est de
créer ce venv avec accès aux paquets Python système :

```bash
python3 -m venv --system-site-packages .venv
```

puis d'y installer le projet :

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install fastapi uvicorn
```

Vérification :

```bash
.venv/bin/python -c "import qgis; print('PyQGIS disponible')"
```

Si le venv standard est conservé sans `--system-site-packages`, utiliser
l'environnement Python fourni par QGIS pour la seule génération du projet QGZ.

### Windows

Installer QGIS/OSGeo4W normalement. La génération du projet QGIS doit être
lancée avec l'environnement Python QGIS/OSGeo4W afin que `qgis.core` soit
disponible.

Le venv Python normal reste utilisé pour le migrateur et l'application web.

La procédure Windows détaillée est documentée dans :

```text
docs/generation_projet_qgis.md
```

---

# Configuration

Créer la configuration locale à partir du modèle :

```bash
cp config.example.env config.env
```

Sous Windows, copier le fichier manuellement ou avec la commande disponible
dans le shell utilisé.

La CLI et l'application chargent le fichier optionnel `config.env` situé à la
racine du projet. Les variables déjà définies dans l'environnement restent
prioritaires.

`config.example.env` est uniquement un modèle et ne doit contenir aucun secret.
`config.env` contient la configuration locale et n'est pas versionné.

La connexion PostgreSQL peut être définie par :

```text
SIRS_POSTGRE_HOST
SIRS_POSTGRE_PORT
SIRS_POSTGRE_DATABASE
SIRS_POSTGRE_USER
SIRS_POSTGRE_PASSWORD
```

ou par :

```text
SIRS_POSTGRE_DSN
```

`SIRS_POSTGRE_DSN` est prioritaire.

La base d'administration utilisée par `recreate` est configurable avec :

```text
SIRS_POSTGRE_ADMIN_DATABASE
```

et vaut `postgres` par défaut.

---

# Lancer l'application web locale

## Linux

Depuis la racine du projet :

```bash
.venv/bin/python -m uvicorn sirs_postgre.web.app:app --reload
```

## Windows

```cmd
.venv\Scripts\python.exe -m uvicorn sirs_postgre.web.app:app --reload
```

Puis ouvrir :

```text
http://127.0.0.1:8000/
```

L'option `--reload` redémarre automatiquement le serveur de développement
lorsque le code Python est modifié.

---

# Migrateur CouchDB → PostgreSQL/PostGIS

## Principe général

Le migrateur reconstruit PostgreSQL/PostGIS à partir d'une base CouchDB SIRS.

Le modèle historique CouchDB est considéré comme la référence. Une propriété
source ne doit pas être abandonnée simplement parce qu'elle paraît inutilisée
dans une base particulière.

Pour chaque évolution du modèle cible, il faut pouvoir documenter :

```text
source CouchDB
→ cible PostgreSQL
→ transformation éventuelle
→ justification
→ impact sur la donnée historique
```

Les écarts structurels restent possibles lorsqu'ils améliorent la cohérence du
modèle relationnel, mais ils doivent être explicites et traçables.

## Cycle courant de migration

```bash
cd ~/Projects/sirs-postgre

sirs-postgre check
sirs-postgre recreate
sirs-postgre init-schema
sirs-postgre migrate-core
sirs-postgre check --target-only
sirs-postgre diagnose
sirs-postgre qgis-project --output qgis/sirs_postgre.qgz
```

Pendant le développement, la base cible est considérée comme recréable. Le
cycle normal consiste à la supprimer, recréer le schéma puis relancer la
migration depuis CouchDB.

---

## Gestion des systèmes de coordonnées

SIRS Digues stocke le CRS global de chaque base CouchDB dans le document `$sirs`,
notamment via `epsgCode`.

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

Affecter arbitrairement le SRID 3950 à des coordonnées exprimées dans un autre
CRS n'est jamais considéré comme une transformation valide.

Un fallback explicite peut être configuré :

```bash
SIRS_SOURCE_SRID=2154
```

La forme suivante est également acceptée :

```bash
SIRS_SOURCE_SRID=EPSG:2154
```

Ce fallback ne masque jamais une contradiction entre `$sirs.epsgCode`,
`crsWkt`, `proj4` et la configuration locale.

Le champ objet historique `crsName` sert uniquement de contrôle de cohérence.

---

# Commandes principales du migrateur

## `check`

```bash
sirs-postgre check
```

Cette commande diagnostique les connexions CouchDB et PostgreSQL, les versions
de PostgreSQL, PostGIS et `pgcrypto`, ainsi que la présence des tables attendues.

Elle ne modifie aucune base.

Options :

```bash
sirs-postgre check --source-only
sirs-postgre check --target-only
sirs-postgre check --profile secure
sirs-postgre check --source-database autre_base
```

---

## `recreate`

```bash
sirs-postgre recreate
```

> **Attention — opération destructive :** cette commande exécute un
> `DROP DATABASE` sur la base PostgreSQL cible configurée.

Toute donnée créée directement dans PostgreSQL, QGIS ou l'application web depuis
la dernière migration est supprimée.

La commande :

- ferme les connexions vers la seule base cible ;
- supprime cette base ;
- la recrée ;
- active PostGIS et `pgcrypto`.

Les bases protégées `postgres`, `template0`, `template1`, la base
d'administration et les noms dangereux sont refusés.

---

## `init-schema`

```bash
sirs-postgre init-schema
```

Cette commande crée transactionnellement le schéma PostgreSQL courant dans
`public`.

Les instructions utilisent `CREATE TABLE IF NOT EXISTS`. Cette commande ne lit
pas CouchDB.

---

## `migrate-core`

```bash
sirs-postgre migrate-core
```

La commande migre actuellement le noyau SIRS, les ouvrages, les aménagements
hydrauliques, les plans/parcelles de gestion et la végétation.

Le noyau couvre notamment :

- `systemes` ;
- `digues` ;
- `troncons` ;
- `desordres` ;
- `observations` ;
- `photos` ;
- les systèmes et bornes de repérage ;
- les référentiels associés.

Les anciennes photos directement portées par un objet sont regroupées sous des
observations synthétiques déterministes.

Les insertions et validations s'exécutent dans une transaction PostgreSQL
unique. Une erreur bloquante entraîne un rollback complet.

La migration refuse actuellement une cible contenant déjà des données et ne
réalise pas d'UPSERT.

Il faut alors rejouer :

```text
recreate
→ init-schema
→ migrate-core
```

---

## `diagnose`

```bash
sirs-postgre diagnose
```

Cette commande analyse les documents CouchDB et génère :

```text
audits/bilan.md
audits/anomalies.json
audits/anomalies.csv
```

Elle découvre les valeurs `@class` et les clés JSON réellement présentes, puis
les compare au registre de couverture.

Les statuts de couverture comprennent notamment :

```text
MIGREE
PARTIELLE
NON_MIGREE
TECHNIQUE_IGNORE
REFERENTIEL_IGNORE
```

Une classe ou un champ inconnu dans une autre base apparaît donc dans le bilan
et, lorsqu'il est actionnable, dans le registre des anomalies.

Le diagnostic inclut également la synthèse du CRS source et de la
transformation éventuelle vers `EPSG:3950`.

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
sirs-postgre anomalies
sirs-postgre anomalies --open
sirs-postgre anomalies --actionable
sirs-postgre anomalies --category INVALID_GEOMETRY
sirs-postgre anomalies --source-document-id <id-couchdb-exact>
sirs-postgre anomalies --source-object-id <id-sous-objet-exact>
```

Enregistrement d'une décision :

```bash
sirs-postgre anomalies resolve <anomaly_id> \
  --status RESOLVED_IN_COUCHDB \
  --comment "Géométrie corrigée et validée dans la source"
```

Cette commande modifie uniquement le registre local d'anomalies. Elle ne
modifie ni CouchDB ni PostgreSQL.

Une correction effectuée seulement dans PostgreSQL sera perdue lors du prochain
`recreate`. Une correction reproductible doit être réalisée dans CouchDB ou
codée dans le migrateur.

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

Les nouvelles lignes PostgreSQL peuvent utiliser `DEFAULT gen_random_uuid()`
lorsque l'identifiant n'est pas fourni.

Les référentiels historiques du noyau conservent leurs identifiants CouchDB en
PK `TEXT`, par exemple :

```text
RefTypeDesordre:57
RefUrgence:1
```

---

## Repérage des désordres

La géométrie PostGIS et le repérage linéaire sont deux représentations liées.

Le noyau expose notamment :

```text
xy_vers_reperage
borne_offset_vers_xy
pr_vers_xy
```

Pour les désordres Point/LineString liés à exactement un tronçon :

- une modification géométrique conserve la géométrie saisie et recalcule le
  repérage ;
- une modification explicite du repérage reconstruit la géométrie sur le
  tronçon.

`desordre_localisations_reperage` contient au plus une ligne par désordre.

Avec zéro ou plusieurs tronçons, aucun repérage unique n'est imposé et la
géométrie reste autoritaire.

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

Le mapping détaillé et exhaustif doit continuer à être audité contre le schéma
SIRS historique. Une absence dans la base de développement `cabbalr` ne constitue
pas une justification suffisante pour abandonner un champ ou une classe SIRS.

---

# Géométries

## Tronçons

`troncons.geometry` utilise :

```text
geometry(LineString, 3950)
```

La géométrie source est interprétée dans le CRS global de la base CouchDB puis
reprojetée si nécessaire.

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

Une géométrie source valide est conservée avec tous ses sommets.

`positionDebut` et `positionFin` ne sont utilisés qu'en fallback lorsqu'une
géométrie exploitable n'est pas disponible.

---

# Ouvrages, aménagements et végétation

Le modèle PostgreSQL regroupe plusieurs classes historiques dans des familles
relationnelles explicites.

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

Les relations spatiales ne sont jamais déduites automatiquement d'une simple
intersection lorsque CouchDB fournit une relation explicite.

Les décisions propres à une base source particulière restent isolées dans :

```text
migration/source_overrides.py
```

et ne doivent jamais devenir implicitement des règles SIRS générales.

---

# Base CouchDB utilisée pendant le développement

Le développement initial s'appuie principalement sur la base CouchDB
`cabbalr`.

Cette base reflète les données historiques d'une collectivité particulière. Elle
ne contient pas nécessairement toutes les classes et tous les usages possibles
du modèle SIRS Digues.

Par conséquent :

```text
schéma SIRS de référence
≠
contenu particulier de cabbalr
```

Toute autre base doit commencer par :

```bash
sirs-postgre diagnose
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

La liste exhaustive et actualisée doit être lue dans :

```text
audits/bilan.md
```

Un élément encore non migré n'est pas considéré comme inutile : il reste à
analyser par rapport au modèle historique SIRS.

---

# Génération du projet QGIS

```bash
sirs-postgre qgis-project --output qgis/sirs_postgre.qgz
```

Cette commande génère entièrement le projet QGZ depuis le code et la
configuration PostgreSQL.

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
qgis/sirs_postgre.qgz
```

est un artifact local ignoré par Git.

Après un `recreate`, QGIS peut conserver une ancienne définition des couches en
cache. Un rafraîchissement ou une réimportation peut alors être nécessaire.

---

# Tests

Suite principale :

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Sous Windows :

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La majorité des tests utilisent des doubles de connexion.

Certains tests d'intégration utilisent réellement PostgreSQL/PostGIS pour
vérifier notamment :

- reprojections ;
- repérage ;
- géométries ;
- triggers ;
- relecture après écriture ;
- API web.

Les tests PyQGIS peuvent être ignorés lorsque l'environnement QGIS n'est pas
disponible.

---

# Structure du code

```text
sirs_postgre/
├── cli.py
├── qgis_project.py
├── web/
│   ├── app.py
│   ├── models.py
│   └── queries.py
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

web/
├── index.html
├── css/
│   └── app.css
└── js/
    └── map.js

qgis/
├── sirs_postgre.qgz
└── styles/

tests/
config.example.env
```

---

# Principes de développement

- Le schéma SIRS Digues/CouchDB reste la référence métier générale.
- La migration vers PostgreSQL doit être fidèle par défaut.
- Tout écart au modèle historique doit être explicite, argumenté et documenté.
- Une absence dans `cabbalr` ne signifie pas qu'une structure SIRS est inutile.
- PostgreSQL/PostGIS porte l'autorité métier et spatiale de la cible.
- Les UUID historiques sont conservés.
- Les nouvelles lignes peuvent recevoir des UUID générés par PostgreSQL.
- Une relation 1-N simple utilise une FK directe.
- Une relation N-N réelle utilise une table `link_`.
- Les référentiels utilisent le préfixe `ref_`.
- Les vues utilisent le préfixe `view_`.
- Les règles spatiales ne doivent pas être dupliquées dans le frontend.
- Les corrections de migration doivent être reproductibles.
- Les particularités d'une base source restent isolées et documentées.

---

# Prochaines briques

Les développements prévus concernent notamment :

- création de nouveaux objets depuis l'application web ;
- édition des observations et photos ;
- autres objets `Positionable` ;
- prestations ;
- intervenants ;
- généralisation des formulaires métier ;
- stockage et service des médias ;
- préparation éventuelle d'une PWA et d'un fonctionnement hors ligne.

Chaque nouvelle brique doit être confrontée au modèle CouchDB historique avant
de modifier le modèle PostgreSQL cible.
