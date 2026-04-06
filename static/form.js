const MILLIMETERS_PER_INCH = 25.4;

function parseNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatLength(value, units) {
  const precision = units === "in" ? 3 : 2;
  return value.toFixed(precision).replace(/\.?0+$/, "");
}

window.plinthForm = function plinthForm(initialState) {
  const lengthsMm = {};
  Object.entries(initialState.lengthsMm).forEach(([name, value]) => {
    lengthsMm[name] = parseNumber(value);
  });

  return {
    plinthType: initialState.plinthType === "circular" ? "circular" : "rectangular",
    displayUnits: initialState.displayUnits === "in" ? "in" : "mm",
    includeCenterPole: Boolean(initialState.includeCenterPole),
    includeBottomHoles: Boolean(initialState.includeBottomHoles),
    includeFooter: Boolean(initialState.includeFooter),
    includeBackdrop: Boolean(initialState.includeBackdrop),
    lengthsMm,
    displayLengths: {},

    init() {
      this.refreshDisplayValues();
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
  };
};
