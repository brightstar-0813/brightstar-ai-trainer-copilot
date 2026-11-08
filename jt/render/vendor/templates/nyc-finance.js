import {
  contactLine,
  escapeHtml,
  richHtml,
  pathAttr,
  renderCerts,
  renderEducationRows,
  renderJobsTitleFirst,
  renderSkills,
  renderTechnicalSummary,
  wrapHtmlDocument
} from "./shared.js";

/**
 * NYC / US finance-tech senior engineer resume (banks, Bloomberg, capital markets IT).
 * Navy band header, Calibri, no graphics.
 */
const CSS = `
    @page { size: A4; margin: 0; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Calibri, "Segoe UI", Arial, Helvetica, sans-serif;
      color: #1b2430;
      background: #fff;
      font-size: 10.2pt;
      line-height: 1.3;
    }

    .banner {
      background: #0b1f3a;
      color: #f4f6f8;
      padding: 11mm 16mm 9mm;
    }

    h1 {
      margin: 0;
      font-size: 22pt;
      font-weight: 700;
      letter-spacing: 0.2px;
      line-height: 1.08;
      color: #fff;
    }

    .headline {
      margin: 3px 0 6px;
      font-size: 11pt;
      font-weight: 600;
      color: #d4b56a;
      letter-spacing: 0.2px;
    }

    .contact {
      margin: 0;
      font-size: 9pt;
      color: #c5d0dc;
    }

    .contact a, .contact a:visited {
      color: #e8eef6;
      text-decoration: none;
    }

    .body { padding: 8mm 16mm 14mm; }

    section { margin: 0 0 8px; }

    h2 {
      margin: 0 0 5px;
      padding: 0 0 2px;
      font-size: 10pt;
      font-weight: 700;
      letter-spacing: 1.3px;
      text-transform: uppercase;
      color: #0b1f3a;
      border-bottom: 2px solid #d4b56a;
    }

    p { margin: 0 0 4px; text-align: justify; }

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
      color: #0b1f3a;
    }

    .job-dates {
      flex: 0 0 auto;
      white-space: nowrap;
      font-size: 9.5pt;
      font-weight: 700;
      color: #4a5a6c;
    }

    .job-meta, .project {
      margin: 0 0 2px;
      font-size: 9.5pt;
      font-style: italic;
      color: #4a5a6c;
    }

    ul { margin: 2px 0 0; padding-left: 16px; }
    li { margin: 0 0 1.5px; text-align: justify; }

    .skills-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 9.5pt;
    }

    .skills-table th, .skills-table td {
      border: 1px solid #c5d0dc;
      padding: 3px 6px;
      vertical-align: top;
      text-align: left;
    }

    .skills-table th {
      background: #0b1f3a;
      color: #fff;
      font-weight: 700;
      border-bottom: 3px solid #d4b56a;
    }

    .skills-table .skill-cat { width: 28%; font-weight: 700; color: #0b1f3a; }

    .edu-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 4px;
      align-items: baseline;
    }

    .edu-degree { font-weight: 700; }
    .edu-year { white-space: nowrap; font-weight: 700; color: #4a5a6c; }
`;

export const nycFinanceTemplate = {
  id: "nyc-finance",
  label: "4 · NYC Finance",
  description: "Navy header band · Calibri · US banks, capital markets, and fintech senior IC.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const skills = renderSkills(data.skills);
    const jobs = renderJobsTitleFirst(data.experience);
    const edu = renderEducationRows(data.education);
    const certs = (data.certifications || []).length ? renderCerts(data.certifications) : "";

    return wrapHtmlDocument({
      title: `${name} - Resume`,
      css: CSS,
      body: `<main class="resume">
  <header class="banner">
    <h1${pathAttr("name")}>${escapeHtml(name)}</h1>
    ${headline ? `<p class="headline"${pathAttr("headline")}>${richHtml(headline)}</p>` : ""}
    <p class="contact">${contactLine(data, { linkColor: "#e8eef6" })}</p>
  </header>
  <div class="body">
    ${profile ? `<section><h2>Profile</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
    ${tech ? `<section><h2>Selected Achievements</h2>${tech}</section>` : ""}
    ${jobs ? `<section><h2>Professional Experience</h2>${jobs}</section>` : ""}
    ${skills ? `<section><h2>Technical Skills</h2>${skills}</section>` : ""}
    ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
    ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
  </div>
</main>`
    });
  }
};
