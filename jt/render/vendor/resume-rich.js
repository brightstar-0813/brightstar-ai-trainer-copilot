/**
 * Limited Word-style marks stored inside resume JSON strings.
 * Bold, italic, underline, allowlisted font and size, left or center.
 * Colors, images, scripts, and other markup are dropped.
 */

export const RICH_FONTS = ["Calibri", "Cambria", "Times New Roman", "Arial", "Georgia"];
export const RICH_SIZES = [10, 11, 12, 14];

const ALLOWED = new Set(["b", "i", "u", "br", "span", "p", "div"]);
const RENAME = { strong: "b", em: "i", font: "span" };

export function isPlainResumePath(path) {
  const p = String(path || "").trim();
  if (/^(name|email|phone|location|linkedin)$/.test(p)) return true;
  if (/\.dates$/.test(p)) return true;
  if (/^experience\.\d+\.location$/.test(p)) return true;
  return false;
}

function escapeText(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function decodeRichEntities(value) {
  return String(value ?? "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'");
}

export function matchRichFont(raw) {
  const name = String(raw || "")
    .trim()
    .replace(/^['"]|['"]$/g, "")
    .split(",")[0]
    .trim()
    .replace(/^['"]|['"]$/g, "");
  return RICH_FONTS.find((font) => font.toLowerCase() === name.toLowerCase()) || "";
}

export function snapRichSize(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return RICH_SIZES.reduce((best, size) =>
    Math.abs(size - n) < Math.abs(best - n) ? size : best
  );
}

function attrValue(attrs, name) {
  const re = new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s"'>]+))`, "i");
  const match = String(attrs || "").match(re);
  return match ? match[1] || match[2] || match[3] || "" : "";
}

function styleValue(style, prop) {
  const re = new RegExp(`${prop}\\s*:\\s*([^;]+)`, "i");
  const match = String(style || "").match(re);
  return match ? match[1].trim() : "";
}

function sanitizeStyle(tag, attrs) {
  const style = attrValue(attrs, "style");
  const parts = [];
  if (tag === "span") {
    const font = matchRichFont(styleValue(style, "font-family") || attrValue(attrs, "face"));
    if (font) parts.push(`font-family:${font}`);
    const sizeRaw = styleValue(style, "font-size").match(/([0-9.]+)\s*pt/i);
    const size = sizeRaw ? snapRichSize(sizeRaw[1]) : 0;
    if (size) parts.push(`font-size:${size}pt`);
  }
  if (tag === "p" || tag === "div") {
    const align = styleValue(style, "text-align").toLowerCase();
    if (align === "left" || align === "center") parts.push(`text-align:${align}`);
  }
  return parts.join(";");
}

/**
 * Keep only the marks the preview bar can create. Safe to run in node:test.
 * @param {string} value
 */
export function sanitizeRichHtml(value) {
  let src = String(value ?? "");
  src = src.replace(/<!--[\s\S]*?-->/g, "");
  src = src.replace(/<(script|style|iframe|object|embed|svg|math)\b[^>]*>[\s\S]*?<\/\1>/gi, "");
  src = src.replace(/<(script|style|iframe|object|embed|svg|math|img|link|meta)\b[^>]*\/?>/gi, "");

  const out = [];
  const stack = [];
  const re = /<\/?([a-zA-Z][\w:-]*)\b([^>]*)>/g;
  let last = 0;
  let match;
  while ((match = re.exec(src))) {
    out.push(escapeText(decodeRichEntities(src.slice(last, match.index))));
    const rawName = match[1].toLowerCase();
    const isClose = match[0].startsWith("</");
    const name = RENAME[rawName] || rawName;
    if (isClose) {
      const opened = stack.pop();
      if (opened) out.push(`</${opened}>`);
    } else if (name === "br") {
      out.push("<br>");
    } else if (ALLOWED.has(name)) {
      const style = sanitizeStyle(name, match[2]);
      if ((name === "span" || name === "p" || name === "div") && !style) {
        stack.push("");
      } else {
        out.push(style ? `<${name} style="${style}">` : `<${name}>`);
        stack.push(name);
      }
    } else {
      stack.push("");
    }
    last = re.lastIndex;
  }
  out.push(escapeText(decodeRichEntities(src.slice(last))));
  return out
    .join("")
    .replace(/(?:<br>)+$/g, "")
    .replace(/^(?:<br>)+/g, "")
    .trim();
}

export function richHtml(value) {
  return sanitizeRichHtml(value);
}

export function plainTextFromRich(value) {
  return decodeRichEntities(sanitizeRichHtml(value).replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}
