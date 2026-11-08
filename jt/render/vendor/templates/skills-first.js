import {
  contactLine,
  escapeHtml,
  richHtml,
  pathAttr,
  renderCerts,
  renderEducationRows,
  renderJobsStacked,
  renderSkills,
  renderTechnicalSummary,
  wrapHtmlDocument
} from "./shared.js";

/**
 * Skills-first US technical resume. Keyword table sits above experience so
 * ATS and Salesforce/platform recruiters see stack coverage immediately.
 */
const CSS = `
    @page { size: A4; margin: 11mm 12mm; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: #111;
      background: #fff;
      font-size: 10pt;
      line-height: 1.28;
    }

    .resume { width: 100%; }

    header.top {
      margin: 0 0 8px;
      padding: 0 0 6px;
      border-bottom: 2.5px solid #111;
    }

    h1 {
      margin: 0;
      font-size: 20pt;
      font-weight: 700;
      letter-spacing: 0.4px;
      text-transform: uppercase;
      line-height: 1.1;
    }

    .headline {
      margin: 2px 0 4px;
      font-size: 10.5pt;
      font-weight: 700;
    }

    .contact { margin: 0; font-size: 9.5pt; }

    a, a:visited { color: #111; text-decoration: underline; }

    section { margin: 0 0 7px; }

    h2 {
      margin: 0 0 4px;
      padding: 2px 0;
      font-size: 10.5pt;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      background: #111;
      color: #fff;
      padding-left: 6px;
    }

    p { margin: 0 0 4px; }

    h3.role-company { margin: 6px 0 0; font-size: 10.5pt; font-weight: 700; }
    p.role-title { margin: 0; font-size: 10.5pt; font-weight: 700; }
    p.role-meta { margin: 0 0 2px; font-size: 9.5pt; font-style: italic; }
    .project { margin: 0 0 2px; font-size: 9.5pt; font-style: italic; }

    ul { margin: 2px 0 0; padding-left: 17px; }
    li { margin: 0 0 1.5px; }

    .skills-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 9.5pt;
    }

    .skills-table th, .skills-table td {
      border: 1px solid #111;
      padding: 3px 6px;
      vertical-align: top;
      text-align: left;
    }

    .skills-table th {
      background: #f2f2f2;
      font-weight: 700;
    }

    .skills-table .skill-cat {
      width: 32%;
      font-weight: 700;
      background: #f4f4f4;
      color: #111;
    }

    .edu-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 3px;
    }

    .edu-degree { font-weight: 700; }
    .edu-year { white-space: nowrap; font-weight: 700; }

    .tech-summary, .certifications { margin: 0; padding-left: 17px; }
`;

export const skillsFirstTemplate = {
  id: "skills-first",
  label: "6 · Skills-First Technical",
  description: "Arial · inverted-bar headings · skills table before experience for US ATS.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const skills = renderSkills(data.skills);
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
  ${profile ? `<section><h2>Summary</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${skills ? `<section><h2>Technical Skills</h2>${skills}</section>` : ""}
  ${tech ? `<section><h2>Selected Highlights</h2>${tech}</section>` : ""}
  ${jobs ? `<section><h2>Professional Experience</h2>${jobs}</section>` : ""}
  ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
  ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
