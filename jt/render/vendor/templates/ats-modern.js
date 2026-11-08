import {
  contactLine,
  escapeHtml,
  richHtml,
  pathAttr,
  renderCerts,
  renderEducationRows,
  renderJobsStacked,
  renderSkillsInline,
  renderTechnicalSummary,
  wrapHtmlDocument
} from "./shared.js";

const CSS = `
    @page { size: A4; margin: 12mm; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Calibri, Arial, Helvetica, sans-serif;
      color: #000;
      background: #fff;
      font-size: 11pt;
      line-height: 1.28;
    }

    .resume { width: 100%; }

    header.top {
      margin: 0 0 8px;
      padding-bottom: 6px;
      border-bottom: 3px solid #1f4e79;
    }

    h1 {
      margin: 0;
      font-size: 20pt;
      font-weight: 700;
      color: #1f4e79;
      line-height: 1.1;
    }

    .headline {
      margin: 2px 0 4px;
      font-size: 11pt;
      font-weight: 700;
      color: #000;
    }

    .contact {
      margin: 0;
      font-size: 10pt;
    }

    a, a:visited { color: #000; text-decoration: underline; }

    section { margin: 0 0 8px; }

    h2 {
      margin: 0 0 4px;
      padding: 0;
      font-size: 12pt;
      font-weight: 700;
      color: #1f4e79;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      padding-bottom: 2px;
      border-bottom: 2.5px solid #1f4e79;
    }

    p { margin: 0 0 4px; }

    h3.role-company {
      margin: 6px 0 0;
      font-size: 11pt;
      font-weight: 700;
      color: #000;
    }

    p.role-title {
      margin: 0;
      font-size: 11pt;
      font-weight: 700;
    }

    p.role-meta {
      margin: 0 0 2px;
      font-size: 10pt;
      font-style: italic;
    }

    .project {
      margin: 0 0 2px;
      font-size: 10pt;
      font-style: italic;
    }

    ul { margin: 2px 0 0; padding-left: 18px; }
    li { margin: 0 0 2px; }

    /*
     * Skills render as plain single-column lines, not a table.
     * Workday and Taleo read table cells linearly and cannot rebuild the
     * row/column pairing, which garbled the most keyword-dense section.
     */
    .skills-inline { font-size: 10pt; }

    .skill-inline { margin: 0 0 3px; }

    .skill-inline .skill-cat { font-weight: 700; color: #1f4e79; }

    .edu-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 4px;
    }

    .edu-degree { font-weight: 700; }
    .edu-year { white-space: nowrap; font-weight: 700; }

    .tech-summary, .certifications { margin: 0; padding-left: 18px; }
`;

export const atsModernTemplate = {
  id: "ats-modern",
  label: "2 · ATS Calibri",
  description: "Calibri · Workday/Taleo-safe · US Fortune 500 ATS.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const skills = renderSkillsInline(data.skills);
    const jobs = renderJobsStacked(data.experience);
    const edu = renderEducationRows(data.education);
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
  ${profile ? `<section><h2>Professional Summary</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${tech ? `<section><h2>Technical Summary</h2>${tech}</section>` : ""}
  ${skills ? `<section><h2>Skills</h2>${skills}</section>` : ""}
  ${jobs ? `<section><h2>Professional Experience</h2>${jobs}</section>` : ""}
  ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
  ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
