import {
  contactLine,
  escapeHtml,
  pathAttr,
  renderCerts,
  renderEducationDatedColumn,
  renderJobsDatedColumn,
  renderSkillsInline,
  renderTechnicalSummary,
  richHtml,
  wrapHtmlDocument
} from "./shared.js";

/**
 * Dates sit in a narrow left rail so each role stays one compact block.
 */
const CSS = `
    @page { size: A4; margin: 10mm 12mm; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Calibri, "Segoe UI", Arial, sans-serif;
      color: #1a1a1a;
      background: #fff;
      font-size: 10.5pt;
      line-height: 1.25;
    }

    .resume { width: 100%; }

    header.top {
      margin: 0 0 7px;
      padding-bottom: 5px;
      border-bottom: 2px solid #1f2937;
    }

    h1 {
      margin: 0;
      font-size: 18pt;
      font-weight: 700;
      letter-spacing: 0.4px;
      line-height: 1.05;
    }

    .headline {
      margin: 2px 0 2px;
      font-size: 10.5pt;
      color: #374151;
    }

    .contact { margin: 0; font-size: 9pt; }

    a, a:visited { color: #111; text-decoration: none; }

    section { margin: 0 0 7px; }

    h2 {
      margin: 0 0 4px;
      font-size: 10pt;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
    }

    p { margin: 0 0 2px; }

    .tech-summary, .certifications { margin: 0; padding-left: 15px; }

    .job, .edu-col {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      column-gap: 10px;
      margin: 0 0 6px;
      padding-bottom: 4px;
      border-bottom: 1px solid #d1d5db;
    }

    .job-body { grid-column: 1; grid-row: 1; min-width: 0; }

    .job-dates {
      grid-column: 2;
      grid-row: 1;
      align-self: start;
      font-size: 10pt;
      font-weight: 700;
      line-height: 1.3;
      color: #111;
      text-align: right;
      white-space: nowrap;
    }

    .job-title {
      margin: 0;
      font-size: 10.5pt;
      font-weight: 700;
    }

    .job-company, .project { margin: 0; font-size: 10pt; color: #333; }

    ul { margin: 1px 0 0; padding-left: 14px; }
    li { margin: 0 0 1px; }

    .skill-inline { margin: 0 0 1px; }
    .skill-inline .skill-cat { font-weight: 700; }
`;

export const dateRailTemplate = {
  id: "date-rail",
  label: "10 · Date Rail",
  description: "Date on the title line · role text uses the full width.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const skills = renderSkillsInline(data.skills);
    const jobs = renderJobsDatedColumn(data.experience);
    const edu = renderEducationDatedColumn(data.education);
    const certs = (data.certifications || []).length ? renderCerts(data.certifications) : "";

    return wrapHtmlDocument({
      title: `${name} - Resume`,
      css: CSS,
      body: `<main class="resume">
  <header class="top">
    <h1${pathAttr("name")}>${escapeHtml(name)}</h1>
    ${headline ? `<p class="headline"${pathAttr("headline")}>${richHtml(headline)}</p>` : ""}
    <p class="contact">${contactLine(data)}</p>
  </header>
  ${profile ? `<section><h2>Summary</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${skills ? `<section><h2>Skills</h2>${skills}</section>` : ""}
  ${jobs ? `<section><h2>Experience</h2>${jobs}</section>` : ""}
  ${tech ? `<section><h2>Highlights</h2>${tech}</section>` : ""}
  ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
  ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
