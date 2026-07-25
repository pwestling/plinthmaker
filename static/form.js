const MILLIMETERS_PER_INCH = 25.4;
const CURRENT_DRAFT_STORAGE_KEY = "plinthmaker.current.v1";
const HISTORY_STORAGE_KEY = "plinthmaker.history.v1";
const HISTORY_LIMIT = 50;
const DRAFT_SAVE_DELAY_MS = 500;

const LENGTH_FIELD_NAMES = [
  "height",
  "depth",
  "width",
  "circular_diameter",
  "center_pole_height",
  "center_pole_diameter",
  "center_hole_depth",
  "center_hole_diameter",
  "bottom_hole_depth",
  "bottom_hole_diameter",
  "bottom_hole_inset",
  "footer_height",
  "footer_lower_outset",
  "footer_upper_outset",
  "footer_lower_band_height",
  "footer_fillet_radius",
  "backdrop_height",
  "backdrop_depth",
];

const MODEL_QUERY_FIELD_NAMES = [
  "plinth_type",
  "circular_diameter",
  "depth",
  "width",
  "height",
  "slope_angle",
  "center_feature",
  "center_pole_height",
  "center_pole_diameter",
  "center_hole_depth",
  "center_hole_diameter",
  "include_bottom_holes",
  "bottom_hole_count",
  "bottom_hole_depth",
  "bottom_hole_diameter",
  "bottom_hole_inset",
  "bottom_hole_start_angle",
  "include_footer",
  "footer_height",
  "footer_lower_outset",
  "footer_upper_outset",
  "footer_lower_band_height",
  "footer_fillet_radius",
  "include_backdrop",
  "backdrop_height",
  "backdrop_depth",
];

const DEFAULT_LENGTHS_MM = {
  height: 60,
  depth: 55,
  width: 55,
  circular_diameter: 110,
  center_pole_height: 20,
  center_pole_diameter: 7.62,
  center_hole_depth: 20,
  center_hole_diameter: 7.62,
  bottom_hole_depth: 3,
  bottom_hole_diameter: 2,
  bottom_hole_inset: 5,
  footer_height: 8,
  footer_lower_outset: 4,
  footer_upper_outset: 2,
  footer_lower_band_height: 3,
  footer_fillet_radius: 0,
  backdrop_height: 12,
  backdrop_depth: 3,
};

const DEFAULT_FORM_VALUES = {
  configuration_name: "",
  plinth_type: "rectangular",
  display_units: "mm",
  include_scale_reference: false,
  scale_reference_mini_id: "",
  scale_reference_mini_name: "",
  slope_angle: 0,
  center_feature: "none",
  include_bottom_holes: true,
  bottom_hole_count: 2,
  bottom_hole_start_angle: 90,
  include_footer: false,
  include_backdrop: false,
};

function parseNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatLength(value, units) {
  const precision = units === "in" ? 3 : 2;
  return value.toFixed(precision).replace(/\.?0+$/, "");
}

function formatLengthFromMillimeters(value, units) {
  const displayValue = units === "in" ? value / MILLIMETERS_PER_INCH : value;
  return formatLength(displayValue, units);
}

function readJsonStorage(key) {
  try {
    const rawValue = window.localStorage.getItem(key);
    if (rawValue === null) {
      return null;
    }

    return JSON.parse(rawValue);
  } catch (error) {
    return null;
  }
}

function writeJsonStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    return false;
  }
}

function removeStorageItem(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    // Storage can fail in privacy-restricted contexts; the UI should keep working.
  }
}

function parseBoolean(value, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    return value === "true" ? true : value === "false" ? false : fallback;
  }

  return fallback;
}

function normalizeChoice(value, choices, fallback) {
  return choices.includes(value) ? value : fallback;
}

function normalizeConfigurationName(value) {
  if (typeof value !== "string") {
    return "";
  }

  return value.trim().slice(0, 120);
}

