/** Resolve same-origin API paths for deployments with a separately hosted backend. */
export function resolveApiUrl(input, baseUrl = "") {
  if (typeof input !== "string" || !input.startsWith("/api/")) return input;
  const base = String(baseUrl).trim().replace(/\/+$/, "");
  return base ? `${base}${input}` : input;
}
