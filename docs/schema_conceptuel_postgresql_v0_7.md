# SIRS — schéma conceptuel PostgreSQL/PostGIS

Version : **0.7 — 5 septembre 2026**  
Source : schéma conceptuel v0.6 + ajout d'un territoire administratif de configuration d'instance + clarification du SRID cible

## Objet de cette version

La v0.7 conserve le modèle opérationnel défini en v0.6 et ajoute un objet
strictement propre à la nouvelle application web : le territoire administratif.

Cet objet n'existe pas dans le modèle CouchDB historique SIRS Digues. Il ne
fait donc pas partie de la migration métier historique. Il constitue un
paramètre de configuration de l'instance SIRS, destiné notamment à :

- circonscrire les données météorologiques futures ;
- fournir la bbox de référence des futures requêtes météo ;
- servir au masque visuel extérieur au territoire dans l'application web.

Le territoire administratif est volontairement non historisé. La base contient
soit aucune ligne, soit une seule ligne courante.

## 1. Table de configuration singleton

```sql
CREATE TABLE IF NOT EXISTS public.territoires_administratifs (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    libelle TEXT NOT NULL,
    geometry geometry(Polygon, 3950) NOT NULL,
    CONSTRAINT territoires_administratifs_geometry_check
        CHECK (
            GeometryType(geometry) = 'POLYGON'
            AND ST_IsValid(geometry)
            AND NOT ST_IsEmpty(geometry)
        )
);
```

Cette table représente une configuration singleton et non une collection
d'entités métier.

La cardinalité est volontairement `0..1` :

- table vide tant qu'aucun territoire n'est configuré ;
- une seule ligne maximum ;
- remplacement du territoire courant sans conservation des anciennes
  géométries.

Le mécanisme retenu repose uniquement sur PostgreSQL standard :

- `id INTEGER PRIMARY KEY DEFAULT 1`;
- `CHECK (id = 1)`;
- une insertion de remplacement peut utiliser un `INSERT ... ON CONFLICT (id)`
  ou un `DELETE` suivi d'un `INSERT`.

## 2. Contraintes géométriques

Le territoire administratif doit respecter les invariants suivants :

- exactement un objet géométrique par enregistrement ;
- géométrie obligatoirement de type `POLYGON` ;
- `MULTIPOLYGON` interdit par le typmod et par la contrainte explicite ;
- géométrie valide ;
- géométrie non vide ;
- aucune fusion automatique de plusieurs entités polygonales à l'import.

Le DDL ci-dessus utilise `geometry(Polygon, 3950)` pour rester cohérent avec
le schéma cible actuel de l'instance.

## 3. SRID et portée

Le SRID `3950` n'est pas une propriété métier universelle de SIRS. Il s'agit
du SRID cible actuellement configuré pour cette instance et pour le reste du
schéma de prototype.

Cette valeur est conservée ici pour la cohérence du déploiement actuel. En
revanche, le SRID devra à terme devenir paramétrable afin de permettre des
déploiements dans d'autres régions et avec d'autres CRS / EPSG.

Cette future paramétrisation n'est pas réalisée dans cette étape. L'audit du
dépôt montre qu'elle serait transversale :

- au migrateur ;
- au DDL PostgreSQL ;
- aux validations SQL ;
- au backend web ;
- au frontend ;
- aux tests ;
- à la documentation.

## 4. Hors périmètre de cette étape

Cette v0.7 ne développe pas :

- l'import ZIP/SHP ;
- l'import GeoPackage ;
- l'API web ;
- le frontend ;
- Leaflet ;
- le masque extérieur ;
- la météo ;
- ARPEGE ;
- la refonte générale des CRS.

Le reste du modèle conceptuel v0.6 demeure inchangé.

