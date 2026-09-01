# Interface web cartographique expérimentale

Ce composant est un prototype local. La carte reste principalement en lecture,
avec une édition volontairement limitée aux désordres Point et à la géométrie
des désordres LineString. Il ne constitue pas l’interface définitive de SIRS.

## Architecture

- `sirs_postgre/web/` : API FastAPI et requêtes PostgreSQL ;
- `web/` : page HTML, styles et JavaScript Leaflet ;
- PostgreSQL/PostGIS : source de vérité, sans modification du schéma ni des
  géométries persistées.

Le navigateur ne reçoit aucun identifiant PostgreSQL. FastAPI utilise la même
configuration `SIRS_POSTGRE_*` et le même pilote psycopg que les commandes de
migration. Les valeurs de `config.env` sont chargées sans remplacer les
variables déjà définies dans l’environnement.

Les tronçons sont lus dans `public.troncons`. Les désordres Point et LineString
sont lus dans `public.desordres`, avec le libellé de type provenant de
`public.ref_types_desordre`. PostGIS transforme explicitement les géométries
EPSG:3950 vers EPSG:4326 uniquement dans les réponses GeoJSON.

La navigation patrimoniale utilise les relations existantes :

```text
public.systemes.id
→ public.digues.systeme_endiguement_id
→ public.troncons.digue_id
```

`GET /api/systemes-endiguement` renvoie l’arbre complet en une seule lecture :

```json
{
  "systemes": [
    {
      "id": "…",
      "libelle": "SE A",
      "valid": true,
      "digues": [
        {
          "id": "…",
          "systeme_endiguement_id": "…",
          "libelle": "Digue 1",
          "valid": true,
          "troncons": [
            {
              "id": "…",
              "digue_id": "…",
              "systeme_reperage_defaut_id": "…",
              "libelle": "Tronçon 1",
              "valid": true
            }
          ]
        }
      ]
    }
  ]
}
```

Cette réponse ne contient aucune géométrie. Pour le zoom explicite, le frontend
retrouve le tronçon par son identifiant dans la FeatureCollection déjà chargée
depuis `/api/troncons`. Les digues sans système d’endiguement ne figurent pas
dans cet arbre centré sur les systèmes.

L’édition ponctuelle passe exclusivement par
`public.view_desordres_points_saisie`. Son trigger `editer_desordre_point()`
arbitre la famille X/Y ou longitude/latitude, reconstruit la géométrie métier et
laisse les triggers de `public.desordres` synchroniser le repérage. Le PUT relit
ensuite la vue dans la même transaction et renvoie ce nouvel état au navigateur.

Le déplacement graphique utilise le handler natif de `L.Marker`. Tous les
marqueurs sont immobiles par défaut ; seul le Point sélectionné devient
déplaçable après l’action explicite `Modifier la position sur la carte`. Le drag
reste local au navigateur. Sa validation envoie uniquement :

```json
{"longitude_4326": 2.25, "latitude_4326": 48.75}
```

PostGIS recalcule ensuite la géométrie métier, X/Y et le repérage éventuel. En
cas d’échec, le marqueur reste à sa position provisoire jusqu’à une nouvelle
validation ou à `Annuler le déplacement`.

### Localisation d'un Point par bornage

Le mode Bornage écrit directement dans l'objet enfant prévu par le modèle :

```text
public.link_desordres_troncons
→ public.desordre_localisations_reperage
→ desordre_reperage_appliquer_trigger
→ public.appliquer_desordre_reperage()
→ public.borne_offset_vers_xy()
→ public.desordres.geometry
```

Il est proposé uniquement lorsque le Point possède exactement un tronçon
associé et que celui-ci fournit un système de repérage. La liste de bornes vient
de `public.view_systemes_reperage_bornes` et reste filtrée sur ce système.

`PUT /api/desordres/{id}/reperage` accepte uniquement :

```json
{
  "borne_debut_id": "00000000-0000-0000-0000-000000000000",
  "distance_debut_m": 12.5,
  "position_debut_relative": "APRES_BORNE"
}
```

Les sens admis par PostgreSQL sont `AVANT_BORNE`, `SUR_BORNE` et
`APRES_BORNE`. `SUR_BORNE` impose une distance nulle. L'API détermine elle-même
le tronçon et le système depuis les relations en base, écrit la table enfant,
puis relit `view_desordres_points_saisie` avec son repérage dans la même
transaction. La réponse GeoJSON — géométrie, quatre coordonnées et repérage —
remplace entièrement l'état affiché et repositionne le marqueur Leaflet.

