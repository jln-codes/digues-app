"""Configuration et gestion de la cible PostgreSQL/PostGIS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import re
from typing import Any

from .schema import EXPECTED_TABLES, SCHEMA_DDL


PROTECTED_DATABASE_NAMES = frozenset({"postgres", "template0", "template1"})
SAFE_DATABASE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class PostgreSQLConfigurationError(ValueError):
    """La configuration PostgreSQL est absente ou incohérente."""


class PostgreSQLConnectionError(RuntimeError):
    """La connexion ou le diagnostic PostgreSQL a échoué."""


class PostgreSQLSchemaError(RuntimeError):
    """L'initialisation ou le contrôle du schéma cible a échoué."""


@dataclass(frozen=True)
class PostgreSQLConfig:
    dsn: str | None = None
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "sirs_postgre"
    user: str = "postgres"
    password: str | None = None
    connect_timeout: int = 10
    admin_database: str = "postgres"

    @classmethod
    def from_env(cls) -> "PostgreSQLConfig":
        config = cls(
            dsn=os.getenv("SIRS_POSTGRE_DSN") or None,
            host=os.getenv("SIRS_POSTGRE_HOST", "127.0.0.1"),
            port=int(os.getenv("SIRS_POSTGRE_PORT", "5432")),
            database=os.getenv("SIRS_POSTGRE_DATABASE", "sirs_postgre"),
            user=os.getenv("SIRS_POSTGRE_USER", "postgres"),
            password=os.getenv("SIRS_POSTGRE_PASSWORD") or None,
            connect_timeout=int(os.getenv("SIRS_POSTGRE_CONNECT_TIMEOUT", "10")),
            admin_database=os.getenv("SIRS_POSTGRE_ADMIN_DATABASE", "postgres"),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.admin_database:
            raise PostgreSQLConfigurationError(
                "La base d'administration PostgreSQL est obligatoire"
            )
        if not self.dsn and (not self.host or not self.database or not self.user):
            raise PostgreSQLConfigurationError(
                "Hôte, base et utilisateur PostgreSQL sont obligatoires"
            )
        if not self.dsn and not 1 <= self.port <= 65_535:
            raise PostgreSQLConfigurationError("Le port PostgreSQL est invalide")
        if self.connect_timeout <= 0:
            raise PostgreSQLConfigurationError(
                "Le délai de connexion PostgreSQL doit être positif"
            )

    def connect_kwargs(
        self,
        *,
        database: str | None = None,
        autocommit: bool = True,
    ) -> dict[str, Any]:
        common: dict[str, Any] = {
            "connect_timeout": self.connect_timeout,
            "autocommit": autocommit,
        }
        if self.dsn:
            connection = {"conninfo": self.dsn, **common}
            if database is not None:
                connection["dbname"] = database
            return connection
        return {
            "host": self.host,
            "port": self.port,
            "dbname": database if database is not None else self.database,
            "user": self.user,
            "password": self.password,
            **common,
        }

    def admin_connect_kwargs(self) -> dict[str, Any]:
        """Construit une connexion autocommit vers la base d'administration."""

        return self.connect_kwargs(database=self.admin_database)

    @property
    def target_database(self) -> str:
        if not self.dsn:
            return self.database
        try:
            from psycopg.conninfo import conninfo_to_dict

            return str(conninfo_to_dict(self.dsn).get("dbname") or self.database)
        except Exception as exc:
            raise PostgreSQLConfigurationError(
                "Impossible de déterminer la base cible depuis SIRS_POSTGRE_DSN"
            ) from exc

    @property
    def password_configured(self) -> bool:
        """Indique si un mot de passe est fourni, sans jamais le retourner."""

        if self.password:
            return True
        if not self.dsn:
            return False
        try:
            from psycopg.conninfo import conninfo_to_dict

            return bool(conninfo_to_dict(self.dsn).get("password"))
        except Exception:
            return False

    def redact_secrets(self, message: str) -> str:
        """Masque le DSN et le mot de passe dans une erreur externe."""

        redacted = message
        if self.password:
            redacted = redacted.replace(self.password, "***")
        if self.dsn:
            redacted = redacted.replace(self.dsn, "DSN masqué")
            try:
                from psycopg.conninfo import conninfo_to_dict

                dsn_password = conninfo_to_dict(self.dsn).get("password")
                if dsn_password:
                    redacted = redacted.replace(str(dsn_password), "***")
            except Exception:
                pass
        return redacted

    @property
    def safe_location(self) -> str:
        if self.dsn:
            return "DSN fourni par SIRS_POSTGRE_DSN"
        return f"{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class PostgreSQLStatus:
    database: str
    user: str
    server_version: str
    postgis_version: str | None
    schema_tables: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PostgreSQLRecreateStatus:
    database: str
    terminated_connections: int
    postgis_version: str


@dataclass(frozen=True)
class PostgreSQLSchemaStatus:
    tables: tuple[str, ...]
    postgis_version: str


def validate_recreatable_database_name(
    database: str, *, admin_database: str | None = None
) -> str:
    """Refuse tout nom ambigu ou sensible avant une opération destructive."""

    if not database or database != database.strip():
        raise PostgreSQLConfigurationError("Le nom de la base cible est vide ou ambigu")
    if len(database.encode("utf-8")) > 63 or not SAFE_DATABASE_NAME.fullmatch(database):
        raise PostgreSQLConfigurationError(
            "Le nom de la base cible doit être un identifiant PostgreSQL simple"
        )
    normalized = database.casefold()
    protected = set(PROTECTED_DATABASE_NAMES)
    if admin_database:
        protected.add(admin_database.casefold())
    if normalized in protected:
        raise PostgreSQLConfigurationError(
            f"Suppression refusée pour la base protégée : {database}"
        )
    return database


def _default_connector() -> Callable[..., Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise PostgreSQLConnectionError(
            "Le pilote psycopg n'est pas installé ; exécutez `python -m pip install -e .`"
        ) from exc
    return psycopg.connect


def check_connection(
    config: PostgreSQLConfig | None = None,
    *,
    connector: Callable[..., Any] | None = None,
) -> PostgreSQLStatus:
    """Exécute des SELECT de diagnostic, sans créer ni modifier aucun objet."""

    selected = config or PostgreSQLConfig.from_env()
    connect = connector or _default_connector()
    try:
        with connect(**selected.connect_kwargs()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user, "
                    "current_setting('server_version'), "
                    "(SELECT extversion FROM pg_extension WHERE extname = 'postgis')"
                )
                row = cursor.fetchone()
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_name = ANY(%s)",
                    ("public", list(EXPECTED_TABLES)),
                )
                schema_tables = frozenset(str(result[0]) for result in cursor.fetchall())
    except Exception as exc:
        if isinstance(exc, PostgreSQLConnectionError):
            raise
        raise PostgreSQLConnectionError(
            f"Connexion PostgreSQL impossible ({selected.safe_location}) : {exc}"
        ) from exc

    if not row:
        raise PostgreSQLConnectionError("Le diagnostic PostgreSQL n'a retourné aucune ligne")
    return PostgreSQLStatus(
        database=str(row[0]),
        user=str(row[1]),
        server_version=str(row[2]),
        postgis_version=str(row[3]) if row[3] is not None else None,
        schema_tables=schema_tables,
    )


def initialize_schema(
    config: PostgreSQLConfig | None = None,
    *,
    connector: Callable[..., Any] | None = None,
) -> PostgreSQLSchemaStatus:
    """Crée transactionnellement le noyau métier dans le schéma public."""

    selected = config or PostgreSQLConfig.from_env()
    connect = connector or _default_connector()
    try:
        with connect(**selected.connect_kwargs(autocommit=False)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'postgis'"
                )
                postgis_row = cursor.fetchone()
                if not postgis_row or postgis_row[0] is None:
                    raise PostgreSQLSchemaError(
                        "PostGIS doit être activée avant l'initialisation du schéma"
                    )
                for statement in SCHEMA_DDL:
                    cursor.execute(statement)
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_name = ANY(%s)",
                    ("public", list(EXPECTED_TABLES)),
                )
                present_tables = frozenset(
                    str(result[0]) for result in cursor.fetchall()
                )
                missing_tables = [
                    table for table in EXPECTED_TABLES if table not in present_tables
                ]
                if missing_tables:
                    raise PostgreSQLSchemaError(
                        "Tables non créées : " + ", ".join(missing_tables)
                    )
    except Exception as exc:
        if isinstance(exc, PostgreSQLSchemaError):
            raise
        error = selected.redact_secrets(str(exc))
        raise PostgreSQLSchemaError(
            f"Initialisation du schéma impossible ({selected.safe_location}) : {error}"
        ) from exc

    return PostgreSQLSchemaStatus(
        tables=EXPECTED_TABLES,
        postgis_version=str(postgis_row[0]),
    )


