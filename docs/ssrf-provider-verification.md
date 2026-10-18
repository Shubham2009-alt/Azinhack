# Remote-fetch SSRF verification

**Status: backend validation is implemented; provider-side DNS and redirect protections still require direct confirmation before arbitrary user-submitted URLs are treated as production-safe.**

## What the application enforces

- Accept only HTTP(S) URLs on ordinary web ports.
- Reject URL user-info/embedded credentials, non-global IP literals, legacy numeric IPv4 spellings, loopback/private/link-local addresses, and common local hostnames.
- Canonicalize URLs before calling TinyFish and reject provider results not tied to requested URLs.
- Discard a result whose reported final URL is unsafe.
- Treat fetched content as untrusted data, never as instructions.

These controls are defense in depth. Because TinyFish performs the remote request, post-fetch checks cannot prevent a request that the provider has already made.

## What the public provider statement confirms

TinyFish's [Fetch API security notes](https://www.tinyfish.ai/blog/production-grade-web-fetching-for-ai-agents) state that Fetch applies SSRF protections before execution, blocks private/reserved IP ranges, and denies cloud metadata endpoints. The public statement does **not** fully specify DNS-rebinding resistance or whether every redirect hop is resolved and revalidated immediately before connection.

## Required staging verification

Before enabling arbitrary remote fetching for production users:

1. Ask TinyFish support to confirm, in writing, how it protects against DNS rebinding and redirects to private/reserved targets, including every redirect hop and the actual connection address.
2. Use a provider-approved isolated test environment and a domain you control. Test a redirect chain and controlled DNS changes that attempt to resolve first to a public test address and then to a private/reserved address. Do not test against real cloud metadata services or unrelated internal networks.
3. Record request IDs, timestamps, and provider outcomes without storing access tokens, sensitive URLs, or page contents. Each private-target attempt must be blocked before connection; a final-URL rejection after fetching is not a pass.
4. Repeat after provider/network configuration changes. Keep the recorded result with the deployment review.

If provider-side behavior cannot be confirmed, use a fetcher with enforceable egress controls (including DNS resolution and redirect-hop checks) or disable arbitrary URL fetching. The current code and mocked CI tests do not prove those remote controls.

## Regression tests

The automated suite covers URL canonicalization and rejection of private IP literals/hostnames, malformed URL forms, restricted ports, unrequested provider results, duplicate results, and unsafe reported final URLs. Those tests validate the backend boundary only; they are not substitutes for the staging checks above.
