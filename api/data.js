const fs = require("fs");
const path = require("path");

const WINDOW_MS = 10 * 60 * 1000;
const MAX_REQUESTS = 60;
const ALLOWED_FILES = new Map([
  ["districts_complete.csv", "text/csv; charset=utf-8"],
  ["district_coordinates.csv", "text/csv; charset=utf-8"],
  ["nces_district_coordinates.csv", "text/csv; charset=utf-8"],
]);

function json(res, statusCode, payload) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(payload));
}

function clientIp(req) {
  const forwarded = req.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.trim()) {
    return forwarded.split(",")[0].trim();
  }
  return req.socket?.remoteAddress || "unknown";
}

function checkRateLimit(req) {
  const now = Date.now();
  const ip = clientIp(req);
  const store = globalThis.__districtDataRateLimit || new Map();
  globalThis.__districtDataRateLimit = store;

  const recent = (store.get(ip) || []).filter(timestamp => now - timestamp < WINDOW_MS);
  if (recent.length >= MAX_REQUESTS) {
    store.set(ip, recent);
    return false;
  }
  recent.push(now);
  store.set(ip, recent);
  return true;
}

function requestedFile(req) {
  const url = new URL(req.url, "https://districtfinder.org");
  const fromQuery = url.searchParams.get("file");
  if (fromQuery) return path.basename(fromQuery);
  const match = url.pathname.match(/^\/data\/([^/]+)$/);
  return match ? path.basename(match[1]) : "";
}

module.exports = function handler(req, res) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.setHeader("Allow", "GET, HEAD");
    return json(res, 405, { ok: false, error: "method_not_allowed" });
  }

  if (!checkRateLimit(req)) {
    res.setHeader("Retry-After", String(Math.ceil(WINDOW_MS / 1000)));
    return json(res, 429, { ok: false, error: "rate_limited" });
  }

  const file = requestedFile(req);
  const contentType = ALLOWED_FILES.get(file);
  if (!contentType) {
    return json(res, 404, { ok: false, error: "not_found" });
  }

  const filePath = path.join(process.cwd(), "data", file);
  if (!fs.existsSync(filePath)) {
    return json(res, 404, { ok: false, error: "not_found" });
  }

  const stat = fs.statSync(filePath);
  res.statusCode = 200;
  res.setHeader("Content-Type", contentType);
  res.setHeader("Content-Length", String(stat.size));
  res.setHeader("Cache-Control", "private, max-age=0, must-revalidate");
  res.setHeader("X-Robots-Tag", "noarchive");

  if (req.method === "HEAD") {
    return res.end();
  }

  fs.createReadStream(filePath).pipe(res);
};
