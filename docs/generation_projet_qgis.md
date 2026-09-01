# Génération reproductible du projet QGIS

Le projet `qgis/sirs_postgre.qgz` est un artifact local : il peut être supprimé
puis recréé à partir de `sirs_postgre/qgis_project.py`. Le code générateur est
versionné, tandis que le QGZ est déjà exclu par `.gitignore`.

## Commande

Depuis un Python qui fournit PyQGIS :

```text
sirs-postgre qgis-project --output qgis/sirs_postgre.qgz
```

La sortie est facultative et vaut `qgis/sirs_postgre.qgz` par défaut. L'option
`--authcfg ID` référence une configuration d'authentification du profil QGIS
local sans inscrire son secret dans le projet.

## Windows et OSGeo4W

Après installation de QGIS 3.38 ou plus récent, ouvrir **OSGeo4W Shell**, puis
exécuter :

```bat
cd /d C:\Users\julien.lorion\sirs-postgre
python-qgis.bat -m pip install -e .
python-qgis.bat -m sirs_postgre.cli qgis-project --output qgis\sirs_postgre.qgz
```

Avec l'installateur autonome, le lanceur se trouve généralement dans le dossier
`bin` de QGIS. Sans modifier le `PATH` système :

```bat
cd /d C:\Users\julien.lorion\sirs-postgre
"C:\Program Files\QGIS 3.xx.x\bin\python-qgis.bat" -m pip install -e .
"C:\Program Files\QGIS 3.xx.x\bin\python-qgis.bat" -m sirs_postgre.cli qgis-project --output qgis\sirs_postgre.qgz
```

Le `config.env` courant reste la seule configuration sirs-postgre : aucune
configuration PostgreSQL parallèle n'est créée.

## Linux

Utiliser le Python qui voit les modules PyQGIS du système. Selon la
distribution, il s'agit du Python système ou d'un environnement dont les
chemins de paquets et bibliothèques QGIS ont été configurés. En environnement
sans affichage :

```text
QT_QPA_PLATFORM=offscreen python -m sirs_postgre.cli qgis-project
```

Le projet de ce lot a été généré et relu avec PyQGIS 3.44 sous Linux. Le
générateur détruit explicitement projets, couches et relations avant
`exitQgis()` afin d'éviter la destruction tardive de wrappers SIP.

## Connexion et secrets

Le générateur reprend `host`, `port`, `database` et `user` depuis
`PostgreSQLConfig`, y compris lorsque ces valeurs proviennent de
`SIRS_POSTGRE_DSN`. Le mot de passe sert temporairement à libpq via la variable
de processus `PGPASSWORD`, puis l'environnement antérieur est restauré. La
source enregistrée dans le QGZ contient un mot de passe vide.

Pour rouvrir le projet, utiliser l'une des stratégies locales suivantes :

- une configuration QGIS existante, transmise avec `--authcfg` ;
- un fichier PostgreSQL `.pgpass` protégé ;
- la demande interactive de mot de passe de QGIS.

Ni `config.env`, ni un mot de passe, ni une base d'authentification QGIS ne sont
écrits dans le dépôt.

## Contenu généré

Le panneau contient `SIRS/Patrimoine`, `SIRS/Désordres`, `SIRS/Repérage` et
`SIRS/Diagnostic`, puis le groupe racine `Fonds de carte` placé en dessous.
Ce dernier contient une unique couche raster XYZ native `OpenStreetMap`,
activée par défaut et construite directement depuis l'URL publique standard :

```text
https://tile.openstreetmap.org/{z}/{x}/{y}.png
```

La couche ne dépend d'aucune connexion QGIS préexistante, d'aucun identifiant
et d'aucun secret. Elle porte l'attribution « © OpenStreetMap contributors ».
Les couches LineString et Polygon pointent vers `desordres` avec un filtre
géométrique. La couche Point utilise la vue éditable
`view_desordres_points_saisie`, afin que X/Y et longitude/latitude réécrivent
la géométrie unique. Les trois couches ont des IDs distincts et possèdent des
relations stables vers le repérage et vers les tronçons concernés.

`desordre_localisations_reperage` et `link_desordres_troncons` sont ajoutées au
registre du projet avec le flag QGIS `Private`, sans nœud dans l'arbre. Les
diagnostics et positions CouchDB ne sont pas des colonnes du modèle
opérationnel ; ils restent dans les artefacts de migration.

Le formulaire parent utilise le Drag-and-Drop Designer. Le groupe **Général**
est conservé car il contient plusieurs champs. Sur la couche ponctuelle, un
groupe **Coordonnées** rassemble quatre champs éditables : X et Y en EPSG:3950,
longitude et latitude en EPSG:4326. La couche LineString affiche en lecture
seule les coordonnées de ses deux extrémités. Polygon reste cartographique.
La relation des tronçons et le message de disponibilité sont à la racine ; le
groupe **Repérage**, visible seulement avec un tronçon unique pour Point ou
LineString, contient l'avertissement et la relation de localisation.

Le formulaire enfant utilise uniquement des widgets standards QGIS/QField :
Value Relation, Value Map et Range. Tronçon filtre les systèmes de repérage,
puis le système filtre les bornes via `view_systemes_reperage_bornes`. Les
bornes stockent toujours leur UUID mais affichent leur rôle spatial « Début du
tronçon » ou « Fin du tronçon », sinon leur libellé métier. Le choix de
position est limité à **Amont** (`AVANT_BORNE`) et **Aval**
(`APRES_BORNE`) ; une distance nulle est présentée comme « sur la borne » et
donne dans les deux cas un offset nul. `SUR_BORNE` reste compatible avec les
données existantes, mais n'est plus proposé à la saisie.

Les PR courants sont calculés par PostgreSQL et affichés à 2 décimales. Les
UUID techniques et offsets signés restent masqués. Les coordonnées sont
exposées par une vue, sans colonne indépendante dans `desordres`. Les champs
de traçabilité CouchDB ont été retirés du schéma métier.

## Contrôle après génération

Le générateur relit lui-même le QGZ et vérifie les IDs de couches, les six
relations, les groupes attendus, les widgets de borne et de position, les
expressions de coordonnées et l'absence de groupe de formulaire ne contenant
qu'un seul élément. Il échoue si une couche PostgreSQL est invalide ou si la
relecture diffère de la spécification.

## Limite QField

Le fond OpenStreetMap est destiné exclusivement à la consultation connectée.
Le générateur ne précharge aucune tuile et ne produit ni MBTiles ni paquet
offline. Le choix et la génération d'un futur fond QField hors connexion sont
volontairement hors périmètre de ce lot.

Les filtres `current_value(...)`, la visibilité conditionnelle et la
présentation des relations doivent encore être validés sur la version QField
réellement déployée. En particulier, une sous-fiche déjà ouverte peut nécessiter
un rafraîchissement après modification du nombre de tronçons. Le système par
défaut n'est qu'une commodité de synchronisation ; toutes les conversions
reçoivent explicitement tronçon, système et borne.
