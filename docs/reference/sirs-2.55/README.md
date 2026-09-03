# Référence historique SIRS Digues 2.55

Ce répertoire contient une copie de référence, traçable et locale, du modèle historique SIRS Digues 2.55. Il sert de base documentaire pour concevoir et auditer la migration PostgreSQL, ainsi que pour répondre à la question: « Quels champs/classes/références existent dans le modèle SIRS 2.55 ? »

La définition structurelle primaire du modèle est `sirs.ecore`. Les libellés métier associés aux classes et propriétés se trouvent dans `labels/*.properties`.

Le build historique du dépôt source utilise `fr.sirs.maven:gen-maven-plugin` avec les objectifs `fxmodel` et `fxmodel2sql` à partir de `model/sirs.ecore`, avec le package modèle `fr.sirs.core.model`.

Les classes Java générées dans `target/generated-sources/fxmodel` sont produites à partir de ce modèle. Elles ne sont pas copiées ici volontairement.

Le corpus CouchDB observé ne constitue pas un inventaire exhaustif du modèle. Côté Java historique, plusieurs classes générées utilisent `@JsonInclude(Include.NON_EMPTY)`, ce qui permet l'absence de propriétés vides dans les documents CouchDB. Une analyse ponctuelle du code Java historique peut donc encore être utile pour comprendre certains comportements applicatifs, mais elle ne doit plus être nécessaire pour refaire l'inventaire structurel du modèle.

Chaîne documentaire visée:

`sirs.ecore` + `labels/*.properties` -> `sirs-postgre generate-model-manifest` -> `sirs_model_manifest.json` -> registre de couverture du migrateur -> corpus CouchDB observé -> rapport de couverture / anomalies

## Provenance

- Source originale de `sirs.ecore`: `/home/julien/Projects/sirs-255-build/sirs-core/model/sirs.ecore`
- SHA-256 source de `sirs.ecore`: `c01ef4e497142c6e60262291ef641cfc8984947ec09a77c2add1aac5811fdec2`
- SHA-256 de la copie intégrée: `c01ef4e497142c6e60262291ef641cfc8984947ec09a77c2add1aac5811fdec2`
- Vérification des empreintes: identiques
- Commit HEAD du dépôt source `/home/julien/Projects/sirs-255-build`: `ff06d0b8aff2093811b83e7c062897d54814c285`
- État Git du dépôt source au moment de la copie: propre, `git status --short` vide
- Nombre de fichiers `labels/*.properties` copiés: 169
- Chemin du binaire historique `sirs-core-2.55.jar` trouvé localement: `/home/julien/Projects/sirs255-extract/app/app/lib/sirs-core-2.55.jar`
- SHA-256 du binaire trouvé: `abcbf59f92983295ee2fbee5d046a295cf41e875ac6c87a720d4ffcc437b5366`

## Contrôles de copie

- `sirs.ecore` est présent dans le dépôt cible.
- Son SHA-256 est strictement identique à celui de la source.
- Le nombre de fichiers `.properties` source et cible est identique.
- Les fichiers `.properties` ont été copiés sans modification.
- Le modèle contient bien les classes attendues suivantes: `SystemeEndiguement`, `Digue`, `TronconDigue`, `Desordre`, `Observation`, `Photo`.

## Rôle prévu

Cette copie doit devenir la référence locale pour l'inventaire structurel du modèle historique. La chaîne de travail prévue à terme est la suivante:

1. `sirs.ecore` et `labels/*.properties`
2. extracteur déterministe `sirs-postgre generate-model-manifest`
3. manifeste généré `sirs_model_manifest.json`
4. registre de couverture du migrateur
5. corpus CouchDB observé
6. rapport de couverture et d'anomalies

Le manifeste `sirs_model_manifest.json` est un artefact généré. Il ne doit pas être édité manuellement pour ajouter, retirer ou corriger des champs: toute modification structurelle doit venir de `sirs.ecore`, et tout libellé doit venir de `labels/*.properties`.

Cette chaîne n'est pas implémentée dans ce lot.
