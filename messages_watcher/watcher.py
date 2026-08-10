#!/usr/bin/env python3
"""Poll macOS Messages (chat.db) for new messages from one sender and POST them to a Make webhook."""

import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

CHAT_DB_PATH = os.path.expanduser(os.environ.get("MESSAGES_DB_PATH", "~/Library/Messages/chat.db"))
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "").strip()
MESSAGE_FILTER_TYPE = os.environ.get("MESSAGE_FILTER_TYPE", "").strip()
MESSAGE_FILTER_VALUE = os.environ.get("MESSAGE_FILTER_VALUE", "").strip()
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "5"))
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"
INCLUDE_FROM_ME = os.environ.get("INCLUDE_FROM_ME", "false").strip().lower() == "true"

STATE_FILE = BASE_DIR / "state" / "last_seen_rowid.txt"

# attributedBody is a serialized NSAttributedString; text is usually populated
# directly, but some carrier/system messages only fill attributedBody. This is
# a best-effort fallback, not a full typedstream parser.
ATTRIBUTED_BODY_NOISE = {
    "streamtyped", "NSMutableAttributedString", "NSAttributedString", "NSObject",
    "NSMutableString", "NSString", "NSDictionary", "NSNumber", "NSValue",
    "NSMutableData", "NSData", "NSKeyedArchiver", "NSArray",
    "__kIMMessagePartAttributeName", "__kIMDataDetectedAttributeName",
}


def require_config():
    missing = [
        name
        for name, value in (
            ("MAKE_WEBHOOK_URL", MAKE_WEBHOOK_URL),
            ("MESSAGE_FILTER_TYPE", MESSAGE_FILTER_TYPE),
            ("MESSAGE_FILTER_VALUE", MESSAGE_FILTER_VALUE),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing required .env settings: {', '.join(missing)}. Copy .env.example to .env first.")


def save_last_seen_rowid(rowid):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(rowid))


def get_current_max_rowid():
    """Highest ROWID currently matching the configured filter, or 0 if there are no matches yet."""
    from_me_clause = "" if INCLUDE_FROM_ME else "AND m.is_from_me = 0"
    query = f"""
        SELECT MAX(m.ROWID)
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE h.id = ?
          {from_me_clause}
    """
    conn = sqlite3.connect(f"file:{CHAT_DB_PATH}?mode=ro", uri=True)
    try:
        row = conn.execute(query, (MESSAGE_FILTER_VALUE,)).fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] is not None else 0


def load_last_seen_rowid():
    if STATE_FILE.exists():
        content = STATE_FILE.read_text().strip()
        if content.isdigit():
            return int(content)

    # No state file: baseline at the current max ROWID so existing (pre-startup)
    # messages are never sent. Only messages that arrive after this point are new.
    baseline = get_current_max_rowid()
    save_last_seen_rowid(baseline)
    print(f"[watcher] no state file found; baselining at ROWID={baseline} (existing messages will not be sent)")
    return baseline


def extract_text(text, attributed_body):
    if text:
        return text
    if not attributed_body:
        return ""
    for candidate in re.findall(rb"[\x20-\x7e]{4,}", attributed_body):
        decoded = candidate.decode("ascii", errors="ignore")
        if decoded in ATTRIBUTED_BODY_NOISE or decoded.startswith(("$", "__")):
            continue
        return decoded
    return ""


def fetch_new_messages(conn, last_rowid):
    from_me_clause = "" if INCLUDE_FROM_ME else "AND m.is_from_me = 0"
    query = f"""
        SELECT m.ROWID, m.guid, m.text, m.attributedBody, h.id AS sender
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.ROWID > ?
          {from_me_clause}
          AND h.id = ?
        ORDER BY m.ROWID ASC
    """
    return conn.execute(query, (last_rowid, MESSAGE_FILTER_VALUE)).fetchall()


def send_to_webhook(sender, message_text, guid):
    payload = {
        "source": "messages",
        "filter_type": MESSAGE_FILTER_TYPE,
        "sender": sender,
        "message": message_text,
        "guid": guid,
    }
    if DRY_RUN:
        print(f"[watcher] DRY_RUN payload={json.dumps(payload, ensure_ascii=False)}")
        return "dry-run"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MAKE_WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


def main():
    require_config()
    print(
        f"[watcher] filter_type={MESSAGE_FILTER_TYPE} filter_value={MESSAGE_FILTER_VALUE} "
        f"dry_run={DRY_RUN} include_from_me={INCLUDE_FROM_ME}"
    )
    print(f"[watcher] watching {CHAT_DB_PATH} every {POLL_INTERVAL_SECONDS}s")

    try:
        last_rowid = load_last_seen_rowid()
    except sqlite3.OperationalError as exc:
        raise SystemExit(
            f"[watcher] could not read {CHAT_DB_PATH} to establish a starting point: {exc}. "
            "Grant Full Disk Access to your terminal app and try again."
        )
    print(f"[watcher] resuming from ROWID={last_rowid}")

    while True:
        try:
            conn = sqlite3.connect(f"file:{CHAT_DB_PATH}?mode=ro", uri=True)
            try:
                rows = fetch_new_messages(conn, last_rowid)
            finally:
                conn.close()

            for rowid, guid, text, attributed_body, sender in rows:
                message_text = extract_text(text, attributed_body)
                if message_text:
                    try:
                        status = send_to_webhook(sender, message_text, guid)
                        print(f"[watcher] sent ROWID={rowid} guid={guid} status={status}")
                    except urllib.error.URLError as exc:
                        print(f"[watcher] ERROR sending ROWID={rowid}: {exc} (will retry next poll)")
                        break
                else:
                    print(f"[watcher] skipped ROWID={rowid} guid={guid} (empty message body)")
                last_rowid = rowid
                save_last_seen_rowid(last_rowid)

        except sqlite3.OperationalError as exc:
            print(f"[watcher] DB read error, will retry: {exc}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
