import {
  educationLocationLine,
  educationYearLine,
  stripEducationDatesFromPlace,
  escapeHtml,
  pathAttr,
  renderCerts,
  renderSkills,
  renderTechnicalSummary,
  richHtml,
  wrapHtmlDocument
} from "./shared.js";

/**
 * Orange banner resume: gray name, labeled contact line, orange section bars
 * for Experience and Education.
 */
const CSS = `
    @page { size: A4; margin: 0; }

    * { box-sizing: border-box; }

    html, body {
      width: 210mm;
      margin: 0;
      padding: 0;
      font-family: Calibri, "Segoe UI", Arial, sans-serif;
      color: #222;
      background: #fff;
      font-size: 10.5pt;
      line-height: 1.32;
    }

    .resume {
      width: 100%;
      padding: 0 16mm 14mm;
    }

    .page-bar {
      height: 8px;
      margin: 0 -16mm 8px;
      background: #e6e6e6;
    }

    h1 {
      margin: 0;
      font-size: 26pt;
      font-weight: 600;
      letter-spacing: 1.4px;
      text-transform: uppercase;
      color: #7b8490;
      line-height: 1.05;
    }

    .headline {
      margin: 2px 0 4px;
      font-size: 11pt;
      font-weight: 400;
      color: #6b7280;
    }

    .contact {
      margin: 0 0 6px;
      font-size: 10pt;
      color: #e8772e;
    }

    .contact .tag { font-weight: 700; }

    .contact a, .contact a:visited { color: #e8772e; text-decoration: none; }

    h2.plain {
      margin: 11px 0 4px;
      font-size: 11pt;
      font-weight: 700;
      letter-spacing: 0.6px;
      text-transform: uppercase;
      color: #e8772e;
    }

    h2.bar {
      display: flex;
      align-items: center;
      margin: 12px 0 8px;
      font-size: 11pt;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: #fff;
    }

    h2.bar span {
      background: #e8772e;
      padding: 3px 12px 3px 8px;
    }

    h2.bar::after {
      content: "";
      flex: 1;
      height: 2px;
      background: #e8772e;
    }

    p { margin: 0 0 4px; }

    .tech-summary { margin: 0; padding-left: 16px; }

    .org {
      margin: 0;
      font-size: 9.5pt;
      font-weight: 600;
      letter-spacing: 0.4px;
      text-transform: uppercase;
      color: #4b5563;
    }

    .job { margin: 0 0 8px; }

    .job-top, .edu-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }

    .job-title, .edu-degree {
      margin: 0;
      font-size: 11pt;
      font-weight: 700;
      color: #111;
    }

    .job-dates, .edu-year {
      flex: 0 0 auto;
      white-space: nowrap;
      font-size: 10.5pt;
      color: #333;
    }

    ul { margin: 2px 0 0; padding-left: 16px; }
    li { margin: 0 0 2px; }

    .skills-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      margin: 2px 0 0;
      font-size: 10pt;
    }

    .skills-table th,
    .skills-table td {
      padding: 2px 8px 2px 0;
      vertical-align: top;
      text-align: left;
      border-bottom: 1px solid #f3d3c0;
    }

    .skills-table th {
      font-size: 8.5pt;
      font-weight: 700;
      letter-spacing: 0.4px;
      text-transform: uppercase;
      color: #e8772e;
      border-bottom: 1.5px solid #e8772e;
    }

    .skills-table .skill-cat {
      width: 28%;
      font-weight: 700;
      color: #333;
    }

    .skills-table .skill-items { width: 72%; }

    .edu { margin: 0 0 8px; }

    .edu-note {
      margin: 1px 0 0;
      font-style: italic;
      color: #333;
    }

    .certifications { margin: 0; padding-left: 16px; }
`;

function shortLink(value) {
  return String(value || "")
    .trim()
    .replace(/^\[([^\]]*)\]\(([^)]+)\)$/, "$2")
    .replace(/^mailto:/i, "")
    .replace(/^https?:\/\//i, "")
    .replace(/^www\./i, "")
    .replace(/\/$/, "");
}

function labeledContact(data) {
  const bits = [];
  if (data.phone) {
    bits.push(
      `<span class="tag">P:</span> <span${pathAttr("phone")}>${escapeHtml(data.phone)}</span>`
    );
  }
  if (data.email) {
    const email = shortLink(data.email);
    bits.push(
      `<span class="tag">E:</span> <a href="mailto:${escapeHtml(email)}"${pathAttr("email")}>${escapeHtml(email)}</a>`
    );
  }
  if (data.linkedin) {
    const shown = shortLink(data.linkedin);
    const href = /^https?:\/\//i.test(String(data.linkedin))
      ? String(data.linkedin).trim()
      : `https://${shown}`;
    bits.push(
      `<span class="tag">LI:</span> <a href="${escapeHtml(href)}"${pathAttr("linkedin")}>${escapeHtml(shown)}</a>`
    );
  }
  if (data.location) {
    bits.push(
      `<span class="tag">L:</span> <span${pathAttr("location")}>${escapeHtml(data.location)}</span>`
    );
  }
  return bits.join(" | ");
}

