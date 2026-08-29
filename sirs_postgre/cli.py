"""Interface en ligne de commande du prototype."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

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
    for table in status.tables:
        print(f"[OK] Table présente : {table}")
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
    raise AssertionError(f"Commande inconnue : {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
