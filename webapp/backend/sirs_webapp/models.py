"""Contrats d'entrée minimaux du prototype web."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    field_validator,
    model_validator,
)


AI_MAX_MESSAGES = 20
AI_MAX_MESSAGE_CHARS = 8000
AI_MAX_CONVERSATION_CHARS = 40000


class AiChatMessage(BaseModel):
    """Message non privilégié accepté depuis le navigateur."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=AI_MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Le message est obligatoire.")
        return normalized


class AiChatRequest(BaseModel):
    """Historique court dont le dernier message doit venir de l'utilisateur."""

    model_config = ConfigDict(extra="forbid")

    messages: list[AiChatMessage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_trim_history(self) -> "AiChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("Le dernier message doit provenir de l’utilisateur.")

        recent = self.messages[-AI_MAX_MESSAGES:]
        retained: list[AiChatMessage] = []
        total_chars = 0
        for message in reversed(recent):
            next_total = total_chars + len(message.content)
            if next_total > AI_MAX_CONVERSATION_CHARS:
                break
            retained.append(message)
            total_chars = next_total
        self.messages = list(reversed(retained))
        return self


class AiExecutedQuery(BaseModel):
    """Métadonnée d'affichage d'une consultation IA réellement réussie."""

    model_config = ConfigDict(extra="forbid")

    sql: str


class AiChatResponse(BaseModel):
    """Réponse publique sans résultat SQL ni structure interne Mistral."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    executed_queries: list[AiExecutedQuery] = Field(default_factory=list)


class NamedObjectCreate(BaseModel):
    """Champs communs réellement persistés pour les objets patrimoniaux."""

    model_config = ConfigDict(extra="forbid")

    libelle: str
    valid: bool = True

    @field_validator("libelle")
    @classmethod
    def validate_libelle(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Le libellé est obligatoire.")
        return normalized


class SystemeEndiguementCreate(NamedObjectCreate):
    """Création d'un système d'endiguement opérationnel."""


class DigueCreate(NamedObjectCreate):
    """Création d'une digue avec un système parent actif."""

    systeme_endiguement_id: UUID


class PointDesordreUpdate(BaseModel):
    """Modification générale d'un désordre, plus coordonnées pour un Point."""

    model_config = ConfigDict(extra="forbid")

    designation: str | None = None
    type_desordre_id: str | None = None
    commentaire: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    valid: bool | None = None
    troncon_ids: list[UUID] | None = None
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
        if self.troncon_ids is not None and len(set(self.troncon_ids)) != len(
            self.troncon_ids
        ):
            raise ValueError("Un tronçon ne peut être associé qu'une fois.")
        return self


class PointReperageUpdate(BaseModel):
    """Famille autoritaire de bornage pour un désordre Point ou LineString."""

    model_config = ConfigDict(extra="forbid")

    borne_debut_id: UUID
    distance_debut_m: FiniteFloat
    position_debut_relative: Literal[
        "AVANT_BORNE", "SUR_BORNE", "APRES_BORNE"
    ]
    borne_fin_id: UUID | None = None
    distance_fin_m: FiniteFloat | None = None
    position_fin_relative: Literal[
        "AVANT_BORNE", "SUR_BORNE", "APRES_BORNE"
    ] | None = None

    @model_validator(mode="after")
    def validate_distance(self) -> "PointReperageUpdate":
        if self.distance_debut_m < 0:
            raise ValueError("La distance doit être positive ou nulle.")
        if (
            self.position_debut_relative == "SUR_BORNE"
            and self.distance_debut_m != 0
        ):
            raise ValueError("La distance doit être nulle pour une position sur borne.")
        end_values = (
            self.borne_fin_id,
            self.distance_fin_m,
            self.position_fin_relative,
        )
        if sum(value is not None for value in end_values) not in (0, 3):
            raise ValueError("Le bornage de fin doit être fourni complètement.")
        if self.distance_fin_m is not None and self.distance_fin_m < 0:
            raise ValueError("La distance de fin doit être positive ou nulle.")
        if (
            self.position_fin_relative == "SUR_BORNE"
            and self.distance_fin_m != 0
        ):
            raise ValueError(
                "La distance de fin doit être nulle pour une position sur borne."
            )
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


class PointGeometry(BaseModel):
    """Point GeoJSON reçu en EPSG:4326."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Point"]
    coordinates: tuple[FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def validate_position(self) -> "PointGeometry":
        longitude, latitude = self.coordinates
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("Le Point doit contenir une longitude/latitude valide.")
        return self


class PolygonGeometry(BaseModel):
    """Polygon GeoJSON simple ou troué reçu en EPSG:4326."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Polygon"]
    coordinates: list[list[tuple[FiniteFloat, FiniteFloat]]]

    @model_validator(mode="after")
    def validate_rings(self) -> "PolygonGeometry":
        if not self.coordinates:
            raise ValueError("Un Polygon exige un anneau extérieur.")
        for ring in self.coordinates:
            if len(ring) < 4:
                raise ValueError("Chaque anneau d'un Polygon exige quatre positions.")
            if ring[0] != ring[-1]:
                raise ValueError("Chaque anneau d'un Polygon doit être fermé.")
            for longitude, latitude in ring:
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError(
                        "Les sommets doivent être des longitude/latitude "
                        "EPSG:4326 valides."
                    )
        return self


