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

Aucune installation QGIS, `qgis_process`, `python-qgis` ou OSGeo4W n'était
accessible dans l'environnement ayant produit ce lot. Les chemins exacts
dépendent donc de l'installation locale. Après installation de QGIS 3.38 ou
plus récent, ouvrir **OSGeo4W Shell**, puis exécuter :

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
`SIRS/Diagnostic`. Les trois couches de désordres pointent vers la même table
avec des filtres Point, LineString et Polygon. Elles ont des IDs distincts et
chacune possède une relation stable vers la même table enfant.

`desordre_localisations_reperage` est ajoutée au registre du projet avec le
flag QGIS `Private`, sans nœud dans l'arbre et avec une source PostgreSQL sans
colonne géométrique principale. Les colonnes `position_debut_source` et
`position_fin_source` restent donc des attributs historiques masqués du
formulaire ; elles ne créent pas deux couches cartographiques visibles.

Le formulaire parent utilise le Drag-and-Drop Designer avec les groupes
**Général** et **Localisation / Repérage**. Le formulaire enfant utilise des
widgets standards QGIS/QField : Value Relation, Value Map et Range. Les UUID,
offsets, positions source, politiques, qualités et traces JSON sont masqués.

## Contrôle après génération

Le générateur relit lui-même le QGZ et vérifie les IDs de couches, les trois
relations et les groupes attendus. Il échoue si une couche PostgreSQL est
invalide ou si la relecture diffère de la spécification.
