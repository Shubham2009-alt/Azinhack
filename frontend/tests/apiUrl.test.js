import test from "node:test";
import assert from "node:assert/strict";
import { resolveApiUrl } from "../src/apiUrl.js";

test("keeps same-origin API paths when no API base URL is configured", () => {
  assert.equal(resolveApiUrl("/api/research-runs"), "/api/research-runs");
});

test("joins a separately hosted API base URL without duplicate slashes", () => {
  assert.equal(
    resolveApiUrl("/api/research-runs", "https://api.example.com/"),
    "https://api.example.com/api/research-runs",
  );
});

test("does not rewrite non-API paths or URL objects", () => {
  assert.equal(resolveApiUrl("/assets/logo.svg", "https://api.example.com"), "/assets/logo.svg");
  const url = new URL("https://example.com/api/research-runs");
  assert.equal(resolveApiUrl(url, "https://api.example.com"), url);
});
