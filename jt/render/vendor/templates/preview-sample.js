/**
 * Generic sample resume for style preview.
 * Contact fields are overlaid from the active person when available.
 */
export function sampleResumeForPerson(person = {}) {
  const name = String(person?.name || person?.label || "Alex Rivera").trim();
  return {
    name,
    headline: String(person?.signatureTitle || "Senior Software Engineer").trim(),
    location: String(person?.location || "Austin, Texas, United States").trim(),
    phone: String(person?.phone || "+1 (555) 010-2048").trim(),
    email: String(person?.email || "alex.rivera@email.com").trim(),
    linkedin: String(person?.linkedin || "https://linkedin.com/in/alexrivera").trim(),
    profile:
      "Senior engineer with 10+ years delivering CRM platforms, integrations, and release automation for enterprise teams. Known for translating messy requirements into maintainable architecture, coaching developers, and shipping on time without sacrificing quality.",
    technicalSummary: [
      "Designed multi-cloud CRM architecture used by 2,400+ agents with 99.9% uptime.",
      "Led integration programs covering REST, SOAP, ETL, and event-driven patterns.",
      "Cut release cycle time 40% by introducing CI/CD, sandbox strategy, and automated tests."
    ],
    skills: [
      { category: "Languages", items: "Apex, JavaScript, TypeScript, SQL, HTML, CSS" },
      { category: "Platform", items: "Salesforce, Lightning Web Components, Flow, Apex Triggers" },
      { category: "Integrations", items: "REST, SOAP, Platform Events, MuleSoft-adjacent APIs, Data Loader" },
      { category: "Delivery", items: "Copado, Git, Jira, Agile, code review, production support" }
    ],
    experience: [
      {
        company: "Northstar Digital",
        location: "Austin, TX · Remote",
        title: "Senior Software Engineer",
        dates: "Jan 2021 – Present",
        project: "Customer 360 platform modernization",
        bullets: [
          "Rebuilt service console workflows in Lightning, reducing average handle time 18%.",
          "Implemented trigger framework and bulk-safe Apex services handling 1.2M nightly records.",
          "Partnered with security on sharing, FLS, and SSO; passed annual audit with zero critical findings."
        ]
      },
      {
        company: "Harbor & Co.",
        location: "Dallas, TX",
        title: "Software Engineer",
        dates: "Mar 2017 – Dec 2020",
        project: "Quote-to-cash integrations",
        bullets: [
          "Delivered REST integrations between CRM, billing, and warehouse systems.",
          "Introduced automated regression suite covering 86% of critical paths.",
          "Mentored four engineers on design reviews, testing, and production diagnostics."
        ]
      },
      {
        company: "Cedar Labs",
        location: "Houston, TX",
        title: "Associate Developer",
        dates: "Jun 2014 – Feb 2017",
        bullets: [
          "Built custom objects, validation, and Visualforce pages for operations teams.",
          "Supported data migrations and sandbox refreshes for quarterly releases."
        ]
      }
    ],
    education: [
      {
        school: "University of Texas at Austin",
        degree: "B.S. Computer Science",
        year: "2014 - 2018",
        details: "Austin, Texas, United States"
      }
    ],
    certifications: [
      "Salesforce Certified Administrator",
      "Salesforce Certified Platform Developer I",
      "Salesforce Certified Platform Developer II",
      "Salesforce Certified Service Cloud Consultant",
      "Salesforce Certified Platform App Builder"
    ]
  };
}

export function isResumePreviewable(data) {
  if (!data || typeof data !== "object") return false;
  const name = String(data.name || "").trim();
  const jobs = Array.isArray(data.experience) ? data.experience.length : 0;
  return Boolean(name || jobs);
}
