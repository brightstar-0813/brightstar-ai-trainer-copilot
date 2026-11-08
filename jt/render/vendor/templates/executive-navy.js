import {
  escapeHtml,
  richHtml,
  pathAttr,
  renderCerts,
  renderEducationRows,
  renderSkillsStacked,
  renderTechnicalSummary,
  wrapHtmlDocument
} from "./shared.js";

const CSS = `
    @page { size: A4; margin: 0; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Calibri, "Segoe UI", Arial, Helvetica, sans-serif;
      color: #1a2332;
      background: #fff;
      font-size: 10pt;
      line-height: 1.32;
    }

    .resume {
      display: grid;
      grid-template-columns: 62mm 1fr;
      min-height: 297mm;
      align-items: stretch;
    }

    aside {
      background: #071e38;
      color: #f4f1e8;
      padding: 16mm 8mm 14mm;
    }

    .aside-name {
      margin: 0 0 4px;
      font-family: Cambria, Georgia, serif;
      font-size: 16pt;
      font-weight: 700;
      line-height: 1.15;
      letter-spacing: 0.2px;
      color: #fff;
    }

    .aside-headline {
      margin: 0 0 8px;
      font-size: 9pt;
      font-weight: 700;
      letter-spacing: 0.4px;
      color: #ffe08a;
    }

    .aside-rule {
      height: 3px;
      background: #f5c542;
      border: 0;
      margin: 0 0 12px;
    }

    aside h2 {
      margin: 14px 0 6px;
      font-size: 8.5pt;
      font-weight: 800;
      letter-spacing: 1.2px;
      text-transform: uppercase;
      color: #f5c542;
      border: 0;
    }

    .aside-contact div {
      margin: 0 0 5px;
      font-size: 8.6pt;
      line-height: 1.3;
      word-break: break-word;
    }

    aside a, aside a:visited {
      color: #ffe08a;
      text-decoration: none;
    }

    .skills-stack { margin: 0; }

    .skill-row { margin: 0 0 7px; }

    .skill-cat {
      display: block;
      font-size: 8.2pt;
      font-weight: 800;
      letter-spacing: 0.3px;
      text-transform: uppercase;
      color: #ffe08a;
      margin-bottom: 1px;
    }

    .skill-items {
      display: block;
      font-size: 8.5pt;
      color: #e8eef8;
      line-height: 1.3;
    }

    aside .certifications {
      margin: 0;
      padding-left: 14px;
      font-size: 8.5pt;
    }

    aside .certifications li { margin: 0 0 3px; }

    aside .edu-row { margin: 0 0 8px; }

    aside .edu-degree {
      font-weight: 700;
      font-size: 9pt;
      color: #fff;
    }

    aside .edu-school, aside .edu-details, aside .edu-year {
      font-size: 8.4pt;
      color: #d5deea;
    }

    aside .edu-year { margin-top: 1px; font-weight: 700; color: #f5c542; }

    .main {
      padding: 14mm 12mm 14mm 11mm;
    }

    .main h2 {
      margin: 0 0 6px;
      padding: 0 0 3px 8px;
      border: 0;
      border-left: 3px solid #f5c542;
      font-size: 10.5pt;
      font-weight: 800;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: #0e2a4c;
    }

    section { margin: 0 0 11px; }

    .summary, .tech-summary {
      text-align: justify;
      margin: 0;
    }

    .tech-summary {
      padding-left: 16px;
    }

    .tech-summary li { margin: 0 0 2px; }

    .job { margin: 0 0 9px; }

    .job-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }

    .job-company {
      margin: 0;
      font-size: 11pt;
      font-weight: 800;
      color: #0e2a4c;
    }

    .job-dates {
      flex: 0 0 auto;
      white-space: nowrap;
      font-size: 10pt;
      font-weight: 800;
      color: #0e2a4c;
      background: #f6f1e4;
      padding: 1px 6px;
    }

    .job-title {
      margin: 0;
      font-size: 10pt;
      font-weight: 700;
      color: #1a2332;
    }

    .job-meta {
      margin: 0 0 2px;
      font-size: 9pt;
      color: #5c6d82;
      font-style: italic;
    }

    .project {
      margin: 0 0 2px;
      font-size: 9pt;
      font-style: italic;
      color: #3d4f66;
    }

    ul {
      margin: 2px 0 0;
      padding-left: 16px;
    }

    li {
      margin: 0 0 2px;
      text-align: justify;
    }
`;

