import { isPlainResumePath, plainTextFromRich, richHtml } from "../resume-rich.js";

export { isPlainResumePath, richHtml };

export function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/** Stable field path for Style preview edit → resumeData round-trip. */
export function pathAttr(path) {
  const p = String(path || "").trim();
  return p ? ` data-bs-path="${escapeHtml(p)}"` : "";
}

/** Wrap escaped text (or sanitized Word marks) with a data-bs-path element. */
export function editableText(path, text, tag = "span") {
  const inner = isPlainResumePath(path) ? escapeHtml(text) : richHtml(text);
  const p = String(path || "").trim();
  if (!p) return inner;
  return `<${tag}${pathAttr(p)}>${inner}</${tag}>`;
}

/**
 * Apply preview edits (path → plain text) onto a deep clone of resume JSON.
 * Numeric path segments are treated as array indices.
 */
export function applyPathEdits(resumeData, edits) {
  const next =
    typeof structuredClone === "function"
      ? structuredClone(resumeData || {})
      : JSON.parse(JSON.stringify(resumeData || {}));
  for (const [path, raw] of Object.entries(edits || {})) {
    const parts = String(path || "")
      .split(".")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) continue;
    const value = isPlainResumePath(path)
      ? plainTextFromRich(raw)
      : richHtml(raw);
    let cur = next;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts[i];
      const nextKey = parts[i + 1];
      const wantArray = /^\d+$/.test(nextKey);
      if (cur[key] == null || typeof cur[key] !== "object") {
        cur[key] = wantArray ? [] : {};
      }
      cur = cur[key];
    }
    const last = parts[parts.length - 1];
    if (Array.isArray(cur) && /^\d+$/.test(last)) {
      cur[Number(last)] = value;
    } else {
      cur[last] = value;
    }
  }
  return next;
}

/** Never render ATS keyword-dump skill rows on the PDF. */
function isKeywordDumpSkillsCategory(category) {
  const c = String(category || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (!c) return false;
  if (/^(jd\s*)?keywords?$/.test(c)) return true;
  if (/^ats\s*keywords?$/.test(c)) return true;
  if (/^keyword\s*(dump|list|bank|match|coverage)?$/.test(c)) return true;
  if (/jd\s*keyword/.test(c)) return true;
  return false;
}

/**
 * Certifications may arrive as strings or as objects ({ name, title, ... }).
 * Always return a displayable label — never "[object Object]".
 */
export function certLabel(cert) {
  if (cert == null) return "";
  if (typeof cert === "string" || typeof cert === "number") {
    return String(cert).trim();
  }
  if (typeof cert === "object") {
    const label =
      cert.name ||
      cert.title ||
      cert.certification ||
      cert.label ||
      cert.credential ||
      cert.text ||
      "";
    return String(label).trim();
  }
  return "";
}

function cleanEmail(value) {
  // Prefer the visible label for [email](mailto:email); fall back to mailto target.
  const raw = String(value || "").trim();
  const md = raw.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
  if (md) {
    const label = md[1].trim();
    const target = md[2].replace(/^mailto:/i, "").trim();
    return (label.includes("@") ? label : target).replace(/^mailto:/i, "").trim();
  }
  return raw.replace(/^mailto:/i, "").replace(/[[\]]/g, "").trim();
}

function cleanUrl(value) {
  let url = String(value || "").trim();
  const md = url.match(/\[([^\]]*)\]\(([^)]+)\)/);
  if (md) url = md[2] || md[1] || url;
  url = url.replace(/[[\]]/g, "").trim();
  const match = url.match(/https?:\/\/[^\s"'<>\\]+/i);
  if (match) url = match[0];
  return url.replace(/[),.]+$/g, "").replace(/\/+$/, "").trim();
}

