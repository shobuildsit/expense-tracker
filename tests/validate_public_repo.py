#!/usr/bin/env python3
"""Offline structural and publication-safety checks for the public repository."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = {
    "Scenario1 Wise Expense Logger.sanitized.blueprint.json": 10,
    "Scenario2 Wise Expense Logger.sanitized.blueprint.json": 8,
    "Scenario3 BOG SMS Expense Logger.sanitized.blueprint.json": 12,
}

passed = 0
failed = 0


def check(condition: bool, label: str) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def modules(blueprint: dict) -> list[dict]:
    return [item for item in walk(blueprint) if isinstance(item, dict) and isinstance(item.get("module"), str)]


def public_candidate_files() -> list[Path]:
    """Files Git would publish: tracked plus untracked, excluding ignored paths."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def public_text_files() -> list[Path]:
    files = []
    for path in public_candidate_files():
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files


def main() -> int:
    loaded = {}
    for name, expected_count in BLUEPRINTS.items():
        path = ROOT / "make" / "examples" / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        check(isinstance(data, dict), f"{name}: valid JSON object")
        if not isinstance(data, dict):
            continue
        loaded[name] = data
        check(len(modules(data)) == expected_count, f"{name}: expected {expected_count} modules")
        text = json.dumps(data, ensure_ascii=False)
        check("YOUR_SPREADSHEET_ID" in text, f"{name}: spreadsheet uses a public placeholder")
        check("YOUR_LINE_USER_ID" in text, f"{name}: LINE user uses a public placeholder")
        check("YOUR_LINE_CHANNEL_ACCESS_TOKEN" in text, f"{name}: LINE token uses a public placeholder")

    wise = loaded.get("Scenario1 Wise Expense Logger.sanitized.blueprint.json")
    if wise:
        openai_modules = [item for item in modules(wise) if item["module"] == "openai-gpt-3:createModelResponse"]
        check(len(openai_modules) == 1, "Wise Blueprint has exactly one OpenAI Responses module")
        mapper = openai_modules[0].get("mapper", {}) if openai_modules else {}
        check(mapper.get("store") is False, "Wise OpenAI module has store=false")
        check(mapper.get("createConversation") is False, "Wise OpenAI module has createConversation=false")
        check("Do not guess" in mapper.get("input", ""), "Wise prompt explicitly prohibits guessing")
        check("{{2.from}}" not in mapper.get("input", ""), "Wise prompt does not send the sender address")

    bog = loaded.get("Scenario3 BOG SMS Expense Logger.sanitized.blueprint.json")
    if bog:
        bog_types = [item["module"] for item in modules(bog)]
        bog_text = json.dumps(bog, ensure_ascii=False)
        check(not any("openai" in item.lower() for item in bog_types), "BOG Blueprint contains no OpenAI module")
        check("parseNumber(" in bog_text, "BOG Blueprint uses deterministic numeric parsing")
        check('\\"გადახდა:\\"' in bog_text, "BOG parser accepts the Georgian payment label")
        check('\\"Purchase:\\"' in bog_text, "BOG parser accepts the English payment label")
        check("escapeJSON(1.message)" in bog_text, "BOG failure alert escapes the raw message")
        check("{{1.guid}}" in bog_text, "BOG Blueprint maps the Messages GUID as source identity")

    watcher = (ROOT / "messages_watcher" / "watcher.py").read_text(encoding="utf-8")
    try:
        compile(watcher, "messages_watcher/watcher.py", "exec")
        watcher_valid = True
    except SyntaxError:
        watcher_valid = False
    check(watcher_valid, "messages_watcher/watcher.py has valid Python syntax")
    check("mode=ro" in watcher, "Messages database is opened read-only")
    check("DRY_RUN" in watcher, "watcher retains a no-webhook dry-run mode")

    required = [
        "README.md",
        "README.en.md",
        "README_ja.md",
        "SECURITY.md",
        "docs/architecture.md",
        "docs/setup.md",
        "docs/evidence.md",
        "docs/limitations.md",
        "LICENSE",
    ]
    check(all((ROOT / item).is_file() for item in required), "required public documentation exists")
    readme_ja = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")
    check("[English](README.en.md)" in readme_ja, "Japanese README links to English")
    check("[日本語](README.md)" in readme_en, "English README links to Japanese")
    check("EVIDENCE_GAP" in (ROOT / "docs" / "evidence.md").read_text(encoding="utf-8"), "evidence gaps are explicitly labeled")

    forbidden_paths = []
    for path in public_candidate_files():
        rel = path.relative_to(ROOT)
        if rel.name == ".env" or rel.suffix.lower() in {".xlsx", ".pyc"} or rel.name == ".DS_Store":
            forbidden_paths.append(str(rel))
        if rel.parent == Path("make") and rel.name.endswith(".blueprint.json"):
            forbidden_paths.append(str(rel))
    check(not forbidden_paths, "no private runtime artifacts are present in the public tree")

    secret_patterns = {
        "OpenAI key": re.compile("s" + r"k-[A-Za-z0-9_-]{20,}"),
        "GitHub token": re.compile("g" + r"h[pousr]_[A-Za-z0-9]{20,}"),
        "Slack token": re.compile("x" + r"ox[baprs]-[A-Za-z0-9-]{20,}"),
        "Google API key": re.compile("A" + r"Iza[0-9A-Za-z_-]{30,}"),
        "private key": re.compile("BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
        "Make webhook": re.compile(r"https://hook\.[a-z0-9-]+\.make\.com/[A-Za-z0-9_-]{20,}"),
    }
    findings = []
    email_findings = []
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    for path in public_text_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for label, pattern in secret_patterns.items():
            if pattern.search(text):
                findings.append(f"{rel}: {label}")
        for match in email_pattern.finditer(text):
            if match.group(1).lower() != "example.com":
                email_findings.append(str(rel))
    check(not findings, "public text contains no common secret-shaped values")
    check(not email_findings, "public text contains no email addresses outside example.com")

    total = passed + failed
    print("=" * 70)
    print(f"{passed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
