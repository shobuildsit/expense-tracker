# Evidence and verification boundary

This document separates what can be reproduced from the public checkout, what was observed in controlled live runs, and what remains unverified. It intentionally avoids production-readiness and ROI claims.

## Reproducible from this repository

Run:

```bash
python3 tests/validate_public_repo.py
```

The validator performs offline checks only. It verifies that:

- all three sanitized Make Blueprints are valid JSON with the expected module counts;
- the Wise path retains its OpenAI safety settings and the BOG path contains no OpenAI module;
- account-specific values use public placeholders;
- tracked public text does not contain common secret-shaped values or non-example email addresses;
- the Messages watcher is syntactically valid; and
- the required README, security, evidence, limitation, setup, and architecture files exist.

Passing this validator proves the structure of the published artifacts. It does not execute Make, Gmail, Google Sheets, LINE, OpenAI, or the macOS Messages database.

## Separately observed live behavior

The following checks were performed against connected services with synthetic data. The underlying operational logs and screenshots are not published because they can contain account and workspace identifiers.

### Wise new-merchant path — observed 2026-08-14

- Trigger method: manual Make `Run once`, not natural scheduled Gmail polling.
- Input: one synthetic Wise-style email.
- Make result: one successful execution with 7 operations, matching the new-merchant route.
- User-facing result: one `Pending` Google Sheets row and one LINE category prompt.
- Values: merchant, GEL, and JPY matched the synthetic input.
- Duplicate side effects in that run: none observed.

This run did not replay the same Gmail message ID, so it does not prove live deduplication.

### LINE category-update path — observed 2026-08-14

- Trigger method: one LINE postback; Make recorded one automatic webhook execution.
- Make result: one successful execution with 5 operations, matching the no-pending-items completion route.
- Google Sheets result: one target row changed from `Pending` to `Done`; the selected category was written; other fields and other rows were unchanged.
- LINE result: one completion notification.
- Duplicate notifications or errors: none observed in that run.

This run did not test double taps or webhook replay.

### BOG English-format recovery — observed 2026-08-21

- Trigger method: four previously unprocessed macOS Messages events were replayed one at a time with their original GUIDs after the Make scenario was restored.
- Parser input format: the first line used `Purchase: GEL...`; the parser was updated to accept that label while retaining the existing Georgian payment label.
- Make result: four successful executions with 8 operations each.
- Google Sheets result: four `Done` rows were added, each with a Source Event ID; the total row count increased by exactly four.
- Duplicate check: one of the GUIDs was deliberately replayed again. Make stopped it after the Source Event ID lookup with 2 operations, and no second row was added.
- Final state: no duplicate Source Event IDs, no DLQ items, and the BOG scenario was active and valid.

The backfilled rows use the processing date because the scenario maps `Date` from `now`; their original SMS receipt dates remain operational evidence rather than a separate sheet column.

## Evidence gaps

- **EVIDENCE_GAP — remaining BOG routes:** the English-format known-merchant and duplicate-GUID paths were observed live, but the Georgian format, invalid extraction, and new-merchant/LINE paths were not re-run in the 2026-08-21 recovery.
- **EVIDENCE_GAP — scheduled Wise trigger:** the recorded Wise run used manual `Run once`; natural scheduled Gmail polling was not verified in that check.
- **EVIDENCE_GAP — Gmail duplicate replay:** a Messages GUID replay was observed and stopped, but the same Gmail message ID has not been deliberately replayed live.
- **EVIDENCE_GAP — concurrent execution:** the check-then-insert design is not an atomic uniqueness guarantee and has not been load-tested for simultaneous duplicate events.
- **EVIDENCE_GAP — watcher regression suite:** the public validator checks Python syntax and static safety properties; the watcher has no automated unit or macOS integration suite in this repository.
- **EVIDENCE_GAP — public UI evidence:** no account-redacted Make, Sheets, or LINE screenshots are currently published.

These gaps are tracked as limitations, not converted into inferred success claims.
