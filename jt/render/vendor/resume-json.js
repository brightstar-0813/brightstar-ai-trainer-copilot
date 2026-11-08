/** Minimal stub — only what templates/index.js imports from Bid bot resume-json. */

export function stripClearanceFromTitle(text) {
  let s = String(text || "").trim();
  if (!s) return "";

  s = s.replace(
    /\s*[\(\[\{]\s*(?:active\s+|interim\s+)?(?:public\s+trust|secret|top\s*secret|ts\s*\/?\s*sci|sci|confidential)(?:\s+clearance|\s+eligibility)?[^)\]\}]*[\)\]\}]/gi,
    ""
  );
  s = s.replace(/\s*[\(\[\{][^)\]\}]*\bclearance\b[^)\]\}]*[\)\]\}]/gi, "");
  s = s.replace(
    /\s*[-–—|:]\s*(?:active\s+|interim\s+)?(?:public\s+trust|secret|top\s*secret|ts\s*\/?\s*sci)(?:\s+clearance)?(?:\s+(?:required|preferred|eligible|eligibility))?\s*$/i,
    ""
  );
  s = s.replace(/\s*[-–—|:]\s*[^|]*\bclearance\b[^|]*$/i, "");
  s = s.replace(
    /\b(?:active\s+|interim\s+)?(?:public\s+trust|secret|top\s*secret|ts\s*\/?\s*sci)\s+clearance\b/gi,
    ""
  );
  s = s.replace(/\b(?:security\s+)?clearance(?:\s+(?:required|preferred|eligible|eligibility))?\b/gi, "");
  s = s.replace(/\bpublic\s+trust\b/gi, "");

  return s
    .replace(/\s{2,}/g, " ")
    .replace(/\s*([|,/])\s*$/g, "")
    .replace(/^[\s|,/–—-]+|[\s|,/–—-]+$/g, "")
    .trim();
}
