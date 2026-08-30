"""Interface en ligne de commande du prototype."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from .migration import TargetNotEmptyError, migrate_core
from .migration.coverage import generate_coverage_report
from .source import connect_couchdb
from .target import (
    PostgreSQLConfig,
    check_connection as check_postgresql,
    initialize_schema as initialize_postgresql_schema,
    recreate_database as recreate_postgresql,
)
from .target.schema import EXPECTED_TABLES

SOURCE_CLASSES = {
    "SystemeEndiguement": "fr.sirs.core.model.SystemeEndiguement",
    "Digue": "fr.sirs.core.model.Digue",
    "TronconDigue": "fr.sirs.core.model.TronconDigue",
    "Desordre": "fr.sirs.core.model.Desordre",
}

CONFIG_ENV_PATH = Path(__file__).resolve().parent.parent / "config.env"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sirs-postgre",
        description="Prépare la migration autonome de SIRS vers PostgreSQL/PostGIS.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check", description="Vérifie les connexions sans modifier les bases."
    )
    direction = check.add_mutually_exclusive_group()
    direction.add_argument("--source-only", action="store_true")
    direction.add_argument("--target-only", action="store_true")
    check.add_argument("--profile", choices=("local", "secure"))
    check.add_argument("--source-database")
    subparsers.add_parser(
        "recreate",
        description="Supprime et recrée la base PostgreSQL cible avec PostGIS.",
    )
    subparsers.add_parser(
        "init-schema",
        description="Crée le premier noyau métier PostgreSQL/PostGIS.",
    )
    subparsers.add_parser(
        "migrate-core",
        description="Migre le noyau CouchDB vers PostgreSQL/PostGIS.",
    )
    diagnose = subparsers.add_parser(
        "diagnose",
        description="Génère audits/bilan.md depuis le contenu CouchDB réel.",
    )
    diagnose.add_argument("--profile", choices=("local", "secure"))
    diagnose.add_argument("--source-database")
    return parser


def _check_source(profile: str | None, database: str | None) -> None:
    client = connect_couchdb(profile=profile, database=database)
    try:
        status = client.check_connection()
    except Exception as exc:
        error = client.config.redact_secrets(str(exc))
        if not client.config.authentication_configured:
            raise RuntimeError(
                f"{error} ; authentification CouchDB non configurée "
                "(aucun utilisateur/mot de passe fourni)"
            ) from exc
        raise RuntimeError(error) from exc
    version = f", CouchDB {status.couchdb_version}" if status.couchdb_version else ""
    total = f", {status.document_count} documents" if status.document_count is not None else ""
    print(f"[OK] Source CouchDB : {status.database}{version}{total}")
    if client.config.authentication_configured:
        print("[INFO] CouchDB : authentification configurée")
    else:
        print("[INFO] CouchDB : authentification non configurée ; connexion réussie")
    for label, class_name in SOURCE_CLASSES.items():
        print(f"     {label}: {client.count_by_class(class_name)}")


def _check_target() -> None:
    config = PostgreSQLConfig.from_env()
    try:
        status = check_postgresql(config)
    except Exception as exc:
        error = config.redact_secrets(str(exc))
        if not config.password_configured:
            raise RuntimeError(
                f"{error} ; aucun mot de passe PostgreSQL fourni ; "
                "vérifiez l'authentification locale"
            ) from exc
        raise RuntimeError(error) from exc
    print(
        f"[OK] Cible PostgreSQL : {status.database} avec {status.user} "
        f"(serveur {status.server_version})"
    )
    if config.password_configured:
        print("[INFO] PostgreSQL : authentification configurée")
    else:
        print(
            "[INFO] PostgreSQL : mot de passe non fourni ; "
            "authentification locale réussie"
        )
    postgis = status.postgis_version or "non installée dans cette base"
    print(f"     PostGIS: {postgis}")
    pgcrypto = status.pgcrypto_version or "non installée dans cette base"
    print(f"     pgcrypto: {pgcrypto}")
    print("Tables métier :")
    for table in EXPECTED_TABLES:
        presence = "présente" if table in status.schema_tables else "absente"
        print(f"  {table}: {presence}")


def run_check(args: argparse.Namespace) -> int:
    failures: list[str] = []
    if not args.target_only:
        try:
            _check_source(args.profile, args.source_database)
        except Exception as exc:
            failures.append(f"Source CouchDB : {exc}")
            print(f"[ERREUR] Source CouchDB : {exc}")
    if not args.source_only:
        try:
            _check_target()
        except Exception as exc:
            failures.append(f"Cible PostgreSQL : {exc}")
            print(f"[ERREUR] Cible PostgreSQL : {exc}")
    return 1 if failures else 0


def run_recreate() -> int:
    try:
        status = recreate_postgresql(PostgreSQLConfig.from_env())
    except Exception as exc:
        print(f"[ERREUR] Recréation PostgreSQL : {exc}")
        return 1
    if status.terminated_connections:
        print(f"[OK] Connexions fermées : {status.terminated_connections}")
    print(f"[OK] Base supprimée : {status.database}")
    print(f"[OK] Base créée : {status.database}")
    print(f"[OK] PostGIS activée : {status.postgis_version}")
    print(f"[OK] pgcrypto activée : {status.pgcrypto_version}")
    print("[OK] Base cible prête")
    return 0


def run_init_schema() -> int:
    config = PostgreSQLConfig.from_env()
    try:
        status = initialize_postgresql_schema(config)
    except Exception as exc:
        print(f"[ERREUR] Initialisation du schéma : {config.redact_secrets(str(exc))}")
        return 1
    print(f"[OK] Schéma métier initialisé dans : {config.target_database}")
    print(f"[OK] PostGIS disponible : {status.postgis_version}")
    print(f"[OK] pgcrypto disponible : {status.pgcrypto_version}")
    for table in status.tables:
        print(f"[OK] Table présente : {table}")
    return 0


def run_migrate_core() -> int:
    try:
        report = migrate_core()
    except TargetNotEmptyError:
        print("[ERREUR] La base cible contient déjà des données. Utiliser :")
        print("sirs-postgre recreate")
        print("sirs-postgre init-schema")
        print("sirs-postgre migrate-core")
        return 1
    except Exception as exc:
        print(f"[ERREUR] Migration du noyau : {exc}")
        return 1

    prepared = report.prepared
    geometries = prepared.desordre_geometry_counts
    print("RefCategorieDesordre :")
    print(f"  source: {len(prepared.categories_desordre)}")
    print(
        "  migrées: "
        f"{report.validation.table_counts['ref_categories_desordre']}"
    )
    print("RefTypeDesordre :")
    print(f"  source: {len(prepared.types_desordre)}")
    print(f"  migrés: {report.validation.table_counts['ref_types_desordre']}")
    print("RefUrgence :")
    print(f"  source: {len(prepared.urgences)}")
    print(f"  migrées: {report.validation.table_counts['ref_urgences']}")
    print("SystemeEndiguement :")
    print(f"  source: {len(prepared.systemes)}")
    print(f"  migrés: {report.validation.table_counts['systemes']}")
    print("Digue :")
    print(f"  source: {len(prepared.digues)}")
    print(f"  migrées: {report.validation.table_counts['digues']}")
    print(f"  sans système d'endiguement: {prepared.digues_without_system}")
    print("TronconDigue :")
    print(f"  source: {len(prepared.troncons)}")
    print(f"  migrés: {report.validation.table_counts['troncons']}")
    print(f"  géométries: {len(prepared.troncons)}")
    print("Desordre :")
    print(f"  source: {len(prepared.desordres)}")
    print(f"  migrés: {report.validation.table_counts['desordres']}")
    print(f"  points: {geometries['point']}")
    print(f"  lignes: {geometries['linestring']}")
    print(f"  sans géométrie: {geometries['null']}")
    print(
        "  avec type de désordre: "
        f"{sum(row.type_desordre_id is not None for row in prepared.desordres)}"
    )
    print(
        "  geometry source présente/absente: "
        f"{prepared.desordre_source_geometry_present}/"
        f"{prepared.desordre_source_geometry_absent}"
    )
    print("link_desordres_troncons :")
    print(f"  créés: {report.validation.table_counts['link_desordres_troncons']}")
    print("Observation :")
    print(f"  migrées: {report.validation.table_counts['observations']}")
    print(f"  valid=false: {sum(not row.valid for row in prepared.observations)}")
    print(
        "  avec urgence: "
        f"{sum(row.urgence_id is not None for row in prepared.observations)}"
    )
    print("Photo :")
    print(f"  migrées: {report.validation.table_counts['photos']}")
    print(f"  valid=false: {sum(not row.valid for row in prepared.photos)}")
    print(f"  observations synthétiques: {prepared.synthetic_observations}")
    print(f"  photos directes tronçons: {prepared.direct_troncon_photos}")
    print(f"  photos directes autres objets: {prepared.direct_other_photos}")
    print("Ouvrages :")
    for table, rows in prepared.ouvrages.rows.items():
        print(f"  {table}: {len(rows)}")
    print(f"  migrés: {prepared.ouvrages.migrated_count}")
    print(f"  différés: {prepared.ouvrages.deferred_count}")
    print(
        "  valid=false: "
        f"{sum(prepared.ouvrages.invalid_counts.values())}"
    )
    print("Aménagements hydrauliques :")
    print(f"  source: {len(prepared.amenagements.amenagements)}")
    print(
        "  migrés: "
        f"{report.validation.table_counts['amenagements_hydrauliques']}"
    )
    print(
        "  relations explicites aux tronçons: "
        f"{report.validation.table_counts['link_amenagements_troncons']}"
    )
    print(
        "  ouvrages associés réintégrés: "
        f"{len(prepared.amenagements.associated_ouvrages)}"
    )
    print(f"  chemins différés: {prepared.amenagements.deferred_chemins}")
    print(
        "  prestations spécifiques différées: "
        f"{prepared.amenagements.deferred_prestations}"
    )
    vegetation_geometries = prepared.vegetation.geometry_counts
    print("Végétation :")
    print(
        "  plans de gestion: "
        f"{report.validation.table_counts['plans_gestion_vegetation']}"
    )
    print(
        "  parcelles de gestion: "
        f"{report.validation.table_counts['parcelles_gestion_vegetation']}"
    )
    print(
        "  relations explicites aux tronçons: "
        f"{report.validation.table_counts['link_parcelles_gestion_troncons']}"
    )
    print(f"  objets: {report.validation.table_counts['vegetation']}")
    print(f"  points: {vegetation_geometries['point']}")
    print(f"  lignes: {vegetation_geometries['linestring']}")
    print(f"  polygones: {vegetation_geometries['polygon']}")
    print(f"  sans géométrie: {vegetation_geometries['null']}")
    print(
        "  revue manuelle: "
        f"{prepared.vegetation.method_counts.get('MANUAL_REVIEW', 0)}"
    )
    print(f"  traitements différés: {prepared.vegetation.deferred_treatments}")
    print(
        "  planifications différées: "
        f"{prepared.vegetation.deferred_planifications}"
    )
    print("Warnings :")
    if prepared.warnings:
        for warning in prepared.warnings:
            print(f"  - {warning}")
    else:
        print("  aucun")
    try:
        coverage = generate_coverage_report(connect_couchdb())
    except Exception as exc:
        print(f"[ERREUR] Migration appliquée mais diagnostic incomplet : {exc}")
        return 1
    print(f"Diagnostic : {coverage.path}")
    print("Résultat final :")
    print("[OK] Migration du noyau et diagnostic terminés")
    return 0


def run_diagnose(args: argparse.Namespace) -> int:
    try:
        result = generate_coverage_report(
            connect_couchdb(
                profile=args.profile,
                database=args.source_database,
            )
        )
    except Exception as exc:
        print(f"[ERREUR] Diagnostic de couverture : {exc}")
        return 1
    print(f"[OK] Bilan généré : {result.path}")
    print(f"Classes CouchDB : {result.total_classes}")
    print(f"Documents non migrés : {result.non_migrated_documents}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(dotenv_path=CONFIG_ENV_PATH, override=False)
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return run_check(args)
    if args.command == "recreate":
        return run_recreate()
    if args.command == "init-schema":
        return run_init_schema()
    if args.command == "migrate-core":
        return run_migrate_core()
    if args.command == "diagnose":
        return run_diagnose(args)
    raise AssertionError(f"Commande inconnue : {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
