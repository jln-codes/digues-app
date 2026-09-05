const TERRITORY_MASK_PANE = "territory-mask";
const TERRITORY_OUTLINE_PANE = "territory-outline";
const mapElement = document.querySelector("#map");
mapElement.style.visibility = "hidden";
const map = L.map("map", {
  zoomControl: false,
  editable: true,
  maxBoundsViscosity: 1,
}).setView([46.8, 2.5], 6);
map.createPane(TERRITORY_MASK_PANE);
map.getPane(TERRITORY_MASK_PANE).style.zIndex = "350";
map.getPane(TERRITORY_MASK_PANE).style.pointerEvents = "none";
map.createPane(TERRITORY_OUTLINE_PANE);
map.getPane(TERRITORY_OUTLINE_PANE).style.zIndex = "360";
map.getPane(TERRITORY_OUTLINE_PANE).style.pointerEvents = "none";
const statusElement = document.querySelector("#status");
const heritageToggleButton = document.querySelector("#toggle-heritage");
const queriesToggleButton = document.querySelector("#toggle-queries");
const aiToggleButton = document.querySelector("#toggle-ai");
const createMenuButton = document.querySelector("#toggle-create-menu");
const createMenuList = document.querySelector("#create-menu-list");
const toolsMenuButton = document.querySelector("#toggle-tools-menu");
const toolsMenuList = document.querySelector("#tools-menu-list");
const heritageCloseButton = document.querySelector("#close-heritage");
const heritagePanel = document.querySelector("#heritage-panel");
const primaryArea = document.querySelector("#primary-area");
const queriesView = document.querySelector("#queries-view");
const aiPanel = document.querySelector("#ai-panel");
const aiCloseButton = document.querySelector("#close-ai");
const aiConversation = document.querySelector("#ai-conversation");
const aiConversationEmpty = document.querySelector("#ai-conversation-empty");
const aiChatForm = document.querySelector("#ai-chat-form");
const aiMessageInput = document.querySelector("#ai-message");
const aiSendButton = document.querySelector("#ai-send");
const aiChatStatus = document.querySelector("#ai-chat-status");
const mapLegend = document.querySelector("#map-legend");
const layerToggleInputs = document.querySelectorAll("[data-layer-toggle]");
const heritageTree = document.querySelector("#heritage-tree");
const heritageLoading = document.querySelector("#heritage-loading");
const heritagePropertiesEmpty = document.querySelector("#heritage-properties-empty");
const heritagePropertiesList = document.querySelector("#heritage-properties-list");
const zoomTronconButton = document.querySelector("#zoom-troncon");
const editorPanel = document.querySelector("#editor-panel");
const heritageObjectForm = document.querySelector("#heritage-object-editor");
const heritageObjectIdField = document.querySelector("#heritage-object-id-field");
const heritageObjectId = document.querySelector("#heritage-object-id");
const heritageParentField = document.querySelector("#heritage-parent-field");
const heritageParentLabel = document.querySelector("#heritage-parent-label");
const heritageParent = document.querySelector("#heritage-parent");
const heritageObjectLabel = document.querySelector("#heritage-object-label");
const heritageObjectValid = document.querySelector("#heritage-object-valid");
const heritageCreateMessage = document.querySelector("#heritage-create-message");
const heritageCreateActions = document.querySelector("#heritage-create-actions");
const cancelCreateButton = document.querySelector("#cancel-create");
const submitCreateButton = document.querySelector("#submit-create");
const tronconCreateGeometry = document.querySelector("#troncon-create-geometry");
const startTronconDrawButton = document.querySelector("#start-troncon-draw");
const tronconDrawStatus = document.querySelector("#troncon-draw-status");
const tronconDrawActions = document.querySelector("#troncon-draw-actions");
const cancelTronconDrawButton = document.querySelector("#cancel-troncon-draw");
const restoreTronconDrawButton = document.querySelector("#restore-troncon-draw");
const desordreEditorForm = document.querySelector("#desordre-editor");
const desordreCreateIdField = document.querySelector("#desordre-create-id-field");
const desordreCreateId = document.querySelector("#desordre-create-id");
const desordreCreateDesignation = document.querySelector("#desordre-create-designation");
const desordreCreateTypeReference = document.querySelector("#desordre-create-type-reference");
const desordreCreateCommentaire = document.querySelector("#desordre-create-commentaire");
const desordreCreateDateDebut = document.querySelector("#desordre-create-date-debut");
const desordreCreateDateFin = document.querySelector("#desordre-create-date-fin");
const desordreCreateValid = document.querySelector("#desordre-create-valid");
const desordreCreateTroncons = document.querySelector("#desordre-create-troncons");
const desordreCreateGeometryType = document.querySelector("#desordre-create-geometry-type");
const desordreXyChoice = document.querySelector("#desordre-xy-choice");
const desordreLonlatChoice = document.querySelector("#desordre-lonlat-choice");
const desordreCreateXy = document.querySelector("#desordre-create-xy");
const desordreCreateLonlat = document.querySelector("#desordre-create-lonlat");
const desordreCreateX = document.querySelector("#desordre-create-x");
const desordreCreateY = document.querySelector("#desordre-create-y");
const desordreCreateLongitude = document.querySelector("#desordre-create-longitude");
const desordreCreateLatitude = document.querySelector("#desordre-create-latitude");
const desordreCreateGeometry = document.querySelector("#desordre-create-geometry");
const desordreCreateGeometryTitle = document.querySelector("#desordre-create-geometry-title");
const desordreCreateGeometryHelp = document.querySelector("#desordre-create-geometry-help");
const startDesordreDrawButton = document.querySelector("#start-desordre-draw");
const desordreDrawStatus = document.querySelector("#desordre-draw-status");
const desordreDrawActions = document.querySelector("#desordre-draw-actions");
const cancelDesordreDrawButton = document.querySelector("#cancel-desordre-draw");
const restoreDesordreDrawButton = document.querySelector("#restore-desordre-draw");
const validateDesordreDrawButton = document.querySelector("#validate-desordre-draw");
const desordreCreateMessage = document.querySelector("#desordre-create-message");
const desordreCreateActions = document.querySelector("#desordre-create-actions");
const cancelDesordreCreateButton = document.querySelector("#cancel-desordre-create");
const submitDesordreCreateButton = document.querySelector("#submit-desordre-create");
const desordreBornageChoice = document.querySelector("#desordre-bornage-choice");
const desordreCreateLineCoordinates = document.querySelector("#desordre-create-line-coordinates");
const desordreCreateLineCrs = document.querySelector("#desordre-create-line-crs");
const desordreCreateLineStart1 = document.querySelector("#desordre-create-line-start-1");
const desordreCreateLineStart2 = document.querySelector("#desordre-create-line-start-2");
const desordreCreateLineEnd1 = document.querySelector("#desordre-create-line-end-1");
const desordreCreateLineEnd2 = document.querySelector("#desordre-create-line-end-2");
const desordreCreateBornage = document.querySelector("#desordre-create-bornage");
const desordreCreateBornageEnd = document.querySelector("#desordre-create-bornage-end");
const desordreCreateBorneStart = document.querySelector("#desordre-create-borne-start");
const desordreCreateDistanceStart = document.querySelector("#desordre-create-distance-start");
const desordreCreateSenseStart = document.querySelector("#desordre-create-sense-start");
const desordreCreateBorneEnd = document.querySelector("#desordre-create-borne-end");
const desordreCreateDistanceEnd = document.querySelector("#desordre-create-distance-end");
const desordreCreateSenseEnd = document.querySelector("#desordre-create-sense-end");
const polygonRepresentativePoint = document.querySelector("#polygon-representative-point");
const polygonRepresentativeX = document.querySelector("#polygon-representative-x");
const polygonRepresentativeY = document.querySelector("#polygon-representative-y");
const polygonRepresentativeLongitude = document.querySelector("#polygon-representative-longitude");
const polygonRepresentativeLatitude = document.querySelector("#polygon-representative-latitude");
const desordreLineDerived = document.querySelector("#desordre-line-derived");
const editorObjectTitle = document.querySelector("#editor-object-title");
const editorObjectSubtitle = document.querySelector("#editor-object-subtitle");
const editorTabs = document.querySelector(".editor-tabs");
const editorMessage = desordreCreateMessage;
const saveButton = submitDesordreCreateButton;
const cancelEditButton = cancelDesordreCreateButton;
const closeEditorButton = document.querySelector("#close-editor");
const startMapPositionButton = document.querySelector("#start-map-position");
const mapPositionActions = document.querySelector("#map-position-actions");
const mapPositionStatus = document.querySelector("#map-position-status");
const validateMapPositionButton = document.querySelector("#validate-map-position");
const cancelMapPositionButton = document.querySelector("#cancel-map-position");
const pointMapEditor = document.querySelector("#point-map-editor");
const lineEditorMessage = desordreCreateMessage;
const startLineEditButton = document.querySelector("#start-line-edit");
const lineGeometryActions = document.querySelector("#line-geometry-actions");
const lineGeometryStatus = document.querySelector("#line-geometry-status");
const validateLineEditButton = document.querySelector("#validate-line-edit");
const cancelLineEditButton = document.querySelector("#cancel-line-edit");
const bornageModeRadio = document.querySelector("#bornage-mode");
const pointEditTroncon = desordreCreateTroncons;
const bornageFields = desordreCreateBornage;
const generalTabButton = document.querySelector("#general-tab-button");
const observationsTabButton = document.querySelector("#observations-tab-button");
const generalTab = document.querySelector("#general-tab");
const observationsTab = document.querySelector("#observations-tab");
const observationsListView = document.querySelector("#observations-list-view");
const observationsList = document.querySelector("#observations-list");
const observationsMessage = document.querySelector("#observations-message");
const observationsCount = document.querySelector("#observations-count");
const observationDetailView = document.querySelector("#observation-detail-view");
const observationDetailTitle = document.querySelector("#observation-detail-title");
const observationProperties = document.querySelector("#observation-properties");
const backToObservationsButton = document.querySelector("#back-to-observations");
const observationPhotos = document.querySelector("#observation-photos");
const photosCount = document.querySelector("#photos-count");
const photosStorageNote = document.querySelector("#photos-storage-note");
const photoLightbox = document.querySelector("#photo-lightbox");
const lightboxImage = document.querySelector("#lightbox-image");
const lightboxUnavailable = document.querySelector("#lightbox-unavailable");
const lightboxTitle = document.querySelector("#lightbox-title");
const lightboxCaption = document.querySelector("#lightbox-caption");
const closeLightboxButton = document.querySelector("#close-lightbox");
const previousPhotoButton = document.querySelector("#previous-photo");
const nextPhotoButton = document.querySelector("#next-photo");
const TERRITORY_VIEW_PADDING_RATIO = 0.08;
const TERRITORY_VIEW_MAX_ZOOM = 17;
const territoireModal = document.querySelector("#territoire-modal");
const territoireForm = document.querySelector("#territoire-form");
const closeTerritoireModalButton = document.querySelector("#close-territoire-modal");
const cancelTerritoireModalButton = document.querySelector("#cancel-territoire-modal");
const territoireCurrentState = document.querySelector("#territoire-current-state");
const territoireLibelleInput = document.querySelector("#territoire-libelle");
const territoireFileInput = document.querySelector("#territoire-file");
const territoireLayerInput = document.querySelector("#territoire-layer");
const territoireMessage = document.querySelector("#territoire-message");
const submitTerritoireButton = document.querySelector("#submit-territoire");
const disorderFields = {
  id: desordreCreateId,
  designation: desordreCreateDesignation,
  type: desordreCreateTypeReference,
  commentaire: desordreCreateCommentaire,
  dateDebut: desordreCreateDateDebut,
  dateFin: desordreCreateDateFin,
  valid: desordreCreateValid,
  x: desordreCreateX,
  y: desordreCreateY,
  longitude: desordreCreateLongitude,
  latitude: desordreCreateLatitude,
  geometryType: desordreCreateGeometryType,
  reperage: document.querySelector("#line-reperage-summary"),
};
const reperageFields = {
  borne: desordreCreateBorneStart,
  distance: desordreCreateDistanceStart,
  sens: desordreCreateSenseStart,
};
const lineEditTroncons = desordreCreateTroncons;
const lineMapEditor = document.querySelector("#line-map-editor");
const lineCoordinateEditor = desordreCreateLineCoordinates;
const lineEndpointsCrs = desordreCreateLineCrs;
const lineStart1 = desordreCreateLineStart1;
const lineStart2 = desordreCreateLineStart2;
const lineEnd1 = desordreCreateLineEnd1;
const lineEnd2 = desordreCreateLineEnd2;
const saveLineEndpointsButton = document.querySelector("#save-line-endpoints");
const lineBorneStart = desordreCreateBorneStart;
const lineDistanceStart = desordreCreateDistanceStart;
const lineSenseStart = desordreCreateSenseStart;
const lineBorneEnd = desordreCreateBorneEnd;
const lineDistanceEnd = desordreCreateDistanceEnd;
const lineSenseEnd = desordreCreateSenseEnd;
const reprojectBornageButton = document.querySelector("#reproject-bornage");
const saveLineBornageButton = document.querySelector("#save-line-bornage");
const lineCoordinateActions = document.querySelector("#line-coordinate-actions");
const desordreBornageActions = document.querySelector("#desordre-bornage-actions");
const pointBornageWarning = document.querySelector("#point-bornage-warning");
const lineBornageWarning = document.querySelector("#line-bornage-warning");

let activePointLayer = null;
let lastServerFeature = null;
let initialFormValues = null;
let requestedDesordreId = null;
let graphicEditActive = false;
let provisionalLatLng = null;
let graphicRequestInFlight = false;
let heritageLoaded = false;
let heritageLoadingPromise = null;
let heritageData = { systemes: [] };
let selectedTreeButton = null;
let selectedHeritageObject = null;
let tronconsGeoJsonLayer = null;
let highlightedTronconLayer = null;
let observationsLoadedFor = null;
let currentObservationPhotos = [];
let currentPhotoIndex = -1;
let currentReperage = null;
let activeLineLayer = null;
let activePolygonLayer = null;
let polygonEditActive = false;
let selectedLineLayer = null;
let lineEditActive = false;
let lineRequestInFlight = false;
let initialLineReperageValues = null;
let desordresGeoJsonLayer = null;
let desordrePointLayer = null;
let desordreLineLayer = null;
let desordrePolygonLayer = null;
let territoireContourLayer = null;
let territoireMaskLayer = null;
let showUuid = false;
let aiRequestPending = false;
let territoireAdministratifGeoJSON = { type: "FeatureCollection", features: [] };
let territoireImportPending = false;
let mapViewportReady = false;
let historicalViewportBounds = null;
const aiConversationHistory = [];
const AI_HISTORY_MAX_MESSAGES = 20;
let editorState = {
  mode: "edit",
  objectType: null,
  geometryType: null,
  objectId: null,
  data: null,
};

function setDisorderEditorState(mode, geometryType, objectId = null, data = null) {
  editorState = {
    mode,
    objectType: "desordre",
    geometryType,
    objectId,
    data,
  };
}
let provisionalTronconLayer = null;
let cancelledTronconGeometry = null;
let provisionalDesordreLayer = null;
let cancelledDesordreGeometry = null;
let desordreTypes = [];
let desordreTypesLoadingPromise = null;
let desordreTronconOptions = [];
let desordreTronconsLoadingPromise = null;
const reperageOptionsByTroncon = new Map();
let previousDesordreGeometryType = "Point";
let creationRequestInFlight = false;
let creationReperageRequestVersion = 0;
let creationReperageAvailable = false;
let lastAcceptedCreationTronconIds = [];
let creationReperageFeedbackActive = false;
const tronconLayersById = new Map();
const desordreLayersById = new Map();

const heritageCreationTypes = {
  systeme: {
    title: "Système d'endiguement",
    draftTitle: "Nouveau système d'endiguement",
    endpoint: "/api/systemes-endiguement",
  },
  digue: {
    title: "Digue",
    draftTitle: "Nouvelle digue",
    endpoint: "/api/digues",
  },
  troncon: {
    title: "Tronçon",
    draftTitle: "Nouveau tronçon",
    endpoint: "/api/troncons",
  },
  desordre: {
    title: "Désordre",
    draftTitle: "Nouveau désordre",
    endpoint: "/api/desordres",
  },
};

const pointIcon = L.divIcon({
  className: "desordre-point-marker",
  html: "<span></span>",
  iconAnchor: [9, 9],
  iconSize: [18, 18],
});

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

function text(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function businessLabel(item, fallback = "Sans libellé") {
  return item?.libelle || (showUuid ? item?.id : null) || fallback;
}

async function loadFrontendConfig() {
  const config = await fetchJson("/api/config");
  showUuid = Boolean(config.show_uuid);
  document.body.classList.toggle("show-uuid", showUuid);
}

function inputText(value) {
  return value === null || value === undefined ? "" : String(value);
}

function optionalPayloadValue(value) {
  if (value === null || value === undefined) return null;
  const normalized = String(value).trim();
  return normalized === "" ? null : normalized;
}

function coordinate(value, precision) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(precision) : "";
}

