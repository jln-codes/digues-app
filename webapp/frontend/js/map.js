const map = L.map("map", {
  zoomControl: false,
  editable: true,
}).setView([46.8, 2.5], 6);
const statusElement = document.querySelector("#status");
const heritageToggleButton = document.querySelector("#toggle-heritage");
const createMenuButton = document.querySelector("#toggle-create-menu");
const createMenuList = document.querySelector("#create-menu-list");
const heritageCloseButton = document.querySelector("#close-heritage");
const heritagePanel = document.querySelector("#heritage-panel");
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
const desordreCreateForm = document.querySelector("#desordre-create-editor");
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
const desordreCreatePointMethods = document.querySelector("#desordre-create-point-methods");
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
const desordreCreatePointBornageChoice = document.querySelector("#desordre-create-point-bornage-choice");
const desordreCreateLineMethods = document.querySelector("#desordre-create-line-methods");
const desordreCreateLineBornageChoice = document.querySelector("#desordre-create-line-bornage-choice");
const desordreCreateLineCoordinates = document.querySelector("#desordre-create-line-coordinates");
const desordreCreateLineCrs = document.querySelector("#desordre-create-line-crs");
const desordreCreateLineStart1 = document.querySelector("#desordre-create-line-start-1");
const desordreCreateLineStart2 = document.querySelector("#desordre-create-line-start-2");
const desordreCreateLineEnd1 = document.querySelector("#desordre-create-line-end-1");
const desordreCreateLineEnd2 = document.querySelector("#desordre-create-line-end-2");
const desordreCreateBornage = document.querySelector("#desordre-create-bornage");
const desordreCreateBornageContext = document.querySelector("#desordre-create-bornage-context");
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
const editorForm = document.querySelector("#point-editor");
const lineEditorForm = document.querySelector("#line-editor");
const editorObjectTitle = document.querySelector("#editor-object-title");
const editorObjectSubtitle = document.querySelector("#editor-object-subtitle");
const editorTabs = document.querySelector(".editor-tabs");
const editorMessage = document.querySelector("#editor-message");
const saveButton = document.querySelector("#save-edit");
const reprojectPointBornageButton = document.querySelector("#reproject-point-bornage");
const cancelEditButton = document.querySelector("#cancel-edit");
const closeEditorButton = document.querySelector("#close-editor");
const startMapPositionButton = document.querySelector("#start-map-position");
const mapPositionActions = document.querySelector("#map-position-actions");
const mapPositionStatus = document.querySelector("#map-position-status");
const validateMapPositionButton = document.querySelector("#validate-map-position");
const cancelMapPositionButton = document.querySelector("#cancel-map-position");
const lineEditorMessage = document.querySelector("#line-editor-message");
const startLineEditButton = document.querySelector("#start-line-edit");
const lineGeometryActions = document.querySelector("#line-geometry-actions");
const lineGeometryStatus = document.querySelector("#line-geometry-status");
const validateLineEditButton = document.querySelector("#validate-line-edit");
const cancelLineEditButton = document.querySelector("#cancel-line-edit");
const bornageModeRadio = document.querySelector("#bornage-mode");
const pointBornageModeChoice = document.querySelector("#point-bornage-mode-choice");
const pointEditTroncon = document.querySelector("#point-edit-troncon");
const bornageAvailability = document.querySelector("#bornage-availability");
const bornageFields = document.querySelector("#bornage-fields");
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
const fields = {
  id: document.querySelector("#desordre-id"),
  designation: document.querySelector("#designation"),
  type: document.querySelector("#type-desordre"),
  commentaire: document.querySelector("#commentaire"),
  dateDebut: document.querySelector("#point-date-debut"),
  dateFin: document.querySelector("#point-date-fin"),
  valid: document.querySelector("#point-valid"),
  x: document.querySelector("#coord-x"),
  y: document.querySelector("#coord-y"),
  longitude: document.querySelector("#longitude"),
  latitude: document.querySelector("#latitude"),
};
const reperageFields = {
  troncon: document.querySelector("#reperage-troncon"),
  systeme: document.querySelector("#reperage-systeme"),
  borne: document.querySelector("#reperage-borne"),
  distance: document.querySelector("#reperage-distance"),
  sens: document.querySelector("#reperage-sens"),
  pr: document.querySelector("#reperage-pr"),
};
const lineFields = {
  id: document.querySelector("#line-desordre-id"),
  designation: document.querySelector("#line-designation"),
  type: document.querySelector("#line-type-desordre"),
  commentaire: document.querySelector("#line-commentaire"),
  dateDebut: document.querySelector("#line-date-debut"),
  dateFin: document.querySelector("#line-date-fin"),
  valid: document.querySelector("#line-valid"),
  geometryType: document.querySelector("#line-geometry-type"),
  vertexCount: document.querySelector("#line-vertex-count"),
  reperage: document.querySelector("#line-reperage-summary"),
};
const lineEditTroncons = document.querySelector("#line-edit-troncons");
const lineMapEditor = document.querySelector("#line-map-editor");
const lineCoordinateEditor = document.querySelector("#line-coordinate-editor");
const lineBornageEditor = document.querySelector("#line-bornage-editor");
const lineEditBornageChoice = document.querySelector("#line-edit-bornage-choice");
const lineEndpointsCrs = document.querySelector("#line-endpoints-crs");
const lineStart1 = document.querySelector("#line-start-1");
const lineStart2 = document.querySelector("#line-start-2");
const lineEnd1 = document.querySelector("#line-end-1");
const lineEnd2 = document.querySelector("#line-end-2");
const saveLineEndpointsButton = document.querySelector("#save-line-endpoints");
const lineBorneStart = document.querySelector("#line-borne-start");
const lineDistanceStart = document.querySelector("#line-distance-start");
const lineSenseStart = document.querySelector("#line-sense-start");
const lineBorneEnd = document.querySelector("#line-borne-end");
const lineDistanceEnd = document.querySelector("#line-distance-end");
const lineSenseEnd = document.querySelector("#line-sense-end");
const reprojectLineBornageButton = document.querySelector("#reproject-line-bornage");
const saveLineBornageButton = document.querySelector("#save-line-bornage");
const saveLineMetadataButton = document.querySelector("#save-line-metadata");

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
let showUuid = false;
let editorState = { mode: "edit", objectType: null };
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
  mapLegend.hidden = open;
  heritageToggleButton.setAttribute("aria-expanded", String(open));
  if (open) {
    loadHeritageTree();
  }
}

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