DesordreGeometry = Annotated[
    PointGeometry | LineStringGeometry | PolygonGeometry,
    Field(discriminator="type"),
]


class LineEndpoints(BaseModel):
    """Extrémités autoritaires d'une LineString dans un CRS explicite."""

    model_config = ConfigDict(extra="forbid")

    crs: Literal["EPSG:3950", "EPSG:4326"]
    debut: tuple[FiniteFloat, FiniteFloat]
    fin: tuple[FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def validate_endpoints(self) -> "LineEndpoints":
        if self.debut == self.fin:
            raise ValueError("Le début et la fin doivent être distincts.")
        if self.crs == "EPSG:4326":
            for longitude, latitude in (self.debut, self.fin):
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError("Extrémité hors domaine EPSG:4326.")
        return self


class DesordreCreate(BaseModel):
    """Création d'un désordre, avec une seule autorité géométrique."""

    model_config = ConfigDict(extra="forbid")

    designation: str | None = None
    type_desordre_id: str | None = None
    commentaire: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    valid: bool = True
    troncon_ids: list[UUID] = Field(default_factory=list)
    geometry_type: Literal["Point", "LineString", "Polygon"] | None = None
    geometry: DesordreGeometry | None = None
    line_endpoints: LineEndpoints | None = None
    reperage: PointReperageUpdate | None = None
    coord_x_3950: FiniteFloat | None = None
    coord_y_3950: FiniteFloat | None = None
    longitude_4326: FiniteFloat | None = None
    latitude_4326: FiniteFloat | None = None

    @field_validator("designation", "type_desordre_id", "commentaire")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_location_authority(self) -> "DesordreCreate":
        xy_supplied = self.coord_x_3950 is not None or self.coord_y_3950 is not None
        lonlat_supplied = (
            self.longitude_4326 is not None or self.latitude_4326 is not None
        )
        if xy_supplied and (
            self.coord_x_3950 is None or self.coord_y_3950 is None
        ):
            raise ValueError("X et Y doivent être fournis ensemble.")
        if lonlat_supplied and (
            self.longitude_4326 is None or self.latitude_4326 is None
        ):
            raise ValueError("Longitude et latitude doivent être fournies ensemble.")
        authority_count = (
            int(self.geometry is not None)
            + int(self.line_endpoints is not None)
            + int(self.reperage is not None)
            + int(xy_supplied)
            + int(lonlat_supplied)
        )
        if authority_count != 1:
            raise ValueError(
                "Fournir exactement une géométrie, une paire X/Y ou une paire "
                "longitude/latitude."
            )
        if (xy_supplied or lonlat_supplied) and self.geometry is not None:
            raise ValueError("Les coordonnées numériques sont réservées au Point.")
        if lonlat_supplied and not (
            -180 <= self.longitude_4326 <= 180
            and -90 <= self.latitude_4326 <= 90
        ):
            raise ValueError("Longitude/latitude hors domaine EPSG:4326.")
        if len(set(self.troncon_ids)) != len(self.troncon_ids):
            raise ValueError("Un tronçon ne peut être associé qu'une fois.")
        inferred_type = (
            self.geometry.type
            if self.geometry is not None
            else "LineString" if self.line_endpoints is not None
            else "Point" if xy_supplied or lonlat_supplied
            else self.geometry_type
        )
        if self.geometry_type is not None and inferred_type != self.geometry_type:
            raise ValueError("Le type géométrique contredit l'autorité fournie.")
        if inferred_type == "Point" and len(self.troncon_ids) > 1:
            raise ValueError("Un désordre Point accepte au plus un tronçon.")
        if self.reperage is not None:
            if len(self.troncon_ids) != 1:
                raise ValueError("Le bornage exige exactement un tronçon.")
            has_end = self.reperage.borne_fin_id is not None
            if inferred_type == "Point" and has_end:
                raise ValueError("Un Point ne possède pas de bornage de fin.")
            if inferred_type == "LineString" and not has_end:
                raise ValueError("Une LineString exige un bornage de fin.")
            if inferred_type not in ("Point", "LineString"):
                raise ValueError("Le bornage est réservé aux Point et LineString.")
        return self


class TronconCreate(NamedObjectCreate):
    """Création d'un tronçon à partir d'une LineString GeoJSON EPSG:4326."""

    digue_id: UUID
    geometry: LineStringGeometry


class DesordreGeometryUpdate(BaseModel):
    """Modification cartographique d'une LineString ou d'un Polygon."""

    model_config = ConfigDict(extra="forbid")

    geometry: LineStringGeometry | PolygonGeometry


# Compatibilité interne avec les imports existants du prototype.
LineStringGeometryUpdate = DesordreGeometryUpdate