function renderAsideContact(data) {
  const lines = [];
  if (data.location) {
    lines.push(`<div${pathAttr("location")}>${escapeHtml(data.location)}</div>`);
  }
  if (data.phone) {
    lines.push(`<div${pathAttr("phone")}>${escapeHtml(data.phone)}</div>`);
  }
  if (data.email) {
    const email = String(data.email).replace(/^mailto:/i, "").trim();
    lines.push(
      `<div><a href="mailto:${escapeHtml(email)}"${pathAttr("email")}>${escapeHtml(email)}</a></div>`
    );
  }
  if (data.linkedin) {
    const raw = String(data.linkedin).trim();
    const href = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
    const label = href.replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "");
    lines.push(
      `<div><a href="${escapeHtml(href)}"${pathAttr("linkedin")}>${escapeHtml(label)}</a></div>`
    );
  }
  return lines.length ? `<div class="aside-contact">${lines.join("")}</div>` : "";
}

function renderJobs(jobs) {
  return (jobs || [])
    .map((job, ji) => {
      const company = String(job.company || "").trim();
      const title = String(job.title || "").trim();
      const dates = String(job.dates || "").trim();
      const location = String(job.location || "").trim();
      const project = String(job.project || "").trim();
      const bullets = (job.bullets || [])
        .map((b, bi) => {
          const text = String(b || "").trim();
          if (!text) return "";
          return `<li${pathAttr(`experience.${ji}.bullets.${bi}`)}>${richHtml(text)}</li>`;
        })
        .filter(Boolean)
        .join("\n");
      return `<article class="job">
  <div class="job-top">
    <h3 class="job-company"${pathAttr(`experience.${ji}.company`)}>${richHtml(company)}</h3>
    ${dates ? `<span class="job-dates"${pathAttr(`experience.${ji}.dates`)}>${escapeHtml(dates)}</span>` : ""}
  </div>
  ${title ? `<p class="job-title"${pathAttr(`experience.${ji}.title`)}>${richHtml(title)}</p>` : ""}
  ${location ? `<p class="job-meta"${pathAttr(`experience.${ji}.location`)}>${escapeHtml(location)}</p>` : ""}
  ${project ? `<p class="project"${pathAttr(`experience.${ji}.project`)}>${richHtml(project)}</p>` : ""}
  ${bullets ? `<ul>\n${bullets}\n  </ul>` : ""}
</article>`;
    })
    .join("\n");
}

export const executiveNavyTemplate = {
  id: "executive-navy",
  label: "8 · Executive Navy",
  description: "Navy sidebar · gold accent · US Staff / Principal / engineering manager.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const skills = renderSkillsStacked(data.skills);
    const edu = renderEducationRows(data.education);
    const certs = (data.certifications || []).length ? renderCerts(data.certifications) : "";
    const jobs = renderJobs(data.experience);

    return wrapHtmlDocument({
      title: `${name} - Resume`,
      css: CSS,
      body: `<main class="resume">
  <aside>
    <p class="aside-name"${pathAttr("name")}>${escapeHtml(name)}</p>
    ${headline ? `<p class="aside-headline"${pathAttr("headline")}>${richHtml(headline)}</p>` : ""}
    <div class="aside-rule"></div>
    ${renderAsideContact(data)}
    ${skills ? `<h2>Skills</h2>${skills}` : ""}
    ${edu ? `<h2>Education</h2>${edu}` : ""}
    ${certs ? `<h2>Certifications</h2>${certs}` : ""}
  </aside>
  <div class="main">
    ${
      profile
        ? `<section><h2>Profile</h2><p class="summary"${pathAttr("profile")}>${richHtml(profile)}</p></section>`
        : ""
    }
    ${tech ? `<section><h2>Highlights</h2>${tech}</section>` : ""}
    ${jobs ? `<section><h2>Experience</h2>${jobs}</section>` : ""}
  </div>
</main>`
    });
  }
};