### Édition graphique d'une LineString

Les LineString sont lues et écrites dans `public.desordres`. Il n'existe pas de
vue de saisie linéaire équivalente à la vue ponctuelle. Le flux est donc :

```text
GeoJSON LineString EPSG:4326
→ ST_GeomFromGeoJSON
→ ST_Transform(..., 3950)
→ UPDATE public.desordres.geometry
→ desordres_recalcul_reperage_trigger
→ synchroniser_desordre_reperage()
→ relecture GeoJSON EPSG:4326
```

Le trigger existant utilise `ST_StartPoint` et `ST_EndPoint` uniquement pour
calculer le repérage des extrémités. La géométrie persistée conserve tous ses
sommets intermédiaires.

`PUT /api/desordres/{id}/geometry` accepte exclusivement :

```json
{
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [2.1, 50.5],
      [2.11, 50.51],
      [2.12, 50.52]
    ]
  }
}
```

Chaque position contient une longitude et une latitude finies. Une ligne doit
avoir au moins deux sommets ; PostGIS contrôle également qu'elle n'est ni vide
ni dégénérée avant l'écriture.

Le frontend utilise
[`Leaflet.Editable` 1.2.0](https://github.com/Leaflet/Leaflet.Editable), chargé
depuis unpkg après Leaflet. Leaflet natif ne fournit pas de poignées d'édition
pour les polylignes. Cette bibliothèque minimale expose `enableEdit()` et
`disableEdit()`, déplace les sommets et permet d'en créer depuis les poignées
intermédiaires, sans barre de dessin globale. Elle est distribuée sous licence
WTFPL. Leaflet-Geoman n'a pas été retenu car ses fonctions de dessin, découpe,
rotation et snapping dépassent le besoin de ce lot.

Pendant l'édition, la couche Leaflet porte la géométrie provisoire et
`lastServerFeature` conserve le GeoJSON complet reçu du serveur. `Annuler`
réapplique tous les sommets de cette copie. Aucun appel HTTP n'est effectué par
les événements de déplacement ; le PUT part uniquement avec `Valider la
géométrie`. Après succès, la réponse PostgreSQL remplace la géométrie locale et
le résumé du repérage.

La consultation des observations respecte la chaîne relationnelle cible :

```text
public.desordres.id
→ public.observations.desordre_id
→ public.photos.observation_id
```

La liste est triée par date décroissante. Elle expose `designation`, `date`,
`evolution`, `urgence_id`/son libellé, `valid` et le nombre de photos. La fiche
d’une observation renvoie en une seule lecture ses photos enfants (`id`, date,
désignation, validité et nom de fichier).

La table `public.photos` ne contient aucun binaire ni URL exploitable : elle
conserve seulement `chemin_source`, hérité de la source. Aucun répertoire média
serveur n’étant configuré, l’API n’expose ni ce chemin local ni un faux endpoint
de contenu. La visionneuse affiche donc les métadonnées, la navigation
précédent/suivant et un message explicite d’indisponibilité. Elle pourra charger
la pleine résolution à la demande lorsqu’une règle sûre de matérialisation des
médias aura été définie.

## Lancement local

Depuis la racine du dépôt :

```console
python -m pip install -e .
python -m uvicorn sirs_postgre.web.app:app --reload
```

Ouvrir ensuite <http://127.0.0.1:8000/>. La documentation automatique de l’API
est disponible sur <http://127.0.0.1:8000/docs>.

Routes disponibles :

- `GET /` ;
- `GET /api/troncons` ;
- `GET /api/systemes-endiguement` ;
- `GET /api/desordres` ;
- `GET /api/desordres/{id}` pour un désordre Point ou LineString ;
- `GET /api/desordres/{id}/observations` pour les observations directement
  liées au désordre ;
- `GET /api/observations/{id}` pour une observation de désordre et les
  métadonnées de ses photos enfants ;
- `PUT /api/desordres/{id}/reperage` pour le bornage d'un Point lié à exactement
  un tronçon ;
- `PUT /api/desordres/{id}/geometry` pour remplacer uniquement la géométrie
  d'un désordre LineString existant ;
- `PUT /api/desordres/{id}` pour une modification ponctuelle contrôlée.

Le PUT accepte les champs texte `designation`, `type_desordre_id` et
`commentaire`, ainsi qu’au plus une des deux familles complètes :

```json
{"coord_x_3950": 123.45, "coord_y_3950": 678.9}
```

ou :

```json
{"longitude_4326": 2.25, "latitude_4326": 48.75}
```

## Vérification manuelle du formulaire

1. Ouvrir <http://127.0.0.1:8000/>.
2. Vérifier l’absence des contrôles Leaflet `+` et `−`, puis utiliser la molette
   pour confirmer que la carte reste zoomable.
3. Cliquer sur `Système d'endiguement` et vérifier l’ouverture du panneau gauche.
4. Déplier successivement un système, une digue puis ses tronçons.
5. Cliquer sur les noms des trois niveaux et vérifier leurs propriétés.
6. Sélectionner un tronçon, vérifier sa mise en évidence, puis cliquer sur
   `Zoomer sur ce tronçon`.
7. Laisser le panneau gauche ouvert et cliquer sur un désordre ponctuel rouge ;
   vérifier que le panneau droit s’ouvre sans fermer le panneau gauche.
8. Vérifier que le panneau droit affiche l’identifiant, les champs métier et les
   deux familles de coordonnées relues depuis PostgreSQL.
9. Choisir `Modifier X/Y`, changer les deux valeurs, puis cliquer sur
   `Enregistrer`.
10. Vérifier que le marqueur se déplace et que longitude/latitude sont remplacées
   par les valeurs renvoyées par PostgreSQL.
11. Choisir ensuite `Modifier longitude/latitude`, modifier les deux valeurs et
   enregistrer ; vérifier cette fois la mise à jour de X/Y et du marqueur.
12. Modifier un champ sans enregistrer puis cliquer sur `Annuler` ; le formulaire
   doit revenir au dernier état reçu du serveur.
13. Pour observer un refus sans perdre la saisie, vider une coordonnée de la
   famille sélectionnée puis cliquer sur `Enregistrer`.
14. Cliquer sur `Modifier la position sur la carte`, déplacer le seul marqueur
   sélectionné et vérifier que les lon/lat changent sans requête d’écriture.
15. Cliquer sur `Annuler le déplacement` et vérifier le retour exact à la
    position serveur.
16. Recommencer le déplacement puis cliquer sur `Valider la position` ; vérifier
    le recalage du marqueur ainsi que l’actualisation des quatre coordonnées.
17. Ouvrir l’onglet `Observations`, vérifier l’ordre décroissant des dates, puis
    ouvrir une observation.
18. Vérifier ses propriétés et la section `Photos`, puis cliquer sur une photo.
19. Dans la visionneuse, utiliser précédent/suivant, la fermer, revenir à la
    liste des observations puis à l’onglet `Général`.
20. Vérifier qu’une édition du désordre fonctionne toujours après ce parcours.
21. Sur un Point lié à exactement un tronçon, sélectionner `Modifier le
    bornage`, choisir une borne, une distance et un sens, puis enregistrer.
22. Vérifier que le marqueur, X/Y, longitude/latitude et le PR sont tous remplacés
    par la réponse PostgreSQL ; fermer puis rouvrir le Point pour vérifier la
    persistance.
23. Modifier le bornage puis cliquer sur `Annuler` et vérifier le retour exact au
    dernier état serveur.
24. Ouvrir un Point sans tronçon, puis un Point avec plusieurs tronçons : le mode
    Bornage doit être désactivé avec une explication courte.
25. Vérifier enfin que les modes X/Y, lon/lat et déplacement graphique restent
    mutuellement exclusifs avec le bornage.
26. Cliquer sur un désordre LineString et vérifier sa fiche, son nombre de
    sommets et le repérage relu.
27. Cliquer sur `Modifier la géométrie`, déplacer un sommet et éventuellement
    une poignée intermédiaire ; vérifier dans l'onglet réseau qu'aucun PUT ne
    part pendant ces manipulations.
28. Cliquer sur `Annuler` et vérifier le retour exact de tous les sommets.
29. Recommencer avec plusieurs sommets, puis cliquer sur `Valider la géométrie`.
30. Vérifier le recalage de la ligne sur la réponse serveur, fermer et rouvrir la
    fiche, puis confirmer la persistance des sommets intermédiaires.
31. Pendant une nouvelle édition, tenter de sélectionner un autre désordre et
    d'ouvrir les observations : l'interface doit demander de valider ou annuler.

La base cible doit avoir été créée, initialisée et alimentée par les commandes
habituelles de `sirs-postgre`. L’accès réseau au serveur de fond OpenStreetMap et
au CDN Leaflet est nécessaire pour afficher la carte complète.
