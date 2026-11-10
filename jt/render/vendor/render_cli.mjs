#!/usr/bin/env node
/**
 * Render resume JSON through Bid bot-style templates.
 * Usage:
 *   node render_cli.mjs list
 *   node render_cli.mjs render --template ats-modern [--accent blue] < resume.json
 *   node render_cli.mjs render --template ats-modern --in resume.json --out out.html
 */
import { readFileSync, writeFileSync } from "node:fs";
import { escapeHtml, richHtml } from "./templates/shared.js";
import {
  DEFAULT_TEMPLATE_ID,
  getAllTemplates,
  resumeJsonToHtml
} from "./templates/index.js";

function usage() {
  process.stderr.write(
    "Usage: render_cli.mjs list | render --template ID [--accent ID] [--in file] [--out file]\n"
  );
  process.exit(2);
}

function readStdin() {
  return readFileSync(0, "utf8");
}

function projectsSection(projects) {
  const items = (projects || [])
    .map((p) => {
      const name = String(p?.name || "").trim();
      const link = String(p?.link || "").trim();
      const desc = String(p?.description || "").trim();
      if (!name && !desc) return "";
      const title = name
        ? link
          ? `<b>${richHtml(name)}</b> (${escapeHtml(link)})`
          : `<b>${richHtml(name)}</b>`
        : "";
      const body = [title, desc ? richHtml(desc) : ""].filter(Boolean).join(": ");
      return `<p class="project-item">${body}</p>`;
    })
    .filter(Boolean);
  if (!items.length) return "";
  return `<section class="jt-projects"><h2>Representative projects</h2>\n${items.join("\n")}\n</section>`;
}

function injectProjects(html, projects) {
  const block = projectsSection(projects);
  if (!block) return html;
  if (html.includes('<div class="main">')) {
    return html.replace(/(<\/div>\s*<\/main>)/, `${block}\n$1`);
  }
  if (html.includes("</main>")) {
    return html.replace("</main>", `${block}\n</main>`);
  }
  return `${html}\n${block}`;
}

function listTemplates() {
  const rows = getAllTemplates().map((t) => ({
    id: t.id,
    label: t.label,
    description: t.description || ""
  }));
  process.stdout.write(
    JSON.stringify({ default: DEFAULT_TEMPLATE_ID, templates: rows }, null, 2) + "\n"
  );
}

function parseArgs(argv) {
  const out = { cmd: "", template: DEFAULT_TEMPLATE_ID, accent: "", inPath: "", outPath: "" };
  out.cmd = argv[0] || "";
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--template") out.template = argv[++i] || out.template;
    else if (a === "--accent") out.accent = argv[++i] || "";
    else if (a === "--in") out.inPath = argv[++i] || "";
    else if (a === "--out") out.outPath = argv[++i] || "";
    else usage();
  }
  return out;
}

function render(opts) {
  const raw = opts.inPath ? readFileSync(opts.inPath, "utf8") : readStdin();
  const data = JSON.parse(raw);
  let html = resumeJsonToHtml(data, opts.template, { accentId: opts.accent || undefined });
  html = injectProjects(html, data.projects);
  if (opts.outPath) writeFileSync(opts.outPath, html, "utf8");
  else process.stdout.write(html);
}

const opts = parseArgs(process.argv.slice(2));
if (opts.cmd === "list") listTemplates();
else if (opts.cmd === "render") render(opts);
else usage();
