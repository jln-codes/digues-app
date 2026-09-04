"""Accès PostgreSQL du prototype web, sans état ni secret côté navigateur."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from digues_app.target import PostgreSQLConfig, configure_extension_search_path


CONFIG_ENV_PATH = Path(__file__).resolve().parents[3] / "config.env"


class WebDatabaseError(RuntimeError):
    """Erreur de lecture de la base présentable par l'API sans secret."""


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
