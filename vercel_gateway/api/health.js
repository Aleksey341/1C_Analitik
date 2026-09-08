export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }

  const hasOpenAI = Boolean((process.env.OPENAI_API_KEY || "").trim());
  const hasAccessCodes = Boolean(
    (process.env.MANAGED_ACCESS_CODE_HASHES || "").trim()
  );

  return res.status(200).json({
    ok: true,
    service: "1C Analitik managed gateway",
    configured: hasOpenAI && hasAccessCodes,
  });
}
