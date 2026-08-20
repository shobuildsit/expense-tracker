# Limitations and non-goals

Expense Tracker is a personal automation reference, not a packaged product and not a production-readiness claim.

## Reliability

- Source Event ID handling uses a check-then-insert pattern. It prevents normal retry and redelivery duplicates, but does not provide atomic uniqueness if the same event is processed simultaneously.
- Missing Source Event IDs are dropped rather than logged without an identity. Operational review is required if a transaction appears missing.
- The current public evidence does not include a live replay of the same Gmail message ID or Messages GUID.
- The Wise live check used manual `Run once`; scheduled Gmail polling remains an evidence gap.
- The current BOG deterministic parser does not have a published final clean end-to-end matrix across all success, failure, and replay routes.
- Make, Gmail, Google Sheets, LINE, OpenAI, and local network failures require operational handling outside this repository.

## Parsing and currency

- Wise extraction relies on an LLM for free-form email text. A nullable schema and fail-closed route reduce guessing risk but do not prove perfect extraction.
- BOG parsing supports one documented fixed SMS format. Bank wording or layout changes can break the deterministic parser.
- BOG JPY conversion uses a fixed `GEL × 62` rule in the shipped Blueprint. It does not track market exchange rates automatically.
- The `attributedBody` fallback in `messages_watcher` is a best-effort ASCII extraction, not a complete Apple typedstream parser. Non-ASCII content can be incomplete when the normal `text` column is empty.

## Operating model

- The design assumes one user, one Google Sheet, and one LINE recipient.
- `messages_watcher` is manually started and stopped; launchd or another service manager is not included.
- A macOS host with Messages synchronization and Full Disk Access for the chosen terminal is required for the SMS path.
- The setup guide requires the operator to create and configure external service connections. Sanitized Blueprints cannot be imported and run without that work.

## Data and privacy

- Transaction details pass through third-party services and may remain in Make execution history, Google Sheets, and LINE chat history.
- `store: false` and `createConversation: false` prevent opting into stored OpenAI Response objects or persistent conversations, but they do not redefine OpenAI's platform-level data handling.
- This repository contains sanitized artifacts only; that does not automatically make a separately exported live Blueprint safe to publish.

## Evidence and commercial claims

- The repository contains no measured time savings, cost savings, accuracy rate, uptime, throughput, or ROI study.
- It does not claim strict exactly-once processing, complete failure recovery, multi-user tenancy, regulatory compliance, or production readiness.
- See [`evidence.md`](evidence.md) for the observed live scope and explicit `EVIDENCE_GAP` items.
