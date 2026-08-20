# Public repository validation

Run the offline validator from the repository root:

```bash
python3 tests/validate_public_repo.py
```

It checks the structure and publication safety of the committed artifacts without calling external APIs or reading live account data. A passing result is not a substitute for Make, Google Sheets, LINE, Gmail, OpenAI, or macOS integration testing; see [`../docs/evidence.md`](../docs/evidence.md).