function popupContent(properties, popupFields) {
  const list = document.createElement("dl");
  list.className = "popup-fields";
  popupFields.forEach(([label, key]) => {
    if (key === "id" && !showUuid) {
      return;
    }
    const term = document.createElement("dt");
    const value = document.createElement("dd");
    term.textContent = label;
    value.textContent = text(properties[key]);
    list.append(term, value);
  });
  return list;
}

function errorDetail(body, fallback) {
  if (typeof body?.detail === "string") {
    return body.detail;
  }
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || String(item)).join(" ");
  }
  return fallback;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/geo+json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      detail = errorDetail(await response.json(), detail);
    } catch (_error) {
      // Le statut HTTP reste affiché si le corps n'est pas du JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

async function fetchGeoJSON(url) {
  const data = await fetchJson(url);
  if (data.type !== "FeatureCollection" || !Array.isArray(data.features)) {
    throw new Error(`${url} : réponse GeoJSON invalide`);
  }
  return data;
}

function setTerritoireAdministratifState(collection) {
  if (collection.type !== "FeatureCollection" || !Array.isArray(collection.features)) {
    throw new Error("Réponse GeoJSON du territoire invalide");
  }
  if (collection.features.length > 1) {
    throw new Error("Réponse GeoJSON du territoire ambiguë");
  }
  territoireAdministratifGeoJSON = {
    type: "FeatureCollection",
    features: collection.features.slice(0, 1),
  };
}

function currentTerritoireFeature() {
  return territoireAdministratifGeoJSON.features[0] || null;
}

async function loadTerritoireAdministratif() {
  const collection = await fetchGeoJSON("/api/territoire-administratif");
  setTerritoireAdministratifState(collection);
}

function territoryBoundsFromFeature(feature) {
  if (!feature) {
    return null;
  }
  const layer = L.geoJSON(feature);
  const bounds = layer.getBounds();
  return bounds.isValid() ? bounds : null;
}

function territoryMaskGeoJSON(feature) {
  const coordinates = feature?.geometry?.coordinates;
  const outerRing = coordinates?.[0];
  if (!Array.isArray(outerRing) || outerRing.length < 4) {
    return null;
  }
  const worldRing = [
    [-180, -90],
    [180, -90],
    [180, 90],
    [-180, 90],
    [-180, -90],
  ];
  const polygons = [
    [worldRing, outerRing],
  ];
  coordinates.slice(1).forEach((hole) => {
    if (Array.isArray(hole) && hole.length >= 4) {
      polygons.push([hole]);
    }
  });
  return {
    type: "Feature",
    geometry: {
      type: "MultiPolygon",
      coordinates: polygons,
    },
    properties: {},
  };
}

function clearTerritoireLayers() {
  if (territoireMaskLayer) {
    map.removeLayer(territoireMaskLayer);
    territoireMaskLayer = null;
  }
  if (territoireContourLayer) {
    map.removeLayer(territoireContourLayer);
    territoireContourLayer = null;
  }
}

function renderTerritoireLayers() {
  clearTerritoireLayers();
  const feature = currentTerritoireFeature();
  if (!feature) {
    return null;
  }

  const maskFeature = territoryMaskGeoJSON(feature);
  if (maskFeature) {
    territoireMaskLayer = L.geoJSON(maskFeature, {
      interactive: false,
      pane: TERRITORY_MASK_PANE,
      style: {
        color: "#c6cfd6",
        fillColor: "#eff3f6",
        fillOpacity: 1,
        opacity: 0,
        stroke: false,
      },
    }).addTo(map);
  }

  territoireContourLayer = L.geoJSON(feature, {
    interactive: false,
    pane: TERRITORY_OUTLINE_PANE,
    style: {
      color: "#385f80",
      fillColor: "#ffffff",
      fillOpacity: 0.04,
      opacity: 0.95,
      weight: 2,
    },
  }).addTo(map);

  return territoireContourLayer.getBounds();
}

function applyViewportBounds(bounds) {
  if (!bounds?.isValid()) {
    return false;
  }
  const paddedBounds = bounds.pad(TERRITORY_VIEW_PADDING_RATIO);
  map.fitBounds(paddedBounds, {
    maxZoom: TERRITORY_VIEW_MAX_ZOOM,
    animate: false,
  });
  map.setMaxBounds(paddedBounds);
  map.setMinZoom(map.getZoom());
  return true;
}

function revealMapAfterInitialViewport() {
  map.invalidateSize({ pan: false, animate: false });
  mapElement.style.visibility = "";
  mapViewportReady = true;
}

function applyTerritoireCartography(bounds) {
  const territoryBounds = renderTerritoireLayers();
  const referenceBounds = territoryBounds || bounds;
  if (referenceBounds?.isValid()) {
    applyViewportBounds(referenceBounds);
  }
  revealMapAfterInitialViewport();
  return referenceBounds;
}

function setToolsMenuOpen(open) {
  toolsMenuList.hidden = !open;
  toolsMenuButton.setAttribute("aria-expanded", String(open));
}

function renderTerritoireModal({ keepMessage = false } = {}) {
  const feature = currentTerritoireFeature();
  territoireCurrentState.textContent = feature
    ? `Territoire actuel : ${text(feature.properties?.libelle, "Sans libellé")}`
    : "Aucun territoire configuré";
  territoireLibelleInput.value = feature
    ? inputText(feature.properties?.libelle)
    : territoireLibelleInput.value;
  submitTerritoireButton.textContent = feature ? "Remplacer" : "Importer";
  if (!keepMessage) {
    territoireMessage.textContent = "";
    territoireMessage.classList.remove("error");
  }
}

function openTerritoireModal() {
  renderTerritoireModal();
  territoireModal.hidden = false;
  territoireLibelleInput.focus();
}

function closeTerritoireModal() {
  if (territoireImportPending) {
    return;
  }
  territoireModal.hidden = true;
  territoireForm.reset();
  territoireMessage.textContent = "";
  territoireMessage.classList.remove("error");
}

function territoireContentType(file) {
  const name = file?.name || "";
  const suffix = name.toLowerCase().split(".").pop();
  if (suffix === "zip") return "application/zip";
  if (suffix === "gpkg") return "application/geopackage+sqlite3";
  throw new Error("Sélectionnez un fichier .gpkg ou .zip.");
}

function setTerritoireImportPending(pending) {
  territoireImportPending = pending;
  territoireLibelleInput.disabled = pending;
  territoireFileInput.disabled = pending;
  territoireLayerInput.disabled = pending;
  submitTerritoireButton.disabled = pending;
  cancelTerritoireModalButton.disabled = pending;
  closeTerritoireModalButton.disabled = pending;
}

async function submitTerritoireImport() {
  const libelle = territoireLibelleInput.value.trim();
  const file = territoireFileInput.files[0];
  if (!libelle) {
    throw new Error("Le libellé est obligatoire.");
  }
  if (!file) {
    throw new Error("Sélectionnez un fichier GeoPackage ou Shapefile ZIP.");
  }
  const contentType = territoireContentType(file);
  const replacing = Boolean(currentTerritoireFeature());
  if (replacing && !window.confirm(
    "Remplacer le territoire administratif actuel ? L'ancien contour ne sera pas conservé."
  )) {
    return;
  }

  const parameters = new URLSearchParams({
    libelle,
    replace: replacing ? "true" : "false",
  });
  const layer = territoireLayerInput.value.trim();
  if (layer) {
    parameters.set("layer", layer);
  }

  setTerritoireImportPending(true);
  territoireMessage.textContent = replacing ? "Remplacement en cours…" : "Import en cours…";
  territoireMessage.classList.remove("error");
  try {
    const collection = await fetchJson(
      `/api/territoire-administratif/import?${parameters.toString()}`,
      {
        method: "POST",
        headers: {
          "X-Filename": file.name,
          "Content-Type": contentType,
        },
        body: file,
      },
    );
    setTerritoireAdministratifState(collection);
    applyTerritoireCartography(historicalViewportBounds);
    territoireFileInput.value = "";
    setTerritoireImportPending(false);
    closeTerritoireModal();
    return collection;
  } finally {
    setTerritoireImportPending(false);
  }
}

function appendDefinition(list, label, value) {
  if (!showUuid && label === "Identifiant") return;
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = text(value);
  if (label === "Identifiant") {
    term.classList.add("technical-identifier");
    description.classList.add("technical-identifier");
  }
  list.append(term, description);
}

function closePhotoLightbox() {
  photoLightbox.hidden = true;
  lightboxImage.removeAttribute("src");
  lightboxImage.hidden = true;
  currentPhotoIndex = -1;
}

function showPhotoInLightbox(index) {
  const photo = currentObservationPhotos[index];
  if (!photo) {
    return;
  }
  currentPhotoIndex = index;
  lightboxTitle.textContent = text(photo.designation, photo.nom_fichier || "Photo");
  lightboxCaption.textContent = [photo.date, photo.nom_fichier]
    .filter(Boolean)
    .join(" — ");
  if (photo.content_available && photo.content_url) {
    lightboxImage.src = photo.content_url;
    lightboxImage.alt = lightboxTitle.textContent;
    lightboxImage.hidden = false;
    lightboxUnavailable.hidden = true;
  } else {
    lightboxImage.removeAttribute("src");
    lightboxImage.hidden = true;
    lightboxUnavailable.hidden = false;
  }
  previousPhotoButton.disabled = currentObservationPhotos.length < 2;
  nextPhotoButton.disabled = currentObservationPhotos.length < 2;
  photoLightbox.hidden = false;
  closeLightboxButton.focus();
}

function navigatePhoto(offset) {
  if (currentObservationPhotos.length < 2) {
    return;
  }
  const nextIndex = (
    currentPhotoIndex + offset + currentObservationPhotos.length
  ) % currentObservationPhotos.length;
  showPhotoInLightbox(nextIndex);
}

function renderPhotoMetadata(photos) {
  currentObservationPhotos = photos;
  observationPhotos.replaceChildren();
  photosCount.textContent = `${photos.length} photo(s)`;
  photosStorageNote.textContent = photos.some((photo) => photo.content_available)
    ? "La pleine résolution est chargée uniquement à l’ouverture."
    : "Métadonnées disponibles ; les fichiers source ne sont pas matérialisés dans la base cible.";
  if (photos.length === 0) {
    const empty = document.createElement("p");
    empty.className = "field-help";
    empty.textContent = "Aucune photo pour cette observation.";
    observationPhotos.append(empty);
    return;
  }
  photos.forEach((photo, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "photo-card";
    const preview = document.createElement("span");
    preview.className = "photo-placeholder";
    preview.textContent = "Photo";
    const label = document.createElement("strong");
    label.textContent = text(photo.designation, photo.nom_fichier || "Photo");
    const metadata = document.createElement("span");
    metadata.textContent = text(photo.date, photo.nom_fichier || "Sans date");
    button.append(preview, label, metadata);
    button.addEventListener("click", () => showPhotoInLightbox(index));
    observationPhotos.append(button);
  });
}

async function openObservation(observationId) {
  observationsMessage.textContent = "Chargement de l’observation…";
  try {
    const observation = await fetchJson(
      `/api/observations/${encodeURIComponent(observationId)}`,
    );
    if (String(observation.desordre_id) !== String(lastServerFeature?.properties.id)) {
      throw new Error("L’observation ne correspond pas au désordre sélectionné.");
    }
    observationProperties.replaceChildren();
    observationDetailTitle.textContent = text(observation.designation, "Observation");
    appendDefinition(observationProperties, "Identifiant", observation.id);
    appendDefinition(observationProperties, "Date", observation.date);
    appendDefinition(
      observationProperties,
      "Urgence",
      observation.urgence_libelle
        || (showUuid ? observation.urgence_id : "Urgence sans libellé"),
    );
    appendDefinition(observationProperties, "Désignation", observation.designation);
    appendDefinition(observationProperties, "Évolution", observation.evolution);
    appendDefinition(observationProperties, "Validité", observation.valid ? "Valide" : "Invalide");
    renderPhotoMetadata(Array.isArray(observation.photos) ? observation.photos : []);
    observationsListView.hidden = true;
    observationDetailView.hidden = false;
    observationsMessage.textContent = "";
  } catch (error) {
    console.error("Lecture de l’observation impossible", error);
    observationsMessage.textContent = `Lecture impossible : ${error.message}`;
  }
}

function renderObservations(data) {
  const observations = Array.isArray(data.observations) ? data.observations : [];
  observationsList.replaceChildren();
  observationsCount.textContent = `${observations.length} observation(s)`;
  if (observations.length === 0) {
    observationsMessage.textContent = "Aucune observation pour ce désordre.";
    return;
  }
  observationsMessage.textContent = "";
  observations.forEach((observation) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "observation-row";
    const heading = document.createElement("span");
    heading.className = "observation-row-heading";
    heading.textContent = [observation.date, observation.urgence_libelle]
      .filter(Boolean)
      .join(" — ") || "Observation sans date";
    const designation = document.createElement("strong");
    designation.textContent = text(observation.designation, "Sans désignation");
    const evolution = document.createElement("span");
    evolution.textContent = text(observation.evolution, "").slice(0, 120);
    const photoCount = document.createElement("small");
    photoCount.textContent = `${observation.photo_count || 0} photo(s)`;
    button.append(heading, designation, evolution, photoCount);
    button.addEventListener("click", () => openObservation(observation.id));
    observationsList.append(button);
  });
}

async function loadObservations() {
  const desordreId = lastServerFeature?.properties.id;
  if (!desordreId || observationsLoadedFor === String(desordreId)) {
    return;
  }
  observationsMessage.textContent = "Chargement des observations…";
  observationsList.replaceChildren();
  try {
    const data = await fetchJson(
      `/api/desordres/${encodeURIComponent(desordreId)}/observations`,
    );
    if (String(data.desordre_id) !== String(desordreId)) {
      throw new Error("Réponse d’observations incohérente.");
    }
    renderObservations(data);
    observationsLoadedFor = String(desordreId);
  } catch (error) {
    console.error("Lecture des observations impossible", error);
    observationsMessage.textContent = `Chargement impossible : ${error.message}`;
  }
}

function showEditorTab(name) {
  const showGeneral = name === "general";
  generalTab.hidden = !showGeneral;
  observationsTab.hidden = showGeneral;
  generalTabButton.classList.toggle("active", showGeneral);
  observationsTabButton.classList.toggle("active", !showGeneral);
  generalTabButton.setAttribute("aria-selected", String(showGeneral));
  observationsTabButton.setAttribute("aria-selected", String(!showGeneral));
  if (!showGeneral) {
    observationsListView.hidden = false;
    observationDetailView.hidden = true;
    closePhotoLightbox();
    loadObservations();
  }
}

function propertyRow(label, value) {
  if (!showUuid && ["Identifiant", "Système de repérage par défaut"].includes(label)) {
    return;
  }
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = text(value);
  if (label === "Identifiant") {
    term.classList.add("technical-identifier");
    description.classList.add("technical-identifier");
  }
  heritagePropertiesList.append(term, description);
}

function clearHighlightedTroncon() {
  if (highlightedTronconLayer && tronconsGeoJsonLayer) {
    tronconsGeoJsonLayer.resetStyle(highlightedTronconLayer);
  }
  highlightedTronconLayer = null;
}

function highlightTroncon(tronconId) {
  clearHighlightedTroncon();
  const layer = tronconLayersById.get(String(tronconId));
  if (!layer) {
    return null;
  }
  layer.setStyle({ color: "#1769aa", opacity: 1, weight: 7 });
  layer.bringToFront();
  highlightedTronconLayer = layer;
  return layer;
}

function selectHeritageObject(kind, item, parent, nameButton) {
  selectedTreeButton?.classList.remove("selected");
  selectedTreeButton = nameButton;
  selectedTreeButton.classList.add("selected");
  selectedHeritageObject = { kind, item, parent };

  heritagePropertiesList.replaceChildren();
  heritagePropertiesEmpty.hidden = true;
  heritagePropertiesList.hidden = false;
  propertyRow("Objet", kind);
  propertyRow("Identifiant", item.id);
  propertyRow("Libellé", item.libelle);
  if (parent) {
    propertyRow(
      "Parent",
      showUuid
        ? businessLabel(parent)
        : businessLabel(parent),
    );
  }
  propertyRow("Validité", item.valid ? "Valide" : "Invalide");

  if (kind === "Système d'endiguement") {
    propertyRow("Nombre de digues", item.digues.length);
  } else if (kind === "Digue") {
    propertyRow("Nombre de tronçons", item.troncons.length);
  } else {
    propertyRow("Système de repérage par défaut", item.systeme_reperage_defaut_id);
  }

  const isTroncon = kind === "Tronçon";
  zoomTronconButton.hidden = !isTroncon;
  clearHighlightedTroncon();
  if (isTroncon) {
    const layer = highlightTroncon(item.id);
    zoomTronconButton.disabled = !layer;
  }
}

