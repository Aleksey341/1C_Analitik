import crypto from "node:crypto";

const PROJECT_NAME = process.env.VERCEL_PROJECT_NAME || "1canalitik";
const TEAM_SLUG = process.env.VERCEL_TEAM_SLUG || "alex-ko1";
const GITHUB_REPO_ID = Number(process.env.GITHUB_REPO_ID || "1360995769");
const GITHUB_BRANCH = process.env.GITHUB_BRANCH || "main";
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

function activeHashesFromEnv() {
  return String(process.env.MANAGED_ACCESS_CODE_HASHES || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter((item) => HASH_RE.test(item));
}

function legacyRegistry() {
  return activeHashesFromEnv().map((hash, index) => ({
    id: `legacy-${index + 1}`,
    name: `Существующий код ${index + 1}`,
    hash,
    active: true,
    createdAt: null,
  }));
}

function parseRegistry(value) {
  try {
    const parsed = JSON.parse(String(value || ""));
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((item) => item && HASH_RE.test(String(item.hash || "")))
      .map((item) => ({
        id: String(item.id || crypto.randomUUID()),
        name: String(item.name || "Без имени").slice(0, 120),
        hash: String(item.hash).toLowerCase(),
        active: item.active !== false,
        createdAt: item.createdAt ? String(item.createdAt) : null,
      }));
  } catch (_error) {
    return [];
  }
}

function currentRegistry() {
  const saved = parseRegistry(process.env.MANAGED_USERS_JSON);
  return saved.length ? saved : legacyRegistry();
}

function normalizeClientRegistry(registry) {
  if (!Array.isArray(registry)) {
    return currentRegistry();
  }
  const normalized = registry
    .filter((item) => item && HASH_RE.test(String(item.hash || "")))
    .slice(0, 100)
    .map((item) => ({
      id: String(item.id || crypto.randomUUID()),
      name: String(item.name || "Без имени").slice(0, 120),
      hash: String(item.hash).toLowerCase(),
      active: item.active !== false,
      createdAt: item.createdAt ? String(item.createdAt) : null,
    }));
  return normalized.length ? normalized : currentRegistry();
}

function makeUserCode() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.randomBytes(16);
  let raw = "";
  for (let i = 0; i < 16; i += 1) {
    raw += alphabet[bytes[i] % alphabet.length];
  }
  return `1CA-${raw.slice(0, 4)}-${raw.slice(4, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}`;
}

function teamQuery() {
  const teamId = String(process.env.VERCEL_TEAM_ID || "").trim();
  if (teamId) {
    return `teamId=${encodeURIComponent(teamId)}`;
  }
  return `slug=${encodeURIComponent(TEAM_SLUG)}`;
}

async function vercelRequest(url, options = {}) {
  const token = String(process.env.VERCEL_API_TOKEN || "").trim();
  if (!token) {
    throw new Error("VERCEL_API_TOKEN is not configured");
  }
  const response = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_error) {
    data = { raw: text };
  }
  if (!response.ok) {
    const message = data?.error?.message || data?.message || text || `HTTP ${response.status}`;
    throw new Error(`Vercel API: ${message}`);
  }
  return data;
}

async function persistRegistry(registry) {
  const activeHashes = registry.filter((user) => user.active).map((user) => user.hash);
  const url = `https://api.vercel.com/v10/projects/${encodeURIComponent(PROJECT_NAME)}/env?upsert=true&${teamQuery()}`;
  await vercelRequest(url, {
    method: "POST",
    body: JSON.stringify([
      {
        key: "MANAGED_USERS_JSON",
        value: JSON.stringify(registry),
        type: "encrypted",
        target: ["production"],
      },
      {
        key: "MANAGED_ACCESS_CODE_HASHES",
        value: activeHashes.join(","),
        type: "encrypted",
        target: ["production"],
      },
    ]),
  });
}

async function triggerProductionDeployment() {
  const url = `https://api.vercel.com/v13/deployments?forceNew=1&${teamQuery()}`;
  return vercelRequest(url, {
    method: "POST",
    body: JSON.stringify({
      name: PROJECT_NAME,
      project: PROJECT_NAME,
      target: "production",
      gitSource: {
        type: "github",
        repoId: GITHUB_REPO_ID,
        ref: GITHUB_BRANCH,
      },
    }),
  });
}

function publicUsers(registry) {
  return registry.map((user) => ({
    ...user,
    fingerprint: user.hash.slice(0, 8),
  }));
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Content-Type-Options", "nosniff");

  if (!process.env.ADMIN_ACCESS_CODE_HASH) {
    return res.status(503).json({ error: "Админ-панель ещё не настроена" });
  }
  if (!adminAuthorized(req)) {
    return res.status(401).json({ error: "Неверный код администратора" });
  }

  if (req.method === "GET") {
    const registry = currentRegistry();
    return res.status(200).json({
      ok: true,
      users: publicUsers(registry),
      registry,
      automationReady: Boolean(process.env.VERCEL_API_TOKEN),
    });
  }

  if (req.method !== "POST") {
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  if (!process.env.VERCEL_API_TOKEN) {
    return res.status(503).json({ error: "VERCEL_API_TOKEN не настроен" });
  }

  const body = req.body && typeof req.body === "object" ? req.body : {};
  const action = String(body.action || "");
  let registry = normalizeClientRegistry(body.registry);
  let accessCode = null;

  if (action === "create") {
    const name = String(body.name || "").trim().slice(0, 120);
    if (!name) {
      return res.status(400).json({ error: "Укажите имя пользователя" });
    }
    accessCode = makeUserCode();
    registry.push({
      id: crypto.randomUUID(),
      name,
      hash: sha256(accessCode),
      active: true,
      createdAt: new Date().toISOString(),
    });
  } else if (action === "toggle") {
    const id = String(body.id || "");
    const user = registry.find((item) => item.id === id);
    if (!user) {
      return res.status(404).json({ error: "Пользователь не найден" });
    }
    user.active = !user.active;
  } else if (action === "delete") {
    const id = String(body.id || "");
    const before = registry.length;
    registry = registry.filter((item) => item.id !== id);
    if (registry.length === before) {
      return res.status(404).json({ error: "Пользователь не найден" });
    }
  } else {
    return res.status(400).json({ error: "Неизвестное действие" });
  }

  try {
    await persistRegistry(registry);
    const deployment = await triggerProductionDeployment();
    return res.status(200).json({
      ok: true,
      accessCode,
      users: publicUsers(registry),
      registry,
      deployment: {
        id: deployment?.id || deployment?.uid || null,
        url: deployment?.url || null,
        readyState: deployment?.readyState || deployment?.state || null,
      },
      note: "Изменения сохранены. Новый Production deployment применит их после сборки.",
    });
  } catch (error) {
    return res.status(502).json({
      error: String(error?.message || error),
      users: publicUsers(registry),
      registry,
      accessCode,
    });
  }
}
