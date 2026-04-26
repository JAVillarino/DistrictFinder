const MAX_FIELD_LENGTH = 2000;
const WINDOW_MS = 10 * 60 * 1000;
const MAX_FLAG_REQUESTS = 5;

function clamp(value, max = MAX_FIELD_LENGTH) {
  return String(value || "").slice(0, max);
}

function escapeHtml(value) {
  return clamp(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

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
  const store = globalThis.__districtFlagRateLimit || new Map();
  globalThis.__districtFlagRateLimit = store;

  const recent = (store.get(ip) || []).filter(timestamp => now - timestamp < WINDOW_MS);
  if (recent.length >= MAX_FLAG_REQUESTS) {
    store.set(ip, recent);
    return false;
  }
  recent.push(now);
  store.set(ip, recent);
  return true;
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return json(res, 405, { ok: false, error: "method_not_allowed" });
  }

  if (!checkRateLimit(req)) {
    res.setHeader("Retry-After", String(Math.ceil(WINDOW_MS / 1000)));
    return json(res, 429, { ok: false, error: "rate_limited" });
  }

  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    chunks.push(buffer);
    size += buffer.length;
    if (size > 32_000) {
      return json(res, 413, { ok: false, error: "payload_too_large" });
    }
  }

  let body;
  try {
    body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    return json(res, 400, { ok: false, error: "invalid_json" });
  }

  if (body.website) {
    return json(res, 200, { ok: true });
  }

  const districtId = clamp(body.districtId, 64);
  const districtName = clamp(body.districtName, 240);
  if (!districtId || !districtName) {
    return json(res, 400, { ok: false, error: "missing_district" });
  }

  const resendKey = process.env.RESEND_API_KEY;
  const to = process.env.FLAG_TO_EMAIL;
  const from = process.env.FLAG_FROM_EMAIL || "District Stream Flags <onboarding@resend.dev>";

  if (!resendKey || !to) {
    console.warn("Flag received but email environment is not configured", {
      districtId,
      districtName,
    });
    return json(res, 202, { ok: true, queued: false });
  }

  const issueType = clamp(body.issueType, 120) || "Reported issue";
  const pageUrl = clamp(body.pageUrl, 500);
  const videoUrl = clamp(body.videoUrl, 500);
  const websiteUrl = clamp(body.websiteUrl, 500);
  const platform = clamp(body.platform, 120);
  const status = clamp(body.status, 120);
  const notes = clamp(body.notes, 1000);
  const userAgent = clamp(req.headers["user-agent"], 500);

  const subject = `District stream issue: ${districtName}`;
  const html = `
    <h2>District stream issue</h2>
    <p><strong>District:</strong> ${escapeHtml(districtName)} (${escapeHtml(districtId)})</p>
    <p><strong>Issue:</strong> ${escapeHtml(issueType)}</p>
    <p><strong>Platform:</strong> ${escapeHtml(platform || "N/A")}</p>
    <p><strong>Status:</strong> ${escapeHtml(status || "N/A")}</p>
    <p><strong>Video URL:</strong> ${videoUrl ? `<a href="${escapeHtml(videoUrl)}">${escapeHtml(videoUrl)}</a>` : "N/A"}</p>
    <p><strong>Website URL:</strong> ${websiteUrl ? `<a href="${escapeHtml(websiteUrl)}">${escapeHtml(websiteUrl)}</a>` : "N/A"}</p>
    <p><strong>App page:</strong> ${pageUrl ? `<a href="${escapeHtml(pageUrl)}">${escapeHtml(pageUrl)}</a>` : "N/A"}</p>
    <p><strong>Reporter note:</strong><br>${escapeHtml(notes || "No note provided.")}</p>
    <p><strong>User agent:</strong><br>${escapeHtml(userAgent)}</p>
  `;

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${resendKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from,
      to,
      subject,
      html,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    console.error("Flag email failed", response.status, text.slice(0, 500));
    return json(res, 502, { ok: false, error: "email_failed" });
  }

  return json(res, 200, { ok: true });
};
