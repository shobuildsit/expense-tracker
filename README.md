# Expense Tracker

Multi-source expense automation: transactions from email and SMS/iMessage are parsed
by an LLM, checked against a stable event ID to avoid duplicate rows, and logged to a
Google Sheet — with known merchants classified automatically and a one-tap LINE
prompt the first time a new merchant shows up.

*(日本語版は [README_ja.md](README_ja.md) をご覧ください)*

## Overview

Expense Tracker watches multiple input channels for payment notifications and turns
each one into a normalized row in a shared Google Sheet:

- **Gmail** — Wise payment confirmation emails
- **macOS Messages / SMS** — bank SMS notifications (e.g. Bank of Georgia), forwarded
  via a small local Python poller
- **Make.com Custom Webhook** — the integration point between the local poller and
  the parsing/logging automation

The design is intentionally source-agnostic: adding a new channel (another bank, a
CSV import, a different chat platform) means adding a new entry point, not rebuilding
the parsing, deduplication, or category-selection logic. See
[`docs/architecture.md`](docs/architecture.md) for how the pieces fit together.

## Features

- Gmail transaction ingestion (Wise payment emails)
- SMS/iMessage transaction ingestion via a local macOS Messages watcher
- Make.com webhook integration for non-email sources
- OpenAI-based transaction parsing (merchant, amount, currency, category)
- Event-level duplicate prevention — each transaction carries a stable `Source Event
  ID` (Gmail message ID / Messages GUID), checked before logging to avoid duplicate
  rows during normal retries, redelivery, or a manual re-run
- Known-merchant classification — separately from the above, merchants that already
  have a logged transaction get their category reused automatically; genuinely new
  merchants trigger a one-tap category prompt over LINE
- Google Sheets as the single source of truth
- Read-only access to the local Messages database; only the sender, message text, and
  message GUID are forwarded to the webhook. The watcher also reads other local
  fields it needs for filtering (e.g. `is_from_me`) and keeps the last processed
  `ROWID` on disk as state — see [Privacy / data handling](#privacy--data-handling)

## Repository layout

```text
expense-tracker/
├── messages_watcher/      # Local Python poller: macOS Messages → Make webhook
├── make/
│   ├── examples/          # Sanitized Make Blueprint exports (safe to inspect/import)
│   └── *.blueprint.json   # Real blueprints with your own credentials (gitignored)
├── docs/
│   ├── architecture.md
│   └── setup.md
├── samples/
│   └── sample_bog_sms.txt # Dummy SMS payload for testing
└── README.md
```

## Getting started

See [`docs/setup.md`](docs/setup.md) for the full setup guide (Google Sheets layout,
importing the Make blueprints, configuring `messages_watcher`, and an end-to-end
test using `curl`).

## Security

- The local Messages database (`chat.db`) is opened **read-only**
  (`mode=ro`); `messages_watcher` never writes to it.
- Webhook URLs, API keys, and connection details live in `.env` files that are never
  committed — see `messages_watcher/.env.example` for the expected shape.
- Real financial data, spreadsheet exports, and the live Make Blueprints (which
  contain your actual webhook/connection IDs) are excluded from this repository.
  `make/examples/` ships sanitized versions with all IDs and tokens replaced by
  placeholders, for reference only.
- No personal data (email addresses, phone numbers, real transactions) is included in
  this repository.

## Privacy / data handling

This project moves real transaction data (merchant names, amounts, sometimes a
person's name for P2P Wise payments) through several third-party services. Here is
what actually happens to it, described plainly rather than as a blanket privacy
promise:

- **OpenAI** receives the full email body (Wise) or SMS text (BOG) as the parsing
  prompt's input. The shipped blueprints set the OpenAI module's `store` and
  `createConversation` options to `false`, so this project does not opt into
  OpenAI retaining the request as a stored Response object or a persistent
  conversation thread. This does not change OpenAI's own baseline API data handling
  (e.g. short-term retention for abuse monitoring), which is outside this project's
  control — see OpenAI's own API data usage policy if you need specifics.
- **Make.com** keeps a scenario execution history (inputs/outputs of every module,
  including the raw email/SMS text and the parsed transaction fields) for a period
  that depends on your Make plan. This project does not clear or disable that
  history — treat it as a place real transaction data can persist.
- **Google Sheets** is the permanent store: each logged transaction (`ID`, `Date`,
  amounts, `Merchant`, `Category`, `Status`, `Source Event ID`) stays in your
  spreadsheet until you delete it yourself.
- **LINE** notifications sent to you contain the merchant name and amount for
  merchants that need a category pick; these appear in your own chat history with
  your LINE bot and are not sent to anyone else.
- **`messages_watcher` locally** reads more from `chat.db` than it forwards: besides
  the sender, message text, and GUID sent to the webhook, it also reads fields like
  `is_from_me` to apply the sender/filter conditions, and keeps the last processed
  `ROWID` in a local state file (`messages_watcher/state/`, gitignored) so it knows
  where to resume. None of that local-only data is sent anywhere.

## Scope / non-goals

This is a personal automation project, not a packaged product. It currently assumes:

- A single user, a single Google Sheet, and a single LINE recipient.
- Manual start/stop of `messages_watcher` (no daemon/launchd setup included).
- One bank's SMS format (Bank of Georgia) as the SMS example; adapting the OpenAI
  prompt for another bank's format is straightforward but not automated.

## License

[MIT](LICENSE)
