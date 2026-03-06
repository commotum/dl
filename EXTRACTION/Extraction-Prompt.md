# Math Academy Topic Capture (Hydrated HTML + Screenshots)

Use this prompt in a fresh agent session.

## EXTRACTION Folder Overview

You are working inside `./EXTRACTION` with these key assets:

- `./Topics.csv`
  - Master input list of topics to capture.
  - Columns: `topic-id`, `name`, `url`.
  - `url` is the topic page to open.

- `./Topic-JSON/`
  - Existing JSON manifests from earlier, non-hydrated or partially hydrated extraction work.
  - Treat these as optional reference context only (for selector hints or structure hints).
  - Do **not** generate new manifests in this pass.

- `./Extraction-Prompt.md`
  - This task brief.

## Objective

For each topic in `Topics.csv`, capture only these artifacts:

1. Hydrated HTML of the topic page.
2. Screenshot of the sidebar/Table of Contents.
3. Ordered screenshots of all lesson content items in sequence (steps, questions, and any other lesson blocks).

No manifest generation is required in this run.

## Tooling

Use **Playwright (Python)**.

Why Playwright:

- Reliable post-render DOM capture for hydrated content.
- Stable element-level screenshot support.
- Good control over waits/timeouts for dynamic pages.

## Selector Strategy (Default + Fallback)

Default behavior per topic:

1. Load selector/order hints from `./Topic-JSON/<topic-id>.json`.
2. Use those selectors first for ToC and lesson item targeting.

Fallback behavior:

- If JSON is missing, or any stored selector fails, switch to structural targeting from the live hydrated DOM.
- Structural targeting should prioritize:
  - `#sidebar` for ToC
  - ordered children/items under `#lessonContent` for lesson sequence capture
- Continue capture instead of failing the topic when fallback is needed.

## Per-Topic Output Layout

For each topic ID `<topic-id>`, create a folder:

- `./<topic-id>/`

Save outputs in that folder:

- Hydrated HTML: `./<topic-id>/<topic-id>.html`
- ToC screenshot: `./<topic-id>/00-TOC.png`
- Lesson item screenshots in strict visual/order sequence:
  - `./<topic-id>/01-...png`
  - `./<topic-id>/02-...png`
  - etc.

Use zero-padded sequence numbers and preserve true order from the lesson content stream.

## Page Structure Background

Common structure on topic pages:

- Sidebar/ToC region: `#sidebar`
- Section links: `#sectionLinks .sectionLink`
- Main lesson stream: `#lessonContent`
- Lesson blocks typically include `step-*` and `question-*` containers, but capture should include **all** ordered lesson items shown in the content stream.

## Capture Requirements

- Save HTML after hydration, not raw pre-render source.
- Capture exactly one ToC screenshot per topic.
- Capture all lesson content items in order, including non-step/non-question blocks when present.
- Use JSON-provided selectors first; fall back to structural DOM targeting when selectors are invalid.
- Do not submit answers or change course progress.

## Completion Criteria Per Topic

A topic is complete when:

1. Topic folder `./<topic-id>/` exists.
2. `./<topic-id>/<topic-id>.html` exists and is non-empty.
3. `./<topic-id>/00-TOC.png` exists and is non-empty.
4. Ordered lesson screenshots exist and cover the full lesson stream.