export function contactLine(data, { linkColor } = {}) {
  const parts = [];
  if (data.location) {
    parts.push(`<span${pathAttr("location")}>${escapeHtml(data.location)}</span>`);
  }
  if (data.phone) {
    parts.push(`<span${pathAttr("phone")}>${escapeHtml(data.phone)}</span>`);
  }
  if (data.email) {
    const email = cleanEmail(data.email);
    parts.push(
      `<a href="mailto:${escapeHtml(email)}"${pathAttr("email")}>${escapeHtml(email)}</a>`
    );
  }
  if (data.linkedin) {
    const url = cleanUrl(data.linkedin);
    const href = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    parts.push(
      `<a href="${escapeHtml(href)}"${pathAttr("linkedin")}>${escapeHtml(href)}</a>`
    );
  }
  const style = linkColor ? ` style="color:${linkColor}"` : "";
  if (style) {
    return parts
      .map((part) => (part.startsWith("<a ") ? part.replace("<a ", `<a${style} `) : part))
      .join(" | ");
  }
  return parts.join(" | ");
}

/** Stacked contact block (left column under name/headline). */
export function renderContactBlock(data, { linkColor = "#000" } = {}) {
  const lines = [];
  if (data.location) {
    lines.push(`<div${pathAttr("location")}>${escapeHtml(data.location)}</div>`);
  }
  if (data.phone) {
    lines.push(`<div${pathAttr("phone")}>${escapeHtml(data.phone)}</div>`);
  }
  if (data.email) {
    const email = cleanEmail(data.email);
    lines.push(
      `<div><a href="mailto:${escapeHtml(email)}" style="color:${linkColor}"${pathAttr("email")}>${escapeHtml(email)}</a></div>`
    );
  }
  if (data.linkedin) {
    const url = cleanUrl(data.linkedin);
    const href = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    lines.push(
      `<div><a href="${escapeHtml(href)}" style="color:${linkColor}"${pathAttr("linkedin")}>${escapeHtml(href)}</a></div>`
    );
  }
  return lines.length ? `<div class="contact-block">${lines.join("\n")}</div>` : "";
}

/** Two-column skills table: Category | Technologies (ATS-friendly HTML table). */
export function renderSkills(skills) {
  const rows = (skills || [])
    .map((row, si) => {
      const category = String(row?.category || "").trim();
      const items = String(row?.items || "").trim();
      if (!category && !items) return "";
      if (isKeywordDumpSkillsCategory(category)) return "";
      return `<tr>
  <td class="skill-cat"${pathAttr(`skills.${si}.category`)}>${richHtml(category)}</td>
  <td class="skill-items"${pathAttr(`skills.${si}.items`)}>${richHtml(items)}</td>
</tr>`;
    })
    .filter(Boolean);

  if (!rows.length) return "";

  return `<table class="skills-table" role="table">
  <thead>
    <tr>
      <th scope="col">Category</th>
      <th scope="col">Technologies / Skills</th>
    </tr>
  </thead>
  <tbody>
${rows.join("\n")}
  </tbody>
</table>`;
}

export function renderCerts(certs, { listClass = "certifications" } = {}) {
  const items = (certs || [])
    .map((c, ci) => {
      const label = certLabel(c);
      if (!label) return "";
      return `<li${pathAttr(`certifications.${ci}`)}>${richHtml(label)}</li>`;
    })
    .filter(Boolean)
    .join("\n");
  if (!items) return "";
  return `<ul class="${listClass}">${items}</ul>`;
}

/** Technical Summary: array of highlight bullets (strings). */
export function renderTechnicalSummary(items) {
  const list = Array.isArray(items)
    ? items
    : typeof items === "string" && items.trim()
      ? items.split(/\n+/).map((s) => s.replace(/^[-•*]\s*/, "").trim())
      : [];
  const bullets = list
    .map((s, ti) => {
      const text = String(s || "").trim();
      if (!text) return "";
      return `<li${pathAttr(`technicalSummary.${ti}`)}>${richHtml(text)}</li>`;
    })
    .filter(Boolean);
  if (!bullets.length) return "";
  return `<ul class="tech-summary">\n${bullets.join("\n")}\n</ul>`;
}

/**
 * Salesforce-style hexagonal cert badges for the resume header.
 * Maps known certification names → short label + colors.
 */