function renderJobs(jobs) {
  return (jobs || [])
    .map((job, ji) => {
      const company = String(job.company || "").trim();
      const title = String(job.title || "").trim();
      const dates = String(job.dates || "").trim();
      const location = String(job.location || "").trim();
      const org = [company, location].filter(Boolean).join(" | ");
      const bullets = (job.bullets || [])
        .map((bullet, bi) => {
          const text = String(bullet || "").trim();
          if (!text) return "";
          return `<li${pathAttr(`experience.${ji}.bullets.${bi}`)}>${richHtml(text)}</li>`;
        })
        .filter(Boolean)
        .join("\n");
      return `<article class="job">
  ${org ? `<p class="org">${company ? `<span${pathAttr(`experience.${ji}.company`)}>${richHtml(company)}</span>` : ""}${company && location ? " | " : ""}${location ? `<span${pathAttr(`experience.${ji}.location`)}>${escapeHtml(location)}</span>` : ""}</p>` : ""}
  <div class="job-top">
    ${title ? `<p class="job-title"${pathAttr(`experience.${ji}.title`)}>${richHtml(title)}</p>` : "<p class=\"job-title\"></p>"}
    ${dates ? `<span class="job-dates"${pathAttr(`experience.${ji}.dates`)}>${escapeHtml(dates)}</span>` : ""}
  </div>
  ${bullets ? `<ul>\n${bullets}\n</ul>` : ""}
</article>`;
    })
    .join("\n");
}

function renderEducation(education) {
  const list = Array.isArray(education) ? education : education ? [education] : [];
  return list
    .map((edu, ei) => {
      const degree = String(edu?.degree || "").trim();
      const school = String(edu?.school || "").trim();
      const year = educationYearLine(edu);
      const location = educationLocationLine(edu);
      let note = String(edu?.details || "").trim();
      // details is often "City | dates"; location already stripped the date — don't re-print it.
      const notePlace = stripEducationDatesFromPlace(note);
      if (note && location && (note.toLowerCase() === location.toLowerCase() || notePlace.toLowerCase() === location.toLowerCase())) {
        note = "";
      }
      if (!school && !degree) return "";
      return `<article class="edu">
  <div class="edu-top">
    <p class="org">${school ? `<span${pathAttr(`education.${ei}.school`)}>${richHtml(school)}</span>` : ""}${school && location ? " | " : ""}${location ? `<span${pathAttr(`education.${ei}.location`)}>${richHtml(location)}</span>` : ""}</p>
    ${year ? `<span class="edu-year"${pathAttr(`education.${ei}.year`)}>${richHtml(year)}</span>` : ""}
  </div>
  ${degree ? `<p class="edu-degree"${pathAttr(`education.${ei}.degree`)}>${richHtml(degree)}</p>` : ""}
  ${note ? `<p class="edu-note"${pathAttr(`education.${ei}.details`)}>${richHtml(note)}</p>` : ""}
</article>`;
    })
    .filter(Boolean)
    .join("\n");
}


export const orangeBannerTemplate = {
  id: "orange-banner",
  label: "9 · Orange Banner",
  description: "Calibri · gray name · orange bars for Experience and Education.",
  render(data) {
    const name = String(data.name || "Resume").trim() || "Resume";
    const headline = String(data.headline || "").trim();
    const profile = String(data.profile || "").trim();
    const tech = renderTechnicalSummary(data.technicalSummary);
    const jobs = renderJobs(data.experience);
    const skills = renderSkills(data.skills);
    const edu = renderEducation(data.education);
    const certs = (data.certifications || []).length ? renderCerts(data.certifications) : "";
    const contact = labeledContact(data);

    return wrapHtmlDocument({
      title: `${name} - Resume`,
      css: CSS,
      body: `<main class="resume">
  <div class="page-bar"></div>
  <header class="top">
    <h1${pathAttr("name")}>${escapeHtml(name)}</h1>
    ${headline ? `<p class="headline"${pathAttr("headline")}>${richHtml(headline)}</p>` : ""}
    ${contact ? `<p class="contact">${contact}</p>` : ""}
  </header>
  ${profile ? `<section><h2 class="plain">About me</h2><p${pathAttr("profile")}>${richHtml(profile)}</p></section>` : ""}
  ${tech ? `<section><h2 class="plain">Technical summary</h2>${tech}</section>` : ""}
  ${jobs ? `<section><h2 class="bar"><span>Experience</span></h2>${jobs}</section>` : ""}
  ${skills ? `<section><h2 class="plain">Areas of expertise</h2>${skills}</section>` : ""}
  ${edu ? `<section><h2 class="bar"><span>Education</span></h2>${edu}</section>` : ""}
  ${certs ? `<section><h2 class="plain">Certifications</h2>${certs}</section>` : ""}
</main>`
    });
  }
};