function createTreeNode(kind, item, parent, children, level) {
  const node = document.createElement("div");
  node.className = "tree-node";
  const row = document.createElement("div");
  row.className = "tree-row";
  row.setAttribute("role", "treeitem");
  row.setAttribute("aria-level", String(level));

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "tree-toggle";
  toggle.setAttribute("aria-label", `Déplier ${businessLabel(item)}`);
  const name = document.createElement("button");
  name.type = "button";
  name.className = "tree-name";
  name.dataset.objectKind = kind;
  name.dataset.objectId = String(item.id);
  name.textContent = businessLabel(item);
  name.title = name.textContent;
  name.addEventListener("click", () => {
    selectHeritageObject(kind, item, parent, name);
  });
  row.append(toggle, name);
  node.append(row);

  if (children.length === 0) {
    toggle.classList.add("empty");
    toggle.textContent = "▸";
    return node;
  }

  const childContainer = document.createElement("div");
  childContainer.className = "tree-node-children";
  childContainer.setAttribute("role", "group");
  childContainer.hidden = true;
  children.forEach((child) => childContainer.append(child));
  node.append(childContainer);
  toggle.textContent = "▸";
  toggle.setAttribute("aria-expanded", "false");
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    toggle.textContent = expanded ? "▸" : "▾";
    toggle.setAttribute(
      "aria-label",
      `${expanded ? "Déplier" : "Replier"} ${businessLabel(item)}`,
    );
    childContainer.hidden = expanded;
  });
  return node;
}

function renderHeritageTree(data) {
  heritageData = data;
  heritageTree.replaceChildren();
  data.systemes.forEach((systeme) => {
    const digueNodes = systeme.digues.map((digue) => {
      const tronconNodes = digue.troncons.map((troncon) => createTreeNode(
        "Tronçon",
        troncon,
        digue,
        [],
        3,
      ));
      return createTreeNode("Digue", digue, systeme, tronconNodes, 2);
    });
    heritageTree.append(
      createTreeNode("Système d'endiguement", systeme, null, digueNodes, 1),
    );
  });
  heritageLoading.textContent = data.systemes.length
    ? `${data.systemes.length} système(s) chargé(s).`
    : "Aucun système d’endiguement disponible.";
}

async function loadHeritageTree() {
  if (heritageLoaded) {
    return;
  }
  if (!heritageLoadingPromise) {
    heritageLoading.textContent = "Chargement du patrimoine…";
    heritageLoadingPromise = fetchJson("/api/systemes-endiguement")
      .then((data) => {
        if (!Array.isArray(data.systemes)) {
          throw new Error("Réponse hiérarchique invalide.");
        }
        renderHeritageTree(data);
        heritageLoaded = true;
      })
      .catch((error) => {
        console.error("Chargement du patrimoine impossible", error);
        heritageLoading.textContent = `Chargement impossible : ${error.message}`;
        heritageLoadingPromise = null;
      });
  }
  await heritageLoadingPromise;
}

function setHeritagePanelOpen(open) {
  heritagePanel.hidden = !open;
  mapLegend.hidden = open || !queriesView.hidden;
  heritageToggleButton.setAttribute("aria-expanded", String(open));
  if (open) {
    loadHeritageTree();
  }
}

function refreshMapSize() {
  if (!mapElement.hidden) {
    window.requestAnimationFrame(() => map.invalidateSize());
  }
}

function setQueriesViewOpen(open) {
  mapElement.hidden = open;
  queriesView.hidden = !open;
  primaryArea.classList.toggle("queries-open", open);
  mapLegend.hidden = open || !heritagePanel.hidden;
  queriesToggleButton.setAttribute("aria-expanded", String(open));
  refreshMapSize();
}

function setAiPanelOpen(open) {
  aiPanel.hidden = !open;
  aiToggleButton.setAttribute("aria-expanded", String(open));
  refreshMapSize();
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (_error) {
      // Le fallback reste utile hors contexte sécurisé ou si l'accès est refusé.
    }
  }
  const temporaryInput = document.createElement("textarea");
  temporaryInput.value = text;
  temporaryInput.setAttribute("aria-hidden", "true");
  temporaryInput.className = "clipboard-fallback";
  document.body.append(temporaryInput);
  temporaryInput.select();
  const copied = document.execCommand("copy");
  temporaryInput.remove();
  if (!copied) {
    throw new Error("Copie indisponible");
  }
}

function safeAiLinkHref(href) {
  if (typeof href !== "string") {
    return null;
  }
  try {
    const url = new URL(href.trim());
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch (_error) {
    return null;
  }
}

function appendAiInlineTokens(parent, tokens) {
  (tokens || []).forEach((token) => {
    if (token.type === "text") {
      if (Array.isArray(token.tokens)) {
        appendAiInlineTokens(parent, token.tokens);
      } else {
        parent.append(document.createTextNode(token.text || ""));
      }
      return;
    }

    const inlineTags = {
      strong: "strong",
      em: "em",
      codespan: "code",
      del: "del",
    };
    if (inlineTags[token.type]) {
      const element = document.createElement(inlineTags[token.type]);
      if (token.type === "codespan") {
        element.textContent = token.text || "";
      } else {
        appendAiInlineTokens(element, token.tokens);
      }
      parent.append(element);
      return;
    }

    if (token.type === "link") {
      const href = safeAiLinkHref(token.href);
      const element = document.createElement(href ? "a" : "span");
      appendAiInlineTokens(element, token.tokens);
      if (href) {
        element.href = href;
        element.target = "_blank";
        element.rel = "noopener noreferrer";
      }
      parent.append(element);
      return;
    }

    if (token.type === "br") {
      parent.append(document.createElement("br"));
      return;
    }

    if (Array.isArray(token.tokens)) {
      appendAiInlineTokens(parent, token.tokens);
      return;
    }
    parent.append(document.createTextNode(token.text || token.raw || ""));
  });
}

function createAiCopyButton(content, className) {
  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = `ai-copy-button ${className}`;
  copyButton.textContent = "Copier";
  copyButton.setAttribute("aria-live", "polite");
  copyButton.addEventListener("click", async () => {
    try {
      await copyTextToClipboard(content);
      copyButton.textContent = "Copié";
    } catch (_error) {
      copyButton.textContent = "Copie impossible";
    }
    window.setTimeout(() => {
      copyButton.textContent = "Copier";
    }, 1400);
  });
  return copyButton;
}

function appendAiMarkdownBlocks(parent, tokens) {
  (tokens || []).forEach((token) => {
    if (token.type === "space") {
      return;
    }
    if (token.type === "heading") {
      const heading = document.createElement(`h${Math.min(token.depth || 1, 4)}`);
      appendAiInlineTokens(heading, token.tokens);
      parent.append(heading);
      return;
    }
    if (["paragraph", "text"].includes(token.type)) {
      const paragraph = document.createElement("p");
      appendAiInlineTokens(paragraph, token.tokens || [token]);
      parent.append(paragraph);
      return;
    }
    if (token.type === "list") {
      const list = document.createElement(token.ordered ? "ol" : "ul");
      token.items.forEach((item) => {
        const listItem = document.createElement("li");
        appendAiMarkdownBlocks(listItem, item.tokens);
        list.append(listItem);
      });
      parent.append(list);
      return;
    }
    if (token.type === "blockquote") {
      const quote = document.createElement("blockquote");
      appendAiMarkdownBlocks(quote, token.tokens);
      parent.append(quote);
      return;
    }
    if (token.type === "code") {
      const wrapper = document.createElement("section");
      wrapper.className = "ai-code-block";
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = token.text || "";
      const language = (token.lang || "").trim().split(/\s+/, 1)[0];
      if (/^[a-z0-9_-]{1,32}$/i.test(language)) {
        code.dataset.language = language.toLowerCase();
      }
      pre.append(code);
      wrapper.append(pre, createAiCopyButton(code.textContent, "ai-code-copy"));
      parent.append(wrapper);
      return;
    }
    if (token.type === "hr") {
      parent.append(document.createElement("hr"));
      return;
    }

    const fallback = document.createElement("p");
    fallback.textContent = token.raw || token.text || "";
    parent.append(fallback);
  });
}

function renderAiMarkdown(content) {
  const body = document.createElement("div");
  body.className = "ai-message-body ai-markdown";
  if (!globalThis.marked?.lexer) {
    body.textContent = content;
    return body;
  }
  try {
    appendAiMarkdownBlocks(body, globalThis.marked.lexer(content, {
      gfm: true,
      breaks: false,
    }));
  } catch (_error) {
    body.textContent = content;
  }
  return body;
}

function appendAiExecutedQueries(message, executedQueries) {
  const queries = Array.isArray(executedQueries)
    ? executedQueries.filter(
      (query) => typeof query?.sql === "string" && query.sql.trim(),
    )
    : [];
  if (!queries.length) {
    return;
  }

  const details = document.createElement("details");
  details.className = "ai-sql-details";
  const summary = document.createElement("summary");
  summary.textContent = `Requêtes SQL utilisées — ${queries.length} requête${queries.length > 1 ? "s" : ""}`;
  details.append(summary);

  queries.forEach((query, index) => {
    const item = document.createElement("section");
    item.className = "ai-sql-query";
    const heading = document.createElement("strong");
    heading.textContent = `Requête ${index + 1}`;
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = query.sql;
    pre.append(code);
    const copyButton = createAiCopyButton(query.sql, "ai-sql-copy");
    item.append(heading, pre, copyButton);
    details.append(item);
  });
  message.append(details);
}

function appendAiMessage(
  role,
  content,
  { error = false, remember = true, executedQueries = [] } = {},
) {
  aiConversationEmpty?.remove();
  const message = document.createElement("article");
  message.className = `ai-message ai-message-${role}`;
  if (error) {
    message.classList.add("ai-message-error");
  }
  const author = document.createElement("strong");
  author.textContent = role === "user" ? "Vous" : "Assistant IA";
  const body = role === "assistant"
    ? renderAiMarkdown(content)
    : document.createElement("span");
  if (role === "user") {
    body.className = "ai-message-body";
    body.textContent = content;
  }
  message.append(author, body);
  if (role === "assistant") {
    appendAiExecutedQueries(message, executedQueries);
  }
  aiConversation.append(message);
  aiConversation.scrollTop = aiConversation.scrollHeight;
  if (remember) {
    aiConversationHistory.push({ role, content });
  }
}

function setAiRequestPending(pending) {
  aiRequestPending = pending;
  aiMessageInput.disabled = pending;
  aiSendButton.disabled = pending;
  aiChatStatus.textContent = pending ? "Envoi en cours…" : "";
}

aiChatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = aiMessageInput.value.trim();
  if (!message || aiRequestPending) {
    return;
  }

  appendAiMessage("user", message);
  aiMessageInput.value = "";
  setAiRequestPending(true);
  try {
    const response = await fetchJson("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: aiConversationHistory.slice(-AI_HISTORY_MAX_MESSAGES),
      }),
    });
    if (typeof response.answer !== "string" || !response.answer.trim()) {
      throw new Error("Réponse invalide du service IA.");
    }
    appendAiMessage("assistant", response.answer.trim(), {
      executedQueries: response.executed_queries,
    });
  } catch (error) {
    console.error("Réponse de l’assistant impossible", error);
    appendAiMessage(
      "assistant",
      error.message || "Impossible d’obtenir une réponse de l’assistant.",
      { error: true, remember: false },
    );
  } finally {
    setAiRequestPending(false);
    aiMessageInput.focus();
  }
});

aiMessageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!aiRequestPending) {
      aiChatForm.requestSubmit();
    }
  }
});

queriesToggleButton.addEventListener("click", () => {
  setQueriesViewOpen(queriesView.hidden);
});

aiToggleButton.addEventListener("click", () => {
  setAiPanelOpen(aiPanel.hidden);
});

aiCloseButton.addEventListener("click", () => {
  setAiPanelOpen(false);
});

heritageToggleButton.addEventListener("click", () => {
  setHeritagePanelOpen(heritagePanel.hidden);
});

heritageCloseButton.addEventListener("click", () => {
  setHeritagePanelOpen(false);
});

zoomTronconButton.addEventListener("click", () => {
  if (selectedHeritageObject?.kind !== "Tronçon") {
    return;
  }
  const layer = tronconLayersById.get(String(selectedHeritageObject.item.id));
  if (layer) {
    map.fitBounds(layer.getBounds(), { padding: [40, 40] });
  }
});

function setCreateMenuOpen(open) {
  createMenuList.hidden = !open;
  createMenuButton.setAttribute("aria-expanded", String(open));
}

function clearTronconDraft({ keepRestorable = false } = {}) {
  if (provisionalTronconLayer) {
    if (keepRestorable) {
      cancelledTronconGeometry = provisionalTronconLayer.toGeoJSON(false).geometry;
    }
    provisionalTronconLayer.disableEdit?.();
    map.removeLayer(provisionalTronconLayer);
    provisionalTronconLayer = null;
  }
  map.editTools?.stopDrawing?.();
  if (!keepRestorable) {
    cancelledTronconGeometry = null;
  }
  tronconDrawStatus.hidden = true;
  tronconDrawActions.hidden = !keepRestorable;
  restoreTronconDrawButton.hidden = !keepRestorable;
  startTronconDrawButton.hidden = false;
}

function updateTronconDraftStatus(message = null) {
  if (!provisionalTronconLayer) {
    return;
  }
  const vertices = provisionalTronconLayer.getLatLngs().length;
  tronconDrawStatus.textContent = message
    || `${vertices} sommet(s) provisoire(s) — double-cliquez pour terminer, puis ajustez si nécessaire.`;
  tronconDrawStatus.hidden = false;
  tronconDrawActions.hidden = false;
  cancelTronconDrawButton.hidden = false;
  restoreTronconDrawButton.hidden = true;
}

function restoreTronconDraft() {
  if (cancelledTronconGeometry?.type !== "LineString") {
    return;
  }
  const latLngs = cancelledTronconGeometry.coordinates.map(
    ([longitude, latitude]) => [latitude, longitude],
  );
  provisionalTronconLayer = L.polyline(latLngs, {
    color: "#1769aa",
    dashArray: "7 5",
    opacity: 1,
    weight: 6,
  }).addTo(map);
  provisionalTronconLayer.enableEdit(map);
  cancelledTronconGeometry = null;
  startTronconDrawButton.hidden = true;
  updateTronconDraftStatus("Dessin restauré localement — aucun enregistrement en base.");
}

function fillHeritageParentOptions(objectType, selectedId = null) {
  heritageParent.replaceChildren();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = objectType === "digue"
    ? "Choisir un système d’endiguement"
    : "Choisir une digue";
  heritageParent.append(empty);

  const parents = objectType === "digue"
    ? heritageData.systemes
    : heritageData.systemes.flatMap((systeme) => systeme.digues);
  parents.filter((parent) => parent.valid).forEach((parent) => {
    const option = document.createElement("option");
    option.value = parent.id;
    option.textContent = businessLabel(parent);
    heritageParent.append(option);
  });
  heritageParent.value = selectedId || "";
}

function creationContextParent(objectType) {
  if (
    objectType === "digue"
    && selectedHeritageObject?.kind === "Système d'endiguement"
  ) {
    return selectedHeritageObject.item.id;
  }
  if (objectType === "troncon" && selectedHeritageObject?.kind === "Digue") {
    return selectedHeritageObject.item.id;
  }
  return null;
}

async function loadDesordreTypes() {
  if (desordreTypes.length > 0) {
    return desordreTypes;
  }
  if (!desordreTypesLoadingPromise) {
    desordreTypesLoadingPromise = fetchJson("/api/referentiels/types-desordre")
      .then((data) => {
        desordreTypes = Array.isArray(data.types)
          ? data.types.filter((item) => item.valid)
          : [];
        return desordreTypes;
      })
      .finally(() => {
        desordreTypesLoadingPromise = null;
      });
  }
  return desordreTypesLoadingPromise;
}

async function loadDesordreTronconOptions() {
  if (desordreTronconOptions.length > 0) {
    return desordreTronconOptions;
  }
  if (!desordreTronconsLoadingPromise) {
    desordreTronconsLoadingPromise = fetchJson("/api/troncons/options")
      .then((data) => {
        desordreTronconOptions = Array.isArray(data.troncons)
          ? data.troncons.filter((item) => item.valid)
          : [];
        return desordreTronconOptions;
      })
      .finally(() => {
        desordreTronconsLoadingPromise = null;
      });
  }
  return desordreTronconsLoadingPromise;
}

async function loadTronconReperageOptions(tronconId) {
  if (!reperageOptionsByTroncon.has(String(tronconId))) {
    const options = await fetchJson(
      `/api/troncons/${encodeURIComponent(tronconId)}/reperage-options`,
    );
    reperageOptionsByTroncon.set(String(tronconId), options);
  }
  return reperageOptionsByTroncon.get(String(tronconId));
}

function fillBorneSelect(select, bornes, selectedId = null) {
  select.replaceChildren();
  bornes.forEach((borne) => {
    const option = document.createElement("option");
    option.value = borne.id;
    option.textContent = borne.libelle_affichage || businessLabel(borne, "Borne");
    select.append(option);
  });
  select.value = selectedId || bornes[0]?.id || "";
}

