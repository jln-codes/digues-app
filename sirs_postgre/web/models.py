"""Contrats d'entrée minimaux du prototype web."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator


class PointDesordreUpdate(BaseModel):
    """Modification partielle d'un désordre Point."""

    model_config = ConfigDict(extra="forbid")

    designation: str | None = None
    type_desordre_id: str | None = None
    commentaire: str | None = None
    coord_x_3950: FiniteFloat | None = None
    coord_y_3950: FiniteFloat | None = None
    longitude_4326: FiniteFloat | None = None
    latitude_4326: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_coordinate_authority(self) -> "PointDesordreUpdate":
        supplied = self.model_fields_set
        xy_fields = {"coord_x_3950", "coord_y_3950"}
        lonlat_fields = {"longitude_4326", "latitude_4326"}
        xy_supplied = bool(supplied & xy_fields)
        lonlat_supplied = bool(supplied & lonlat_fields)

        if not supplied:
            raise ValueError("Au moins un champ doit être fourni.")
        if xy_supplied and not xy_fields <= supplied:
            raise ValueError("X et Y doivent être fournis ensemble.")
        if lonlat_supplied and not lonlat_fields <= supplied:
            raise ValueError("Longitude et latitude doivent être fournies ensemble.")
        if xy_supplied and (
            self.coord_x_3950 is None or self.coord_y_3950 is None
        ):
            raise ValueError("X et Y ne peuvent pas être nuls.")
        if lonlat_supplied and (
            self.longitude_4326 is None or self.latitude_4326 is None
        ):
            raise ValueError("Longitude et latitude ne peuvent pas être nulles.")
        if xy_supplied and lonlat_supplied:
            raise ValueError(
                "Une seule famille de localisation peut être modifiée par opération."
            )
        return self


class PointReperageUpdate(BaseModel):
    """Famille autoritaire de bornage pour un désordre Point."""

    model_config = ConfigDict(extra="forbid")

    borne_debut_id: UUID
    distance_debut_m: FiniteFloat
    position_debut_relative: Literal[
        "AVANT_BORNE", "SUR_BORNE", "APRES_BORNE"
    ]

    @model_validator(mode="after")
    def validate_distance(self) -> "PointReperageUpdate":
        if self.distance_debut_m < 0:
            raise ValueError("La distance doit être positive ou nulle.")
        if (
            self.position_debut_relative == "SUR_BORNE"
            and self.distance_debut_m != 0
        ):
            raise ValueError("La distance doit être nulle pour une position sur borne.")
        return self


class LineStringGeometry(BaseModel):
    """Géométrie GeoJSON linéaire reçue en EPSG:4326."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["LineString"]
    coordinates: list[tuple[FiniteFloat, FiniteFloat]]

    @model_validator(mode="after")
    def validate_vertices(self) -> "LineStringGeometry":
        if len(self.coordinates) < 2:
            raise ValueError("Une LineString exige au moins deux sommets.")
        for longitude, latitude in self.coordinates:
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError(
                    "Les sommets doivent être des longitude/latitude EPSG:4326 valides."
                )
        return self


class LineStringGeometryUpdate(BaseModel):
    """Modification exclusivement géométrique d'un désordre LineString."""

    model_config = ConfigDict(extra="forbid")

    geometry: LineStringGeometry
