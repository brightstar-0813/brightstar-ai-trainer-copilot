import {
  contactLine,
  escapeHtml,
  richHtml,
  pathAttr,
  renderCerts,
  renderEducationRows,
  renderJobsTitleFirst,
  renderSkillsInline,
  wrapHtmlDocument
} from "./shared.js";

/**
 * Silicon Valley / Big Tech senior IC (L5–L7 / Staff-track).
 * Experience-first, Arial, almost no decoration — Google, Meta, Amazon,
 * Stripe, Uber recruiter screens.
 */
const CSS = `
    @page { size: A4; margin: 12mm 13mm; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: #222;
      background: #fff;
      font-size: 10pt;
      line-height: 1.28;
    }

    .resume { width: 100%; }

    header.top {
      margin: 0 0 8px;
      text-align: center;
    }

    h1 {
      margin: 0;
      font-size: 16.5pt;
      font-weight: 700;
      letter-spacing: 0;
      line-height: 1.15;
    }

    .headline {
      margin: 1px 0 3px;
      font-size: 10pt;
      font-weight: 400;
      color: #333;
    }

    .contact {
      margin: 0;
      font-size: 9pt;
      color: #333;
    }

    .contact a, .contact a:visited {
      color: #222;
      text-decoration: none;
    }

    section { margin: 0 0 7px; }

    h2 {
      margin: 8px 0 3px;
      padding: 0;
      font-size: 10pt;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: #111;
      border: 0;
    }

    p { margin: 0 0 3px; }

    .job { margin: 0 0 7px; }

    .job-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }

    .job-title {
      margin: 0;
      font-size: 10.5pt;
      font-weight: 500;
    }

    .job-title span:last-child { font-weight: 800; }

    .job-dates {
      flex: 0 0 auto;
      white-space: nowrap;
      font-size: 10pt;
    }

    .job-meta, .project {
      margin: 0;
      font-size: 10pt;
      font-style: italic;
    }

    ul {
      margin: 1px 0 0;
      padding-left: 16px;
    }

    li { margin: 0 0 1px; }

    .skills-inline { margin: 0; }

    .skill-inline {
      margin: 0 0 1px;
      font-size: 10pt;
    }

    .skill-inline .skill-cat { font-weight: 700; }

    .edu-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 2px;
      align-items: baseline;
    }

    .edu-degree { font-weight: 700; }
    .edu-year { white-space: nowrap; }

    .certifications {
      margin: 0;
      padding-left: 16px;
    }
`;

export const svSeniorTemplate = {
  id: "sv-senior",
  label: "3 · Silicon Valley",
  description: "Arial · experience-first · US Big Tech L5–L7 / Staff-track.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
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
    <p class="contact">${contactLine(data)}</p>
  </header>
  ${profile ? `<section><h2>Summary</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${jobs ? `<section><h2>Experience</h2>${jobs}</section>` : ""}
  ${skills ? `<section><h2>Skills</h2>${skills}</section>` : ""}
  ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
  ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
