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
        ↓
PostgreSQL / PostGIS
```

Le frontend reste volontairement simple : pas de React, Vue, TypeScript, Node
ou chaîne de build obligatoire. Les géométries sont exposées en GeoJSON
`EPSG:4326`. PostGIS conserve les géométries métier en `EPSG:3950` et réalise
les transformations ainsi que les règles spatiales et de repérage.

Le navigateur ne se connecte jamais directement à PostgreSQL. Le backend
utilise le modèle et la configuration de cible fournis par le paquet public
`sirs-postgre`.

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
l'interface ; la valeur `true` les affiche.

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
