# Sonde expérimentale ARPEGE

`arpege_precipitation_probe.py` compare les coverages de précipitation ARPEGE
`P1D`, `PT1H`, `PT3H` et `PT6H` sur une petite emprise commune. Il découvre le
dernier run complet avec WCS, choisit leur première échéance valide commune,
télécharge quatre GeoTIFF temporaires puis affiche leurs statistiques et leurs
métadonnées GDAL/GRIB.

Cette sonde est un outil d'investigation local. Elle n'est appelée ni par le
backend ni par le frontend et ne constitue pas le futur cache météo SIRS.

## Prérequis

- Python 3.11 ou supérieur ;
- `requests` et `python-dotenv`, déjà déclarés par le projet ;
- GDAL et ses bindings Python `osgeo`, déjà installés par le `Dockerfile` du
  projet et requis par l'import du territoire administratif.

La sonde n'utilise ni rasterio, ni NumPy, ni une commande shell GDAL.

## Exécution

Définir la clé uniquement dans l'environnement ou dans le fichier local ignoré
`config.env` :

```text
METEOFRANCE_API_KEY=...
```

Puis lancer :

```bash
.venv/bin/python scripts/weather/arpege_precipitation_probe.py
```

La bbox WGS84 par défaut est une petite fenêtre située dans le secteur CABBALR.
Elle peut être remplacée sans télécharger tout le territoire :

```bash
.venv/bin/python scripts/weather/arpege_precipitation_probe.py \
  --bbox 2.45,50.40,2.75,50.60
```

`--temporal-samples 1` à `3` ajoute autant d'échéances P1D successives pour
examiner un éventuel cumul glissant. Les rasters sont placés dans un répertoire
temporaire automatiquement supprimé. `--json-output chemin.json` permet de
conserver les statistiques et métadonnées, mais jamais la clé API.
