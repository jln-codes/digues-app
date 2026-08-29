"""Client CouchDB autonome et limité aux lectures nécessaires à la migration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import os
from typing import Any
from urllib.parse import quote, urlparse

import requests

Document = dict[str, Any]


class CouchDBError(RuntimeError):
    """Une lecture CouchDB a échoué."""


class DocumentNotFound(CouchDBError):
    """Le document ou la pièce jointe demandé n'existe pas."""


class CouchDBConfigurationError(ValueError):
    """La configuration CouchDB est absente ou incohérente."""


@dataclass(frozen=True)
class CouchDBConfig:
    """Paramètres d'accès à une base CouchDB SIRS."""

    url: str = "http://127.0.0.1:5984"
    database: str = "cabbalr"
    username: str | None = None
    password: str | None = None
    timeout: float = 60.0
    profile: str = "local"

    @property
    def database_url(self) -> str:
        return f"{self.url.rstrip('/')}/{quote(self.database, safe='')}"

    @property
    def auth(self) -> tuple[str, str] | None:
        if not self.username:
            return None
        return self.username, self.password or ""

    @property
    def authentication_configured(self) -> bool:
        """Indique si la connexion HTTP utilise des credentials, sans les exposer."""

        return self.auth is not None

    def redact_secrets(self, message: str) -> str:
        """Masque les secrets qui pourraient apparaître dans une erreur externe."""

        if self.password:
            return message.replace(self.password, "***")
        return message

    @property
    def is_local(self) -> bool:
        host = (urlparse(self.url).hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "::1"}

    @classmethod
    def from_profile(
        cls,
        profile: str | None = None,
        *,
        database: str | None = None,
    ) -> "CouchDBConfig":
        selected = (profile or os.getenv("SIRS_PROFILE", "local")).lower()
        if selected not in {"local", "secure"}:
            raise CouchDBConfigurationError(
                "SIRS_PROFILE doit valoir 'local' ou 'secure'"
            )

        prefix = f"SIRS_{selected.upper()}_"
        default_url = "http://127.0.0.1:5984" if selected == "local" else ""
        default_database = "cabbalr" if selected == "local" else ""
        config = cls(
            url=os.getenv(f"{prefix}COUCHDB_URL", default_url),
            database=database or os.getenv(f"{prefix}DATABASE", default_database),
            username=os.getenv(f"{prefix}USERNAME") or None,
            password=os.getenv(f"{prefix}PASSWORD") or None,
            timeout=float(os.getenv(f"{prefix}TIMEOUT", "60")),
            profile=selected,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.url or not self.database:
            raise CouchDBConfigurationError(
                "L'URL CouchDB et le nom de base sont obligatoires"
            )
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CouchDBConfigurationError("L'URL CouchDB est invalide")
        if self.profile == "secure":
            if parsed.scheme != "https":
                raise CouchDBConfigurationError("Le profil secure exige HTTPS")
            if not self.username or not self.password:
                raise CouchDBConfigurationError(
                    "Le profil secure exige un nom d'utilisateur et un mot de passe"
                )
        if self.timeout <= 0:
            raise CouchDBConfigurationError("Le délai CouchDB doit être positif")


@dataclass(frozen=True)
class CouchDBSourceStatus:
    database: str
    couchdb_version: str | None
    document_count: int | None


class CouchDBClient:
    """Façade HTTP injectable, sans aucune opération d'écriture."""

    def __init__(
        self,
        config: CouchDBConfig,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()

    def _request(self, method: str, path: str = "", **kwargs: Any) -> requests.Response:
        url = self.config.database_url
        if path:
            url = f"{url}/{path.lstrip('/')}"
        try:
            response = self.session.request(
                method,
                url,
                auth=self.config.auth,
                timeout=self.config.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise CouchDBError(f"Connexion à CouchDB impossible : {exc}") from exc

        if response.status_code == 404:
            raise DocumentNotFound(path or self.config.database)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise CouchDBError(
                f"CouchDB a répondu HTTP {response.status_code} pour {path or '/'}"
            ) from exc
        return response

    def check_connection(self) -> CouchDBSourceStatus:
        data = self._request("GET").json()
        return CouchDBSourceStatus(
            database=str(data.get("db_name") or self.config.database),
            couchdb_version=(str(data["version"]) if data.get("version") else None),
            document_count=(int(data["doc_count"]) if data.get("doc_count") is not None else None),
        )

    def get(self, document_id: str) -> Document:
        return self._request("GET", quote(document_id, safe="")).json()

    def get_attachment(self, document_id: str, attachment_name: str) -> bytes:
        path = f"{quote(document_id, safe='')}/{quote(attachment_name, safe='')}"
        return self._request("GET", path).content

    def find(
        self,
        selector: Mapping[str, Any],
        *,
        limit: int = 200_000,
        fields: Iterable[str] | None = None,
    ) -> list[Document]:
        payload: dict[str, Any] = {"selector": dict(selector), "limit": limit}
        if fields is not None:
            payload["fields"] = list(fields)
        data = self._request("POST", "_find", json=payload).json()
        return list(data.get("docs", []))

    def find_by_class(
        self,
        class_name: str,
        *,
        limit: int = 200_000,
        fields: Iterable[str] | None = None,
    ) -> list[Document]:
        return self.find({"@class": class_name}, limit=limit, fields=fields)

    def count_by_class(self, class_name: str, *, limit: int = 200_000) -> int:
        return len(self.find_by_class(class_name, limit=limit, fields=("_id",)))

    def all_documents(self, *, batch_size: int = 1_000) -> list[Document]:
        documents: list[Document] = []
        params: dict[str, Any] = {"include_docs": "true", "limit": batch_size}
        while True:
            data = self._request("GET", "_all_docs", params=params).json()
            rows = data.get("rows", [])
            documents.extend(row["doc"] for row in rows if "doc" in row)
            if len(rows) < batch_size:
                return documents
            params["startkey"] = f'"{rows[-1]["key"]}"'
            params["skip"] = 1


def connect_couchdb(
    *,
    profile: str | None = None,
    database: str | None = None,
    session: requests.Session | None = None,
) -> CouchDBClient:
    """Construit un client CouchDB autonome à partir de l'environnement."""

    config = CouchDBConfig.from_profile(profile, database=database)
    return CouchDBClient(config, session=session)
