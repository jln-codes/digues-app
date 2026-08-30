"""Accès en lecture aux sources SIRS."""

from .couchdb import (
    CouchDBClient,
    CouchDBConfig,
    CouchDBDatabaseInfo,
    CouchDBError,
    CouchDBSourceStatus,
    DocumentNotFound,
    connect_couchdb,
)

__all__ = [
    "CouchDBClient",
    "CouchDBConfig",
    "CouchDBDatabaseInfo",
    "CouchDBError",
    "CouchDBSourceStatus",
    "DocumentNotFound",
    "connect_couchdb",
]