function fillTypeSelect(select, selectedId = null) {
  select.replaceChildren();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Sans type";
  select.append(empty);
  desordreTypes.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = businessLabel(item);
    select.append(option);
  });
  select.value = selectedId || "";
}

function fillDesordreReferenceOptions() {
  fillTypeSelect(desordreCreateTypeReference);
}

function fillTronconSelect(select, selectedIds = [], { multiple = true } = {}) {
  select.replaceChildren();
  if (!multiple) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Aucun tronçon";
    select.append(empty);
  }
  const selected = new Set(selectedIds.map(String));
  desordreTronconOptions.forEach((troncon) => {
    const option = document.createElement("option");
    option.value = troncon.id;
    option.textContent = `${businessLabel(troncon, "Tronçon sans libellé")} — ${troncon.digue_libelle || "Digue sans libellé"}`;
    option.selected = selected.has(String(troncon.id));
    select.append(option);
  });
}

function fillDesordreTronconOptions() {
  const selectedId = selectedHeritageObject?.kind === "Tronçon"
    ? String(selectedHeritageObject.item.id)
    : null;
  const point = desordreCreateGeometryType.value === "Point";
  desordreCreateTroncons.multiple = !point;
  desordreCreateTroncons.size = point ? 1 : 5;
  fillTronconSelect(
    desordreCreateTroncons,
    selectedId ? [selectedId] : [],
    { multiple: !point },
  );
}

function selectedDesordreMode() {
  return desordreEditorForm.elements["desordre-mode"].value || "map";
}

function availableDisorderModes(geometryType, tronconCount, reperageAvailable) {
  if (geometryType === "Polygon") return ["map"];
  const modes = ["map", "xy", "lonlat"];
  if (tronconCount === 1 && reperageAvailable) modes.push("bornage");
  return modes;
}

function setModeChoiceAvailability(choice, available) {
  choice.hidden = !available;
  const input = choice.querySelector("input");
  if (input) input.disabled = !available;
}

function creationBornageChoiceState(geometryType, tronconCount, reperageAvailable) {
  const visible = geometryType !== "Polygon" && tronconCount === 1;
  return { visible, enabled: visible && reperageAvailable };
}

function setModeChoiceState(choice, { visible, enabled }) {
  choice.hidden = !visible;
  const input = choice.querySelector("input");
  if (input) input.disabled = !enabled;
}

function renderDisorderModeChoices(reperageAvailable = false) {
  const geometryType = editorState.geometryType || desordreCreateGeometryType.value;
  const tronconCount = selectedDesordreTronconIds().length;
  const modes = availableDisorderModes(
    geometryType,
    tronconCount,
    reperageAvailable,
  );
  setModeChoiceAvailability(desordreXyChoice, modes.includes("xy"));
  setModeChoiceAvailability(desordreLonlatChoice, modes.includes("lonlat"));
  if (editorState.mode === "create") {
    setModeChoiceState(
      desordreBornageChoice,
      creationBornageChoiceState(geometryType, tronconCount, reperageAvailable),
    );
  } else {
    setModeChoiceAvailability(desordreBornageChoice, modes.includes("bornage"));
  }
  if (!modes.includes(selectedDesordreMode())) {
    desordreEditorForm.elements["desordre-mode"].value = "map";
    updateDisorderEditorControls();
  }
  return modes;
}

function updateLineCoordinateLabels(container, crs) {
  const labels = crs === "EPSG:4326"
    ? ["Longitude", "Latitude"] : ["X (EPSG:3950)", "Y (EPSG:3950)"];
  container.querySelectorAll(".line-axis-1").forEach((item) => {
    item.textContent = labels[0];
  });
  container.querySelectorAll(".line-axis-2").forEach((item) => {
    item.textContent = labels[1];
  });
}

function creationBornageDraftModified() {
  return desordreCreateDistanceStart.value !== ""
    || desordreCreateDistanceEnd.value !== "";
}

function desordreDraftVertexCount() {
  if (!provisionalDesordreLayer) {
    return 0;
  }
  const latLngs = provisionalDesordreLayer.getLatLngs?.();
  if (!Array.isArray(latLngs)) {
    return 1;
  }
  if (latLngs.length && Array.isArray(latLngs[0])) {
    return latLngs[0].length;
  }
  return latLngs.length;
}

function clearDesordreDraft({ keepRestorable = false } = {}) {
  if (provisionalDesordreLayer) {
    if (keepRestorable) {
      try {
        const candidate = provisionalDesordreLayer.toGeoJSON(false).geometry;
        const hasCoordinates = candidate?.type === "Point"
          ? candidate.coordinates?.length === 2
          : candidate?.coordinates?.length > 0;
        cancelledDesordreGeometry = hasCoordinates ? candidate : null;
      } catch (_error) {
        cancelledDesordreGeometry = null;
      }
    }
    provisionalDesordreLayer.disableEdit?.();
    map.removeLayer(provisionalDesordreLayer);
    provisionalDesordreLayer = null;
  }
  map.editTools?.stopDrawing?.();
  if (!keepRestorable) {
    cancelledDesordreGeometry = null;
  }
  const restorable = keepRestorable && cancelledDesordreGeometry !== null;
  desordreDrawStatus.hidden = true;
  desordreDrawActions.hidden = !restorable;
  restoreDesordreDrawButton.hidden = !restorable;
  startDesordreDrawButton.hidden = false;
}

function updateDesordreDraftStatus(message = null) {
  if (!provisionalDesordreLayer) {
    return;
  }
  const type = desordreCreateGeometryType.value;
  const count = desordreDraftVertexCount();
  desordreDrawStatus.textContent = message || (type === "Point"
    ? "Point provisoire — déplacez-le si nécessaire."
    : `${count} sommet(s) provisoire(s) — terminez puis ajustez le tracé.`);
  desordreDrawStatus.hidden = false;
  desordreDrawActions.hidden = false;
  cancelDesordreDrawButton.hidden = false;
  restoreDesordreDrawButton.hidden = true;
}

function layerFromDesordreGeometry(geometry) {
  if (geometry.type === "Point") {
    return L.marker([geometry.coordinates[1], geometry.coordinates[0]], {
      draggable: false,
      icon: pointIcon,
    });
  }
  if (geometry.type === "LineString") {
    return L.polyline(
      geometry.coordinates.map(([longitude, latitude]) => [latitude, longitude]),
      { color: "#a44f18", dashArray: "7 5", opacity: 1, weight: 6 },
    );
  }
  const outerRing = geometry.coordinates[0];
  const withoutClosingDuplicate = outerRing.slice(0, -1);
  return L.polygon(
    withoutClosingDuplicate.map(([longitude, latitude]) => [latitude, longitude]),
    { color: "#a44f18", dashArray: "7 5", fillOpacity: 0.18, weight: 4 },
  );
}

function restoreDesordreDraft() {
  if (!cancelledDesordreGeometry) {
    return;
  }
  provisionalDesordreLayer = layerFromDesordreGeometry(
    cancelledDesordreGeometry,
  ).addTo(map);
  provisionalDesordreLayer.enableEdit(map);
  cancelledDesordreGeometry = null;
  startDesordreDrawButton.hidden = true;
  updateDesordreDraftStatus("Dessin restauré localement — aucune écriture en base.");
}

function updateDisorderEditorControls() {
  const geometryType = editorState.geometryType || desordreCreateGeometryType.value;
  const point = geometryType === "Point";
  const line = geometryType === "LineString";
  const editing = editorState.mode === "edit";
  const method = geometryType === "Polygon" ? "map" : selectedDesordreMode();
  disorderFields.x.readOnly = method !== "xy";
  disorderFields.y.readOnly = method !== "xy";
  disorderFields.longitude.readOnly = method !== "lonlat";
  disorderFields.latitude.readOnly = method !== "lonlat";
  desordreCreateXy.hidden = !point || method !== "xy";
  desordreCreateLonlat.hidden = !point || method !== "lonlat";
  const lineCoordinateMode = line && ["xy", "lonlat"].includes(method);
  desordreCreateLineCoordinates.hidden = !lineCoordinateMode;
  if (lineCoordinateMode) {
    desordreCreateLineCrs.value = method === "lonlat" ? "EPSG:4326" : "EPSG:3950";
    updateLineCoordinateLabels(
      desordreCreateLineCoordinates,
      desordreCreateLineCrs.value,
    );
  }
  desordreCreateBornage.hidden = method !== "bornage";
  desordreCreateBornageEnd.hidden = point;
  desordreCreateGeometry.hidden = method !== "map";
  startDesordreDrawButton.hidden = editing && geometryType !== "Polygon";
  if (editing && geometryType !== "Polygon") {
    desordreDrawStatus.hidden = true;
    desordreDrawActions.hidden = true;
  }
  pointMapEditor.hidden = !editing || !point || method !== "map";
  lineMapEditor.hidden = !editing || !line || method !== "map";
  lineCoordinateActions.hidden = !editing || !line || !lineCoordinateMode;
  desordreBornageActions.hidden = !editing || method !== "bornage";
  pointBornageWarning.hidden = !editing || !point || method !== "bornage";
  lineBornageWarning.hidden = !editing || !line || method !== "bornage";
  saveLineBornageButton.hidden = !editing || !line || method !== "bornage";
  desordreLineDerived.hidden = !editing || (!point && !line);
  polygonRepresentativePoint.hidden = !editing || geometryType !== "Polygon";
  desordreCreateGeometryTitle.textContent = point
    ? "Placement cartographique"
    : `Dessin ${geometryType === "LineString" ? "de la ligne" : "du polygone"}`;
  desordreCreateGeometryHelp.textContent = geometryType === "Polygon"
    ? "Extension web du modèle historique : l'emprise reste libre et sans repérage éditable."
    : editing ? "La géométrie reste provisoire jusqu’à validation."
      : "Le dessin reste local jusqu’à « Créer ».";
  startDesordreDrawButton.textContent = point
    ? "Placer le Point"
    : geometryType === "LineString" ? "Dessiner la ligne" : "Dessiner le polygone";
}

async function refreshCreationReperageAvailability() {
  const requestVersion = ++creationReperageRequestVersion;
  creationReperageAvailable = false;
  if (creationReperageFeedbackActive) {
    desordreCreateMessage.textContent = "";
    desordreCreateMessage.classList.remove("error");
    creationReperageFeedbackActive = false;
  }
  const ids = selectedDesordreTronconIds();
  const geometryType = desordreCreateGeometryType.value;
  const eligible = availableDisorderModes(
    geometryType, ids.length, true,
  ).includes("bornage");
  renderDisorderModeChoices(false);
  if (!eligible) {
    return;
  }
  try {
    const options = await loadTronconReperageOptions(ids[0]);
    if (requestVersion !== creationReperageRequestVersion
        || desordreCreateGeometryType.value !== geometryType
        || selectedDesordreTronconIds().length !== 1
        || selectedDesordreTronconIds()[0] !== ids[0]) {
      return;
    }
    if (!options.systeme_reperage_id || options.bornes.length === 0) {
      return;
    }
    creationReperageAvailable = true;
    renderDisorderModeChoices(true);
    fillBorneSelect(desordreCreateBorneStart, options.bornes);
    fillBorneSelect(desordreCreateBorneEnd, options.bornes);
  } catch (error) {
    if (requestVersion === creationReperageRequestVersion) {
      creationReperageAvailable = false;
      renderDisorderModeChoices(false);
      desordreCreateMessage.textContent =
        "Le repérage n’est pas disponible pour le tronçon sélectionné.";
      desordreCreateMessage.classList.remove("error");
      creationReperageFeedbackActive = true;
    }
  }
}

async function openDesordreCreation() {
  await Promise.all([
    loadHeritageTree(), loadDesordreTypes(), loadDesordreTronconOptions(),
  ]);
  clearTronconDraft();
  clearDesordreDraft();
  setDisorderEditorState("create", "Point");
  lastServerFeature = null;
  requestedDesordreId = null;
  editorObjectTitle.textContent = "Nouveau désordre";
  editorObjectSubtitle.textContent = "Brouillon local — aucune écriture avant Créer";
  editorTabs.hidden = true;
  generalTab.hidden = false;
  observationsTab.hidden = true;
  heritageObjectForm.hidden = true;
  desordreEditorForm.reset();
  creationReperageAvailable = false;
  updateLineCoordinateLabels(desordreCreateLineCoordinates, desordreCreateLineCrs.value);
  desordreEditorForm.hidden = false;
  desordreCreateIdField.hidden = true;
  desordreCreateValid.checked = true;
  desordreCreateGeometryType.disabled = false;
  desordreCreateId.disabled = false;
  submitDesordreCreateButton.textContent = "Créer";
  cancelDesordreCreateButton.textContent = "Annuler";
  validateDesordreDrawButton.hidden = true;
  polygonRepresentativePoint.hidden = true;
  desordreCreateActions.hidden = false;
  Array.from(desordreEditorForm.elements).forEach((element) => {
    element.disabled = false;
  });
  fillDesordreReferenceOptions();
  fillDesordreTronconOptions();
  lastAcceptedCreationTronconIds = selectedDesordreTronconIds();
  previousDesordreGeometryType = "Point";
  desordreCreateMessage.textContent = "";
  desordreCreateMessage.classList.remove("error");
  updateDisorderEditorControls();
  renderDisorderModeChoices(false);
  await refreshCreationReperageAvailability();
  editorPanel.hidden = false;
  desordreCreateDesignation.focus();
}

function closeDesordreDraft() {
  clearDesordreDraft();
  desordreEditorForm.reset();
  desordreEditorForm.hidden = true;
  editorPanel.hidden = true;
  editorState = { mode: "edit", objectType: null };
}

async function openHeritageCreation(objectType) {
  if (objectType === "desordre") {
    await openDesordreCreation();
    return;
  }
  const configuration = heritageCreationTypes[objectType];
  if (!configuration || creationRequestInFlight) {
    return;
  }
  if (lineRequestInFlight || graphicRequestInFlight) {
    statusElement.textContent = "Attendez la réponse PostgreSQL en cours.";
    statusElement.classList.add("error");
    return;
  }
  if (lineEditActive) {
    stopLineEdit({ restore: true });
  }
  if (graphicEditActive) {
    stopGraphicEdit({ restore: true });
  }
  await loadHeritageTree();
  clearTronconDraft();
  editorState = { mode: "create", objectType };
  lastServerFeature = null;
  requestedDesordreId = null;
  editorObjectTitle.textContent = configuration.draftTitle;
  editorObjectSubtitle.textContent = "Brouillon local — aucune écriture avant Créer";
  editorTabs.hidden = true;
  generalTab.hidden = false;
  observationsTab.hidden = true;
  heritageObjectForm.hidden = false;
  desordreEditorForm.hidden = true;
  heritageObjectIdField.hidden = true;
  heritageObjectId.value = "";
  heritageObjectLabel.value = "";
  heritageObjectLabel.disabled = false;
  heritageObjectValid.checked = true;
  heritageObjectValid.disabled = false;
  heritageCreateActions.hidden = false;
  heritageCreateMessage.textContent = "";
  heritageCreateMessage.classList.remove("error");
  tronconCreateGeometry.hidden = objectType !== "troncon";
  heritageParentField.hidden = objectType === "systeme";
  if (objectType !== "systeme") {
    heritageParentLabel.textContent = objectType === "digue"
      ? "Système d’endiguement parent"
      : "Digue parente";
    heritageParent.disabled = false;
    fillHeritageParentOptions(objectType, creationContextParent(objectType));
  } else {
    heritageParent.disabled = true;
  }
  editorPanel.hidden = false;
  heritageObjectLabel.focus();
}

function closeHeritageDraft() {
  clearTronconDraft();
  heritageObjectForm.reset();
  heritageObjectForm.hidden = true;
  editorPanel.hidden = true;
  editorState = { mode: "edit", objectType: null };
}

function selectCreatedHeritageObject(kind, identifier) {
  const button = Array.from(heritageTree.querySelectorAll(".tree-name")).find(
    (candidate) => candidate.dataset.objectKind === kind
      && candidate.dataset.objectId === String(identifier),
  );
  button?.click();
}

function addCreatedObjectToHeritage(objectType, created) {
  if (objectType === "systeme") {
    heritageData.systemes.push({ ...created, digues: created.digues || [] });
  } else if (objectType === "digue") {
    const systeme = heritageData.systemes.find(
      (item) => String(item.id) === String(created.systeme_endiguement_id),
    );
    systeme?.digues.push({ ...created, troncons: created.troncons || [] });
  } else {
    const properties = created.properties || {};
    const digue = heritageData.systemes.flatMap(
      (systeme) => systeme.digues,
    ).find((item) => String(item.id) === String(properties.digue_id));
    digue?.troncons.push(properties);
  }
  renderHeritageTree(heritageData);
  setHeritagePanelOpen(true);
  const kind = heritageCreationTypes[objectType].title;
  const identifier = objectType === "troncon" ? created.properties.id : created.id;
  selectCreatedHeritageObject(kind, identifier);
}