function normalizeMiniId(value) {
  if (typeof value !== "string") {
    return "";
  }

  const normalized = value.trim();
  return /^[A-Za-z0-9][A-Za-z0-9 _+'-]{0,159}$/.test(normalized) ? normalized : "";
}

function normalizeMiniName(value) {
  if (typeof value !== "string") {
    return "";
  }

  return value.trim().replace(/\s+/g, " ").slice(0, 180);
}

function storageId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return `pmh_${window.crypto.randomUUID()}`;
  }

  return `pmh_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function queryValue(value) {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (typeof value === "number") {
    return formatLength(value, "mm");
  }

  return String(value);
}

function modelQueryString(payload) {
  const params = new URLSearchParams();
  MODEL_QUERY_FIELD_NAMES.forEach((name) => {
    params.set(name, queryValue(payload[name]));
  });
  return params.toString();
}

function historySignature(payload) {
  return JSON.stringify(
    MODEL_QUERY_FIELD_NAMES.map((name) => [name, queryValue(payload[name])]),
  );
}

function dimensionLabelForPayload(payload) {
  const unitLabel = payload.display_units === "in" ? "in" : "mm";
  if (payload.plinth_type === "circular") {
    return `Circular ${formatLengthFromMillimeters(
      payload.circular_diameter,
      payload.display_units,
    )} ${unitLabel}`;
  }

  return `Rectangular ${formatLengthFromMillimeters(
    payload.depth,
    payload.display_units,
  )} x ${formatLengthFromMillimeters(
    payload.width,
    payload.display_units,
  )} x ${formatLengthFromMillimeters(
    payload.height,
    payload.display_units,
  )} ${unitLabel}`;
}

function labelForPayload(payload) {
  return payload.configuration_name || dimensionLabelForPayload(payload);
}

function badgesForPayload(payload) {
  const badges = [];
  if (payload.center_feature === "pole") {
    badges.push("pole");
  } else if (payload.center_feature === "hole") {
    badges.push("hole");
  }

  if (payload.include_bottom_holes) {
    badges.push("bottom holes");
  }

  if (payload.include_footer) {
    badges.push("footer");
  }

  if (payload.plinth_type === "rectangular" && payload.include_backdrop) {
    badges.push("backdrop");
  }

  return badges;
}

function formatTimestamp(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

window.plinthForm = function plinthForm(initialState) {
  const lengthsMm = {};
  Object.entries(initialState.lengthsMm).forEach(([name, value]) => {
    lengthsMm[name] = parseNumber(value);
  });

  return {
    plinthType: initialState.plinthType === "circular" ? "circular" : "rectangular",
    displayUnits: initialState.displayUnits === "in" ? "in" : "mm",
    centerFeature: ["none", "pole", "hole"].includes(initialState.centerFeature)
      ? initialState.centerFeature
      : "none",
    includeBottomHoles: Boolean(initialState.includeBottomHoles),
    includeFooter: Boolean(initialState.includeFooter),
    includeBackdrop: Boolean(initialState.includeBackdrop),
    lengthsMm,
    displayLengths: {},
    historyEntries: [],
    currentDraftSavedAt: "",
    draftSaveTimer: 0,
    storageNotice: "",
    formElement: null,
    activePanel: "configuration",
    configurationName: normalizeConfigurationName(initialState.configurationName),
    selectedMiniId: normalizeMiniId(initialState.selectedMiniId),
    selectedMiniName: normalizeMiniName(initialState.selectedMiniName),
    miniSearchQuery: "",
    miniSearchResults: [],
    miniSearchState: "idle",
    miniSearchMessage: "",
    miniSearchTimer: 0,
    miniSearchAbortController: null,

    init() {
      this.formElement = this.$el;
      this.formElement.plinthFormController = this;
      this.refreshDisplayValues();
      this.loadHistory();
      this.restoreCurrentDraft();
      this.bindDraftAutosave();
    },

    queueMiniSearch() {
      window.clearTimeout(this.miniSearchTimer);
      const query = this.miniSearchQuery.trim();
      if (query.length < 2) {
        if (this.miniSearchAbortController !== null) {
          this.miniSearchAbortController.abort();
        }
        this.miniSearchResults = [];
        this.miniSearchState = "idle";
        this.miniSearchMessage = query.length === 1 ? "Type one more character." : "";
        return;
      }

      this.miniSearchState = "waiting";
      this.miniSearchMessage = "Searching MiniCompare…";
      this.miniSearchTimer = window.setTimeout(() => {
        this.performMiniSearch(query);
      }, 250);
    },

    async performMiniSearch(query) {
      if (this.miniSearchAbortController !== null) {
        this.miniSearchAbortController.abort();
      }

      const controller = new AbortController();
      this.miniSearchAbortController = controller;
      this.miniSearchState = "loading";

      try {
        const response = await fetch(
          `/api/minicompare/search?q=${encodeURIComponent(query)}&limit=16`,
          {
            headers: { Accept: "application/json" },
            signal: controller.signal,
          },
        );
        if (!response.ok) {
          throw new Error(`MiniCompare search failed with ${response.status}`);
        }

        const payload = await response.json();
        if (controller.signal.aborted || this.miniSearchQuery.trim() !== query) {
          return;
        }

        this.miniSearchResults = Array.isArray(payload.items) ? payload.items : [];
        this.miniSearchState = "ready";
        this.miniSearchMessage = this.miniSearchResults.length === 0
          ? "No matching minis found."
          : `${this.miniSearchResults.length} matches`;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        this.miniSearchResults = [];
        this.miniSearchState = "error";
        this.miniSearchMessage = "MiniCompare is temporarily unavailable. Try again.";
      }
    },

    selectMini(mini) {
      const miniId = normalizeMiniId(mini.id);
      const miniName = normalizeMiniName(mini.name);
      if (miniId === "" || miniName === "") {
        return;
      }

      this.selectedMiniId = miniId;
      this.selectedMiniName = miniName;
      this.miniSearchQuery = "";
      this.miniSearchResults = [];
      this.miniSearchState = "idle";
      this.miniSearchMessage = "";
      this.setFieldValue("scale_reference_mini_id", miniId);
      this.setFieldValue("scale_reference_mini_name", miniName);
      this.setFieldValue("include_scale_reference", "true");
      this.$nextTick(() => {
        this.saveCurrentDraft();
        this.requestPreview();
      });
    },

    clearSelectedMini() {
      this.selectedMiniId = "";
      this.selectedMiniName = "";
      this.setFieldValue("scale_reference_mini_id", "");
      this.setFieldValue("scale_reference_mini_name", "");
      this.setFieldValue("include_scale_reference", "false");
      this.$nextTick(() => {
        this.saveCurrentDraft();
        this.requestPreview();
      });
    },

    miniImageUrl(miniId) {
      const normalized = normalizeMiniId(miniId);
      return normalized === ""
        ? ""
        : `/api/minicompare/image/${encodeURIComponent(normalized)}`;
    },

    miniSourceUrl(miniId) {
      const normalized = normalizeMiniId(miniId);
      return normalized === ""
        ? "https://minicompare.info/"
        : `https://minicompare.info/?${encodeURIComponent(normalized)}=`;
    },

    toMillimeters(value) {
      return this.displayUnits === "in" ? value * MILLIMETERS_PER_INCH : value;
    },

    fromMillimeters(value) {
      return this.displayUnits === "in" ? value / MILLIMETERS_PER_INCH : value;
    },

    displayMin(valueMm) {
      return formatLength(this.fromMillimeters(valueMm), this.displayUnits);
    },

    displayStep(valueMm) {
      return "any";
    },

    mmValue(name) {
      return formatLength(this.lengthsMm[name], "mm");
    },

    refreshDisplayValues() {
      Object.keys(this.lengthsMm).forEach((name) => {
        this.displayLengths[name] = formatLength(
          this.fromMillimeters(this.lengthsMm[name]),
          this.displayUnits,
        );
      });
    },

    setLength(name, rawValue) {
      this.displayLengths[name] = rawValue;
      if (rawValue === "") {
        return;
      }

      const parsedValue = Number(rawValue);
      if (!Number.isFinite(parsedValue)) {
        return;
      }

      this.lengthsMm[name] = this.toMillimeters(parsedValue);
    },

    setConfigurationName(rawValue) {
      this.configurationName = rawValue.slice(0, 120);
      this.scheduleDraftSave();
    },

    fieldValue(name, fallback = "") {
      if (this.formElement === null) {
        return fallback;
      }

      const field = this.formElement.elements.namedItem(name);
      if (field === null || !("value" in field)) {
        return fallback;
      }

      return field.value;
    },

    setFieldValue(name, value) {
      if (this.formElement === null) {
        return;
      }

      const field = this.formElement.elements.namedItem(name);
      if (field !== null && "value" in field) {
        field.value = String(value);
      }
    },

    readScaleReferenceValue() {
      return parseBoolean(
        this.fieldValue(
          "include_scale_reference",
          DEFAULT_FORM_VALUES.include_scale_reference ? "true" : "false",
        ),
        DEFAULT_FORM_VALUES.include_scale_reference,
      );
    },

    snapshotFormPayload() {
      const payload = {
        ...DEFAULT_FORM_VALUES,
        configuration_name: normalizeConfigurationName(this.configurationName),
        plinth_type: this.plinthType,
        display_units: this.displayUnits,
        include_scale_reference: this.readScaleReferenceValue(),
        scale_reference_mini_id: normalizeMiniId(this.selectedMiniId),
        scale_reference_mini_name: normalizeMiniName(this.selectedMiniName),
        slope_angle: parseNumber(
          this.fieldValue("slope_angle", DEFAULT_FORM_VALUES.slope_angle),
          DEFAULT_FORM_VALUES.slope_angle,
        ),
        center_feature: this.centerFeature,
        include_bottom_holes: Boolean(this.includeBottomHoles),
        bottom_hole_count: Math.max(
          1,
          Math.round(
            parseNumber(
              this.fieldValue(
                "bottom_hole_count",
                DEFAULT_FORM_VALUES.bottom_hole_count,
              ),
              DEFAULT_FORM_VALUES.bottom_hole_count,
            ),
          ),
        ),
        bottom_hole_start_angle: parseNumber(
          this.fieldValue(
            "bottom_hole_start_angle",
            DEFAULT_FORM_VALUES.bottom_hole_start_angle,
          ),
          DEFAULT_FORM_VALUES.bottom_hole_start_angle,
        ),
        include_footer: Boolean(this.includeFooter),
        include_backdrop: Boolean(this.includeBackdrop),
      };

      LENGTH_FIELD_NAMES.forEach((name) => {
        payload[name] = parseNumber(this.lengthsMm[name], DEFAULT_LENGTHS_MM[name]);
      });

      return payload;
    },

    normalizeFormPayload(rawPayload) {
      if (rawPayload === null || typeof rawPayload !== "object") {
        return null;
      }

      const fallback = this.snapshotFormPayload();
      const scaleReferenceMiniId = normalizeMiniId(rawPayload.scale_reference_mini_id);
      const payload = {
        ...fallback,
        configuration_name: normalizeConfigurationName(rawPayload.configuration_name),
        plinth_type: normalizeChoice(
          rawPayload.plinth_type,
          ["rectangular", "circular"],
          fallback.plinth_type,
        ),
        display_units: normalizeChoice(
          rawPayload.display_units,
          ["mm", "in"],
          fallback.display_units,
        ),
        include_scale_reference: parseBoolean(
          rawPayload.include_scale_reference,
          fallback.include_scale_reference,
        ) && scaleReferenceMiniId !== "",
        scale_reference_mini_id: scaleReferenceMiniId,
        scale_reference_mini_name: normalizeMiniName(
          rawPayload.scale_reference_mini_name,
        ),
        slope_angle: parseNumber(rawPayload.slope_angle, fallback.slope_angle),
        center_feature: normalizeChoice(
          rawPayload.center_feature,
          ["none", "pole", "hole"],
          fallback.center_feature,
        ),
        include_bottom_holes: parseBoolean(
          rawPayload.include_bottom_holes,
          fallback.include_bottom_holes,
        ),
        bottom_hole_count: Math.max(
          1,
          Math.round(parseNumber(rawPayload.bottom_hole_count, fallback.bottom_hole_count)),
        ),
        bottom_hole_start_angle: parseNumber(
          rawPayload.bottom_hole_start_angle,
          fallback.bottom_hole_start_angle,
        ),
        include_footer: parseBoolean(rawPayload.include_footer, fallback.include_footer),
        include_backdrop: parseBoolean(
          rawPayload.include_backdrop,
          fallback.include_backdrop,
        ),
      };

      LENGTH_FIELD_NAMES.forEach((name) => {
        payload[name] = parseNumber(rawPayload[name], fallback[name]);
      });

      return payload;
    },

    applyFormPayload(rawPayload, options = {}) {
      const payload = this.normalizeFormPayload(rawPayload);
      if (payload === null) {
        return false;
      }

      const shouldRequestPreview = options.requestPreview !== false;
      const shouldSaveDraft = options.saveDraft !== false;

      this.plinthType = payload.plinth_type;
      this.displayUnits = payload.display_units;
      this.centerFeature = payload.center_feature;
      this.includeBottomHoles = payload.include_bottom_holes;
      this.includeFooter = payload.include_footer;
      this.includeBackdrop = payload.include_backdrop;
      this.configurationName = payload.configuration_name;
      this.selectedMiniId = payload.scale_reference_mini_id;
      this.selectedMiniName = payload.scale_reference_mini_name;

      LENGTH_FIELD_NAMES.forEach((name) => {
        this.lengthsMm[name] = payload[name];
      });
      this.refreshDisplayValues();

      this.setFieldValue("include_scale_reference", payload.include_scale_reference);
      this.setFieldValue("scale_reference_mini_id", payload.scale_reference_mini_id);
      this.setFieldValue("scale_reference_mini_name", payload.scale_reference_mini_name);
      this.setFieldValue("slope_angle", payload.slope_angle);
      this.setFieldValue("bottom_hole_count", payload.bottom_hole_count);
      this.setFieldValue("bottom_hole_start_angle", payload.bottom_hole_start_angle);

      this.$nextTick(() => {
        if (shouldSaveDraft) {
          this.saveCurrentDraft();
        }

        if (shouldRequestPreview) {
          window.setTimeout(() => {
            this.requestPreview();
          }, 0);
        }
      });

      return true;
    },

    requestPreview() {
      if (this.formElement === null) {
        return;
      }

      if (window.htmx) {
        window.htmx.trigger(this.formElement, "submit");
        return;
      }

      if (typeof this.formElement.requestSubmit === "function") {
        this.formElement.requestSubmit();
      }
    },

    bindDraftAutosave() {
      if (this.formElement === null) {
        return;
      }

      this.formElement.addEventListener("input", () => {
        this.scheduleDraftSave();
      });
      this.formElement.addEventListener("change", () => {
        this.scheduleDraftSave();
      });
    },

    scheduleDraftSave() {
      window.clearTimeout(this.draftSaveTimer);
      this.draftSaveTimer = window.setTimeout(() => {
        this.saveCurrentDraft();
      }, DRAFT_SAVE_DELAY_MS);
    },

    saveCurrentDraft() {
      const savedAt = new Date().toISOString();
      const stored = writeJsonStorage(CURRENT_DRAFT_STORAGE_KEY, {
        schemaVersion: 1,
        savedAt,
        form: this.snapshotFormPayload(),
      });

      if (stored) {
        this.currentDraftSavedAt = savedAt;
        this.storageNotice = "";
      } else {
        this.storageNotice = "Browser storage is unavailable.";
      }
    },

    restoreCurrentDraft() {
      const draft = readJsonStorage(CURRENT_DRAFT_STORAGE_KEY);
      if (
        draft === null ||
        draft.schemaVersion !== 1 ||
        draft.form === null ||
        typeof draft.form !== "object"
      ) {
        return false;
      }

      this.currentDraftSavedAt = draft.savedAt || "";
      return this.applyFormPayload(draft.form, {
        requestPreview: true,
        saveDraft: false,
      });
    },

    draftStatusText() {
      if (this.currentDraftSavedAt === "") {
        return "No draft saved yet";
      }

      return `Last edited ${formatTimestamp(this.currentDraftSavedAt)}`;
    },

    payloadFromDownloadUrl(href) {
      const payload = this.snapshotFormPayload();
      const url = new URL(href, window.location.href);

      MODEL_QUERY_FIELD_NAMES.forEach((name) => {
        if (!url.searchParams.has(name)) {
          return;
        }

        const value = url.searchParams.get(name);
        if (
          [
            "include_bottom_holes",
            "include_footer",
            "include_backdrop",
          ].includes(name)
        ) {
          payload[name] = parseBoolean(value, payload[name]);
        } else if (["plinth_type", "center_feature"].includes(name)) {
          payload[name] = value;
        } else if (name === "bottom_hole_count") {
          payload[name] = Math.max(1, Math.round(parseNumber(value, payload[name])));
        } else {
          payload[name] = parseNumber(value, payload[name]);
        }
      });

      return this.normalizeFormPayload(payload);
    },

    decorateHistoryEntry(rawEntry) {
      const payload = this.normalizeFormPayload(rawEntry.form);
      if (payload === null) {
        return null;
      }

      const query = modelQueryString(payload);
      return {
        id: rawEntry.id || storageId(),
        createdAt: rawEntry.createdAt || new Date().toISOString(),
        updatedAt: rawEntry.updatedAt || rawEntry.createdAt || new Date().toISOString(),
        filename: rawEntry.filename || "plinth.stl",
        form: payload,
        query,
        href: `/api/model.stl?${query}`,
        name: payload.configuration_name,
        label: labelForPayload(payload),
        dimensionLabel: dimensionLabelForPayload(payload),
        badges: badgesForPayload(payload),
        signature: historySignature(payload),
      };
    },

    loadHistory() {
      const storedHistory = readJsonStorage(HISTORY_STORAGE_KEY);
      if (
        storedHistory === null ||
        storedHistory.schemaVersion !== 1 ||
        !Array.isArray(storedHistory.entries)
      ) {
        this.historyEntries = [];
        return;
      }

      this.historyEntries = storedHistory.entries
        .map((entry) => this.decorateHistoryEntry(entry))
        .filter((entry) => entry !== null)
        .slice(0, HISTORY_LIMIT);
    },

    persistHistory() {
      const entries = this.historyEntries.map((entry) => ({
        id: entry.id,
        createdAt: entry.createdAt,
        updatedAt: entry.updatedAt,
        filename: entry.filename,
        query: entry.query,
        form: entry.form,
      }));

      const stored = writeJsonStorage(HISTORY_STORAGE_KEY, {
        schemaVersion: 1,
        entries,
      });

      if (!stored) {
        this.storageNotice = "Browser storage is unavailable.";
      } else {
        this.storageNotice = "";
      }
    },

    recordDownloadSnapshot(href, filename) {
      const payload = this.payloadFromDownloadUrl(href);
      if (payload === null) {
        return;
      }

      const now = new Date().toISOString();
      const signature = historySignature(payload);
      const existingEntry = this.historyEntries.find(
        (entry) => entry.signature === signature,
      );
      const entryPayload = { ...payload };
      if (
        existingEntry &&
        entryPayload.configuration_name === "" &&
        existingEntry.form.configuration_name !== ""
      ) {
        entryPayload.configuration_name = existingEntry.form.configuration_name;
      }

      const nextEntry = this.decorateHistoryEntry({
        id: existingEntry ? existingEntry.id : storageId(),
        createdAt: existingEntry ? existingEntry.createdAt : now,
        updatedAt: now,
        filename: filename || (existingEntry ? existingEntry.filename : "plinth.stl"),
        form: entryPayload,
      });

      if (nextEntry === null) {
        return;
      }

      this.historyEntries = [
        nextEntry,
        ...this.historyEntries.filter((entry) => entry.signature !== signature),
      ].slice(0, HISTORY_LIMIT);
      this.persistHistory();
      this.saveCurrentDraft();
    },

    loadHistoryEntry(id) {
      const entry = this.historyEntries.find((candidate) => candidate.id === id);
      if (!entry) {
        return;
      }

      this.touchHistoryEntry(id);
      this.applyFormPayload(entry.form, {
        requestPreview: true,
        saveDraft: true,
      });
      this.activePanel = "configuration";
    },

    renameHistoryEntry(id, rawName) {
      const entry = this.historyEntries.find((candidate) => candidate.id === id);
      if (!entry) {
        return;
      }

      const renamedEntry = this.decorateHistoryEntry({
        ...entry,
        form: {
          ...entry.form,
          configuration_name: normalizeConfigurationName(rawName),
        },
      });
      if (renamedEntry === null) {
        return;
      }

      this.historyEntries = this.historyEntries.map((candidate) => (
        candidate.id === id ? renamedEntry : candidate
      ));
      this.persistHistory();
    },

    touchHistoryEntry(id) {
      const entry = this.historyEntries.find((candidate) => candidate.id === id);
      if (!entry) {
        return;
      }

      const touchedEntry = {
        ...entry,
        updatedAt: new Date().toISOString(),
      };
      this.historyEntries = [
        touchedEntry,
        ...this.historyEntries.filter((candidate) => candidate.id !== id),
      ];
      this.persistHistory();
    },

    deleteHistoryEntry(id) {
      this.historyEntries = this.historyEntries.filter((entry) => entry.id !== id);
      this.persistHistory();
    },

    clearHistory() {
      this.historyEntries = [];
      removeStorageItem(HISTORY_STORAGE_KEY);
    },

    formattedEntryTime(entry) {
      return formatTimestamp(entry.updatedAt);
    },
  };
};

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }

  const downloadLink = event.target.closest("[data-history-download]");
  if (downloadLink === null) {
    return;
  }

  const form = document.querySelector("[data-plinth-form]");
  const controller = form ? form.plinthFormController : null;
  if (controller) {
    controller.recordDownloadSnapshot(
      downloadLink.href,
      downloadLink.getAttribute("download") || "",
    );
  }
});

document.addEventListener(
  "change",
  (event) => {
    if (
      !(event.target instanceof Element) ||
      !event.target.matches("[data-scale-reference-toggle]")
    ) {
      return;
    }

    const hiddenField = document.getElementById("include_scale_reference_hidden");
    if (hiddenField !== null) {
      hiddenField.value = event.target.checked ? "true" : "false";
    }
  },
  true,
);

document.body.addEventListener("htmx:beforeRequest", (event) => {
  const trigger = event.detail.elt;
  if (
    trigger === null ||
    trigger === undefined ||
    typeof trigger.matches !== "function" ||
    !trigger.matches("[data-scale-reference-toggle]")
  ) {
    return;
  }

  const hiddenField = document.getElementById("include_scale_reference_hidden");
  if (hiddenField !== null) {
    hiddenField.value = trigger.checked ? "true" : "false";
  }

  const form = document.querySelector("[data-plinth-form]");
  const controller = form ? form.plinthFormController : null;
  if (controller) {
    controller.saveCurrentDraft();
  }
});
