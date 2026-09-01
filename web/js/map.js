const map = L.map("map", {
  zoomControl: false,
  editable: true,
}).setView([46.8, 2.5], 6);
const statusElement = document.querySelector("#status");
const heritageToggleButton = document.querySelector("#toggle-heritage");
const heritageCloseButton = document.querySelector("#close-heritage");
const heritagePanel = document.querySelector("#heritage-panel");
const mapLegend = document.querySelector("#map-legend");
const heritageTree = document.querySelector("#heritage-tree");
const heritageLoading = document.querySelector("#heritage-loading");
const heritagePropertiesEmpty = document.querySelector("#heritage-properties-empty");
const heritagePropertiesList = document.querySelector("#heritage-properties-list");
const zoomTronconButton = document.querySelector("#zoom-troncon");
const editorPanel = document.querySelector("#editor-panel");
const editorForm = document.querySelector("#point-editor");
const lineEditorForm = document.querySelector("#line-editor");
const editorObjectTitle = document.querySelector("#editor-object-title");
const editorObjectSubtitle = document.querySelector("#editor-object-subtitle");
const editorMessage = document.querySelector("#editor-message");
const saveButton = document.querySelector("#save-edit");
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
  geometryType: document.querySelector("#line-geometry-type"),
  vertexCount: document.querySelector("#line-vertex-count"),
  reperage: document.querySelector("#line-reperage-summary"),
};

let activePointLayer = null;
let lastServerFeature = null;
let initialFormValues = null;
let requestedDesordreId = null;
let graphicEditActive = false;
let provisionalLatLng = null;
let graphicRequestInFlight = false;
let heritageLoaded = false;
let heritageLoadingPromise = null;
let selectedTreeButton = null;
let selectedHeritageObject = null;
let tronconsGeoJsonLayer = null;
let highlightedTronconLayer = null;
let observationsLoadedFor = null;
let currentObservationPhotos = [];
let currentPhotoIndex = -1;
let currentReperage = null;
let activeLineLayer = null;
let selectedLineLayer = null;
let lineEditActive = false;
let lineRequestInFlight = false;
let desordresGeoJsonLayer = null;
const tronconLayersById = new Map();

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

function inputText(value) {
  return value === null || value === undefined ? "" : String(value);
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
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = text(value);
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
      observation.urgence_libelle || observation.urgence_id,
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
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = text(value);
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
    propertyRow("Parent", `${parent.libelle || "—"} — ${parent.id}`);
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
  toggle.setAttribute("aria-label", `Déplier ${item.libelle || item.id}`);
  const name = document.createElement("button");
  name.type = "button";
  name.className = "tree-name";
  name.textContent = item.libelle || item.id;
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
      `${expanded ? "Déplier" : "Replier"} ${item.libelle || item.id}`,
    );
    childContainer.hidden = expanded;
  });
  return node;
}