function showCreatedObject(objectType, created) {
  const values = objectType === "troncon" ? created.properties : created;
  editorState = { mode: "edit", objectType };
  editorObjectTitle.textContent = heritageCreationTypes[objectType].title;
  editorObjectSubtitle.textContent = "État relu depuis PostgreSQL";
  heritageObjectIdField.hidden = false;
  heritageObjectId.value = values.id;
  heritageObjectLabel.value = values.libelle || "";
  heritageObjectLabel.disabled = true;
  heritageObjectValid.checked = Boolean(values.valid);
  heritageObjectValid.disabled = true;
  heritageParent.disabled = true;
  heritageCreateActions.hidden = true;
  if (objectType === "troncon") {
    tronconDrawStatus.textContent = `${values.nombre_sommets} sommet(s) relu(s) depuis PostgreSQL.`;
    tronconDrawStatus.hidden = false;
    tronconDrawActions.hidden = true;
    startTronconDrawButton.hidden = true;
  }
  heritageCreateMessage.textContent = "Objet créé et relu avec succès.";
  heritageCreateMessage.classList.remove("error");
}

function configureTronconLayer(feature, layer) {
  tronconLayersById.set(String(feature.properties.id), layer);
  layer.bindPopup(
    popupContent(feature.properties || {}, [
      ["Tronçon", "libelle"],
      ["Digue", "digue_libelle"],
      ["Identifiant", "id"],
    ]),
  );
}

function addCreatedTronconToMap(feature) {
  const layer = L.geoJSON(feature, {
    style: { color: "#39735a", opacity: 0.85, weight: 4 },
    onEachFeature: configureTronconLayer,
  });
  layer.eachLayer((item) => tronconsGeoJsonLayer.addLayer(item));
}

createMenuButton.addEventListener("click", () => {
  setToolsMenuOpen(false);
  setCreateMenuOpen(createMenuList.hidden);
});

createMenuList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-create-type]");
  if (!button) {
    return;
  }
  setCreateMenuOpen(false);
  openHeritageCreation(button.dataset.createType);
});

toolsMenuButton.addEventListener("click", () => {
  setCreateMenuOpen(false);
  setToolsMenuOpen(toolsMenuList.hidden);
});

toolsMenuList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-tool-action]");
  if (!button) {
    return;
  }
  setToolsMenuOpen(false);
  if (button.dataset.toolAction === "territoire-administratif") {
    openTerritoireModal();
  }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".create-menu")) {
    setCreateMenuOpen(false);
  }
  if (!event.target.closest(".tools-menu")) {
    setToolsMenuOpen(false);
  }
});

territoireForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (territoireImportPending) {
    return;
  }
  submitTerritoireImport().catch((error) => {
    console.error("Import du territoire administratif impossible", error);
    territoireMessage.textContent = error.message;
    territoireMessage.classList.add("error");
    setTerritoireImportPending(false);
  });
});

closeTerritoireModalButton.addEventListener("click", closeTerritoireModal);
cancelTerritoireModalButton.addEventListener("click", closeTerritoireModal);
territoireModal.addEventListener("click", (event) => {
  if (event.target === territoireModal) {
    closeTerritoireModal();
  }
});

startTronconDrawButton.addEventListener("click", () => {
  if (editorState.mode !== "create" || editorState.objectType !== "troncon") {
    return;
  }
  clearTronconDraft();
  provisionalTronconLayer = map.editTools.startPolyline(undefined, {
    color: "#1769aa",
    dashArray: "7 5",
    opacity: 1,
    weight: 6,
  });
  startTronconDrawButton.hidden = true;
  updateTronconDraftStatus("Cliquez pour poser les sommets, puis double-cliquez pour terminer.");
});

cancelTronconDrawButton.addEventListener("click", () => {
  clearTronconDraft({ keepRestorable: true });
  tronconDrawStatus.textContent = "Dessin annulé localement ; vous pouvez le restaurer.";
  tronconDrawStatus.hidden = false;
});

restoreTronconDrawButton.addEventListener("click", restoreTronconDraft);

map.on("editable:drawing:end", (event) => {
  if (event.layer === provisionalTronconLayer) {
    provisionalTronconLayer.enableEdit(map);
    updateTronconDraftStatus("Dessin provisoire terminé — tous les sommets restent éditables.");
  } else if (event.layer === provisionalDesordreLayer) {
    provisionalDesordreLayer.enableEdit(map);
    updateDesordreDraftStatus("Géométrie provisoire terminée — elle reste éditable.");
  }
});

cancelCreateButton.addEventListener("click", closeHeritageDraft);

heritageObjectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (editorState.mode !== "create" || creationRequestInFlight) {
    return;
  }
  const objectType = editorState.objectType;
  const configuration = heritageCreationTypes[objectType];
  const payload = {
    libelle: heritageObjectLabel.value,
    valid: heritageObjectValid.checked,
  };
  if (objectType === "digue") {
    payload.systeme_endiguement_id = heritageParent.value;
  } else if (objectType === "troncon") {
    if (!provisionalTronconLayer) {
      heritageCreateMessage.textContent = "Dessinez ou restaurez une LineString avant de créer le tronçon.";
      heritageCreateMessage.classList.add("error");
      return;
    }
    if (provisionalTronconLayer.editor?.drawing?.()) {
      heritageCreateMessage.textContent = "Terminez le dessin par un double-clic avant validation.";
      heritageCreateMessage.classList.add("error");
      return;
    }
    payload.digue_id = heritageParent.value;
    payload.geometry = provisionalTronconLayer.toGeoJSON(false).geometry;
  }
  creationRequestInFlight = true;
  submitCreateButton.disabled = true;
  cancelCreateButton.disabled = true;
  closeEditorButton.disabled = true;
  heritageCreateMessage.textContent = "Création et relecture PostgreSQL…";
  heritageCreateMessage.classList.remove("error");
  try {
    const created = await fetchJson(configuration.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (objectType === "troncon") {
      clearTronconDraft();
      addCreatedTronconToMap(created);
    }
    addCreatedObjectToHeritage(objectType, created);
    showCreatedObject(objectType, created);
  } catch (error) {
    console.error(`Création ${objectType} impossible`, error);
    heritageCreateMessage.textContent = `Création refusée : ${error.message}`;
    heritageCreateMessage.classList.add("error");
  } finally {
    creationRequestInFlight = false;
    submitCreateButton.disabled = false;
    cancelCreateButton.disabled = false;
    closeEditorButton.disabled = false;
  }
});

function desordreDraftHasNumericCoordinates() {
  return [
    desordreCreateX.value,
    desordreCreateY.value,
    desordreCreateLongitude.value,
    desordreCreateLatitude.value,
  ].some((value) => value !== "");
}

desordreCreateGeometryType.addEventListener("change", () => {
  if (provisionalDesordreLayer || desordreDraftHasNumericCoordinates()) {
    desordreCreateGeometryType.value = previousDesordreGeometryType;
    desordreCreateMessage.textContent =
      "Annulez le dessin ou effacez les coordonnées avant de changer de type géométrique.";
    desordreCreateMessage.classList.add("error");
    return;
  }
  previousDesordreGeometryType = desordreCreateGeometryType.value;
  editorState.geometryType = desordreCreateGeometryType.value;
  cancelledDesordreGeometry = null;
  const selectedIds = selectedDesordreTronconIds();
  const point = desordreCreateGeometryType.value === "Point";
  desordreCreateTroncons.multiple = !point;
  desordreCreateTroncons.size = point ? 1 : 5;
  fillTronconSelect(
    desordreCreateTroncons,
    point ? selectedIds.slice(0, 1) : selectedIds,
    { multiple: !point },
  );
  lastAcceptedCreationTronconIds = selectedDesordreTronconIds();
  updateDisorderEditorControls();
  creationReperageAvailable = false;
  renderDisorderModeChoices(false);
  refreshCreationReperageAvailability();
});

desordreCreateLineCrs.addEventListener("change", () => {
  updateLineCoordinateLabels(desordreCreateLineCoordinates, desordreCreateLineCrs.value);
});

desordreCreateTroncons.addEventListener("change", () => {
  if (editorState.mode !== "create") return;
  const ids = selectedDesordreTronconIds();
  const geometryType = desordreCreateGeometryType.value;
  const method = geometryType === "Point"
    ? selectedDesordreMode() : geometryType === "LineString"
      ? selectedDesordreMode() : "map";
  if (method === "bornage" && ids.length !== 1 && creationBornageDraftModified()) {
    fillTronconSelect(
      desordreCreateTroncons,
      lastAcceptedCreationTronconIds,
      { multiple: geometryType !== "Point" },
    );
    desordreCreateMessage.textContent =
      "Le bornage exige exactement un tronçon. Changez d’abord de mode pour modifier les rattachements.";
    desordreCreateMessage.classList.add("error");
    return;
  }
  lastAcceptedCreationTronconIds = ids;
  creationReperageAvailable = false;
  renderDisorderModeChoices(false);
  refreshCreationReperageAvailability();
});

startDesordreDrawButton.addEventListener("click", () => {
  if (editorState.mode === "edit" && editorState.geometryType === "Polygon") {
    if (!activePolygonLayer?.enableEdit) return;
    polygonEditActive = true;
    activePolygonLayer.enableEdit(map);
    startDesordreDrawButton.hidden = true;
    desordreDrawActions.hidden = false;
    cancelDesordreDrawButton.hidden = false;
    restoreDesordreDrawButton.hidden = true;
    validateDesordreDrawButton.hidden = false;
    desordreDrawStatus.textContent = "Polygone provisoire — validez ou annulez.";
    return;
  }
  if (editorState.mode !== "create" || editorState.objectType !== "desordre") {
    return;
  }
  clearDesordreDraft();
  const geometryType = desordreCreateGeometryType.value;
  if (geometryType === "Point") {
    provisionalDesordreLayer = map.editTools.startMarker(undefined, {
      icon: pointIcon,
    });
  } else if (geometryType === "LineString") {
    provisionalDesordreLayer = map.editTools.startPolyline(undefined, {
      color: "#a44f18", dashArray: "7 5", opacity: 1, weight: 6,
    });
  } else {
    provisionalDesordreLayer = map.editTools.startPolygon(undefined, {
      color: "#a44f18", dashArray: "7 5", fillOpacity: 0.18, weight: 4,
    });
  }
  startDesordreDrawButton.hidden = true;
  updateDesordreDraftStatus(
    geometryType === "Point"
      ? "Cliquez pour placer le Point."
      : "Cliquez pour poser les sommets, puis double-cliquez pour terminer.",
  );
});

cancelDesordreDrawButton.addEventListener("click", () => {
  if (polygonEditActive) {
    activePolygonLayer.disableEdit();
    polygonEditActive = false;
    const geometry = lastServerFeature.geometry.coordinates.map((ring) => ring
      .slice(0, -1)
      .map(([longitude, latitude]) => [latitude, longitude]));
    activePolygonLayer.setLatLngs(geometry);
    renderPolygonServerFeature(lastServerFeature, activePolygonLayer);
    return;
  }
  clearDesordreDraft({ keepRestorable: true });
  desordreDrawStatus.textContent = cancelledDesordreGeometry
    ? "Dessin annulé localement ; vous pouvez le restaurer ou changer de type."
    : "Dessin vide annulé localement ; vous pouvez recommencer.";
  desordreDrawStatus.hidden = false;
});

restoreDesordreDrawButton.addEventListener("click", restoreDesordreDraft);
cancelDesordreCreateButton.addEventListener("click", () => {
  if (editorState.mode === "edit" && editorState.geometryType === "Polygon") {
    renderPolygonServerFeature(lastServerFeature, activePolygonLayer);
    return;
  }
  if (editorState.mode === "edit") {
    if (graphicEditActive) {
      stopGraphicEdit({ restore: true });
    } else {
      restoreLastServerState();
    }
    return;
  }
  closeDesordreDraft();
});

validateDesordreDrawButton.addEventListener("click", async () => {
  if (!polygonEditActive || !activePolygonLayer) return;
  const geometry = activePolygonLayer.toGeoJSON(false).geometry;
  try {
    const feature = await fetchJson(
      `/api/desordres/${encodeURIComponent(lastServerFeature.properties.id)}/geometry`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ geometry }) },
    );
    activePolygonLayer.disableEdit();
    polygonEditActive = false;
    updatePolygonLayer(feature);
    renderPolygonServerFeature(feature, activePolygonLayer);
    desordreCreateMessage.textContent =
      "Polygone et point représentatif recalculé relus depuis PostgreSQL.";
  } catch (error) {
    desordreCreateMessage.textContent = `Géométrie refusée : ${error.message}`;
    desordreCreateMessage.classList.add("error");
  }
});

function selectedDesordreTronconIds() {
  return Array.from(desordreCreateTroncons.selectedOptions).map(
    (option) => option.value,
  ).filter(Boolean);
}

function buildDesordreCreationPayload() {
  const payload = {
    designation: optionalPayloadValue(desordreCreateDesignation.value),
    type_desordre_id: optionalPayloadValue(desordreCreateTypeReference.value),
    commentaire: optionalPayloadValue(desordreCreateCommentaire.value),
    date_debut: optionalPayloadValue(desordreCreateDateDebut.value),
    date_fin: optionalPayloadValue(desordreCreateDateFin.value),
    valid: desordreCreateValid.checked,
    troncon_ids: selectedDesordreTronconIds(),
  };
  const geometryType = desordreCreateGeometryType.value;
  payload.geometry_type = geometryType;
  const method = geometryType === "Point"
    ? selectedDesordreMode()
    : geometryType === "LineString" ? selectedDesordreMode() : "map";
  if (geometryType === "Point" && method === "xy") {
    if (desordreCreateX.value === "" || desordreCreateY.value === "") {
      throw new Error("X et Y doivent être renseignés ensemble.");
    }
    payload.coord_x_3950 = Number(desordreCreateX.value);
    payload.coord_y_3950 = Number(desordreCreateY.value);
    return payload;
  }
  if (geometryType === "LineString" && ["xy", "lonlat"].includes(method)) {
    const values = [
      desordreCreateLineStart1.value, desordreCreateLineStart2.value,
      desordreCreateLineEnd1.value, desordreCreateLineEnd2.value,
    ];
    if (values.some((value) => value === "")) {
      throw new Error("Les quatre coordonnées de début/fin sont obligatoires.");
    }
    payload.line_endpoints = {
      crs: desordreCreateLineCrs.value,
      debut: [Number(values[0]), Number(values[1])],
      fin: [Number(values[2]), Number(values[3])],
    };
    return payload;
  }
  if (method === "bornage") {
    const modes = availableDisorderModes(
      geometryType,
      selectedDesordreTronconIds().length,
      creationReperageAvailable,
    );
    if (!modes.includes("bornage")) {
      throw new Error("Le bornage exige exactement un tronçon exploitable.");
    }
    const startDistance = Number(desordreCreateDistanceStart.value);
    const endDistance = Number(desordreCreateDistanceEnd.value);
    if (!desordreCreateBorneStart.value || !Number.isFinite(startDistance)) {
      throw new Error("Le bornage de début est incomplet.");
    }
    payload.reperage = {
      borne_debut_id: desordreCreateBorneStart.value,
      distance_debut_m: startDistance,
      position_debut_relative: desordreCreateSenseStart.value,
    };
    if (geometryType === "LineString") {
      if (!desordreCreateBorneEnd.value || !Number.isFinite(endDistance)) {
        throw new Error("Le bornage de fin est incomplet.");
      }
      Object.assign(payload.reperage, {
        borne_fin_id: desordreCreateBorneEnd.value,
        distance_fin_m: endDistance,
        position_fin_relative: desordreCreateSenseEnd.value,
      });
    }
    return payload;
  }
  if (geometryType === "Point" && method === "lonlat") {
    if (
      desordreCreateLongitude.value === ""
      || desordreCreateLatitude.value === ""
    ) {
      throw new Error("Longitude et latitude doivent être renseignées ensemble.");
    }
    payload.longitude_4326 = Number(desordreCreateLongitude.value);
    payload.latitude_4326 = Number(desordreCreateLatitude.value);
    return payload;
  }
  if (!provisionalDesordreLayer) {
    throw new Error("Dessinez ou restaurez la géométrie avant de créer le désordre.");
  }
  if (provisionalDesordreLayer.editor?.drawing?.()) {
    throw new Error("Terminez le dessin avant validation.");
  }
  payload.geometry = provisionalDesordreLayer.toGeoJSON(false).geometry;
  return payload;
}

