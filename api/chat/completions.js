import crypto from "node:crypto";

function sha256(value) {
  return crypto.createHash("sha256").update(value, "utf8").digest("hex");
}

function safeHexEqual(a, b) {
  if (!/^[a-f0-9]{64}$/i.test(a) || !/^[a-f0-9]{64}$/i.test(b)) {
    return false;
  }
  const left = Buffer.from(a, "hex");
  const right = Buffer.from(b, "hex");
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function isAllowedAccessCode(code) {
  const configured = (process.env.MANAGED_ACCESS_CODE_HASHES || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  if (!code || configured.length === 0) {
    return false;
  }
  const digest = sha256(code);
  return configured.some((allowed) => safeHexEqual(digest, allowed));
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");

  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: { message: "Method not allowed" } });
  }

  const openaiKey = (process.env.OPENAI_API_KEY || "").trim();
  if (!openaiKey) {
    return res.status(503).json({
      error: { message: "Managed AI service is not configured" },
    });
  }

  const auth = String(req.headers.authorization || "");
  const match = auth.match(/^Bearer\s+(.+)$/i);
  const accessCode = match ? match[1].trim() : "";
  if (!isAllowedAccessCode(accessCode)) {
    return res.status(401).json({
      error: { message: "Invalid or expired 1C Analitik access code" },
    });
  }

  const incoming = req.body && typeof req.body === "object" ? req.body : {};
  if (!Array.isArray(incoming.messages) || incoming.messages.length === 0) {
    return res.status(400).json({ error: { message: "messages are required" } });
  }

  const requestedMax = Number(incoming.max_completion_tokens || 1000);
  const maxCompletionTokens = Number.isFinite(requestedMax)
    ? Math.max(128, Math.min(Math.trunc(requestedMax), 3000))
    : 1000;

  const payload = {
    ...incoming,
    model: process.env.OPENAI_MODEL || "gpt-5.6-sol",
    reasoning_effort: "none",
    max_completion_tokens: maxCompletionTokens,
  };

  try {
    const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${openaiKey}`,
      },
      body: JSON.stringify(payload),
    });

    const text = await upstream.text();
    res.status(upstream.status);
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    return res.send(text);
  } catch (_error) {
    return res.status(502).json({
      error: { message: "Managed AI service could not reach OpenAI" },
    });
  }
}
