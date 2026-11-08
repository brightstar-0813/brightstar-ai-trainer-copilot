import { timesClassicTemplate } from "./times-classic.js";
import { atsModernTemplate } from "./ats-modern.js";
import { svSeniorTemplate } from "./sv-senior.js";
import { nycFinanceTemplate } from "./nyc-finance.js";
import { harvardRuleTemplate } from "./harvard-rule.js";
import { skillsFirstTemplate } from "./skills-first.js";
import { modernSansTemplate } from "./modern-sans.js";
import { executiveNavyTemplate } from "./executive-navy.js";
import { orangeBannerTemplate } from "./orange-banner.js";
import { dateRailTemplate } from "./date-rail.js";
import { stripClearanceFromTitle } from "../resume-json.js";
import { accentOverrideCss } from "./accent.js";

export {
  TEMPLATE_ACCENTS,
  TEMPLATE_ACCENT_KEY,
  accentById,
  defaultAccentIdForTemplate,
  resolveAccentId
} from "./accent.js";

/** Built-in resume PDF/HTML templates. Add new files here and register them. */
export const BUILTIN_TEMPLATES = [
  timesClassicTemplate,
  atsModernTemplate,
  svSeniorTemplate,
  nycFinanceTemplate,
  harvardRuleTemplate,
  skillsFirstTemplate,
  modernSansTemplate,
  executiveNavyTemplate,
  orangeBannerTemplate,
  dateRailTemplate
];

export const DEFAULT_TEMPLATE_ID = atsModernTemplate.id;

/** Old ids kept so saved people still resolve after renames. */
const TEMPLATE_ID_ALIASES = {
  "sandeep-classic": "ats-modern",
  "ruled-sans": "ats-modern",
  "classic-blue": "ats-modern",
  "modern-timeline": "modern-sans",
  "uk-city": "nyc-finance",
  "eu-structured": "harvard-rule",
  "consulting-classic": "times-classic",
  "cambria-corporate": "ats-modern",
  "compact-slate": "ats-modern",
  "split-contact": "ats-modern",
  "brief-grid": "skills-first"
};

export function getAllTemplates() {
  return BUILTIN_TEMPLATES;
}

export function getTemplateById(templateId) {
  const resolved = TEMPLATE_ID_ALIASES[templateId] || templateId;
  return (
    BUILTIN_TEMPLATES.find((t) => t.id === resolved) ||
    BUILTIN_TEMPLATES.find((t) => t.id === DEFAULT_TEMPLATE_ID) ||
    BUILTIN_TEMPLATES[0]
  );
}

/**
 * Render resume JSON to a full HTML document using the selected template.
 * Drops GPT placeholder headlines / schema echo that make resumes look broken.
 * @param {object} data - Parsed resume JSON
 * @param {string} [templateId] - Template id from BUILTIN_TEMPLATES
 * @param {{ accentId?: string }} [options]
 */
function sanitizeResumeData(raw) {
  const data = { ...(raw || {}) };
  const headline = stripClearanceFromTitle(String(data.headline || "").trim());
  if (
    !headline ||
    /JD-aligned|role list above|from the (job|role)|placeholder|TODO|TBD|\{JOB/i.test(headline) ||
    headline.length > 90
  ) {
    data.headline = "";
  } else {
    data.headline = headline;
  }

  if (Array.isArray(data.skills)) {
    data.skills = data.skills.filter((row) => {
      const category = String(row?.category || "").trim();
      if (!category) return Boolean(String(row?.items || "").trim());
      return !/^(jd\s*)?keywords?$/i.test(category) && !/jd\s*keyword/i.test(category);
    });
  }

  if (Array.isArray(data.experience)) {
    data.experience = data.experience.map((job) => {
      const next = { ...(job || {}) };
      next.title = stripClearanceFromTitle(next.title);
      const bullets = Array.isArray(next.bullets) ? next.bullets : [];
      next.bullets = bullets
        .map((b) => String(b || "").replace(/\s+/g, " ").trim())
        .filter(Boolean)
        .filter((b) => !/while ensuring production reliability/i.test(b));
      return next;
    });
  }

  return data;
}

export function resumeJsonToHtml(data, templateId, options = {}) {
  const clean = sanitizeResumeData(data);
  const template = getTemplateById(templateId);
  let html = template.render(clean);
  const align = clean?.headingAlign === "center" ? "center" : clean?.headingAlign === "left" ? "left" : "";
  if (align) {
    html = html.replace("</style>", `    h2 { text-align: ${align}; }\n  </style>`);
  }
  const accentCss = accentOverrideCss(template.id, options.accentId);
  if (accentCss) {
    html = html.replace("</style>", `${accentCss}\n  </style>`);
  }
  return html;
}
