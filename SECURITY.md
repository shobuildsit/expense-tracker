# Security and privacy boundary

## Public repository contents

This repository is intended to contain only sanitized implementation artifacts:

- placeholder-based Make Blueprint exports under `make/examples/`;
- source code and configuration examples without credentials;
- synthetic sample data; and
- documentation that does not expose account, workspace, webhook, spreadsheet, or customer identifiers.

The live Make Blueprints, `.env` files, runtime state, spreadsheet exports, and internal reports are excluded by `.gitignore`. Always review the exact staged file list before publishing; `.gitignore` does not protect files uploaded through GitHub's drag-and-drop interface.

Run the offline publication-safety validator before every public update:

```bash
python3 tests/validate_public_repo.py
```

The validator is a defense-in-depth check, not a guarantee that every possible secret format will be detected.

## Runtime data flow

- **Wise / OpenAI:** the Wise email subject and body are sent to OpenAI for structured extraction. The customer email address is not required by the extraction schema. The published module sets `store: false` and `createConversation: false`.
- **BOG SMS:** BOG SMS text is parsed with Make text functions and is not sent to OpenAI.
- **Make.com:** scenario execution history can contain raw input and parsed transaction data. Retention depends on the operator's Make plan and settings.
- **Google Sheets:** this is the durable transaction store until the operator deletes data.
- **LINE:** new-merchant prompts include merchant and amount information. Parse-failure notifications can include the raw BOG message.
- **Local watcher:** `messages_watcher` opens the macOS Messages database with SQLite `mode=ro`. It forwards sender, message text, and GUID. Filtering fields and the last processed ROWID remain local.

## Credentials and identifiers

Never commit:

- Make webhook URLs or connection IDs;
- Google Spreadsheet or Drive IDs from a live account;
- LINE channel access tokens or user IDs;
- OpenAI API keys;
- `.env` files, local watcher state, real financial data, or production Blueprint exports.

Use the placeholder values already present in the sanitized examples and reconnect services after import.

## Operational safeguards

- Test with synthetic data and keep imported scenarios inactive until every route and destination is reviewed.
- Use `DRY_RUN=true` when validating the local watcher without calling the Make webhook.
- Keep `INCLUDE_FROM_ME=false` for normal received-message operation.
- Treat parse-failure alerts as human-review requests; do not turn missing values into guessed financial records.
- Review Make execution-history retention and access control before processing real transactions.

## Reporting a security issue

Do not open a public issue containing credentials, webhook URLs, financial data, or account identifiers. Revoke or rotate exposed credentials first, remove sensitive values from any report, and use a private contact channel supplied by the repository owner if one is made available.
