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

function messageText(message) {
  const content = message?.content;
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((item) => (typeof item?.text === "string" ? item.text : ""))
      .join("\n");
  }
  return "";
}

function isLiveSpokenRequest(messages) {
  const systemText = (messages || [])
    .filter((message) => message?.role === "system")
    .map(messageText)
    .join("\n")
    .toLowerCase();
  return (
    systemText.includes("живом созвоне") ||
    systemText.includes("короткая реплика") ||
    systemText.includes("произнести вслух")
  );
}

function addLiveGuard(messages) {
  if (!isLiveSpokenRequest(messages)) {
    return messages;
  }
  const guard =
    "\n\nКРИТИЧНО ДЛЯ ЖИВОГО СОЗВОНА: начинай сразу с ответа по существу. " +
    "Не пиши служебные фразы о качестве связи или слышимости, например " +
    "«Да, слышно хорошо», «Вас слышно», «Я вас слышу». Не добавляй приветствие " +
    "или подтверждение ради вежливости, если оно не является частью ответа.";

  let applied = false;
  const result = (messages || []).map((message) => {
    if (!applied && message?.role === "system" && typeof message.content === "string") {
      applied = true;
      return { ...message, content: message.content + guard };
    }
    return message;
  });
  if (!applied) {
    result.unshift({ role: "system", content: guard.trim() });
  }
  return result;
}

function stripHearingFiller(content) {
  if (typeof content !== "string") {
    return content;
  }
  const original = content.trim();
  let cleaned = original;
  const patterns = [
    /^(?:да[,!.]?\s*)?(?:вас\s+)?слышно(?:\s+(?:хорошо|отлично|нормально))?[.!]?\s*/iu,
    /^(?:да[,!.]?\s*)?я\s+(?:вас\s+)?слышу(?:\s+(?:хорошо|отлично|нормально))?[.!]?\s*/iu,
  ];
  for (const pattern of patterns) {
    cleaned = cleaned.replace(pattern, "");
  }
  return cleaned.trim() || original;
}

function cleanLiveResponse(text, shouldClean) {
  if (!shouldClean) {
    return text;
  }
  try {
    const payload = JSON.parse(text);
    const choices = Array.isArray(payload?.choices) ? payload.choices : [];
    for (const choice of choices) {
      if (choice?.message && typeof choice.message.content === "string") {
        choice.message.content = stripHearingFiller(choice.message.content);
      }
    }
    return JSON.stringify(payload);
  } catch (_error) {
    return text;
  }
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

  const liveSpoken = isLiveSpokenRequest(incoming.messages);
  const requestedMax = Number(incoming.max_completion_tokens || 1000);
  const maxCompletionTokens = Number.isFinite(requestedMax)
    ? Math.max(128, Math.min(Math.trunc(requestedMax), 3000))
    : 1000;

  const payload = {
    ...incoming,
    messages: addLiveGuard(incoming.messages),
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
    const output = cleanLiveResponse(text, liveSpoken && !incoming.stream);
    res.status(upstream.status);
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    return res.send(output);
  } catch (_error) {
    return res.status(502).json({
      error: { message: "Managed AI service could not reach OpenAI" },
    });
  }
}