def recreate_database(
    config: PostgreSQLConfig | None = None,
    *,
    connector: Callable[..., Any] | None = None,
) -> PostgreSQLRecreateStatus:
    """Recrée uniquement la base cible et y active PostGIS."""

    selected = config or PostgreSQLConfig.from_env()
    selected.validate()
    target_database = validate_recreatable_database_name(
        selected.target_database,
        admin_database=selected.admin_database,
    )
    connect = connector or _default_connector()

    try:
        from psycopg import sql

        with connect(**selected.admin_connect_kwargs()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (target_database,),
                )
                terminated_connections = sum(
                    result[0] is True for result in cursor.fetchall()
                )
                cursor.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(target_database)
                    )
                )
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_database))
                )
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = %s)",
                    (target_database,),
                )
                database_exists = cursor.fetchone()

        if not database_exists or database_exists[0] is not True:
            raise PostgreSQLConnectionError(
                f"La base créée n'est pas visible : {target_database}"
            )

        with connect(
            **selected.connect_kwargs(database=target_database)
        ) as target_connection:
            with target_connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                cursor.execute(
                    "SELECT current_database(), "
                    "(SELECT extversion FROM pg_extension WHERE extname = 'postgis')"
                )
                target_status = cursor.fetchone()
    except Exception as exc:
        if isinstance(exc, (PostgreSQLConfigurationError, PostgreSQLConnectionError)):
            raise
        raise PostgreSQLConnectionError(
            f"Recréation PostgreSQL impossible ({target_database}) : {exc}"
        ) from exc

    if not target_status or str(target_status[0]) != target_database:
        raise PostgreSQLConnectionError(
            f"La connexion à la base recréée a échoué : {target_database}"
        )
    if target_status[1] is None:
        raise PostgreSQLConnectionError(
            f"PostGIS n'est pas disponible dans la base : {target_database}"
        )
    return PostgreSQLRecreateStatus(
        database=target_database,
        terminated_connections=terminated_connections,
        postgis_version=str(target_status[1]),
    )