const CERT_BADGE_DEFS = [
  {
    match: /platform\s*developer\s*ii|pdii|pd\s*ii/i,
    label: "Platform\nDeveloper II",
    top: "#2a1f6e",
    bottom: "#5b4db8"
  },
  {
    match: /platform\s*developer\s*i(?!\s*i)|pdi(?!\s*i)|pd\s*i(?!\s*i)/i,
    label: "Platform\nDeveloper I",
    top: "#1f3b8a",
    bottom: "#6b7fd7"
  },
  {
    match: /service\s*cloud\s*consultant/i,
    label: "Service Cloud\nConsultant",
    top: "#5b2d8e",
    bottom: "#e8a317"
  },
  {
    match: /sales\s*cloud\s*consultant/i,
    label: "Sales Cloud\nConsultant",
    top: "#1a3a7a",
    bottom: "#e8a317"
  },
  {
    match: /application\s*architect|system\s*architect|data\s*architect|sharing\s*and\s*visibility|development\s*lifecycle|deployment\s*architect/i,
    label: "Architect",
    top: "#0d3b66",
    bottom: "#3d7ea6"
  },
  {
    match: /business\s*analyst/i,
    label: "Business\nAnalyst",
    top: "#1f5f8b",
    bottom: "#5dade2"
  },
  {
    match: /app\s*builder|platform\s*app\s*builder/i,
    label: "Platform\nApp Builder",
    top: "#0e6655",
    bottom: "#48c9b0"
  },
  {
    match: /administrator|admin\b/i,
    label: "Administrator",
    top: "#1f4e79",
    bottom: "#5dade2"
  },
  {
    match: /associate/i,
    label: "Associate",
    top: "#2874a6",
    bottom: "#85c1e9"
  },
  {
    match: /agentforce|ai\s*associate|ai\s*specialist/i,
    label: "AI /\nAgentforce",
    top: "#6c3483",
    bottom: "#bb8fce"
  }
];

function resolveCertBadge(certText) {
  const text = certLabel(certText);
  if (!text) return null;
  for (const def of CERT_BADGE_DEFS) {
    if (def.match.test(text)) {
      return { ...def, source: text };
    }
  }
  return null;
}

function sfCloudIcon() {
  // Simple white Salesforce-like cloud glyph
  return `<path fill="#fff" d="M18.2 14.2c-.3-2.2-2.2-3.9-4.5-3.9-1.1 0-2.1.4-2.9 1-.7-2.5-3-4.3-5.7-4.3-3.3 0-6 2.6-6.1 5.8C-.8 13.5 0 15.2 1.6 16.1c.5.3 1 .4 1.6.4h14.1c1.8 0 3.2-1.4 3.2-3.1 0-1.5-1.1-2.8-2.3-3.2z"/>`;
}

function certBadgeSvg({ label, top, bottom }, index = 0) {
  const lines = String(label).split("\n");
  const lineStarts = lines.length === 1 ? [78] : lines.length === 2 ? [72, 86] : [68, 80, 92];
  const textEls = lines
    .map(
      (line, i) =>
        `<text x="50" y="${lineStarts[i]}" text-anchor="middle" fill="#fff" font-family="Arial, Helvetica, sans-serif" font-size="${lines.length > 2 ? 8.5 : 9.5}" font-weight="700">${escapeHtml(line)}</text>`
    )
    .join("");

  return `<svg class="cert-badge" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 110" width="58" height="64" aria-hidden="true">
  <polygon points="50,2 95,28 95,82 50,108 5,82 5,28" fill="${top}"/>
  <polygon points="8,74 92,74 95,82 50,108 5,82" fill="${bottom}"/>
  <g transform="translate(31,14) scale(0.95)">${sfCloudIcon()}</g>
  <text x="50" y="58" text-anchor="middle" fill="#fff" font-family="Arial, Helvetica, sans-serif" font-size="9" font-weight="800" letter-spacing="0.5">CERTIFIED</text>
  ${textEls}
</svg>`;
}

/**
 * Render up to `limit` Salesforce cert badges from certification strings.
 * Prefer higher-signal certs (PDII, consultants, architects) when many are present.
 */
