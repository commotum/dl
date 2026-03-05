# Principles of Practical Download Tooling

This repo is a personal workspace for three small tools:

- `cookiekit`: get cookies out of a logged-in browser and write `cookies.txt`
- `requestkit`: make requests with sane browser-like session behavior
- `downloadkit`: turn a URL into a correct file on disk

These are principles of practical download tooling for logged-in web workflows, not principles of general web crawling.

## The point

Most download problems are not one problem.

They are usually three different problems that get tangled together:

- finding the authenticated browser state you already have
- making requests that survive real sites
- downloading files without corrupting, truncating, or misclassifying them

This repo keeps those concerns separate on purpose.

## Principles

### 1. Prefer real browser state over scripted login

If the user is already logged in, use that.

That is usually more reliable than:

- reimplementing login flows
- storing usernames and passwords
- chasing MFA and challenge pages

This is why `cookiekit` exists.

### 2. Separate cookies, requests, and downloads

Cookie extraction, request/session behavior, and file transfer are different concerns with different failure modes.

They should not live in one giant kitchen-sink library unless that complexity is actually paying for itself.

The intended split here is:

- `cookiekit` for browser cookies
- `requestkit` for sessions and request behavior
- `downloadkit` for robust file transfer

### 3. Optimize for the real failure modes

Naive tools usually fail because of ordinary operational problems:

- wrong browser profile
- stale or missing cookies
- bad `Referer` or headers
- `429` responses
- challenge pages returned as HTML
- expired tokenized media URLs
- interrupted downloads

The toolkit should make those failure modes explicit and manageable.

### 4. Keep the core generic and the hacks local

There is no universal anti-detection trick that works everywhere.

The reusable core is things like:

- browser-like headers
- pacing and retries
- cookie loading
- challenge detection
- fallback URLs
- resume support

If a site needs weird reverse-engineered behavior, that should live in site-specific code, not in the shared core.

### 5. Small CLIs, composable libraries

Each package should be usable in two ways:

- as a small CLI with obvious flags
- as a library with a narrow surface area

The CLI should be the shortest path for a human or an AI agent. The library should exist so tools can be composed without shelling out.

### 6. Be explicit instead of magical

Good defaults matter, but hidden behavior should be limited.

Prefer:

- explicit profile selection
- explicit domain scoping
- visible retry and sleep settings
- visible output paths
- inspectable JSON or text summaries

The operator should be able to tell what happened without reverse-engineering the tool.

### 7. Redact secrets and preserve evidence

Debugging network problems is necessary. Leaking credentials is not.

Diagnostics should:

- allow request/response dumps
- redact cookies and auth headers
- preserve enough evidence to explain failures

### 8. Personal tools first

This repo is for personal use, not for building a maximal framework.

That means:

- fewer abstractions
- less ceremony
- no speculative generalization
- only enough packaging structure to keep the tools clean

If a feature is not helping real workflows, it should probably not exist.

## Workspace map

- `cookiekit/`: cookie extraction package
- `requestkit/`: request/session package scaffold
- `downloadkit/`: download package scaffold
- `gallery-dl/`: reference codebase used for comparison and idea extraction
- `building-clis-uv-summary.md`: notes on packaging small CLIs with `uv`

## Current status

- `cookiekit` is already usable
- `requestkit` has a working v1 core with `get` and `dump`, browser-like session setup, retries, pacing, challenge detection, cookies.txt loading, and redacted diagnostics
- `downloadkit` is scaffolded but not implemented

Package-specific usage and implementation details belong in each package README, not in this root document.

## Related Docs

- Package README: [`cookiekit/README.md`](cookiekit/README.md)
- `uv` tooling summary: [`building-clis-uv-summary.md`](building-clis-uv-summary.md)
- V1 feature inventory: [`V1/cookie-features.md`](V1/cookie-features.md)
- V1 roadmap: [`V1/todo.md`](V1/todo.md)
- Release workflow: [`cookiekit/docs/release.md`](cookiekit/docs/release.md)
