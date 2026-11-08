import {
  contactLine,
  escapeHtml,
  richHtml,
  pathAttr,
  renderCerts,
  renderEducationRows,
  renderJobsTitleFirst,
  renderSkillsInline,
  renderTechnicalSummary,
  wrapHtmlDocument
} from "./shared.js";

/**
 * Modern US product/SaaS senior engineer: left-aligned name, teal accent,
 * open spacing. Common at US software companies outside classic FAANG.
 */
const CSS = `
    @page { size: A4; margin: 12mm 14mm; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: "Segoe UI", Calibri, Arial, Helvetica, sans-serif;
      color: #1c2430;
      background: #fff;
      font-size: 10.2pt;
      line-height: 1.32;
    }

    .resume { width: 100%; }

    header.top { margin: 0 0 12px; }

    h1 {
      margin: 0;
      font-size: 24pt;
      font-weight: 700;
      letter-spacing: -0.5px;
      line-height: 1.05;
      color: #0f172a;
    }

    .headline {
      margin: 3px 0 8px;
      font-size: 11pt;
      font-weight: 600;
      color: #334155;
    }

    .accent {
      height: 3px;
      width: 48px;
      background: #0f766e;
      margin: 0 0 8px;
      border: 0;
    }

    .contact { margin: 0; font-size: 9pt; color: #475569; }

    .contact a, .contact a:visited {
      color: #0f766e;
      text-decoration: none;
    }

    section {
      margin: 0 0 10px;
      padding-left: 10px;
      border-left: 3px solid #0f766e;
    }

    h2 {
      margin: 0 0 6px;
      font-size: 9.5pt;
      font-weight: 800;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #0f766e;
      border: 0;
    }

    p { margin: 0 0 4px; }

    .tech-summary, .certifications { margin: 0; padding-left: 16px; }

    .job { margin: 0 0 8px; }

    .job-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }

    .job-title {
      margin: 0;
      font-size: 11pt;
      font-weight: 700;
      color: #0f172a;
    }

    .job-dates {
      flex: 0 0 auto;
      white-space: nowrap;
      font-size: 9.5pt;
      font-weight: 700;
      color: #64748b;
    }

    .job-meta, .project {
      margin: 0 0 2px;
      font-size: 9.5pt;
      color: #64748b;
      font-style: italic;
    }

    ul { margin: 2px 0 0; padding-left: 16px; }
    li { margin: 0 0 1.5px; }

    .skills-inline { margin: 0; }
    .skill-inline { margin: 0 0 3px; font-size: 9.8pt; }
    .skill-inline .skill-cat { font-weight: 700; color: #0f766e; }

    .edu-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 3px;
      align-items: baseline;
    }

    .edu-degree { font-weight: 700; }
    .edu-year { white-space: nowrap; font-weight: 700; color: #64748b; }
`;

export const modernSansTemplate = {
  id: "modern-sans",
  label: "7 · Modern US Sans",
  description: "Segoe · teal accent · US product/SaaS senior engineer.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const skills = renderSkillsInline(data.skills);
    const jobs = renderJobsTitleFirst(data.experience);
    const edu = renderEducationRows(data.education);
    const certs = (data.certifications || []).length ? renderCerts(data.certifications) : "";

    return wrapHtmlDocument({
      title: `${name} - Resume`,
      css: CSS,
      body: `<main class="resume">
  <header class="top">
    <h1${pathAttr("name")}>${escapeHtml(name)}</h1>
    ${headline ? `<p class="headline"${pathAttr("headline")}>${richHtml(headline)}</p>` : ""}
    <div class="accent"></div>
    <p class="contact">${contactLine(data, { linkColor: "#0f766e" })}</p>
  </header>
  ${profile ? `<section><h2>About</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${tech ? `<section><h2>Impact</h2>${tech}</section>` : ""}
  ${jobs ? `<section><h2>Experience</h2>${jobs}</section>` : ""}
  ${skills ? `<section><h2>Skills</h2>${skills}</section>` : ""}
  ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
  ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
