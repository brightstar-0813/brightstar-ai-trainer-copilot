/** Accent colors for the Resume style picker. Each template remembers its own id. */
export const TEMPLATE_ACCENT_KEY = "template_accent_by_id";

/**
 * Twelve print-safe enterprise accents. Dark enough for headings, and far enough
 * apart that neighboring swatches do not blend. The picker shows them on one row.
 */
export const TEMPLATE_ACCENTS = [
  { id: "blue", label: "Blue", hex: "#1F4E79" },
  { id: "navy", label: "Navy", hex: "#0A2540" },
  { id: "slate", label: "Slate", hex: "#5B6770" },
  { id: "teal", label: "Teal", hex: "#0D7377" },
  { id: "green", label: "Green", hex: "#1E7A46" },
  { id: "burgundy", label: "Burgundy", hex: "#8B2332" },
  { id: "purple", label: "Purple", hex: "#5B2C6F" },
  { id: "bronze", label: "Bronze", hex: "#8A5A2B" },
  { id: "olive", label: "Olive", hex: "#3F6212" },
  { id: "crimson", label: "Crimson", hex: "#9F1239" },
  { id: "indigo", label: "Indigo", hex: "#312E81" },
  { id: "charcoal", label: "Charcoal", hex: "#27272A" }
];

/** Built-in accent when the person has not picked one for that template. */
const TEMPLATE_DEFAULT_ACCENT = {
  "ats-modern": "blue",
  "nyc-finance": "navy",
  "executive-navy": "navy",
  "modern-sans": "teal",
  "date-rail": "slate",
  "orange-banner": "bronze"
};

export function accentById(accentId) {
  const id = String(accentId || "").trim();
  return TEMPLATE_ACCENTS.find((row) => row.id === id) || null;
}

export function defaultAccentIdForTemplate(templateId) {
  return TEMPLATE_DEFAULT_ACCENT[templateId] || "";
}

/** Stored choice wins. Otherwise the template's built-in accent, or "" to leave CSS alone. */
export function resolveAccentId(templateId, storedMap = {}) {
  const chosen = storedMap && typeof storedMap === "object" ? storedMap[templateId] : "";
  if (accentById(chosen)) return chosen;
  return defaultAccentIdForTemplate(templateId);
}

/**
 * Extra CSS so a picked color tints rules and headings, not body text.
 * Empty when this template should keep its original colors.
 */
export function accentOverrideCss(templateId, accentId) {
  const accent = accentById(accentId);
  if (!accent) return "";
  const hex = accent.hex;
  const rules = {
    "ats-modern": `
      h1, h2, .skill-inline .skill-cat { color: ${hex} !important; }
      header.top, h2 { border-bottom-color: ${hex} !important; }`,
    "modern-sans": `
      .accent { background: ${hex} !important; }
      h2, .skill-inline .skill-cat, .contact a, .contact a:visited { color: ${hex} !important; }
      h2 { border-left-color: ${hex} !important; }`,
    "orange-banner": `
      .contact, .contact a, .contact a:visited, h2.plain, .skills-table th { color: ${hex} !important; }
      h2.bar span, h2.bar::after { background: ${hex} !important; }
      .skills-table th { border-bottom-color: ${hex} !important; }`,
    "nyc-finance": `
      .banner { background: ${hex} !important; }
      h2, .skills-table .skill-cat { color: ${hex} !important; }`,
    "executive-navy": `
      aside { background: ${hex} !important; }`,
    "date-rail": `
      header.top { border-bottom-color: ${hex} !important; }`,
    "times-classic": `
      h2 { color: ${hex} !important; border-bottom-color: ${hex} !important; }
      table, th, td { border-color: ${hex} !important; }`,
    "skills-first": `
      header.top { border-bottom-color: ${hex} !important; }
      h2 { background: ${hex} !important; }`,
    "harvard-rule": `
      header.top { border-bottom-color: ${hex} !important; }
      h1, h2 { color: ${hex} !important; }`,
    "sv-senior": `
      h2 { color: ${hex} !important; }`
  };
  const css = rules[templateId];
  if (!css) return "";
  return css;
}
