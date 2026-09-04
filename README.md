# digues-app

## Présentation

digues-app est un projet Python consacré à la transition de **SIRS Digues V2**
depuis CouchDB vers PostgreSQL/PostGIS.

Le dépôt public contient un **migrateur CouchDB → PostgreSQL/PostGIS** chargé de
reconstruire de façon reproductible la base cible à partir d'une base SIRS
Digues existante.

Un générateur de projet QGIS complète le migrateur pour les usages SIG
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
                         └───────────┬──────────┘
                                     │ SQL
                                     ▼
                              ┌────────────┐
                              │    QGIS    │
                              │ usage SIG  │
                              └────────────┘
```

### Principes

- CouchDB reste la source de migration tant que la bascule n'est pas achevée.
- PostgreSQL/PostGIS constitue la base cible et l'autorité métier/spatiale.
- Les calculs spatiaux et les règles de repérage restent côté
  PostgreSQL/PostGIS.
- QGIS reste disponible comme interface SIG complémentaire.
- La base PostgreSQL de développement reste actuellement recréable à partir de
  CouchDB.

---

# Installation et dépendances

## 1. Prérequis

Le projet nécessite au minimum :

- Python 3.11 ou plus récent ;
- `venv` ;
- PostgreSQL 16 ou compatible ;
- PostGIS ;
- l'extension PostgreSQL `pgcrypto`.

Pour la génération du projet QGIS uniquement :

- QGIS ;
- PyQGIS 3.38 ou plus récent.

**PyQGIS n'est pas requis pour lancer le migrateur.**

---

## 2. Linux — environnement Python

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
.venv/bin/python -m pip install -e .
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

Le venv Python normal reste utilisé pour le migrateur.

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

La CLI charge le fichier optionnel `config.env` situé à la racine du projet.
Les variables déjà définies dans l'environnement restent prioritaires.

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
cd ~/Projects/digues-app

digues-app check
digues-app recreate
digues-app init-schema
digues-app migrate-core
digues-app check --target-only
digues-app diagnose
digues-app qgis-project --output qgis/digues_app.qgz
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
digues-app check
```

Cette commande diagnostique les connexions CouchDB et PostgreSQL, les versions
de PostgreSQL, PostGIS et `pgcrypto`, ainsi que la présence des tables attendues.

Elle ne modifie aucune base.

Options :

```bash
digues-app check --source-only
digues-app check --target-only
digues-app check --profile secure
digues-app check --source-database autre_base
```

---

## `recreate`

```bash
digues-app recreate
```

> **Attention — opération destructive :** cette commande exécute un
> `DROP DATABASE` sur la base PostgreSQL cible configurée.

