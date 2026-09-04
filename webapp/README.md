# sirs-webapp

Application web métier privée associée au migrateur et au modèle PostgreSQL
publics `sirs-postgre`. Elle permet de consulter et modifier les données SIRS
depuis un navigateur, avec FastAPI, Leaflet et PostgreSQL/PostGIS.

## Architecture

```text
Navigateur
├── HTML / CSS / JavaScript
├── Leaflet
└── Leaflet.Editable
        ↓
     FastAPI
        ├── PostgreSQL / PostGIS
        └── API Mistral (texte uniquement, appel côté serveur)
```

Le frontend reste volontairement simple : pas de React, Vue, TypeScript, Node
ou chaîne de build obligatoire. Les géométries sont exposées en GeoJSON
`EPSG:4326`. PostGIS conserve les géométries métier en `EPSG:3950` et réalise
les transformations ainsi que les règles spatiales et de repérage.

Le navigateur ne se connecte jamais directement à PostgreSQL. Le backend
utilise le modèle et la configuration de cible fournis par le paquet public
`sirs-postgre`.

L’assistant reçoit un contexte de schéma construit côté serveur depuis
`pg_catalog`. L’introspection est limitée au schéma `public` et aux tables et
vues déclarées par le modèle SIRS versionné, puis mise en cache en mémoire
pendant cinq minutes. Seules les métadonnées de structure sont lues : aucune
ligne métier n’est transmise à Mistral.

## Moteur SQL de lecture

Le module serveur `readonly_sql.py` fournit un moteur commun à l’Assistant IA et
à la future vue Requêtes. Il n'est pas exposé par une route SQL publique. Il
accepte une instruction unique `SELECT` ou `WITH … SELECT`, y
compris les jointures, agrégations et fonctions PostgreSQL/PostGIS. Il refuse
les mutations (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, etc.), les opérations de
schéma ou de permissions (`CREATE`, `ALTER`, `DROP`, `GRANT`, `REVOKE`, etc.) et
une liste prudente de fonctions à effet de bord connu.

La validation applicative n'est qu'une première barrière : chaque requête est
exécutée dans une transaction PostgreSQL explicitement `READ ONLY`, avec un
`statement_timeout` local de 30 secondes. En production, la connexion de ce
moteur doit en plus employer un rôle PostgreSQL dédié ne possédant que les
droits de lecture nécessaires sur les objets SIRS. Le rôle actuellement utilisé
en développement et dans les tests d'intégration possède des droits d'écriture
et ne constitue donc pas le rôle cible. Une fonction appelée depuis un `SELECT`
peut avoir des effets de bord ; l'analyse lexicale ne remplace ni la transaction
en lecture seule ni les permissions du rôle.

Le SQL n'est pas réécrit et aucun `LIMIT` n'est ajouté. Un curseur serveur ne
matérialise au plus que 1 000 lignes et environ 1 Mo de JSON ; `truncated=true`
signale que le transport a été coupé, sans fausser une agrégation calculée par
PostgreSQL. Les valeurs non JSON sont normalisées en texte. Une géométrie brute
reste donc sous la représentation textuelle/binaire fournie par psycopg ; une
requête peut demander explicitement `ST_AsText` ou `ST_AsGeoJSON` lorsqu'un
format précis est nécessaire.

L’Assistant IA peut consulter les données SIRS au moyen de l’unique outil
Mistral `query_sirs_database`. Mistral choisit automatiquement de l’appeler
lorsqu’une réponse dépend des données courantes. Chaque lecture passe sans
exception par `readonly_sql.py` et conserve sa validation, sa transaction
`READ ONLY`, son timeout, ses limites de transport et les permissions du rôle
PostgreSQL. Aucun outil d’écriture n’existe. Les échanges techniques et le SQL
restent côté serveur, à l’exception du texte des requêtes exécutées avec succès,
associé à la réponse pour permettre leur consultation et leur copie. Le panneau
IA ne permet ni de les exécuter, ni de les transférer automatiquement vers la
vue Requêtes. Une demande utilisateur peut déclencher au maximum cinq
appels d’outil, puis un dernier appel Mistral sans outil est imposé afin de
produire une réponse avec les résultats déjà obtenus.

L’assistant peut exécuter des consultations, mais toute modification persistante
reste une action humaine explicite.

## Fonctions disponibles

- navigation `Système d'endiguement → Digue → Tronçon` ;
- consultation, création et édition limitée des désordres Point, LineString et
  Polygon ;
- localisation par coordonnées `EPSG:3950`, longitude/latitude `EPSG:4326`,
  déplacement graphique ou repérage par borne ;
- édition graphique des LineString avec conservation des sommets
  intermédiaires ;
- consultation des observations et des métadonnées de photos ;
- relecture systématique des valeurs réellement persistées par PostgreSQL.

La création et les modifications restent contrôlées par les contraintes, vues,
fonctions et triggers du modèle PostgreSQL public. Le stockage et le service du
contenu binaire des médias restent à finaliser.

L'application est encore une interface expérimentale de développement. Elle
n'est pas une PWA complète et ne propose pas de synchronisation hors ligne.
Leaflet, Leaflet.Editable et les tuiles OpenStreetMap sont actuellement chargés
depuis des services externes ; ces dépendances devront être embarquées pour un
déploiement intranet ou hors ligne.

La documentation fonctionnelle et la procédure de recette complètes se trouvent
dans `docs/interface_web_experimentale.md`.

## Installation

Installer d'abord le migrateur public puis le sous-projet web depuis la racine
du dépôt :

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e . -e webapp
```

Sous Windows :

```cmd
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e . -e webapp
```

Le backend charge sans écraser l'environnement le fichier optionnel
`config.env` situé à la racine du dépôt. Il utilise les variables
`SIRS_POSTGRE_*` du migrateur. `SIRS_WEB_SHOW_UUID=false` masque les UUID dans
l'interface ; la valeur `true` les affiche. L’assistant texte utilise
`MISTRAL_API_KEY`, à définir dans l’environnement du serveur ou dans le fichier
local non versionné `config.env`. Cette clé n’est jamais envoyée au navigateur.

## Lancement local

Depuis la racine du dépôt :

```bash
.venv/bin/python -m uvicorn --app-dir webapp/backend sirs_webapp.app:app --reload
```

Sous Windows :

```cmd
.venv\Scripts\python.exe -m uvicorn --app-dir webapp\backend sirs_webapp.app:app --reload
```

Ouvrir ensuite `http://127.0.0.1:8000/`. L'option `--reload` redémarre le
serveur lorsque le code Python est modifié.

## Tests privés

```bash
PYTHONPATH=webapp/backend .venv/bin/python -m unittest discover -s webapp/tests -v
```

Sous Windows :

```cmd
set PYTHONPATH=webapp\backend&& .venv\Scripts\python.exe -m unittest discover -s webapp\tests -v
```

La suite comporte des tests unitaires avec doubles de connexion et des tests
d'intégration PostgreSQL/PostGIS conditionnels. Elle contrôle également la
présence et le service des assets frontend.

## Prochaines briques

- création de nouveaux objets métier supplémentaires ;
- édition des observations et photos ;
- généralisation des formulaires métier ;
- stockage et service des médias ;
- préparation éventuelle d'une PWA et d'un fonctionnement hors ligne.

Chaque nouvelle brique doit être confrontée au modèle CouchDB historique avant
de demander une évolution du modèle PostgreSQL public.