export function renderCertBadges(certs, { limit = 5 } = {}) {
  const list = Array.isArray(certs) ? certs : [];
  const resolved = [];
  const seen = new Set();

  for (const cert of list) {
    const badge = resolveCertBadge(cert);
    if (!badge) continue;
    const key = badge.label;
    if (seen.has(key)) continue;
    seen.add(key);
    resolved.push(badge);
  }

  // Prefer order similar to the reference screenshot when possible
  const preferred = [
    /Administrator/i,
    /Developer I(?!\s*I)/i,
    /Developer II/i,
    /Service Cloud/i,
    /Sales Cloud/i,
    /Architect/i,
    /App Builder/i,
    /Business/i
  ];
  resolved.sort((a, b) => {
    const ai = preferred.findIndex((re) => re.test(a.label));
    const bi = preferred.findIndex((re) => re.test(b.label));
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  const chosen = resolved.slice(0, limit);
  if (!chosen.length) return "";

  return `<div class="cert-badges" aria-label="Salesforce certifications">
${chosen.map((b, i) => certBadgeSvg(b, i)).join("\n")}
</div>`;
}

/** Flex header: company (location) — title | dates on the right. */
export function renderJobsFlex(jobs) {
  return (jobs || [])
    .map((job, ji) => {
      const company = String(job.company || "").trim();
      const location = String(job.location || "").trim();
      const title = String(job.title || "").trim();
      const dates = String(job.dates || "").trim();
      const project = String(job.project || "").trim();
      const bullets = (job.bullets || [])
        .map((b, bi) => {
          const text = String(b || "").trim();
          if (!text) return "";
          return `<li${pathAttr(`experience.${ji}.bullets.${bi}`)}>${richHtml(text)}</li>`;
        })
        .filter(Boolean)
        .join("\n");

      const companyHtml = company
        ? `<span${pathAttr(`experience.${ji}.company`)}>${richHtml(company)}</span>`
        : "";
      const locationHtml = location
        ? ` (<span${pathAttr(`experience.${ji}.location`)}>${escapeHtml(location)}</span>)`
        : "";
      const titleHtml = title
        ? `<span${pathAttr(`experience.${ji}.title`)}>${richHtml(title)}</span>`
        : "";
      const mid = [companyHtml + locationHtml, titleHtml].filter(Boolean).join(" — ");

      return `<article class="job">
  <div class="job-header">
    <span class="company">${mid}</span>
    ${dates ? `<span class="date"${pathAttr(`experience.${ji}.dates`)}>${escapeHtml(dates)}</span>` : ""}
  </div>
  ${project ? `<p class="project"${pathAttr(`experience.${ji}.project`)}>${richHtml(project)}</p>` : ""}
  <ul>
${bullets}
  </ul>
</article>`;
    })
    .join("\n");
}

/**
 * Experience header style (reference):
 *   Company                  (bold)
 *   Job Title                (bold)
 *   Location | Mode | Dates  (normal)
 */
export function renderJobsStacked(jobs) {
  return (jobs || [])
    .map((job, ji) => {
      const company = String(job.company || "").trim();
      const location = String(job.location || "").trim();
      const title = String(job.title || "").trim();
      const dates = String(job.dates || "").trim();
      const project = String(job.project || "").trim();
      const metaBits = [];
      if (location) {
        metaBits.push(`<span${pathAttr(`experience.${ji}.location`)}>${escapeHtml(location)}</span>`);
      }
      if (dates) {
        metaBits.push(`<span${pathAttr(`experience.${ji}.dates`)}>${escapeHtml(dates)}</span>`);
      }
      const meta = metaBits.join(" | ");
      const bullets = (job.bullets || [])
        .map((b, bi) => {
          const text = String(b || "").trim();
          if (!text) return "";
          return `<li${pathAttr(`experience.${ji}.bullets.${bi}`)}>${richHtml(text)}</li>`;
        })
        .filter(Boolean)
        .join("\n");

      return `<article class="job">
  <h3 class="role-company"${pathAttr(`experience.${ji}.company`)}>${richHtml(company)}</h3>
  <p class="role-title"${pathAttr(`experience.${ji}.title`)}>${richHtml(title)}</p>
  ${meta ? `<p class="role-meta">${meta}</p>` : ""}
  ${project ? `<p class="project"${pathAttr(`experience.${ji}.project`)}>${richHtml(project)}</p>` : ""}
  <ul>
${bullets}
  </ul>
</article>`;
    })
    .join("\n");
}

export function educationList(education) {
  const list = Array.isArray(education)
    ? education
    : education && typeof education === "object"
      ? [education]
      : [];
  return list.filter(
    (edu) => String(edu?.school || "").trim() || String(edu?.degree || "").trim()
  );
}

/** Month/year ranges that belong in edu.year, not location. */
const EDU_PLACE_DATE_RE =
  /(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(?:19|20)\d{2}\s*[-–—]\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(?:(?:19|20)\d{2}|present)/i;

/**
 * Location only — strip pipe-joined date ranges so templates that also render
 * edu.year do not show "Recife, Brazil | Mar 2013 – Aug 2017" plus a right date.
 */
export function stripEducationDatesFromPlace(text) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  return raw
    .split(/\s*\|\s*/)
    .map((b) => b.trim())
    .filter(Boolean)
    .filter((b) => !EDU_PLACE_DATE_RE.test(b) && !/^(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present)$/i.test(b))
    .map((b) =>
      b
        .replace(EDU_PLACE_DATE_RE, "")
        .replace(/\s*[|–—,-]\s*$/g, "")
        .replace(/^\s*[|–—,-]\s*/g, "")
        .trim()
    )
    .filter(Boolean)
    .join(", ");
}

/**
 * Education "details" is location only (city / region / country).
 * Drop honors, coursework, thesis, and other academic narrative the model sometimes invents.
 */
export function educationLocationLine(edu) {
  const explicit = stripEducationDatesFromPlace(String(edu?.location || "").trim());
  if (explicit) return explicit;

  const raw = String(edu?.details || edu?.gpa || "").trim();
  if (!raw) return "";

  const fluffRe =
    /coursework|relevant courses|final[\s-]?year|honou?rs|dean'?s list|thesis|dissertation|capstone|degree classification|conferred|gpa\b|grade\b|focus on |project:/i;
  if (fluffRe.test(raw)) {
    const firstLine = raw.split(/\n/)[0].trim();
    // Keep a short place-like first line when fluff was appended after it.
    if (
      firstLine &&
      firstLine.length <= 80 &&
      !fluffRe.test(firstLine) &&
      !/[.]{2,}|;/.test(firstLine)
    ) {
      return stripEducationDatesFromPlace(firstLine);
    }
    return "";
  }

  // Prefer a single short location line over multi-paragraph essays.
  const firstLine = raw.split(/\n/)[0].trim();
  if (firstLine.length > 100) return "";
  return stripEducationDatesFromPlace(firstLine);
}

/** Strip invented conferral notes from education year ranges. */
export function educationYearLine(edu) {
  return String(edu?.year || "")
    .replace(/,?\s*degree conferred\b.*$/i, "")
    .trim();
}

/** Degree + school on the left, year on the right. */
export function renderEducationRows(education) {
  const list = Array.isArray(education)
    ? education
    : education && typeof education === "object"
      ? [education]
      : [];
  return list
    .map((edu, ei) => {
      const degreeRaw = String(edu?.degree || "").trim();
      let schoolRaw = String(edu?.school || "").trim();
      if (schoolRaw && degreeRaw && schoolRaw.toLowerCase() === degreeRaw.toLowerCase()) {
        schoolRaw = "";
      }
      const yearRaw = educationYearLine(edu);
      let detailsRaw = educationLocationLine(edu);
      if (detailsRaw && degreeRaw && detailsRaw.toLowerCase() === degreeRaw.toLowerCase()) {
        detailsRaw = "";
      }
      if (detailsRaw && schoolRaw && detailsRaw.toLowerCase() === schoolRaw.toLowerCase()) {
        detailsRaw = "";
      }
      if (!schoolRaw && !degreeRaw) return "";
      return `<div class="edu-row">
  <div class="edu-main">
    ${degreeRaw ? `<div class="edu-degree"${pathAttr(`education.${ei}.degree`)}>${richHtml(degreeRaw)}</div>` : ""}
    ${schoolRaw ? `<div class="edu-school"${pathAttr(`education.${ei}.school`)}>${richHtml(schoolRaw)}</div>` : ""}
    ${detailsRaw ? `<div class="edu-details"${pathAttr(`education.${ei}.location`)}>${richHtml(detailsRaw)}</div>` : ""}
  </div>
  ${yearRaw ? `<div class="edu-year"${pathAttr(`education.${ei}.year`)}>${richHtml(yearRaw)}</div>` : ""}
</div>`;
    })
    .filter(Boolean)
    .join("\n");
}

/** Category / items as stacked rows (no table borders). */
export function renderSkillsStacked(skills) {
  const rows = (skills || [])
    .map((row, si) => {
      const category = String(row?.category || "").trim();
      const items = String(row?.items || "").trim();
      if (!category && !items) return "";
      if (isKeywordDumpSkillsCategory(category)) return "";
      // Keep a literal space between the spans: .skill-cat is display:block, so
      // this is invisible, but PDF text extraction would otherwise glue the
      // category onto the first skill ("IntegrationREST, SOAP").
      return `<div class="skill-row"><span class="skill-cat"${pathAttr(
        `skills.${si}.category`
      )}>${richHtml(category)}</span> <span class="skill-items"${pathAttr(
        `skills.${si}.items`
      )}>${richHtml(items)}</span></div>`;
    })
    .filter(Boolean);
  if (!rows.length) return "";
  return `<div class="skills-stack">${rows.join("\n")}</div>`;
}

/** One line per skill group: Category — items (FAANG / senior IC). */
export function renderSkillsInline(skills) {
  const rows = (skills || [])
    .map((row, si) => {
      const category = String(row?.category || "").trim();
      const items = String(row?.items || "").trim();
      if (!category && !items) return "";
      if (isKeywordDumpSkillsCategory(category)) return "";
      if (!category) {
        return `<div class="skill-inline"${pathAttr(`skills.${si}.items`)}>${richHtml(items)}</div>`;
      }
      return `<div class="skill-inline"><span class="skill-cat"${pathAttr(
        `skills.${si}.category`
      )}>${richHtml(category)}:</span> <span${pathAttr(`skills.${si}.items`)}>${richHtml(
        items
      )}</span></div>`;
    })
    .filter(Boolean);
  if (!rows.length) return "";
  return `<div class="skills-inline">${rows.join("\n")}</div>`;
}

function jobBullets(job, ji) {
  return (job?.bullets || [])
    .map((b, bi) => {
      const text = String(b || "").trim();
      if (!text) return "";
      return `<li${pathAttr(`experience.${ji}.bullets.${bi}`)}>${richHtml(text)}</li>`;
    })
    .filter(Boolean)
    .join("\n");
}

/** Title, Company — dates on the right. Used by NYC Finance, Silicon Valley, Harvard Rule. */
export function renderJobsTitleFirst(jobs) {
  return (jobs || [])
    .map((job, ji) => {
      const company = String(job.company || "").trim();
      const title = String(job.title || "").trim();
      const dates = String(job.dates || "").trim();
      const location = String(job.location || "").trim();
      const project = String(job.project || "").trim();
      const bullets = jobBullets(job, ji);
      const headingParts = [];
      if (title) {
        headingParts.push(`<span${pathAttr(`experience.${ji}.title`)}>${richHtml(title)}</span>`);
      }
      if (company) {
        headingParts.push(`<span${pathAttr(`experience.${ji}.company`)}>${richHtml(company)}</span>`);
      }
      const heading = headingParts.join(", ");
      return `<article class="job">
  <div class="job-top">
    <p class="job-title">${heading}</p>
    ${dates ? `<span class="job-dates"${pathAttr(`experience.${ji}.dates`)}>${escapeHtml(dates)}</span>` : ""}
  </div>
  ${location ? `<p class="job-meta"${pathAttr(`experience.${ji}.location`)}>${escapeHtml(location)}</p>` : ""}
  ${project ? `<p class="project"${pathAttr(`experience.${ji}.project`)}>${richHtml(project)}</p>` : ""}
  ${bullets ? `<ul>\n${bullets}\n  </ul>` : ""}
</article>`;
    })
    .join("\n");
}

/** DACH/Benelux Lebenslauf: dates in a left column, role on the right. */
export function renderJobsDatedColumn(jobs) {
  return (jobs || [])
    .map((job, ji) => {
      const company = String(job.company || "").trim();
      const title = String(job.title || "").trim();
      const dates = String(job.dates || "").trim();
      const location = String(job.location || "").trim();
      const project = String(job.project || "").trim();
      const bullets = jobBullets(job, ji);
      const orgParts = [];
      if (company) {
        orgParts.push(`<span${pathAttr(`experience.${ji}.company`)}>${richHtml(company)}</span>`);
      }
      if (location) {
        orgParts.push(`<span${pathAttr(`experience.${ji}.location`)}>${escapeHtml(location)}</span>`);
      }
      const org = orgParts.join(" · ");
      return `<article class="job">
  <div class="job-dates"${dates ? pathAttr(`experience.${ji}.dates`) : ""}>${escapeHtml(dates)}</div>
  <div class="job-body">
    ${title ? `<h3 class="job-title"${pathAttr(`experience.${ji}.title`)}>${richHtml(title)}</h3>` : ""}
    ${org ? `<p class="job-company">${org}</p>` : ""}
    ${project ? `<p class="project"${pathAttr(`experience.${ji}.project`)}>${richHtml(project)}</p>` : ""}
    ${bullets ? `<ul>\n${bullets}\n  </ul>` : ""}
  </div>
</article>`;
    })
    .join("\n");
}

export function renderEducationDatedColumn(education) {
  const list = Array.isArray(education)
    ? education
    : education && typeof education === "object"
      ? [education]
      : [];
  return list
    .map((edu, ei) => {
      const degreeRaw = String(edu?.degree || "").trim();
      let schoolRaw = String(edu?.school || "").trim();
      if (schoolRaw && degreeRaw && schoolRaw.toLowerCase() === degreeRaw.toLowerCase()) {
        schoolRaw = "";
      }
      const yearRaw = educationYearLine(edu);
      let detailsRaw = educationLocationLine(edu);
      if (detailsRaw && degreeRaw && detailsRaw.toLowerCase() === degreeRaw.toLowerCase()) {
        detailsRaw = "";
      }
      if (detailsRaw && schoolRaw && detailsRaw.toLowerCase() === schoolRaw.toLowerCase()) {
        detailsRaw = "";
      }
      if (!schoolRaw && !degreeRaw) return "";
      return `<article class="edu-col">
  <div class="job-dates"${yearRaw ? pathAttr(`education.${ei}.year`) : ""}>${richHtml(yearRaw)}</div>
  <div class="job-body">
    ${degreeRaw ? `<h3 class="job-title"${pathAttr(`education.${ei}.degree`)}>${richHtml(degreeRaw)}</h3>` : ""}
    ${schoolRaw ? `<p class="job-company"${pathAttr(`education.${ei}.school`)}>${richHtml(schoolRaw)}</p>` : ""}
    ${detailsRaw ? `<p class="project"${pathAttr(`education.${ei}.location`)}>${richHtml(detailsRaw)}</p>` : ""}
  </div>
</article>`;
    })
    .filter(Boolean)
    .join("\n");
}

export function wrapHtmlDocument({ title, css, body }) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  <style>
${css}
    /* Body copy fills the column. Last line stays left so PDF print does not stretch leftover words.
       Do not hyphenate: Chrome splits words like "enterprise" in the middle of a line. */
    p, li {
      text-align: justify;
      text-justify: inter-word;
      text-align-last: left;
      hyphens: manual;
      -webkit-hyphens: manual;
    }
  </style>
</head>
<body>
${body}
</body>
</html>`;
}