function desordrePointMethod() {
  return desordreCreateForm.elements["desordre-point-method"].value || "map";
}

function desordreLineMethod() {
  return desordreCreateForm.elements["desordre-line-method"].value || "map";
}

function availableDisorderModes(geometryType, tronconCount, reperageAvailable) {
  if (geometryType === "Polygon") return ["map"];
  const modes = geometryType === "Point"
    ? ["map", "xy", "lonlat"]
    : ["map", "coordinates"];
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

function renderCreationModeChoices(reperageAvailable = false) {
  const geometryType = desordreCreateGeometryType.value;
  const tronconCount = selectedDesordreTronconIds().length;
  const modes = availableDisorderModes(
    geometryType,
    tronconCount,
    reperageAvailable,
  );
  const bornageState = creationBornageChoiceState(
    geometryType, tronconCount, reperageAvailable,
  );
  setModeChoiceState(
    desordreCreatePointBornageChoice,
    geometryType === "Point"
      ? bornageState : { visible: false, enabled: false },
  );
  setModeChoiceState(
    desordreCreateLineBornageChoice,
    geometryType === "LineString"
      ? bornageState : { visible: false, enabled: false },
  );
  if (geometryType !== "Polygon") {
    const groupName = geometryType === "Point"
      ? "desordre-point-method" : "desordre-line-method";
    const selectedMethod = desordreCreateForm.elements[groupName].value || "map";
    if (!modes.includes(selectedMethod)) {
      desordreCreateForm.elements[groupName].value = "map";
      updateDesordreCreationControls();
    }
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

function updateDesordreCreationControls() {
  const geometryType = desordreCreateGeometryType.value;
  const point = geometryType === "Point";
  const line = geometryType === "LineString";
  const method = point ? desordrePointMethod() : line ? desordreLineMethod() : "map";
  desordreCreatePointMethods.hidden = !point;
  desordreCreateLineMethods.hidden = !line;
  desordreCreateXy.hidden = !point || method !== "xy";
  desordreCreateLonlat.hidden = !point || method !== "lonlat";
  desordreCreateLineCoordinates.hidden = !line || method !== "coordinates";
  desordreCreateBornage.hidden = method !== "bornage";
  desordreCreateBornageEnd.hidden = point;
  desordreCreateGeometry.hidden = method !== "map";
  desordreCreateGeometryTitle.textContent = point
    ? "Placement cartographique"
    : `Dessin ${geometryType === "LineString" ? "de la ligne" : "du polygone"}`;
  desordreCreateGeometryHelp.textContent = geometryType === "Polygon"
    ? "Extension web du modèle historique : l'emprise reste libre et sans repérage éditable."
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
  renderCreationModeChoices(false);
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
    renderCreationModeChoices(true);
    desordreCreateBornageContext.textContent =
      `${options.troncon_libelle} — ${options.systeme_reperage_libelle}`;
    fillBorneSelect(desordreCreateBorneStart, options.bornes);
    fillBorneSelect(desordreCreateBorneEnd, options.bornes);
  } catch (error) {
    if (requestVersion === creationReperageRequestVersion) {
      creationReperageAvailable = false;
      renderCreationModeChoices(false);
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
  editorState = { mode: "create", objectType: "desordre" };
  lastServerFeature = null;
  requestedDesordreId = null;
  editorObjectTitle.textContent = "Nouveau désordre";
  editorObjectSubtitle.textContent = "Brouillon local — aucune écriture avant Créer";
  editorTabs.hidden = true;
  generalTab.hidden = false;
  observationsTab.hidden = true;
  heritageObjectForm.hidden = true;
  editorForm.hidden = true;
  lineEditorForm.hidden = true;
  desordreCreateForm.reset();
  creationReperageAvailable = false;
  updateLineCoordinateLabels(desordreCreateLineCoordinates, desordreCreateLineCrs.value);
  desordreCreateForm.hidden = false;
  desordreCreateIdField.hidden = true;
  desordreCreateValid.checked = true;
  desordreCreateGeometryType.disabled = false;
  desordreCreateId.disabled = false;
  submitDesordreCreateButton.textContent = "Créer";
  cancelDesordreCreateButton.textContent = "Annuler";
  validateDesordreDrawButton.hidden = true;
  polygonRepresentativePoint.hidden = true;
  desordreCreateActions.hidden = false;
  Array.from(desordreCreateForm.elements).forEach((element) => {
    element.disabled = false;
  });
  fillDesordreReferenceOptions();
  fillDesordreTronconOptions();
  lastAcceptedCreationTronconIds = selectedDesordreTronconIds();
  previousDesordreGeometryType = "Point";
  desordreCreateMessage.textContent = "";
  desordreCreateMessage.classList.remove("error");
  updateDesordreCreationControls();
  renderCreationModeChoices(false);
  await refreshCreationReperageAvailability();
  editorPanel.hidden = false;
  desordreCreateDesignation.focus();
}

function closeDesordreDraft() {
  clearDesordreDraft();
  desordreCreateForm.reset();
  desordreCreateForm.hidden = true;
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
  desordreCreateForm.hidden = true;
  editorForm.hidden = true;
  lineEditorForm.hidden = true;
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

document.addEventListener("click", (event) => {
  if (!event.target.closest(".create-menu")) {
    setCreateMenuOpen(false);
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
  updateDesordreCreationControls();
  creationReperageAvailable = false;
  renderCreationModeChoices(false);
  refreshCreationReperageAvailability();
});

Array.from(desordreCreateForm.elements["desordre-point-method"]).forEach((radio) => {
  radio.addEventListener("change", (event) => {
    if (provisionalDesordreLayer && event.target.value !== "map") {
      desordreCreateForm.elements["desordre-point-method"].value = "map";
      desordreCreateMessage.textContent =
        "Annulez explicitement le Point cartographique avant de changer de mode.";
      desordreCreateMessage.classList.add("error");
      return;
    }
    updateDesordreCreationControls();
  });
});

Array.from(desordreCreateForm.elements["desordre-line-method"]).forEach((radio) => {
  radio.addEventListener("change", (event) => {
    if (provisionalDesordreLayer && event.target.value !== "map") {
      desordreCreateForm.elements["desordre-line-method"].value = "map";
      desordreCreateMessage.textContent =
        "Annulez explicitement la ligne cartographique avant de changer de mode.";
      desordreCreateMessage.classList.add("error");
      return;
    }
    updateDesordreCreationControls();
  });
});

desordreCreateLineCrs.addEventListener("change", () => {
  updateLineCoordinateLabels(desordreCreateLineCoordinates, desordreCreateLineCrs.value);
});

desordreCreateTroncons.addEventListener("change", () => {
  const ids = selectedDesordreTronconIds();
  const geometryType = desordreCreateGeometryType.value;
  const method = geometryType === "Point"
    ? desordrePointMethod() : geometryType === "LineString"
      ? desordreLineMethod() : "map";
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
  renderCreationModeChoices(false);
  refreshCreationReperageAvailability();
});

startDesordreDrawButton.addEventListener("click", () => {
  if (editorState.mode === "edit" && editorState.objectType === "desordre_polygon") {
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
    showReadonlyPolygon(lastServerFeature, activePolygonLayer);
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
  if (editorState.mode === "edit" && editorState.objectType === "desordre_polygon") {
    showReadonlyPolygon(lastServerFeature, activePolygonLayer);
  } else {
    closeDesordreDraft();
  }
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
    showReadonlyPolygon(feature, activePolygonLayer);
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
    ? desordrePointMethod()
    : geometryType === "LineString" ? desordreLineMethod() : "map";
  if (geometryType === "Point" && method === "xy") {
    if (desordreCreateX.value === "" || desordreCreateY.value === "") {
      throw new Error("X et Y doivent être renseignés ensemble.");
    }
    payload.coord_x_3950 = Number(desordreCreateX.value);
    payload.coord_y_3950 = Number(desordreCreateY.value);
    return payload;
  }
  if (geometryType === "LineString" && method === "coordinates") {
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
      fields.longitude.value = coordinate(position.lng, 6);
      fields.latitude.value = coordinate(position.lat, 6);
    });
    layer.on("dragend", () => {
      if (!graphicEditActive || layer !== activePointLayer) {
        return;
      }
      provisionalLatLng = layer.getLatLng();
      fields.longitude.value = coordinate(provisionalLatLng.lng, 6);
      fields.latitude.value = coordinate(provisionalLatLng.lat, 6);
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

function showReadonlyPolygon(feature, layer = activePolygonLayer) {
  const properties = feature.properties;
  activePolygonLayer = layer;
  lastServerFeature = feature;
  editorState = { mode: "edit", objectType: "desordre_polygon" };
  editorObjectTitle.textContent = "Désordre polygonal";
  editorObjectSubtitle.textContent = "État relu depuis PostgreSQL — géométrie cartographique";
  editorTabs.hidden = false;
  showEditorTab("general");
  heritageObjectForm.hidden = true;
  editorForm.hidden = true;
  lineEditorForm.hidden = true;
  desordreCreateForm.hidden = false;
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
  desordreCreatePointMethods.hidden = true;
  desordreCreateLineMethods.hidden = true;
  desordreCreateLineCoordinates.hidden = true;
  desordreCreateBornage.hidden = true;
  desordreCreateGeometry.hidden = false;
  startDesordreDrawButton.hidden = false;
  startDesordreDrawButton.textContent = "Modifier le polygone sur la carte";
  desordreDrawStatus.textContent =
    `${properties.nombre_sommets} sommet(s) relu(s) depuis PostgreSQL.`;
  desordreDrawStatus.hidden = false;
  desordreDrawActions.hidden = true;
  validateDesordreDrawButton.hidden = true;
  desordreCreateActions.hidden = false;
  Array.from(desordreCreateForm.elements).forEach((element) => {
    element.disabled = false;
  });
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

desordreCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (creationRequestInFlight) {
    return;
  }
  if (editorState.mode === "edit" && editorState.objectType === "desordre_polygon") {
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
      showReadonlyPolygon(feature, activePolygonLayer);
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
      showReadonlyPolygon(feature, layer);
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

function selectedCoordinateFamily() {
  return editorForm.elements["coordinate-family"].value || null;
}

function generalEditInProgress() {
  return lineEditActive || graphicEditActive
    || ![null, "map"].includes(selectedCoordinateFamily()) || textFieldsChanged();
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

function updateCoordinateInputs() {
  const family = selectedCoordinateFamily();
  fields.x.readOnly = family !== "xy";
  fields.y.readOnly = family !== "xy";
  fields.longitude.readOnly = family !== "lonlat";
  fields.latitude.readOnly = family !== "lonlat";
  bornageFields.hidden = family !== "bornage";
  fields.designation.disabled = family === "bornage" || graphicEditActive;
  fields.commentaire.disabled = family === "bornage" || graphicEditActive;
  fields.type.disabled = family === "bornage" || graphicEditActive;
  fields.dateDebut.disabled = family === "bornage" || graphicEditActive;
  fields.dateFin.disabled = family === "bornage" || graphicEditActive;
  fields.valid.disabled = family === "bornage" || graphicEditActive;
  pointEditTroncon.disabled = family === "bornage" || graphicEditActive;
  startMapPositionButton.disabled = family !== "map";
  reprojectPointBornageButton.hidden = family !== "bornage";
}

function clearCoordinateAuthority() {
  Array.from(editorForm.elements["coordinate-family"]).forEach((radio) => {
    radio.checked = radio.value === "map";
  });
  updateCoordinateInputs();
}

function textFieldsChanged() {
  return initialFormValues && (
    fields.designation.value !== initialFormValues.designation
    || fields.commentaire.value !== initialFormValues.commentaire
    || fields.type.value !== initialFormValues.type_desordre_id
    || fields.dateDebut.value !== initialFormValues.date_debut
    || fields.dateFin.value !== initialFormValues.date_fin
    || fields.valid.checked !== initialFormValues.valid
    || pointEditTroncon.value !== initialFormValues.troncon_id
  );
}

function setGraphicControls(active) {
  graphicEditActive = active;
  startMapPositionButton.hidden = active;
  mapPositionActions.hidden = !active;
  saveButton.disabled = active;
  fields.designation.disabled = active || selectedCoordinateFamily() === "bornage";
  fields.commentaire.disabled = active || selectedCoordinateFamily() === "bornage";
  fields.type.disabled = active || selectedCoordinateFamily() === "bornage";
  fields.dateDebut.disabled = active || selectedCoordinateFamily() === "bornage";
  fields.dateFin.disabled = active || selectedCoordinateFamily() === "bornage";
  fields.valid.disabled = active || selectedCoordinateFamily() === "bornage";
  pointEditTroncon.disabled = active || selectedCoordinateFamily() === "bornage";
  Array.from(editorForm.elements["coordinate-family"]).forEach((radio) => {
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
  pointBornageModeChoice.hidden = !modes.includes("bornage");
  bornageAvailability.hidden = !currentReperage.disponible;
  bornageAvailability.textContent = currentReperage.disponible
    ? "Disponible : un seul tronçon est associé."
    : `Repérage indisponible : ${text(
      currentReperage.motif_indisponibilite,
      "contexte incomplet.",
    )}`;
  reperageFields.troncon.value = text(
    currentReperage.troncon_libelle,
    showUuid ? inputText(currentReperage.troncon_id) : "Tronçon sans libellé",
  );
  reperageFields.systeme.value = text(
    currentReperage.systeme_reperage_libelle,
    showUuid ? inputText(currentReperage.systeme_reperage_id) : "Système sans libellé",
  );
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
  reperageFields.pr.value = coordinate(currentReperage.pr_debut, 2);
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

function renderServerFeature(feature) {
  const properties = feature.properties || {};
  lastServerFeature = feature;
  fields.id.value = inputText(properties.id);
  fields.designation.value = inputText(properties.designation);
  fillTypeSelect(fields.type, properties.type_desordre_id);
  fillTronconSelect(
    pointEditTroncon,
    properties.troncon_ids || [],
    { multiple: false },
  );
  fields.commentaire.value = inputText(properties.commentaire);
  fields.dateDebut.value = inputText(properties.date_debut);
  fields.dateFin.value = inputText(properties.date_fin);
  fields.valid.checked = Boolean(properties.valid);
  fields.x.value = coordinate(properties.coord_x_3950, 2);
  fields.y.value = coordinate(properties.coord_y_3950, 2);
  fields.longitude.value = coordinate(properties.longitude_4326, 6);
  fields.latitude.value = coordinate(properties.latitude_4326, 6);
  renderReperage(properties.reperage);
  initialFormValues = {
    designation: fields.designation.value,
    commentaire: fields.commentaire.value,
    type_desordre_id: fields.type.value,
    date_debut: fields.dateDebut.value,
    date_fin: fields.dateFin.value,
    valid: fields.valid.checked,
    troncon_id: pointEditTroncon.value,
    x: fields.x.value,
    y: fields.y.value,
    longitude: fields.longitude.value,
    latitude: fields.latitude.value,
  };
  clearCoordinateAuthority();
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
  lineFields.id.value = inputText(properties.id);
  lineFields.designation.value = inputText(properties.designation);
  fillTypeSelect(lineFields.type, properties.type_desordre_id);
  lineFields.commentaire.value = inputText(properties.commentaire);
  lineFields.dateDebut.value = inputText(properties.date_debut);
  lineFields.dateFin.value = inputText(properties.date_fin);
  lineFields.valid.checked = Boolean(properties.valid);
  fillTronconSelect(lineEditTroncons, properties.troncon_ids || []);
  lineFields.geometryType.value = text(properties.type_geometrie, "LineString");
  lineFields.vertexCount.value = inputText(properties.nombre_sommets);
  lineFields.reperage.value = lineReperageSummary(properties.reperage);
  const modes = availableDisorderModes(
    "LineString",
    (properties.troncon_ids || []).length,
    properties.reperage?.disponible,
  );
  setModeChoiceAvailability(lineEditBornageChoice, modes.includes("bornage"));
  const activeMode = lineEditorForm.elements["line-edit-mode"].value || "map";
  if (activeMode === "bornage" && !properties.reperage?.disponible) {
    lineEditorForm.elements["line-edit-mode"].value = "map";
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
  updateLineModeControls();
  lineEditorMessage.textContent = "";
  lineEditorMessage.classList.remove("error");
}

function selectedLineMode() {
  return lineEditorForm.elements["line-edit-mode"].value || "map";
}

function updateLineModeControls() {
  const mode = selectedLineMode();
  lineMapEditor.hidden = mode !== "map";
  lineCoordinateEditor.hidden = mode !== "coordinates";
  lineBornageEditor.hidden = mode !== "bornage";
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
  const selected = selectedValues(lineEditTroncons);
  const persisted = (lastServerFeature?.properties?.troncon_ids || []).map(String);
  const sameSelection = selected.length === persisted.length
    && selected.every((id) => persisted.includes(id));
  const bornageAvailable = sameSelection
    && selected.length === 1
    && Boolean(lastServerFeature?.properties?.reperage?.disponible);
  if (selectedLineMode() === "bornage" && !bornageAvailable) {
    if (lineBornageDraftModified()) {
      fillTronconSelect(lineEditTroncons, persisted);
      lineEditorMessage.textContent =
        "Le bornage en cours exige exactement le tronçon actuel. Annulez ou enregistrez ce bornage avant de modifier les rattachements.";
      lineEditorMessage.classList.add("error");
      return;
    }
    lineEditorForm.elements["line-edit-mode"].value = "map";
  }
  setModeChoiceAvailability(lineEditBornageChoice, bornageAvailable);
  updateLineModeControls();
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
  editorState = { mode: "edit", objectType: "desordre_point" };
  activePointLayer = layer;
  editorObjectTitle.textContent = "Désordre ponctuel";
  editorObjectSubtitle.textContent = "État relu depuis PostgreSQL";
  editorTabs.hidden = false;
  heritageObjectForm.hidden = true;
  desordreCreateForm.hidden = true;
  editorForm.hidden = false;
  lineEditorForm.hidden = true;
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
    renderServerFeature(feature);
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
  editorState = { mode: "edit", objectType: "desordre_line" };
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
  desordreCreateForm.hidden = true;
  editorForm.hidden = true;
  lineEditorForm.hidden = false;
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
    showReadonlyPolygon(feature, _layer);
  } catch (error) {
    desordreCreateMessage.textContent = `Lecture impossible : ${error.message}`;
    desordreCreateMessage.classList.add("error");
  }
}

function restoreLastServerState() {
  if (lastServerFeature?.geometry?.type === "Point") {
    renderServerFeature(lastServerFeature);
    updatePointLayer(lastServerFeature);
  } else if (lastServerFeature?.geometry?.type === "LineString") {
    renderLineServerFeature(lastServerFeature);
    updateLineLayer(lastServerFeature);
  }
}

function changedNullableText(current, initial) {
  return current === initial ? undefined : current || null;
}

function buildUpdatePayload() {
  const payload = {};
  const designation = changedNullableText(
    fields.designation.value,
    initialFormValues.designation,
  );
  const commentaire = changedNullableText(
    fields.commentaire.value,
    initialFormValues.commentaire,
  );
  if (designation !== undefined) {
    payload.designation = designation;
  }
  if (commentaire !== undefined) {
    payload.commentaire = commentaire;
  }
  if (fields.type.value !== initialFormValues.type_desordre_id) {
    payload.type_desordre_id = optionalPayloadValue(fields.type.value);
  }
  if (fields.dateDebut.value !== initialFormValues.date_debut) {
    payload.date_debut = fields.dateDebut.value || null;
  }
  if (fields.dateFin.value !== initialFormValues.date_fin) {
    payload.date_fin = fields.dateFin.value || null;
  }
  if (fields.valid.checked !== initialFormValues.valid) {
    payload.valid = fields.valid.checked;
  }
  if (pointEditTroncon.value !== initialFormValues.troncon_id) {
    payload.troncon_ids = pointEditTroncon.value
      ? [pointEditTroncon.value] : [];
  }

  const family = selectedCoordinateFamily();
  if (family === "xy") {
    if (!fields.x.value || !fields.y.value) {
      throw new Error("X et Y doivent être renseignés ensemble.");
    }
    if (fields.x.value !== initialFormValues.x || fields.y.value !== initialFormValues.y) {
      payload.coord_x_3950 = fields.x.value !== initialFormValues.x
        ? Number(fields.x.value)
        : lastServerFeature.properties.coord_x_3950;
      payload.coord_y_3950 = fields.y.value !== initialFormValues.y
        ? Number(fields.y.value)
        : lastServerFeature.properties.coord_y_3950;
    }
  } else if (family === "lonlat") {
    if (!fields.longitude.value || !fields.latitude.value) {
      throw new Error("Longitude et latitude doivent être renseignées ensemble.");
    }
    if (
      fields.longitude.value !== initialFormValues.longitude
      || fields.latitude.value !== initialFormValues.latitude
    ) {
      payload.longitude_4326 = fields.longitude.value !== initialFormValues.longitude
        ? Number(fields.longitude.value)
        : lastServerFeature.properties.longitude_4326;
      payload.latitude_4326 = fields.latitude.value !== initialFormValues.latitude
        ? Number(fields.latitude.value)
        : lastServerFeature.properties.latitude_4326;
    }
  }
  if (Object.keys(payload).length === 0) {
    throw new Error("Aucune modification à enregistrer.");
  }
  return payload;
}

function buildReperagePayload() {
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

Array.from(editorForm.elements["coordinate-family"]).forEach((radio) => {
  radio.addEventListener("change", (event) => {
    if (event.target.value === "xy") {
      fields.longitude.value = initialFormValues.longitude;
      fields.latitude.value = initialFormValues.latitude;
    } else if (event.target.value === "lonlat") {
      fields.x.value = initialFormValues.x;
      fields.y.value = initialFormValues.y;
    } else if (event.target.value === "bornage") {
      if (textFieldsChanged()) {
        event.target.checked = false;
        editorMessage.textContent =
          "Enregistrez ou annulez les champs généraux avant le mode Bornage.";
        editorMessage.classList.add("error");
      } else {
        fields.x.value = initialFormValues.x;
        fields.y.value = initialFormValues.y;
        fields.longitude.value = initialFormValues.longitude;
        fields.latitude.value = initialFormValues.latitude;
      }
    }
    updateCoordinateInputs();
  });
});

reperageFields.sens.addEventListener("change", () => {
  if (reperageFields.sens.value === "SUR_BORNE") {
    reperageFields.distance.value = "0.00";
  }
});

reprojectPointBornageButton.addEventListener("click", () => {
  editorForm.requestSubmit();
});

Array.from(lineEditorForm.elements["line-edit-mode"]).forEach((radio) => {
  radio.addEventListener("change", updateLineModeControls);
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

saveLineMetadataButton.addEventListener("click", () => {
  saveLineRequest("", {
    designation: optionalPayloadValue(lineFields.designation.value),
    type_desordre_id: optionalPayloadValue(lineFields.type.value),
    commentaire: optionalPayloadValue(lineFields.commentaire.value),
    date_debut: optionalPayloadValue(lineFields.dateDebut.value),
    date_fin: optionalPayloadValue(lineFields.dateFin.value),
    valid: lineFields.valid.checked,
    troncon_ids: selectedValues(lineEditTroncons),
  }, "Informations et rattachements relus depuis PostgreSQL.");
});

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

reprojectLineBornageButton.addEventListener("click", () => {
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
  if (selectedCoordinateFamily() !== "map") {
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
  fields.longitude.value = coordinate(provisionalLatLng.lng, 6);
  fields.latitude.value = coordinate(provisionalLatLng.lat, 6);
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
    renderServerFeature(feature);
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
  lineFields.vertexCount.value = String(activeLineLayer.getLatLngs().length);
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

editorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!lastServerFeature) {
    return;
  }
  let payload;
  const family = selectedCoordinateFamily();
  try {
    payload = family === "bornage"
      ? buildReperagePayload()
      : buildUpdatePayload();
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
    renderServerFeature(feature);
    updatePointLayer(feature);
    editorMessage.textContent = "Enregistré — valeurs relues depuis PostgreSQL.";
  } catch (error) {
    console.error("Mise à jour du désordre impossible", error);
    editorMessage.textContent = `Enregistrement refusé : ${error.message}`;
    editorMessage.classList.add("error");
  } finally {
    saveButton.disabled = false;
  }
});

cancelEditButton.addEventListener("click", () => {
  if (graphicEditActive) {
    stopGraphicEdit({ restore: true });
  } else {
    restoreLastServerState();
  }
});

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
    const [troncons, desordres] = await Promise.all([
      fetchGeoJSON("/api/troncons"),
      fetchGeoJSON("/api/desordres"),
    ]);

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
    const bounds = allData.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17 });
    }

    statusElement.textContent =
      `${troncons.features.length} tronçon(s), `
      + `${desordres.features.length} désordre(s)`;
  } catch (error) {
    console.error("Chargement cartographique impossible", error);
    statusElement.textContent = `Chargement impossible : ${error.message}`;
    statusElement.classList.add("error");
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
