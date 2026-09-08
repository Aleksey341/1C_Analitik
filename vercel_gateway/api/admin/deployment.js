import crypto from "node:crypto";

const TEAM_SLUG = process.env.VERCEL_TEAM_SLUG || "alex-ko1";
const HASH_RE = /^[a-f0-9]{64}$/i;

function sha256(value) {
  return crypto.createHash("sha256").update(value, "utf8").digest("hex");
}

function safeHexEqual(a, b) {
  if (!HASH_RE.test(a || "") || !HASH_RE.test(b || "")) {
    return false;
  }
  const left = Buffer.from(a, "hex");
  const right = Buffer.from(b, "hex");
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function adminAuthorized(req) {
  const expected = String(process.env.ADMIN_ACCESS_CODE_HASH || "").trim().toLowerCase();
  if (!HASH_RE.test(expected)) {
    return false;
  }
  const auth = String(req.headers.authorization || "");
  const match = auth.match(/^Bearer\s+(.+)$/i);
  const code = match ? match[1].trim() : "";
  return Boolean(code) && safeHexEqual(sha256(code), expected);
}

function teamQuery() {
  const teamId = String(process.env.VERCEL_TEAM_ID || "").trim();
  if (teamId) {
    return `teamId=${encodeURIComponent(teamId)}`;
  }
  return `slug=${encodeURIComponent(TEAM_SLUG)}`;
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Content-Type-Options", "nosniff");

  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed" });
  }
  if (!adminAuthorized(req)) {
    return res.status(401).json({ error: "Неверный код администратора" });
  }

  const token = String(process.env.VERCEL_API_TOKEN || "").trim();
  if (!token) {
    return res.status(503).json({ error: "VERCEL_API_TOKEN не настроен" });
  }

  const deploymentId = String(req.query?.id || "").trim();
  if (!deploymentId) {
    return res.status(400).json({ error: "Не указан deployment id" });
  }

  const url = `https://api.vercel.com/v13/deployments/${encodeURIComponent(deploymentId)}?${teamQuery()}`;
  try {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data?.error?.message || data?.message || `HTTP ${response.status}`;
      return res.status(502).json({ error: `Vercel API: ${message}` });
    }
    const readyState = data?.readyState || data?.state || null;
    return res.status(200).json({
      ok: true,
      id: data?.id || data?.uid || deploymentId,
      url: data?.url || null,
      readyState,
      ready: String(readyState || "").toUpperCase() === "READY",
    });
  } catch (error) {
    return res.status(502).json({ error: String(error?.message || error) });
  }
}
