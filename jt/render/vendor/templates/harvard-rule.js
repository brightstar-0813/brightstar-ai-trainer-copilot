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
 * US “Harvard rule” resume: centered name, double horizontal rules.
 * Common for senior ICs, MBA hybrids, and Staff-track packets.
 */
const CSS = `
    @page { size: A4; margin: 14mm 16mm; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Garamond, "Times New Roman", Times, serif;
      color: #111;
      background: #fff;
      font-size: 10.5pt;
      line-height: 1.28;
    }

    .resume { width: 100%; }

    header.top {
      text-align: center;
      margin: 0 0 10px;
      padding: 0 0 8px;
      border-bottom: 3px double #111;
    }

    h1 {
      margin: 0;
      font-size: 22pt;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
      line-height: 1.1;
    }

    .headline {
      margin: 3px 0 4px;
      font-size: 11pt;
      font-style: italic;
      font-weight: 400;
    }

    .contact {
      margin: 0;
      font-size: 9.5pt;
      font-family: Calibri, Arial, sans-serif;
    }

    a, a:visited { color: #111; text-decoration: underline; }

    section { margin: 0 0 8px; }

    h2 {
      margin: 0 0 4px;
      padding: 0;
      font-size: 13pt;
      font-weight: 700;
      letter-spacing: 0.12em;
      font-variant: small-caps;
      text-transform: none;
      border: 0;
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

    .job-title { margin: 0; font-size: 11pt; font-weight: 700; }

    .job-dates {
      flex: 0 0 auto;
      white-space: nowrap;
      font-size: 10pt;
      font-style: italic;
    }

    .job-meta, .project {
      margin: 0 0 2px;
      font-size: 10pt;
      font-style: italic;
    }

    ul { margin: 2px 0 0; padding-left: 16px; }
    li { margin: 0 0 1.5px; text-align: justify; }

    .skills-inline { font-family: Calibri, Arial, sans-serif; font-size: 10pt; }
    .skill-inline { margin: 0 0 2px; }
    .skill-inline .skill-cat { font-weight: 700; }

    .edu-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 3px;
      align-items: baseline;
    }

    .edu-degree { font-weight: 700; }
    .edu-year { white-space: nowrap; font-weight: 700; }
`;

export const harvardRuleTemplate = {
  id: "harvard-rule",
  label: "5 · Harvard Rule",
  description: "Garamond · centered name · double rule · US senior IC / MBA hybrid.",
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
    <p class="contact">${contactLine(data)}</p>
  </header>
  ${profile ? `<section><h2>Summary</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${tech ? `<section><h2>Highlights</h2>${tech}</section>` : ""}
  ${jobs ? `<section><h2>Experience</h2>${jobs}</section>` : ""}
  ${edu ? `<section><h2>Education</h2>${edu}</section>` : ""}
  ${skills ? `<section><h2>Skills</h2>${skills}</section>` : ""}
  ${certs ? `<section><h2>Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
