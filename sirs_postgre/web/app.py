"""Application FastAPI du prototype cartographique SIRS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import WebDatabaseError, get_connection, get_write_connection
from .models import (
    DesordreCreate,
    DigueCreate,
    LineEndpoints,
    LineStringGeometryUpdate,
    PointDesordreUpdate,
    PointReperageUpdate,
    SystemeEndiguementCreate,
    TronconCreate,
)
from .queries import (
    DesordreCreationError,
    DesordreNotFoundError,
    HeritageCreationError,
    LineDesordreNotFoundError,
    LineDesordreUpdateError,
    ObservationNotFoundError,
    PointDesordreNotFoundError,
    PointReperageUnavailableError,
    PointReperageUpdateError,
    PointDesordreUpdateError,
    create_digue,
    create_desordre,
    create_systeme_endiguement,
    create_troncon,
    fetch_desordres,
    fetch_desordre,
    fetch_desordre_observations,
    fetch_observation,
    fetch_systemes_endiguement,
    fetch_troncon_options,
    fetch_troncon_reperage_options,
    fetch_types_desordre,
    fetch_troncons,
    update_line_desordre_geometry,
    update_line_desordre_endpoints,
    update_point_desordre,
    update_point_reperage,
)


FRONTEND_DIRECTORY = Path(__file__).resolve().parents[2] / "web"


class GeoJSONResponse(JSONResponse):
    media_type = "application/geo+json"


def web_show_uuid() -> bool:
    """Indique si les identifiants techniques doivent être affichés."""

    return os.getenv("SIRS_WEB_SHOW_UUID", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def create_app() -> FastAPI:
    application = FastAPI(
        title="SIRS PostgreSQL — carte expérimentale",
        description="Prototype local d'édition limitée des désordres cartographiques.",
        version="0.1.0",
    )
    application.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIRECTORY),
        name="static",
    )

    @application.exception_handler(WebDatabaseError)
    async def database_error_handler(
        _request: Request, exc: WebDatabaseError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(PointDesordreNotFoundError)
    async def point_not_found_handler(
        _request: Request, exc: PointDesordreNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(PointDesordreUpdateError)
    async def point_update_error_handler(
        _request: Request, exc: PointDesordreUpdateError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(PointReperageUnavailableError)
    async def reperage_unavailable_handler(
        _request: Request, exc: PointReperageUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(PointReperageUpdateError)
    async def reperage_update_error_handler(
        _request: Request, exc: PointReperageUpdateError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(DesordreNotFoundError)
    async def desordre_not_found_handler(
        _request: Request, exc: DesordreNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(LineDesordreNotFoundError)
    async def line_not_found_handler(
        _request: Request, exc: LineDesordreNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(LineDesordreUpdateError)
    async def line_update_error_handler(
        _request: Request, exc: LineDesordreUpdateError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(ObservationNotFoundError)
    async def observation_not_found_handler(
        _request: Request, exc: ObservationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(HeritageCreationError)
    async def heritage_creation_error_handler(
        _request: Request, exc: HeritageCreationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(DesordreCreationError)
    async def desordre_creation_error_handler(
        _request: Request, exc: DesordreCreationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIRECTORY / "index.html")

    @application.get("/api/config")
    def frontend_config() -> dict[str, bool]:
        return {"show_uuid": web_show_uuid()}

    @application.get("/api/troncons", response_class=GeoJSONResponse)
    def troncons(connection: Any = Depends(get_connection)) -> dict[str, Any]:
        return fetch_troncons(connection)

    @application.get("/api/systemes-endiguement")
    def systemes_endiguement(
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_systemes_endiguement(connection)

    @application.get("/api/referentiels/types-desordre")
    def types_desordre(
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_types_desordre(connection)

    @application.get("/api/troncons/options")
    def troncon_options(
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_troncon_options(connection)

    @application.get("/api/troncons/{troncon_id}/reperage-options")
    def troncon_reperage_options(
        troncon_id: UUID,
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_troncon_reperage_options(connection, troncon_id)

    @application.post("/api/systemes-endiguement", status_code=201)
    def create_systeme(
        creation: SystemeEndiguementCreate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return create_systeme_endiguement(connection, creation)

    @application.post("/api/digues", status_code=201)
    def create_new_digue(
        creation: DigueCreate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return create_digue(connection, creation)

    @application.post(
        "/api/troncons", status_code=201, response_class=GeoJSONResponse
    )
    def create_new_troncon(
        creation: TronconCreate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return create_troncon(connection, creation)

    @application.get("/api/desordres", response_class=GeoJSONResponse)
    def desordres(connection: Any = Depends(get_connection)) -> dict[str, Any]:
        return fetch_desordres(connection)

    @application.post(
        "/api/desordres", status_code=201, response_class=GeoJSONResponse
    )
    def create_new_desordre(
        creation: DesordreCreate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return create_desordre(connection, creation)

    @application.get("/api/desordres/{desordre_id}/observations")
    def desordre_observations(
        desordre_id: UUID,
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_desordre_observations(connection, desordre_id)

    @application.get("/api/observations/{observation_id}")
    def observation(
        observation_id: UUID,
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_observation(connection, observation_id)

    @application.get(
        "/api/desordres/{desordre_id}",
        response_class=GeoJSONResponse,
    )
    def desordre_detail(
        desordre_id: UUID,
        connection: Any = Depends(get_connection),
    ) -> dict[str, Any]:
        return fetch_desordre(connection, desordre_id)

    @application.put(
        "/api/desordres/{desordre_id}",
        response_class=GeoJSONResponse,
    )
    def edit_point_desordre(
        desordre_id: UUID,
        update: PointDesordreUpdate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return update_point_desordre(connection, desordre_id, update)

    @application.put(
        "/api/desordres/{desordre_id}/reperage",
        response_class=GeoJSONResponse,
    )
    def edit_point_reperage(
        desordre_id: UUID,
        update: PointReperageUpdate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return update_point_reperage(connection, desordre_id, update)

    @application.put(
        "/api/desordres/{desordre_id}/geometry",
        response_class=GeoJSONResponse,
    )
    def edit_line_desordre_geometry(
        desordre_id: UUID,
        update: LineStringGeometryUpdate,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return update_line_desordre_geometry(connection, desordre_id, update)

    @application.put(
        "/api/desordres/{desordre_id}/endpoints",
        response_class=GeoJSONResponse,
    )
    def edit_line_desordre_endpoints(
        desordre_id: UUID,
        endpoints: LineEndpoints,
        connection: Any = Depends(get_write_connection),
    ) -> dict[str, Any]:
        return update_line_desordre_endpoints(connection, desordre_id, endpoints)

    return application


app = create_app()
