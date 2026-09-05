"""Accès PostgreSQL du prototype web, sans état ni secret côté navigateur."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


CONFIG_ENV_PATH = Path(__file__).resolve().parents[3] / "config.env"


class WebDatabaseError(RuntimeError):
    """Erreur de lecture de la base présentable par l'API sans secret."""


class WebDatabaseConfigurationError(ValueError):
    """Configuration PostgreSQL absente ou incohérente côté webapp."""


class WebDatabaseSchemaError(RuntimeError):
    """Schéma PostgreSQL incomplet pour les sessions webapp."""


@dataclass(frozen=True)
class PostgreSQLConfig:
    """Configuration PostgreSQL autonome du backend web.

    DATABASE_URL reste prioritaire. Les variables SIRS_POSTGRE_* historiques
    sont conservées pour les déploiements qui ne fournissent pas de DSN.
    """

    dsn: str | None = None
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "digues_app"
    user: str = "postgres"
    password: str | None = None
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "PostgreSQLConfig":
        config = cls(
            dsn=os.getenv("DATABASE_URL") or None,
            host=os.getenv("SIRS_POSTGRE_HOST", "127.0.0.1"),
            port=int(os.getenv("SIRS_POSTGRE_PORT", "5432")),
            database=os.getenv("SIRS_POSTGRE_DATABASE", "digues_app"),
            user=os.getenv("SIRS_POSTGRE_USER", "postgres"),
            password=os.getenv("SIRS_POSTGRE_PASSWORD") or None,
            connect_timeout=int(os.getenv("SIRS_POSTGRE_CONNECT_TIMEOUT", "10")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.dsn and (not self.host or not self.database or not self.user):
            raise WebDatabaseConfigurationError(
                "Hôte, base et utilisateur PostgreSQL sont obligatoires"
            )
        if not self.dsn and not 1 <= self.port <= 65_535:
            raise WebDatabaseConfigurationError("Le port PostgreSQL est invalide")
        if self.connect_timeout <= 0:
            raise WebDatabaseConfigurationError(
                "Le délai de connexion PostgreSQL doit être positif"
            )

    def connect_kwargs(self, *, autocommit: bool = True) -> dict[str, Any]:
        common: dict[str, Any] = {
            "connect_timeout": self.connect_timeout,
            "autocommit": autocommit,
        }
        if self.dsn:
            return {"conninfo": self.dsn, **common}
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            **common,
        }

    @property
    def safe_location(self) -> str:
        if self.dsn:
            return "DSN fourni par DATABASE_URL"
        return f"{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class PostgreSQLExtensionStatus:
    postgis_version: str
    postgis_schema: str
    pgcrypto_version: str
    pgcrypto_schema: str


def quote_identifier(identifier: str) -> str:
    """Protège un identifiant PostgreSQL utilisé dans le search_path."""

    if not identifier or "\x00" in identifier:
        raise ValueError("Identifiant PostgreSQL invalide")
    return '"' + identifier.replace('"', '""') + '"'


def extension_search_path(*schemas: str | None) -> str:
    """Construit le search_path de session avec public et les extensions."""

    selected = ["pg_catalog", "public"]
    for schema in schemas:
        if schema is None or schema in selected:
            continue
        selected.append(schema)
    return ", ".join(
        schema if schema in {"pg_catalog", "public"} else quote_identifier(schema)
        for schema in selected
    )


def read_extension_status(cursor: Any) -> PostgreSQLExtensionStatus:
    """Détecte dynamiquement les schémas d'installation PostGIS et pgcrypto."""

    cursor.execute(
        """
        SELECT e.extname, e.extversion, n.nspname
        FROM pg_extension AS e
        JOIN pg_namespace AS n ON n.oid = e.extnamespace
        WHERE e.extname = ANY(%s)
        """,
        (["postgis", "pgcrypto"],),
    )
    extensions = {
        str(name): (str(version), str(schema))
        for name, version, schema in cursor.fetchall()
    }
    missing = [name for name in ("postgis", "pgcrypto") if name not in extensions]
    if missing:
        raise WebDatabaseSchemaError(
            "Extensions PostgreSQL requises absentes : " + ", ".join(missing)
        )
    postgis_version, postgis_schema = extensions["postgis"]
    pgcrypto_version, pgcrypto_schema = extensions["pgcrypto"]
    return PostgreSQLExtensionStatus(
        postgis_version=postgis_version,
        postgis_schema=postgis_schema,
        pgcrypto_version=pgcrypto_version,
        pgcrypto_schema=pgcrypto_schema,
    )


def configure_extension_search_path(cursor: Any) -> PostgreSQLExtensionStatus:
    """Configure la session courante pour résoudre PostGIS et pgcrypto."""

    status = read_extension_status(cursor)
    cursor.execute(
        "SELECT set_config('search_path', %s, false)",
        (extension_search_path(status.postgis_schema, status.pgcrypto_schema),),
    )
    return status


def _connection(*, read_only: bool) -> Iterator[Any]:
    """Ouvre une connexion courte avec le niveau d'accès demandé."""

    config: PostgreSQLConfig | None = None
    try:
        load_dotenv(CONFIG_ENV_PATH, override=False)
        config = PostgreSQLConfig.from_env()
        import psycopg

        options = "-c default_transaction_read_only=on" if read_only else None
        kwargs = config.connect_kwargs(autocommit=True)
        if options:
            kwargs["options"] = options
        connection = psycopg.connect(**kwargs)
        try:
            with connection.cursor() as cursor:
                configure_extension_search_path(cursor)
        except Exception:
            connection.close()
            raise
    except Exception as exc:
        location = config.safe_location if config else "configuration cible"
        raise WebDatabaseError(
            f"Base PostgreSQL indisponible ({location})."
        ) from exc

    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def open_read_connection() -> Iterator[Any]:
    """Connexion réutilisable par les services serveur en lecture seule."""

    yield from _connection(read_only=True)


def get_connection() -> Iterator[Any]:
    """Connexion des endpoints strictement en lecture seule."""

    with open_read_connection() as connection:
        yield connection


def get_write_connection() -> Iterator[Any]:
    """Connexion d'écriture réservée aux mutations contrôlées par PostGIS."""

    yield from _connection(read_only=False)