function configureDesordreLayer(feature, layer) {
  const identifier = String(feature.properties.id);
  desordreLayersById.set(identifier, layer);
  layer.bindPopup(popupContent(feature.properties || {}, [
    ["Désordre", "designation"],
    ["Type", "type_desordre_libelle"],
    ["Géométrie", "type_geometrie"],
    ["Identifiant", "id"],
  ]));
  if (feature.geometry?.type === "Point") {
    layer.on("click", () => openPointEditor(feature.properties.id, layer));
    layer.on("dragstart", () => {
      if (graphicEditActive && layer === activePointLayer) {
        mapPositionStatus.textContent = "Déplacement en cours — position non enregistrée.";
      }
    });
    layer.on("drag", () => {
      if (!graphicEditActive || layer !== activePointLayer) {
        return;
      }
      const position = layer.getLatLng();
      disorderFields.longitude.value = coordinate(position.lng, 6);
      disorderFields.latitude.value = coordinate(position.lat, 6);
    });
    layer.on("dragend", () => {
      if (!graphicEditActive || layer !== activePointLayer) {
        return;
      }
      provisionalLatLng = layer.getLatLng();
      disorderFields.longitude.value = coordinate(provisionalLatLng.lng, 6);
      disorderFields.latitude.value = coordinate(provisionalLatLng.lat, 6);
      validateMapPositionButton.disabled = false;
      mapPositionStatus.textContent = "Position provisoire — validez ou annulez le déplacement.";
    });
  } else if (feature.geometry?.type === "LineString") {
    layer.on("click", () => openLineEditor(feature.properties.id, layer));
  } else if (feature.geometry?.type === "Polygon") {
    layer.on("click", () => openPolygonEditor(feature.properties.id, layer));
  }
}

function addCreatedDesordreToMap(feature) {
  const collection = L.geoJSON(feature, {
    style: { color: "#e4772f", fillOpacity: 0.22, opacity: 0.95, weight: 5 },
    pointToLayer(_feature, latlng) {
      return L.marker(latlng, { draggable: false, icon: pointIcon });
    },
    onEachFeature: configureDesordreLayer,
  });
  let createdLayer = null;
  collection.eachLayer((layer) => {
    const target = feature.geometry.type === "Point"
      ? desordrePointLayer
      : feature.geometry.type === "LineString" ? desordreLineLayer : desordrePolygonLayer;
    target.addLayer(layer);
    createdLayer = layer;
  });
  return createdLayer;
}

function renderPolygonServerFeature(feature, layer = activePolygonLayer) {
  const properties = feature.properties;
  activePolygonLayer = layer;
  lastServerFeature = feature;
  prepareDisorderEditorForEdit("Polygon", properties.id);
  editorState.data = feature;
  editorObjectTitle.textContent = "Désordre polygonal";
  editorObjectSubtitle.textContent = "État relu depuis PostgreSQL — géométrie cartographique";
  editorTabs.hidden = false;
  showEditorTab("general");
  heritageObjectForm.hidden = true;
  desordreEditorForm.hidden = false;
  desordreCreateIdField.hidden = false;
  desordreCreateId.value = properties.id;
  desordreCreateDesignation.value = properties.designation || "";
  desordreCreateTypeReference.value = properties.type_desordre_id || "";
  desordreCreateCommentaire.value = properties.commentaire || "";
  desordreCreateDateDebut.value = properties.date_debut || "";
  desordreCreateDateFin.value = properties.date_fin || "";
  desordreCreateValid.checked = Boolean(properties.valid);
  desordreCreateGeometryType.value = "Polygon";
  Array.from(desordreCreateTroncons.options).forEach((option) => {
    option.selected = (properties.troncon_ids || []).map(String).includes(
      String(option.value),
    );
  });
  desordreEditorForm.elements["desordre-mode"].value = "map";
  renderDisorderModeChoices(false);
  updateDisorderEditorControls();
  startDesordreDrawButton.hidden = false;
  startDesordreDrawButton.textContent = "Modifier le polygone sur la carte";
  desordreDrawStatus.textContent = "Géométrie relue depuis PostgreSQL.";
  desordreDrawStatus.hidden = false;
  desordreDrawActions.hidden = true;
  validateDesordreDrawButton.hidden = true;
  desordreCreateActions.hidden = false;
  desordreCreateGeometryType.disabled = true;
  desordreCreateId.disabled = true;
  submitDesordreCreateButton.textContent = "Enregistrer";
  cancelDesordreCreateButton.textContent = "Annuler les modifications";
  polygonRepresentativePoint.hidden = false;
  polygonRepresentativeX.value = coordinate(properties.coord_x_3950, 2);
  polygonRepresentativeY.value = coordinate(properties.coord_y_3950, 2);
  polygonRepresentativeLongitude.value = coordinate(properties.longitude_4326, 6);
  polygonRepresentativeLatitude.value = coordinate(properties.latitude_4326, 6);
  desordreCreateMessage.textContent =
    "Le point représentatif est dérivé et non modifiable.";
  desordreCreateMessage.classList.remove("error");
  editorPanel.hidden = false;
}

desordreEditorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (creationRequestInFlight) {
    return;
  }
  if (editorState.mode === "edit" && editorState.geometryType === "Polygon") {
    creationRequestInFlight = true;
    try {
      const feature = await fetchJson(
        `/api/desordres/${encodeURIComponent(lastServerFeature.properties.id)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            designation: optionalPayloadValue(desordreCreateDesignation.value),
            type_desordre_id: optionalPayloadValue(desordreCreateTypeReference.value),
            commentaire: optionalPayloadValue(desordreCreateCommentaire.value),
            date_debut: optionalPayloadValue(desordreCreateDateDebut.value),
            date_fin: optionalPayloadValue(desordreCreateDateFin.value),
            valid: desordreCreateValid.checked,
            troncon_ids: selectedValues(desordreCreateTroncons),
          }),
        },
      );
      renderPolygonServerFeature(feature, activePolygonLayer);
      if (activePolygonLayer) activePolygonLayer.feature = feature;
      desordreCreateMessage.textContent = "Informations relues depuis PostgreSQL.";
    } catch (error) {
      desordreCreateMessage.textContent = `Enregistrement refusé : ${error.message}`;
      desordreCreateMessage.classList.add("error");
    } finally {
      creationRequestInFlight = false;
    }
    return;
  }
  if (editorState.mode === "edit" && editorState.geometryType === "LineString") {
    saveLineRequest("", {
      designation: optionalPayloadValue(disorderFields.designation.value),
      type_desordre_id: optionalPayloadValue(disorderFields.type.value),
      commentaire: optionalPayloadValue(disorderFields.commentaire.value),
      date_debut: optionalPayloadValue(disorderFields.dateDebut.value),
      date_fin: optionalPayloadValue(disorderFields.dateFin.value),
      valid: disorderFields.valid.checked,
      troncon_ids: selectedValues(lineEditTroncons),
    }, "Informations et rattachements relus depuis PostgreSQL.");
    return;
  }
  if (editorState.mode === "edit" && editorState.geometryType === "Point") {
    await savePointDesordre();
    return;
  }
  if (editorState.mode !== "create") return;
  let payload;
  try {
    payload = buildDesordreCreationPayload();
  } catch (error) {
    desordreCreateMessage.textContent = error.message;
    desordreCreateMessage.classList.add("error");
    return;
  }
  creationRequestInFlight = true;
  submitDesordreCreateButton.disabled = true;
  cancelDesordreCreateButton.disabled = true;
  closeEditorButton.disabled = true;
  desordreCreateMessage.textContent = "Création et relecture PostgreSQL…";
  desordreCreateMessage.classList.remove("error");
  try {
    const feature = await fetchJson("/api/desordres", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    clearDesordreDraft();
    const layer = addCreatedDesordreToMap(feature);
    if (feature.geometry.type === "Point") {
      await openPointEditor(feature.properties.id, layer);
    } else if (feature.geometry.type === "LineString") {
      await openLineEditor(feature.properties.id, layer);
    } else {
      renderPolygonServerFeature(feature, layer);
    }
  } catch (error) {
    console.error("Création du désordre impossible", error);
    desordreCreateMessage.textContent = `Création refusée : ${error.message}`;
    desordreCreateMessage.classList.add("error");
  } finally {
    creationRequestInFlight = false;
    submitDesordreCreateButton.disabled = false;
    cancelDesordreCreateButton.disabled = false;
    closeEditorButton.disabled = false;
  }
});

function generalEditInProgress() {
  return lineEditActive || graphicEditActive || polygonEditActive
    || selectedDesordreMode() !== "map"
    || (editorState.geometryType === "Point" && textFieldsChanged());
}

generalTabButton.addEventListener("click", () => showEditorTab("general"));

observationsTabButton.addEventListener("click", () => {
  if (generalEditInProgress()) {
    const messageElement = lineEditActive ? lineEditorMessage : editorMessage;
    messageElement.textContent =
      "Enregistrez ou annulez l’édition en cours avant de consulter les observations.";
    messageElement.classList.add("error");
    return;
  }
  showEditorTab("observations");
});

backToObservationsButton.addEventListener("click", () => {
  closePhotoLightbox();
  observationDetailView.hidden = true;
  observationsListView.hidden = false;
});

closeLightboxButton.addEventListener("click", closePhotoLightbox);
previousPhotoButton.addEventListener("click", () => navigatePhoto(-1));
nextPhotoButton.addEventListener("click", () => navigatePhoto(1));
photoLightbox.addEventListener("click", (event) => {
  if (event.target === photoLightbox) {
    closePhotoLightbox();
  }
});
document.addEventListener("keydown", (event) => {
  if (photoLightbox.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closePhotoLightbox();
  } else if (event.key === "ArrowLeft") {
    navigatePhoto(-1);
  } else if (event.key === "ArrowRight") {
    navigatePhoto(1);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !territoireModal.hidden) {
    closeTerritoireModal();
  }
});

function updateCoordinateInputs() {
  const family = selectedDesordreMode();
  const bornageAuthority = editorState.mode === "edit" && family === "bornage";
  disorderFields.x.readOnly = family !== "xy";
  disorderFields.y.readOnly = family !== "xy";
  disorderFields.longitude.readOnly = family !== "lonlat";
  disorderFields.latitude.readOnly = family !== "lonlat";
  bornageFields.hidden = family !== "bornage";
  disorderFields.designation.disabled = bornageAuthority || graphicEditActive;
  disorderFields.commentaire.disabled = bornageAuthority || graphicEditActive;
  disorderFields.type.disabled = bornageAuthority || graphicEditActive;
  disorderFields.dateDebut.disabled = bornageAuthority || graphicEditActive;
  disorderFields.dateFin.disabled = bornageAuthority || graphicEditActive;
  disorderFields.valid.disabled = bornageAuthority || graphicEditActive;
  pointEditTroncon.disabled = bornageAuthority || graphicEditActive;
  startMapPositionButton.disabled = family !== "map";
  updateDisorderEditorControls();
}

function clearCoordinateAuthority() {
  Array.from(desordreEditorForm.elements["desordre-mode"]).forEach((radio) => {
    radio.checked = radio.value === "map";
  });
  updateCoordinateInputs();
}

function textFieldsChanged() {
  return initialFormValues && (
    disorderFields.designation.value !== initialFormValues.designation
    || disorderFields.commentaire.value !== initialFormValues.commentaire
    || disorderFields.type.value !== initialFormValues.type_desordre_id
    || disorderFields.dateDebut.value !== initialFormValues.date_debut
    || disorderFields.dateFin.value !== initialFormValues.date_fin
    || disorderFields.valid.checked !== initialFormValues.valid
    || pointEditTroncon.value !== initialFormValues.troncon_id
  );
}

function setGraphicControls(active) {
  graphicEditActive = active;
  startMapPositionButton.hidden = active;
  mapPositionActions.hidden = !active;
  saveButton.disabled = active;
  disorderFields.designation.disabled = active || selectedDesordreMode() === "bornage";
  disorderFields.commentaire.disabled = active || selectedDesordreMode() === "bornage";
  disorderFields.type.disabled = active || selectedDesordreMode() === "bornage";
  disorderFields.dateDebut.disabled = active || selectedDesordreMode() === "bornage";
  disorderFields.dateFin.disabled = active || selectedDesordreMode() === "bornage";
  disorderFields.valid.disabled = active || selectedDesordreMode() === "bornage";
  pointEditTroncon.disabled = active || selectedDesordreMode() === "bornage";
  Array.from(desordreEditorForm.elements["desordre-mode"]).forEach((radio) => {
    radio.disabled = active || (
      radio.value === "bornage" && !currentReperage?.disponible
    );
  });
  if (activePointLayer?._icon) {
    activePointLayer._icon.classList.toggle("position-editing", active);
  }
}

function renderReperage(reperage) {
  currentReperage = reperage || {
    nombre_troncons: 0,
    disponible: false,
    motif_indisponibilite: "Aucun état de repérage disponible.",
    bornes: [],
  };
  const modes = availableDisorderModes(
    "Point", currentReperage.nombre_troncons, currentReperage.disponible,
  );
  bornageModeRadio.disabled = !modes.includes("bornage");
  desordreBornageChoice.hidden = !modes.includes("bornage");
  reperageFields.borne.replaceChildren();
  const bornes = Array.isArray(currentReperage.bornes)
    ? currentReperage.bornes
    : [];
  bornes.forEach((borne) => {
    const option = document.createElement("option");
    option.value = borne.id;
    option.textContent = borne.libelle_affichage || borne.libelle
      || (showUuid ? borne.id : "Borne");
    reperageFields.borne.append(option);
  });
  if (
    currentReperage.borne_debut_id
    && !bornes.some((borne) => borne.id === currentReperage.borne_debut_id)
  ) {
    const option = document.createElement("option");
    option.value = currentReperage.borne_debut_id;
    option.textContent = text(
      currentReperage.borne_debut_libelle,
      showUuid ? currentReperage.borne_debut_id : "Borne",
    );
    reperageFields.borne.append(option);
  }
  reperageFields.borne.value = inputText(currentReperage.borne_debut_id);
  reperageFields.distance.value = coordinate(
    currentReperage.distance_debut_m,
    2,
  );
  reperageFields.sens.value = currentReperage.position_debut_relative
    || "SUR_BORNE";
}

function stopGraphicEdit({ restore }) {
  if (!graphicEditActive) {
    return;
  }
  activePointLayer?.dragging?.disable();
  setGraphicControls(false);
  provisionalLatLng = null;
  validateMapPositionButton.disabled = true;
  mapPositionStatus.textContent = "";
  if (restore) {
    restoreLastServerState();
  }
}

function renderPointServerFeature(feature) {
  const properties = feature.properties || {};
  lastServerFeature = feature;
  editorState.objectId = properties.id;
  editorState.data = feature;
  desordreCreateGeometryType.value = "Point";
  disorderFields.id.value = inputText(properties.id);
  disorderFields.designation.value = inputText(properties.designation);
  fillTypeSelect(disorderFields.type, properties.type_desordre_id);
  fillTronconSelect(
    pointEditTroncon,
    properties.troncon_ids || [],
    { multiple: false },
  );
  disorderFields.commentaire.value = inputText(properties.commentaire);
  disorderFields.dateDebut.value = inputText(properties.date_debut);
  disorderFields.dateFin.value = inputText(properties.date_fin);
  disorderFields.valid.checked = Boolean(properties.valid);
  disorderFields.x.value = coordinate(properties.coord_x_3950, 2);
  disorderFields.y.value = coordinate(properties.coord_y_3950, 2);
  disorderFields.longitude.value = coordinate(properties.longitude_4326, 6);
  disorderFields.latitude.value = coordinate(properties.latitude_4326, 6);
  renderReperage(properties.reperage);
  disorderFields.reperage.value = lineReperageSummary(properties.reperage);
  initialFormValues = {
    designation: disorderFields.designation.value,
    commentaire: disorderFields.commentaire.value,
    type_desordre_id: disorderFields.type.value,
    date_debut: disorderFields.dateDebut.value,
    date_fin: disorderFields.dateFin.value,
    valid: disorderFields.valid.checked,
    troncon_id: pointEditTroncon.value,
    x: disorderFields.x.value,
    y: disorderFields.y.value,
    longitude: disorderFields.longitude.value,
    latitude: disorderFields.latitude.value,
  };
  clearCoordinateAuthority();
  desordreCreateIdField.hidden = false;
  desordreCreateGeometryType.disabled = true;
  submitDesordreCreateButton.textContent = "Enregistrer";
  cancelDesordreCreateButton.textContent = "Annuler les modifications";
  renderDisorderModeChoices(Boolean(properties.reperage?.disponible));
  updateDisorderEditorControls();
  editorMessage.textContent = "";
  editorMessage.classList.remove("error");
}

function lineReperageSummary(reperage) {
  if (!reperage?.disponible) {
    const count = reperage?.nombre_troncons ?? 0;
    return `Indisponible (${count} tronçon(s) associé(s)).`;
  }
  const start = [
    reperage.borne_debut_libelle,
    coordinate(reperage.distance_debut_m, 2) && `${coordinate(reperage.distance_debut_m, 2)} m`,
    reperage.position_debut_relative,
  ].filter(Boolean).join(" — ");
  const end = [
    reperage.borne_fin_libelle,
    coordinate(reperage.distance_fin_m, 2) && `${coordinate(reperage.distance_fin_m, 2)} m`,
    reperage.position_fin_relative,
  ].filter(Boolean).join(" — ");
  return end ? `${start} → ${end}` : start || "Repérage disponible.";
}

function renderLineServerFeature(feature) {
  const properties = feature.properties || {};
  lastServerFeature = feature;
  editorState.objectId = properties.id;
  editorState.data = feature;
  disorderFields.id.value = inputText(properties.id);
  disorderFields.designation.value = inputText(properties.designation);
  fillTypeSelect(disorderFields.type, properties.type_desordre_id);
  disorderFields.commentaire.value = inputText(properties.commentaire);
  disorderFields.dateDebut.value = inputText(properties.date_debut);
  disorderFields.dateFin.value = inputText(properties.date_fin);
  disorderFields.valid.checked = Boolean(properties.valid);
  fillTronconSelect(lineEditTroncons, properties.troncon_ids || []);
  disorderFields.geometryType.value = feature.geometry.type;
  disorderFields.reperage.value = lineReperageSummary(properties.reperage);
  const modes = availableDisorderModes(
    "LineString",
    (properties.troncon_ids || []).length,
    properties.reperage?.disponible,
  );
  setModeChoiceAvailability(desordreBornageChoice, modes.includes("bornage"));
  const activeMode = desordreEditorForm.elements["desordre-mode"].value || "map";
  if (activeMode === "bornage" && !properties.reperage?.disponible) {
    desordreEditorForm.elements["desordre-mode"].value = "map";
  }
  const crs = lineEndpointsCrs.value || "EPSG:3950";
  if (crs === "EPSG:4326") {
    lineStart1.value = coordinate(properties.debut_longitude_4326, 6);
    lineStart2.value = coordinate(properties.debut_latitude_4326, 6);
    lineEnd1.value = coordinate(properties.fin_longitude_4326, 6);
    lineEnd2.value = coordinate(properties.fin_latitude_4326, 6);
  } else {
    lineStart1.value = coordinate(properties.debut_x_3950, 2);
    lineStart2.value = coordinate(properties.debut_y_3950, 2);
    lineEnd1.value = coordinate(properties.fin_x_3950, 2);
    lineEnd2.value = coordinate(properties.fin_y_3950, 2);
  }
  const reperage = properties.reperage || {};
  fillBorneSelect(lineBorneStart, reperage.bornes || [], reperage.borne_debut_id);
  fillBorneSelect(lineBorneEnd, reperage.bornes || [], reperage.borne_fin_id);
  lineDistanceStart.value = coordinate(reperage.distance_debut_m, 2);
  lineDistanceEnd.value = coordinate(reperage.distance_fin_m, 2);
  lineSenseStart.value = reperage.position_debut_relative || "SUR_BORNE";
  lineSenseEnd.value = reperage.position_fin_relative || "SUR_BORNE";
  initialLineReperageValues = {
    borneStart: lineBorneStart.value,
    distanceStart: lineDistanceStart.value,
    senseStart: lineSenseStart.value,
    borneEnd: lineBorneEnd.value,
    distanceEnd: lineDistanceEnd.value,
    senseEnd: lineSenseEnd.value,
  };
  desordreCreateIdField.hidden = false;
  desordreCreateGeometryType.disabled = true;
  submitDesordreCreateButton.textContent = "Enregistrer";
  cancelDesordreCreateButton.textContent = "Annuler les modifications";
  renderDisorderModeChoices(Boolean(properties.reperage?.disponible));
  updateDisorderEditorControls();
  lineEditorMessage.textContent = "";
  lineEditorMessage.classList.remove("error");
}

function lineBornageDraftModified() {
  return initialLineReperageValues && (
    lineBorneStart.value !== initialLineReperageValues.borneStart
    || lineDistanceStart.value !== initialLineReperageValues.distanceStart
    || lineSenseStart.value !== initialLineReperageValues.senseStart
    || lineBorneEnd.value !== initialLineReperageValues.borneEnd
    || lineDistanceEnd.value !== initialLineReperageValues.distanceEnd
    || lineSenseEnd.value !== initialLineReperageValues.senseEnd
  );
}

lineEditTroncons.addEventListener("change", () => {
  if (editorState.mode !== "edit" || editorState.geometryType !== "LineString") {
    return;
  }
  const selected = selectedValues(lineEditTroncons);
  const persisted = (lastServerFeature?.properties?.troncon_ids || []).map(String);
  const sameSelection = selected.length === persisted.length
    && selected.every((id) => persisted.includes(id));
  const bornageAvailable = sameSelection
    && selected.length === 1
    && Boolean(lastServerFeature?.properties?.reperage?.disponible);
  if (selectedDesordreMode() === "bornage" && !bornageAvailable) {
    if (lineBornageDraftModified()) {
      fillTronconSelect(lineEditTroncons, persisted);
      lineEditorMessage.textContent =
        "Le bornage en cours exige exactement le tronçon actuel. Annulez ou enregistrez ce bornage avant de modifier les rattachements.";
      lineEditorMessage.classList.add("error");
      return;
    }
    desordreEditorForm.elements["desordre-mode"].value = "map";
  }
  setModeChoiceAvailability(desordreBornageChoice, bornageAvailable);
  updateDisorderEditorControls();
});

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value)
    .filter(Boolean);
}

function updatePointLayer(feature) {
  if (!activePointLayer || feature.geometry?.type !== "Point") {
    return;
  }
  const [longitude, latitude] = feature.geometry.coordinates;
  activePointLayer.setLatLng([latitude, longitude]);
  activePointLayer.feature = feature;
}

function setLineStyle(mode) {
  if (!activeLineLayer) {
    return;
  }
  if (mode === "editing") {
    activeLineLayer.setStyle({
      color: "#b8470a",
      dashArray: "7 5",
      opacity: 1,
      weight: 8,
    });
  } else {
    activeLineLayer.setStyle({
      color: "#9b3d0b",
      dashArray: null,
      opacity: 1,
      weight: 7,
    });
  }
  activeLineLayer.bringToFront();
}

function clearSelectedLine() {
  if (selectedLineLayer && desordreLineLayer && !lineEditActive) {
    desordreLineLayer.resetStyle(selectedLineLayer);
  }
  selectedLineLayer = null;
  activeLineLayer = null;
}

function updateLineLayer(feature) {
  if (!activeLineLayer || feature.geometry?.type !== "LineString") {
    return;
  }
  const latLngs = feature.geometry.coordinates.map(
    ([longitude, latitude]) => [latitude, longitude],
  );
  activeLineLayer.setLatLngs(latLngs);
  activeLineLayer.feature = feature;
  setLineStyle("selected");
}

function updatePolygonLayer(feature) {
  if (!activePolygonLayer || feature.geometry?.type !== "Polygon") return;
  const rings = feature.geometry.coordinates.map((ring) => ring
    .slice(0, -1)
    .map(([longitude, latitude]) => [latitude, longitude]));
  activePolygonLayer.setLatLngs(rings);
  activePolygonLayer.feature = feature;
}

function prepareDisorderEditorForEdit(geometryType, objectId) {
  setDisorderEditorState("edit", geometryType, objectId);
  desordreEditorForm.reset();
  Array.from(desordreEditorForm.elements).forEach((element) => {
    element.disabled = false;
  });
  desordreEditorForm.elements["desordre-mode"].value = "map";
  desordreCreateGeometryType.value = geometryType;
  desordreCreateGeometryType.disabled = true;
  desordreCreateTroncons.multiple = geometryType !== "Point";
  desordreCreateTroncons.size = geometryType === "Point" ? 1 : 5;
  desordreCreateIdField.hidden = false;
  desordreEditorForm.hidden = false;
  submitDesordreCreateButton.textContent = "Enregistrer";
  cancelDesordreCreateButton.textContent = "Annuler les modifications";
  desordreCreateActions.hidden = false;
  validateDesordreDrawButton.hidden = true;
  updateDisorderEditorControls();
}

function setLineEditControls(active) {
  lineEditActive = active;
  startLineEditButton.hidden = active;
  lineGeometryActions.hidden = !active;
  observationsTabButton.disabled = active;
  setLineStyle(active ? "editing" : "selected");
}

function stopLineEdit({ restore }) {
  if (!lineEditActive) {
    return;
  }
  activeLineLayer?.disableEdit?.();
  setLineEditControls(false);
  validateLineEditButton.disabled = true;
  lineGeometryStatus.textContent = "";
  if (restore && lastServerFeature?.geometry?.type === "LineString") {
    renderLineServerFeature(lastServerFeature);
    updateLineLayer(lastServerFeature);
  }
}

async function openPointEditor(id, layer) {
  if (lineEditActive || lineRequestInFlight) {
    lineEditorMessage.textContent =
      "Validez ou annulez explicitement la géométrie en cours avant de changer de désordre.";
    lineEditorMessage.classList.add("error");
    return;
  }
  if (graphicRequestInFlight) {
    editorMessage.textContent = "Attendez la réponse PostgreSQL en cours.";
    editorMessage.classList.add("error");
    return;
  }
  if (graphicEditActive && activePointLayer === layer) {
    return;
  }
  if (graphicEditActive) {
    stopGraphicEdit({ restore: true });
  }
  await Promise.all([loadDesordreTypes(), loadDesordreTronconOptions()]);
  activePointLayer?.dragging?.disable();
  clearSelectedLine();
  requestedDesordreId = id;
  prepareDisorderEditorForEdit("Point", id);
  activePointLayer = layer;
  editorObjectTitle.textContent = "Désordre ponctuel";
  editorObjectSubtitle.textContent = "État relu depuis PostgreSQL";
  editorTabs.hidden = false;
  heritageObjectForm.hidden = true;
  desordreEditorForm.hidden = false;
  observationsLoadedFor = null;
  currentObservationPhotos = [];
  observationsList.replaceChildren();
  observationsMessage.textContent = "";
  closePhotoLightbox();
  showEditorTab("general");
  editorPanel.hidden = false;
  editorMessage.textContent = "Chargement…";
  editorMessage.classList.remove("error");
  try {
    const feature = await fetchJson(`/api/desordres/${encodeURIComponent(id)}`);
    if (requestedDesordreId !== id) {
      return;
    }
    if (feature.type !== "Feature" || feature.geometry?.type !== "Point") {
      throw new Error("Réponse ponctuelle invalide.");
    }
    renderPointServerFeature(feature);
    updatePointLayer(feature);
  } catch (error) {
    console.error("Lecture du désordre impossible", error);
    editorMessage.textContent = `Lecture impossible : ${error.message}`;
    editorMessage.classList.add("error");
  }
}

async function openLineEditor(id, layer) {
  if (lineEditActive || lineRequestInFlight) {
    lineEditorMessage.textContent =
      "Validez ou annulez explicitement la géométrie en cours avant de changer de désordre.";
    lineEditorMessage.classList.add("error");
    return;
  }
  if (graphicRequestInFlight) {
    editorMessage.textContent = "Attendez la réponse PostgreSQL en cours.";
    editorMessage.classList.add("error");
    return;
  }
  if (graphicEditActive) {
    stopGraphicEdit({ restore: true });
  }
  await Promise.all([loadDesordreTypes(), loadDesordreTronconOptions()]);
  activePointLayer?.dragging?.disable();
  activePointLayer = null;
  clearSelectedLine();
  requestedDesordreId = id;
  prepareDisorderEditorForEdit("LineString", id);
  activeLineLayer = layer;
  selectedLineLayer = layer;
  setLineStyle("selected");
  observationsLoadedFor = null;
  currentObservationPhotos = [];
  observationsList.replaceChildren();
  observationsMessage.textContent = "";
  closePhotoLightbox();
  showEditorTab("general");
  editorObjectTitle.textContent = "Désordre linéaire";
  editorObjectSubtitle.textContent = "Géométrie relue depuis PostgreSQL";
  editorTabs.hidden = false;
  heritageObjectForm.hidden = true;
  desordreEditorForm.hidden = false;
  editorPanel.hidden = false;
  lineEditorMessage.textContent = "Chargement…";
  lineEditorMessage.classList.remove("error");
  try {
    const feature = await fetchJson(`/api/desordres/${encodeURIComponent(id)}`);
    if (requestedDesordreId !== id) {
      return;
    }
    if (feature.type !== "Feature" || feature.geometry?.type !== "LineString") {
      throw new Error("Réponse LineString invalide.");
    }
    renderLineServerFeature(feature);
    updateLineLayer(feature);
  } catch (error) {
    console.error("Lecture du désordre LineString impossible", error);
    lineEditorMessage.textContent = `Lecture impossible : ${error.message}`;
    lineEditorMessage.classList.add("error");
  }
}

async function openPolygonEditor(id, _layer) {
  if (lineEditActive || lineRequestInFlight || graphicRequestInFlight) {
    return;
  }
  if (graphicEditActive) {
    stopGraphicEdit({ restore: true });
  }
  await Promise.all([
    loadHeritageTree(), loadDesordreTypes(), loadDesordreTronconOptions(),
  ]);
  fillDesordreReferenceOptions();
  fillDesordreTronconOptions();
  editorPanel.hidden = false;
  desordreCreateMessage.textContent = "Chargement…";
  try {
    const feature = await fetchJson(`/api/desordres/${encodeURIComponent(id)}`);
    if (feature.geometry?.type !== "Polygon") {
      throw new Error("Réponse Polygon invalide.");
    }
    renderPolygonServerFeature(feature, _layer);
  } catch (error) {
    desordreCreateMessage.textContent = `Lecture impossible : ${error.message}`;
    desordreCreateMessage.classList.add("error");
  }
}

function restoreLastServerState() {
  if (lastServerFeature?.geometry?.type === "Point") {
    renderPointServerFeature(lastServerFeature);
    updatePointLayer(lastServerFeature);
  } else if (lastServerFeature?.geometry?.type === "LineString") {
    renderLineServerFeature(lastServerFeature);
    updateLineLayer(lastServerFeature);
  }
}

function changedNullableText(current, initial) {
  return current === initial ? undefined : current || null;
}

function buildPointUpdatePayload() {
  const payload = {};
  const designation = changedNullableText(
    disorderFields.designation.value,
    initialFormValues.designation,
  );
  const commentaire = changedNullableText(
    disorderFields.commentaire.value,
    initialFormValues.commentaire,
  );
  if (designation !== undefined) {
    payload.designation = designation;
  }
  if (commentaire !== undefined) {
    payload.commentaire = commentaire;
  }
  if (disorderFields.type.value !== initialFormValues.type_desordre_id) {
    payload.type_desordre_id = optionalPayloadValue(disorderFields.type.value);
  }
  if (disorderFields.dateDebut.value !== initialFormValues.date_debut) {
    payload.date_debut = disorderFields.dateDebut.value || null;
  }
  if (disorderFields.dateFin.value !== initialFormValues.date_fin) {
    payload.date_fin = disorderFields.dateFin.value || null;
  }
  if (disorderFields.valid.checked !== initialFormValues.valid) {
    payload.valid = disorderFields.valid.checked;
  }
  if (pointEditTroncon.value !== initialFormValues.troncon_id) {
    payload.troncon_ids = pointEditTroncon.value
      ? [pointEditTroncon.value] : [];
  }

  const family = selectedDesordreMode();
  if (family === "xy") {
    if (!disorderFields.x.value || !disorderFields.y.value) {
      throw new Error("X et Y doivent être renseignés ensemble.");
    }
    if (disorderFields.x.value !== initialFormValues.x || disorderFields.y.value !== initialFormValues.y) {
      payload.coord_x_3950 = disorderFields.x.value !== initialFormValues.x
        ? Number(disorderFields.x.value)
        : lastServerFeature.properties.coord_x_3950;
      payload.coord_y_3950 = disorderFields.y.value !== initialFormValues.y
        ? Number(disorderFields.y.value)
        : lastServerFeature.properties.coord_y_3950;
    }
  } else if (family === "lonlat") {
    if (!disorderFields.longitude.value || !disorderFields.latitude.value) {
      throw new Error("Longitude et latitude doivent être renseignées ensemble.");
    }
    if (
      disorderFields.longitude.value !== initialFormValues.longitude
      || disorderFields.latitude.value !== initialFormValues.latitude
    ) {
      payload.longitude_4326 = disorderFields.longitude.value !== initialFormValues.longitude
        ? Number(disorderFields.longitude.value)
        : lastServerFeature.properties.longitude_4326;
      payload.latitude_4326 = disorderFields.latitude.value !== initialFormValues.latitude
        ? Number(disorderFields.latitude.value)
        : lastServerFeature.properties.latitude_4326;
    }
  }
  if (Object.keys(payload).length === 0) {
    throw new Error("Aucune modification à enregistrer.");
  }
  return payload;
}

function buildPointReperagePayload() {
  if (!currentReperage?.disponible) {
    throw new Error("Le repérage n’est pas disponible pour ce désordre.");
  }
  const distance = Number(reperageFields.distance.value);
  if (!reperageFields.borne.value) {
    throw new Error("Une borne doit être sélectionnée.");
  }
  if (!Number.isFinite(distance) || distance < 0) {
    throw new Error("La distance doit être positive ou nulle.");
  }
  if (
    reperageFields.sens.value === "SUR_BORNE"
    && distance !== 0
  ) {
    throw new Error("La distance doit être nulle pour une position sur borne.");
  }
  return {
    borne_debut_id: reperageFields.borne.value,
    distance_debut_m: distance,
    position_debut_relative: reperageFields.sens.value,
  };
}

Array.from(desordreEditorForm.elements["desordre-mode"]).forEach((radio) => {
  radio.addEventListener("change", (event) => {
    const geometryType = editorState.geometryType || desordreCreateGeometryType.value;
    if (editorState.mode === "create") {
      if (provisionalDesordreLayer && event.target.value !== "map") {
        desordreEditorForm.elements["desordre-mode"].value = "map";
        desordreCreateMessage.textContent =
          "Annulez explicitement la géométrie cartographique avant de changer de mode.";
        desordreCreateMessage.classList.add("error");
        return;
      }
      updateDisorderEditorControls();
      return;
    }
    if (geometryType === "Point") {
      if (event.target.value === "xy") {
        disorderFields.longitude.value = initialFormValues.longitude;
        disorderFields.latitude.value = initialFormValues.latitude;
      } else if (event.target.value === "lonlat") {
        disorderFields.x.value = initialFormValues.x;
        disorderFields.y.value = initialFormValues.y;
      } else if (event.target.value === "bornage") {
        if (textFieldsChanged()) {
          desordreEditorForm.elements["desordre-mode"].value = "map";
          editorMessage.textContent =
            "Enregistrez ou annulez les champs généraux avant le mode Bornage.";
          editorMessage.classList.add("error");
        } else {
          disorderFields.x.value = initialFormValues.x;
          disorderFields.y.value = initialFormValues.y;
          disorderFields.longitude.value = initialFormValues.longitude;
          disorderFields.latitude.value = initialFormValues.latitude;
        }
      }
      updateCoordinateInputs();
      return;
    }
    updateDisorderEditorControls();
    if (geometryType === "LineString"
        && ["xy", "lonlat"].includes(selectedDesordreMode())
        && lastServerFeature?.geometry?.type === "LineString") {
      renderLineServerFeature(lastServerFeature);
    }
  });
});

reperageFields.sens.addEventListener("change", () => {
  if (reperageFields.sens.value === "SUR_BORNE") {
    reperageFields.distance.value = "0.00";
  }
});

lineEndpointsCrs.addEventListener("change", () => {
  updateLineCoordinateLabels(lineCoordinateEditor, lineEndpointsCrs.value);
  if (lastServerFeature?.geometry?.type === "LineString") {
    renderLineServerFeature(lastServerFeature);
  }
});

async function saveLineRequest(path, payload, successMessage) {
  if (!lastServerFeature || lineRequestInFlight) {
    return;
  }
  lineRequestInFlight = true;
  lineEditorMessage.textContent = "Enregistrement et relecture PostgreSQL…";
  lineEditorMessage.classList.remove("error");
  try {
    const feature = await fetchJson(
      `/api/desordres/${encodeURIComponent(lastServerFeature.properties.id)}${path}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    renderLineServerFeature(feature);
    updateLineLayer(feature);
    lineEditorMessage.textContent = successMessage;
  } catch (error) {
    lineEditorMessage.textContent = `Enregistrement refusé : ${error.message}`;
    lineEditorMessage.classList.add("error");
  } finally {
    lineRequestInFlight = false;
  }
}

saveLineEndpointsButton.addEventListener("click", () => {
  const values = [lineStart1, lineStart2, lineEnd1, lineEnd2]
    .map((input) => Number(input.value));
  if (values.some((value) => !Number.isFinite(value))) {
    lineEditorMessage.textContent = "Les quatre coordonnées sont obligatoires.";
    lineEditorMessage.classList.add("error");
    return;
  }
  saveLineRequest("/endpoints", {
    crs: lineEndpointsCrs.value,
    debut: values.slice(0, 2),
    fin: values.slice(2),
  }, "Extrémités modifiées sans supprimer les sommets intermédiaires.");
});

function buildLineReperagePayload() {
  const startDistance = Number(lineDistanceStart.value);
  const endDistance = Number(lineDistanceEnd.value);
  if (!lineBorneStart.value || !lineBorneEnd.value
      || !Number.isFinite(startDistance) || !Number.isFinite(endDistance)) {
    throw new Error("Le bornage de début et de fin est obligatoire.");
  }
  return {
    borne_debut_id: lineBorneStart.value,
    distance_debut_m: startDistance,
    position_debut_relative: lineSenseStart.value,
    borne_fin_id: lineBorneEnd.value,
    distance_fin_m: endDistance,
    position_fin_relative: lineSenseEnd.value,
  };
}

function applyLineReperage(successMessage) {
  let payload;
  try {
    payload = buildLineReperagePayload();
  } catch (error) {
    lineEditorMessage.textContent = error.message;
    lineEditorMessage.classList.add("error");
    return;
  }
  saveLineRequest("/reperage", payload, successMessage);
}

reprojectBornageButton.addEventListener("click", () => {
  if (editorState.geometryType === "Point") {
    desordreEditorForm.requestSubmit();
    return;
  }
  applyLineReperage(
    "Ligne reprojetée depuis le bornage ; la géométrie libre a été remplacée.",
  );
});

saveLineBornageButton.addEventListener("click", () => {
  applyLineReperage(
    "Bornage enregistré ; géométrie reconstruite depuis le tronçon.",
  );
});

[lineSenseStart, lineSenseEnd].forEach((select) => {
  select.addEventListener("change", () => {
    if (select.value === "SUR_BORNE") {
      (select === lineSenseStart ? lineDistanceStart : lineDistanceEnd).value = "0.00";
    }
  });
});

startMapPositionButton.addEventListener("click", () => {
  if (selectedDesordreMode() !== "map") {
    editorMessage.textContent =
      "Annulez d’abord le mode d’édition numérique des coordonnées.";
    editorMessage.classList.add("error");
    return;
  }
  if (textFieldsChanged()) {
    editorMessage.textContent =
      "Enregistrez ou annulez d’abord les modifications du formulaire.";
    editorMessage.classList.add("error");
    return;
  }
  if (!activePointLayer?.dragging) {
    editorMessage.textContent = "Ce marqueur ne peut pas être déplacé.";
    editorMessage.classList.add("error");
    return;
  }
  provisionalLatLng = null;
  validateMapPositionButton.disabled = true;
  setGraphicControls(true);
  activePointLayer.dragging.enable();
  mapPositionStatus.textContent =
    "Édition graphique en cours — déplacez le marqueur sélectionné.";
  editorMessage.textContent = "Aucune écriture n’est effectuée pendant le déplacement.";
  editorMessage.classList.remove("error");
});

map.on("click", (event) => {
  if (!graphicEditActive || !activePointLayer || lineEditActive) return;
  // Leaflet n'émet pas ce click après un pan : un tap/clic volontaire reste
  // donc distinct de la navigation tactile normale.
  provisionalLatLng = event.latlng;
  activePointLayer.setLatLng(provisionalLatLng);
  disorderFields.longitude.value = coordinate(provisionalLatLng.lng, 6);
  disorderFields.latitude.value = coordinate(provisionalLatLng.lat, 6);
  validateMapPositionButton.disabled = false;
  mapPositionStatus.textContent =
    "Position provisoire choisie sur la carte — validez ou annulez.";
});

cancelMapPositionButton.addEventListener("click", () => {
  stopGraphicEdit({ restore: true });
  editorMessage.textContent = "Déplacement annulé — position serveur restaurée.";
});

validateMapPositionButton.addEventListener("click", async () => {
  if (!graphicEditActive || !provisionalLatLng || !lastServerFeature) {
    return;
  }
  const payload = {
    longitude_4326: provisionalLatLng.lng,
    latitude_4326: provisionalLatLng.lat,
  };
  activePointLayer.dragging.disable();
  graphicRequestInFlight = true;
  validateMapPositionButton.disabled = true;
  cancelMapPositionButton.disabled = true;
  cancelEditButton.disabled = true;
  closeEditorButton.disabled = true;
  mapPositionStatus.textContent =
    "Validation PostgreSQL et relecture de la position…";
  try {
    const feature = await fetchJson(
      `/api/desordres/${encodeURIComponent(lastServerFeature.properties.id)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    stopGraphicEdit({ restore: false });
    renderPointServerFeature(feature);
    updatePointLayer(feature);
    editorMessage.textContent =
      "Position validée — marqueur et coordonnées relus depuis PostgreSQL.";
    editorMessage.classList.remove("error");
  } catch (error) {
    console.error("Validation de la position impossible", error);
    activePointLayer.dragging.enable();
    validateMapPositionButton.disabled = false;
    mapPositionStatus.textContent =
      "Position toujours provisoire — corrigez le déplacement ou annulez-le.";
    editorMessage.textContent = `Validation refusée : ${error.message}`;
    editorMessage.classList.add("error");
  } finally {
    graphicRequestInFlight = false;
    cancelMapPositionButton.disabled = false;
    cancelEditButton.disabled = false;
    closeEditorButton.disabled = false;
  }
});

map.on("editable:editing", (event) => {
  if (event.layer === provisionalTronconLayer) {
    updateTronconDraftStatus();
    return;
  }
  if (event.layer === provisionalDesordreLayer) {
    updateDesordreDraftStatus();
    return;
  }
  if (polygonEditActive && event.layer === activePolygonLayer) {
    desordreDrawStatus.textContent = "Polygone provisoire modifié — aucune écriture avant validation.";
    return;
  }
  if (!lineEditActive || event.layer !== activeLineLayer) {
    return;
  }
  validateLineEditButton.disabled = false;
  lineGeometryStatus.textContent =
    "Géométrie provisoire — validez ou annulez les sommets.";
});

startLineEditButton.addEventListener("click", () => {
  if (!activeLineLayer || lastServerFeature?.geometry?.type !== "LineString") {
    return;
  }
  if (typeof activeLineLayer.enableEdit !== "function") {
    lineEditorMessage.textContent =
      "Le module léger d’édition Leaflet n’a pas pu être chargé.";
    lineEditorMessage.classList.add("error");
    return;
  }
  activeLineLayer.enableEdit(map);
  setLineEditControls(true);
  validateLineEditButton.disabled = true;
  lineGeometryStatus.textContent =
    "Édition en cours — déplacez un sommet ou utilisez une poignée intermédiaire.";
  lineEditorMessage.textContent =
    "Aucune écriture n’est effectuée avant Valider la géométrie.";
  lineEditorMessage.classList.remove("error");
});

cancelLineEditButton.addEventListener("click", () => {
  if (lineRequestInFlight) {
    return;
  }
  stopLineEdit({ restore: true });
  lineEditorMessage.textContent =
    "Édition annulée — géométrie serveur restaurée exactement.";
});

validateLineEditButton.addEventListener("click", async () => {
  if (!lineEditActive || !activeLineLayer || lineRequestInFlight) {
    return;
  }
  const geometry = activeLineLayer.toGeoJSON(false).geometry;
  const payload = { geometry };
  activeLineLayer.disableEdit();
  lineRequestInFlight = true;
  validateLineEditButton.disabled = true;
  cancelLineEditButton.disabled = true;
  closeEditorButton.disabled = true;
  lineGeometryStatus.textContent =
    "Validation PostgreSQL et relecture de la géométrie…";
  try {
    const feature = await fetchJson(
      `/api/desordres/${encodeURIComponent(
        lastServerFeature.properties.id,
      )}/geometry`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    setLineEditControls(false);
    validateLineEditButton.disabled = true;
    lineGeometryStatus.textContent = "";
    renderLineServerFeature(feature);
    updateLineLayer(feature);
    lineEditorMessage.textContent =
      "Géométrie validée — ligne et repérage relus depuis PostgreSQL.";
    lineEditorMessage.classList.remove("error");
  } catch (error) {
    console.error("Validation de la LineString impossible", error);
    activeLineLayer.enableEdit(map);
    setLineStyle("editing");
    validateLineEditButton.disabled = false;
    lineGeometryStatus.textContent =
      "Géométrie toujours provisoire — corrigez les sommets ou annulez.";
    lineEditorMessage.textContent = `Validation refusée : ${error.message}`;
    lineEditorMessage.classList.add("error");
  } finally {
    lineRequestInFlight = false;
    cancelLineEditButton.disabled = false;
    closeEditorButton.disabled = false;
  }
});

async function savePointDesordre() {
  if (!lastServerFeature) {
    return;
  }
  let payload;
  const family = selectedDesordreMode();
  try {
    payload = family === "bornage"
      ? buildPointReperagePayload()
      : buildPointUpdatePayload();
  } catch (error) {
    editorMessage.textContent = error.message;
    editorMessage.classList.add("error");
    return;
  }

  saveButton.disabled = true;
  editorMessage.textContent = "Enregistrement et relecture…";
  editorMessage.classList.remove("error");
  try {
    const endpoint = family === "bornage"
      ? `/api/desordres/${encodeURIComponent(
        lastServerFeature.properties.id,
      )}/reperage`
      : `/api/desordres/${encodeURIComponent(lastServerFeature.properties.id)}`;
    const feature = await fetchJson(
      endpoint,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    renderPointServerFeature(feature);
    updatePointLayer(feature);
    editorMessage.textContent = "Enregistré — valeurs relues depuis PostgreSQL.";
  } catch (error) {
    console.error("Mise à jour du désordre impossible", error);
    editorMessage.textContent = `Enregistrement refusé : ${error.message}`;
    editorMessage.classList.add("error");
  } finally {
    saveButton.disabled = false;
  }
}

closeEditorButton.addEventListener("click", () => {
  if (editorState.mode === "create") {
    if (!creationRequestInFlight) {
      if (editorState.objectType === "desordre") {
        closeDesordreDraft();
      } else {
        closeHeritageDraft();
      }
    }
    return;
  }
  if (["systeme", "digue", "troncon"].includes(editorState.objectType)) {
    heritageObjectForm.hidden = true;
    editorPanel.hidden = true;
    editorState = { mode: "edit", objectType: null };
    return;
  }
  if (lineEditActive || lineRequestInFlight) {
    lineEditorMessage.textContent =
      "Validez ou annulez explicitement la géométrie avant de fermer.";
    lineEditorMessage.classList.add("error");
    return;
  }
  if (graphicEditActive) {
    stopGraphicEdit({ restore: true });
  } else {
    restoreLastServerState();
  }
  editorPanel.hidden = true;
  requestedDesordreId = null;
  closePhotoLightbox();
  showEditorTab("general");
  clearSelectedLine();
});

async function loadMapData() {
  try {
    await loadFrontendConfig();
    const [troncons, desordres, territoire] = await Promise.all([
      fetchGeoJSON("/api/troncons"),
      fetchGeoJSON("/api/desordres"),
      fetchGeoJSON("/api/territoire-administratif"),
    ]);
    setTerritoireAdministratifState(territoire);

    tronconsGeoJsonLayer = L.geoJSON(troncons, {
      style: { color: "#39735a", opacity: 0.85, weight: 4 },
      onEachFeature: configureTronconLayer,
    }).addTo(map);

    if (selectedHeritageObject?.kind === "Tronçon") {
      const layer = highlightTroncon(selectedHeritageObject.item.id);
      zoomTronconButton.disabled = !layer;
    }

    const commonOptions = {
      style: { color: "#e4772f", fillOpacity: 0.22, opacity: 0.95, weight: 5 },
      pointToLayer(_feature, latlng) {
        return L.marker(latlng, {
          draggable: false,
          icon: pointIcon,
        });
      },
      onEachFeature: configureDesordreLayer,
    };
    const features = desordres.features || [];
    const collection = (type) => ({
      type: "FeatureCollection",
      features: features.filter((feature) => feature.geometry?.type === type),
    });
    desordrePointLayer = L.geoJSON(collection("Point"), commonOptions).addTo(map);
    desordreLineLayer = L.geoJSON(collection("LineString"), commonOptions).addTo(map);
    desordrePolygonLayer = L.geoJSON(collection("Polygon"), commonOptions).addTo(map);
    desordresGeoJsonLayer = L.featureGroup([
      desordrePointLayer, desordreLineLayer, desordrePolygonLayer,
    ]);

    const allData = L.featureGroup([
      tronconsGeoJsonLayer,
      desordresGeoJsonLayer,
    ]);
    historicalViewportBounds = allData.getBounds();
    applyTerritoireCartography(historicalViewportBounds);

    statusElement.textContent =
      `${troncons.features.length} tronçon(s), `
      + `${desordres.features.length} désordre(s)`;
  } catch (error) {
    console.error("Chargement cartographique impossible", error);
    statusElement.textContent = `Chargement impossible : ${error.message}`;
    statusElement.classList.add("error");
    revealMapAfterInitialViewport();
  }
}

loadMapData();

layerToggleInputs.forEach((input) => {
  input.addEventListener("change", () => {
    const layers = {
      troncons: tronconsGeoJsonLayer,
      Point: desordrePointLayer,
      LineString: desordreLineLayer,
      Polygon: desordrePolygonLayer,
    };
    const layer = layers[input.dataset.layerToggle];
    if (!layer) return;
    if (input.checked) layer.addTo(map);
    else map.removeLayer(layer);
  });
});
