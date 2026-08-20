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

## Evidence gaps

- **EVIDENCE_GAP — current BOG deterministic parser:** the published structure and fail-closed routes are statically validated, but a final clean end-to-end run of the current deterministic parser across valid, invalid, known-merchant, new-merchant, and duplicate-GUID cases is not published or claimed here.
- **EVIDENCE_GAP — scheduled Wise trigger:** the recorded Wise run used manual `Run once`; natural scheduled Gmail polling was not verified in that check.
- **EVIDENCE_GAP — live duplicate replay:** Source Event ID filters are present, but the current public evidence does not include a deliberate replay of the same Gmail message ID or Messages GUID.
- **EVIDENCE_GAP — concurrent execution:** the check-then-insert design is not an atomic uniqueness guarantee and has not been load-tested for simultaneous duplicate events.
- **EVIDENCE_GAP — watcher regression suite:** the public validator checks Python syntax and static safety properties; the watcher has no automated unit or macOS integration suite in this repository.
- **EVIDENCE_GAP — public UI evidence:** no account-redacted Make, Sheets, or LINE screenshots are currently published.

These gaps are tracked as limitations, not converted into inferred success claims.