Toute donnée créée directement dans PostgreSQL ou QGIS depuis la dernière
migration est supprimée.

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
digues-app init-schema
```

Cette commande crée transactionnellement le schéma PostgreSQL courant dans
`public`.

Les instructions utilisent `CREATE TABLE IF NOT EXISTS`. Cette commande ne lit
pas CouchDB.

---

## `migrate-core`

```bash
digues-app migrate-core
```

La reconstruction sur le tronçon des désordres linéaires est activée par
défaut, avec une tolérance métrique de `0.0001` m (0,1 mm). Elle peut être
désactivée ou réglée explicitement :

```bash
digues-app migrate-core --no-reproject-on-troncon
digues-app migrate-core --on-troncon-tolerance 0.001
```

La tolérance doit être un nombre positif ou nul et s'exprime en mètres dans le
CRS cible EPSG:3950.

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

## `generate-model-manifest`

```bash
digues-app generate-model-manifest
```

Cette commande régénère le manifeste structurel du modèle historique SIRS
Digues 2.55 à partir de la référence versionnée dans :

```text
docs/reference/sirs-2.55/sirs.ecore
docs/reference/sirs-2.55/labels/*.properties
```

Le manifeste produit est :

```text
docs/reference/sirs-2.55/sirs_model_manifest.json
```

Il décrit les classes Ecore, attributs, références, cardinalités, super-types et
champs effectifs après héritage, enrichis lorsque possible avec leurs libellés
métier. Le fichier est généré de manière déterministe et ne doit pas être édité
manuellement.

Cette référence permet d'auditer le migrateur contre le modèle SIRS 2.55 même
lorsqu'un champ n'apparaît dans aucun document de la base CouchDB analysée.

La provenance et les empreintes de la référence historique sont documentées
dans `docs/reference/sirs-2.55/README.md`.

---

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

- le manifeste structurel SIRS 2.55 généré depuis `sirs.ecore`, qui décrit ce
  qui existe dans le modèle historique ;
- le registre de couverture de `migration/coverage.py`, qui décrit les décisions
  du projet ;
- les documents CouchDB, qui indiquent ce qui est effectivement rencontré dans
  le corpus analysé.

Le diagnostic ne déduit donc plus l'existence d'un champ de sa présence dans
CouchDB. Un champ du modèle peut être signalé avec zéro occurrence. À
l'inverse, une clé observée dans une classe Ecore connue mais absente du
manifeste est distinguée par `UNKNOWN_OBSERVED_FIELD`.

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

Les classes entièrement différées restent représentées au niveau classe, sans
produire artificiellement une anomalie pour chacune de leurs propriétés. Les
sous-objets contenus tels que `Observation` et `Photo` sont audités selon leur
propre classe Ecore, même lorsqu'ils ne constituent pas des documents CouchDB
racines.

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

Chaque entrée reçoit un `anomaly_id` déterministe. Les anomalies de couverture
par champ conservent notamment dans `details` le libellé métier, la classe
déclarante, l'héritage, le type Ecore, la présence dans le corpus, les nombres
d'occurrences et de valeurs non nulles, le statut de couverture et la référence
du manifeste utilisé. `source_field` identifie le champ concerné.

`UNMIGRATED_FIELD` reste la catégorie compatible pour un champ défini par le
modèle mais sans décision de couverture suffisante. `UNKNOWN_OBSERVED_FIELD`
désigne une clé effectivement observée dans CouchDB mais absente du manifeste
SIRS 2.55 ; elle doit être qualifiée avant toute décision de migration.

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
SIRS historique. Une absence dans un corpus source particulier ne constitue pas
une justification suffisante pour abandonner un champ ou une classe SIRS.

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

Pour les seuls `Desordre` historiques, `geometry` CouchDB peut être une
représentation projetée ou reconstruite par SIRS sur le tronçon. La migration
utilise donc prioritairement `positionDebut` et `positionFin`, qui constituent
la meilleure géométrie physique encore disponible : des positions identiques
produisent toujours un Point. Pour des positions différentes, le comportement
de base est une LineString directe A-B. Par défaut, si `linearId` désigne un
tronçon migré et si A et B sont chacun à au plus `0.0001` m (0,1 mm) de sa
géométrie canonique PostgreSQL, la migration reconstruit automatiquement la
portion de ce tronçon comprise entre A et B. Son orientation reste A vers B.
Cette reconstruction peut être désactivée avec
`--no-reproject-on-troncon`, ou son seuil modifié avec
`--on-troncon-tolerance <mètres>`.

Les sommets intermédiaires d'une ancienne géométrie QGIS ont déjà été perdus
lors de l'import historique dans SIRS et ne sont pas recréés. `geometry` n'est
utilisée qu'en fallback lorsque les positions sont inexploitables. Cette règle
est propre aux `Desordre` et ne s'applique pas aux autres classes géométriques.
Le tronçon n'est jamais choisi par proximité : seul celui référencé par le
`linearId` historique peut servir à la reconstruction.

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

# Variabilité des bases CouchDB sources

Une base CouchDB donnée ne contient pas nécessairement toutes les classes ni
tous les usages possibles du modèle SIRS Digues. Les valeurs vides peuvent en
outre être absentes des documents sérialisés. Un corpus source particulier ne
doit donc pas être traité comme une description exhaustive du schéma.

La référence structurelle locale du modèle historique est le snapshot SIRS 2.55
versionné sous `docs/reference/sirs-2.55/`, dont le manifeste est régénérable
avec `digues-app generate-model-manifest`.

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

Un élément encore non migré n'est pas considéré comme inutile : il reste à
analyser par rapport au modèle historique SIRS.

---

# Génération du projet QGIS

```bash
digues-app qgis-project --output qgis/digues_app.qgz
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
qgis/digues_app.qgz
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
- relecture après écriture.

Les tests PyQGIS peuvent être ignorés lorsque l'environnement QGIS n'est pas
disponible.

---

# Structure du code

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
```

---

# Principes de développement

- Le schéma SIRS Digues/CouchDB reste la référence métier générale.
- La migration vers PostgreSQL doit être fidèle par défaut.
- Tout écart au modèle historique doit être explicite, argumenté et documenté.
- Le manifeste SIRS 2.55 décrit le modèle historique indépendamment des champs
  effectivement rencontrés dans un corpus CouchDB.
- Une absence dans un corpus source ne signifie pas qu'une structure SIRS est
  inutile.
- PostgreSQL/PostGIS porte l'autorité métier et spatiale de la cible.
- Les UUID historiques sont conservés.
- Les nouvelles lignes peuvent recevoir des UUID générés par PostgreSQL.
- Une relation 1-N simple utilise une FK directe.
- Une relation N-N réelle utilise une table `link_`.
- Les référentiels utilisent le préfixe `ref_`.
- Les vues utilisent le préfixe `view_`.
- Les corrections de migration doivent être reproductibles.
- Les particularités d'une base source restent isolées et documentées.

---

# Prochaines briques

Les développements prévus concernent notamment :

- autres objets `Positionable` ;
- prestations ;
- intervenants ;
- migration du stockage des médias.

Chaque nouvelle brique doit être confrontée au modèle CouchDB historique avant
de modifier le modèle PostgreSQL cible.