function renderHeritageTree(data) {
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

function selectedCoordinateFamily() {
  return editorForm.elements["coordinate-family"].value || null;
}

function generalEditInProgress() {
  return lineEditActive || graphicEditActive
    || selectedCoordinateFamily() !== null || textFieldsChanged();
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
  startMapPositionButton.disabled = family !== null;
}

function clearCoordinateAuthority() {
  Array.from(editorForm.elements["coordinate-family"]).forEach((radio) => {
    radio.checked = false;
  });
  updateCoordinateInputs();
}

function textFieldsChanged() {
  return initialFormValues && (
    fields.designation.value !== initialFormValues.designation
    || fields.commentaire.value !== initialFormValues.commentaire
  );
}

function setGraphicControls(active) {
  graphicEditActive = active;
  startMapPositionButton.hidden = active;
  mapPositionActions.hidden = !active;
  saveButton.disabled = active;
  fields.designation.disabled = active || selectedCoordinateFamily() === "bornage";
  fields.commentaire.disabled = active || selectedCoordinateFamily() === "bornage";
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
  bornageModeRadio.disabled = !currentReperage.disponible;
  bornageAvailability.textContent = currentReperage.disponible
    ? "Disponible : un seul tronçon est associé."
    : `Repérage indisponible : ${text(
      currentReperage.motif_indisponibilite,
      "contexte incomplet.",
    )}`;
  reperageFields.troncon.value = text(
    currentReperage.troncon_libelle,
    inputText(currentReperage.troncon_id),
  );
  reperageFields.systeme.value = text(
    currentReperage.systeme_reperage_libelle,
    inputText(currentReperage.systeme_reperage_id),
  );
  reperageFields.borne.replaceChildren();
  const bornes = Array.isArray(currentReperage.bornes)
    ? currentReperage.bornes
    : [];
  bornes.forEach((borne) => {
    const option = document.createElement("option");
    option.value = borne.id;
    option.textContent = borne.libelle_affichage || borne.libelle || borne.id;
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
      currentReperage.borne_debut_id,
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
  fields.type.value = text(
    properties.type_desordre_libelle,
    inputText(properties.type_desordre_id) || "—",
  );
  fields.commentaire.value = inputText(properties.commentaire);
  fields.x.value = coordinate(properties.coord_x_3950, 2);
  fields.y.value = coordinate(properties.coord_y_3950, 2);
  fields.longitude.value = coordinate(properties.longitude_4326, 6);
  fields.latitude.value = coordinate(properties.latitude_4326, 6);
  renderReperage(properties.reperage);
  initialFormValues = {
    designation: fields.designation.value,
    commentaire: fields.commentaire.value,
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
  lineFields.type.value = text(
    properties.type_desordre_libelle,
    inputText(properties.type_desordre_id) || "—",
  );
  lineFields.commentaire.value = inputText(properties.commentaire);
  lineFields.geometryType.value = text(properties.type_geometrie, "LineString");
  lineFields.vertexCount.value = inputText(properties.nombre_sommets);
  lineFields.reperage.value = lineReperageSummary(properties.reperage);
  lineEditorMessage.textContent = "";
  lineEditorMessage.classList.remove("error");
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
  if (selectedLineLayer && desordresGeoJsonLayer && !lineEditActive) {
    desordresGeoJsonLayer.resetStyle(selectedLineLayer);
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
  activePointLayer?.dragging?.disable();
  clearSelectedLine();
  requestedDesordreId = id;
  activePointLayer = layer;
  editorObjectTitle.textContent = "Désordre ponctuel";
  editorObjectSubtitle.textContent = "État relu depuis PostgreSQL";
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
  activePointLayer?.dragging?.disable();
  activePointLayer = null;
  clearSelectedLine();
  requestedDesordreId = id;
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

startMapPositionButton.addEventListener("click", () => {
  if (selectedCoordinateFamily()) {
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
    const [troncons, desordres] = await Promise.all([
      fetchGeoJSON("/api/troncons"),
      fetchGeoJSON("/api/desordres"),
    ]);

    tronconsGeoJsonLayer = L.geoJSON(troncons, {
      style: { color: "#39735a", opacity: 0.85, weight: 4 },
      onEachFeature(feature, layer) {
        tronconLayersById.set(String(feature.properties.id), layer);
        layer.bindPopup(
          popupContent(feature.properties || {}, [
            ["Tronçon", "libelle"],
            ["Digue", "digue_libelle"],
            ["Identifiant", "id"],
          ]),
        );
      },
    }).addTo(map);

    if (selectedHeritageObject?.kind === "Tronçon") {
      const layer = highlightTroncon(selectedHeritageObject.item.id);
      zoomTronconButton.disabled = !layer;
    }

    desordresGeoJsonLayer = L.geoJSON(desordres, {
      style: { color: "#e4772f", opacity: 0.95, weight: 5 },
      pointToLayer(_feature, latlng) {
        return L.marker(latlng, {
          draggable: false,
          icon: pointIcon,
        });
      },
      onEachFeature(feature, layer) {
        if (feature.geometry?.type === "Point") {
          layer.on("click", () => openPointEditor(feature.properties.id, layer));
          layer.on("dragstart", () => {
            if (graphicEditActive && layer === activePointLayer) {
              mapPositionStatus.textContent =
                "Déplacement en cours — position non enregistrée.";
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
            mapPositionStatus.textContent =
              "Position provisoire — validez ou annulez le déplacement.";
          });
          return;
        }
        if (feature.geometry?.type === "LineString") {
          layer.on("click", () => openLineEditor(feature.properties.id, layer));
        }
      },
    }).addTo(map);

    L.control.layers(null, {
      Tronçons: tronconsGeoJsonLayer,
      Désordres: desordresGeoJsonLayer,
    }).addTo(map);

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
