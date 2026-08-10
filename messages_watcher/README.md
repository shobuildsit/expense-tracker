# Messages Watcher (SMS/iMessage → Make Webhook) — MVP

macOSの `Messages` アプリ（`chat.db`）を監視し、指定した送信者（メールアドレス or 電話番号/ショートコード）からの新着メッセージをMakeのCustom WebhookへPOSTするMVPです。

```
特定送信者 → macOS Messages → Python (watcher.py) → Make Webhook
```

Google Sheets登録・AI分類・Merchant解析・launchd常駐化は今回のスコープ外です（`watcher.py` を手動起動して動作確認する想定）。

## 必要要件

- macOS + Messagesアプリでメッセージが同期されていること（iCloud経由のiMessage同期、または「テキストメッセージ転送」でSMSを同期）
- Python 3.9+
- `watcher.py` を実行するアプリ（Terminal.app / iTerm2 / VSCode など）に **フルディスクアクセス** が必要です
  - システム設定 → プライバシーとセキュリティ → フルディスクアクセス → 実行するターミナルアプリを追加してON
  - 付与しないと `sqlite3.OperationalError: unable to open database file` になります

## セットアップ

```bash
cd messages_watcher
pip install -r requirements.txt
cp .env.example .env
```

`.env` を編集:

```
MAKE_WEBHOOK_URL=https://hook.eu1.make.com/xxxxxxxxxx
MESSAGE_FILTER_TYPE=email
MESSAGE_FILTER_VALUE=you@example.com
```

## 実行

```bash
python3 watcher.py
```

- 状態ファイル（`state/last_seen_rowid.txt`）が存在しない**初回起動時**は、その時点で条件（送信者・`INCLUDE_FROM_ME`）に一致する既存メッセージの最大ROWIDを取得し、それをbaselineとして状態ファイルへ保存します。**起動前の過去メッセージは送信されません** — 以降に届いた新着メッセージのみが対象です。
- 5秒間隔（デフォルト）で `chat.db` をポーリングし、`MESSAGE_FILTER_VALUE` に完全一致する送信者からの新着メッセージをWebhookへPOSTします。
- 停止するには `Ctrl+C`。

## フィルターの切り替え（コード修正不要）

`.env` の2行を書き換えるだけで対象を切り替えられます。

メール（iMessage）を監視する場合:
```
MESSAGE_FILTER_TYPE=email
MESSAGE_FILTER_VALUE=you@example.com
```

SMS（ショートコード）に切り替える場合:
```
MESSAGE_FILTER_TYPE=sms
MESSAGE_FILTER_VALUE=4444
```

`MESSAGE_FILTER_VALUE` はMessagesが保存している送信者IDと**完全一致**が必要です。電話番号は国番号付き（例: `+819012345678`）で保存されている場合があるため、一致しない場合は下記の確認方法で実際の値を確認してください。

### 送信者IDの確認方法

```bash
sqlite3 -readonly ~/Library/Messages/chat.db \
  "SELECT DISTINCT id, service FROM handle ORDER BY id;"
```

## Webhookへ送信されるJSON

```json
{
  "source": "messages",
  "filter_type": "email",
  "sender": "you@example.com",
  "message": "本文",
  "guid": "message-guid-from-chat.db"
}
```

`filter_type` / `sender` の値は `.env` の設定とMessagesの実データに応じて `email` / `sms` のいずれかになります。`guid` はMessages DB上のそのメッセージ固有のGUIDで、Make側で取引単位の重複登録防止（Source Event ID）に使われます。

## 重複防止

このwatcher自体は、送信済みメッセージの最終 `ROWID` を `state/last_seen_rowid.txt` に保存します。watcherを再起動しても、そのROWIDより新しいメッセージのみ再送されます（このファイルはgit管理外です）。

ただしこれは「同じメッセージを二度読まない」ためのローカルな仕組みであり、Google Sheets側での取引の重複登録防止は、Make Scenario側（`Source Event ID`列によるチェック、`guid`が一致する行の存在確認）が担当します。watcher再起動時にROWIDがずれた場合や、webhookを手動で再送した場合でも、通常はMake側のチェックにより重複登録が防止されます（アプリケーションレベルのcheck-then-insertであり、同一`guid`の同時実行に対するatomicな一意性保証ではありません）。

## テストモード（Webhookを実際に叩かずに確認）

`.env` で `DRY_RUN=true` にすると、実際にはPOSTせずペイロードをログ出力するだけになります。Make側のシナリオに影響を与えずに動作確認したいときに使ってください。

```
DRY_RUN=true
```

## 自分発信メッセージでのテスト（開発用）

本番運用では受信メッセージのみを対象とするため `is_from_me = 0` で絞り込んでいますが、開発中に「自分から自分（または監視対象アドレス）へ送ったiMessage」でもWebhook連携を確認できるよう `INCLUDE_FROM_ME` を用意しています。

```
INCLUDE_FROM_ME=true
```

- `false`（デフォルト）: 従来通り `is_from_me = 0` のみ取得（受信メッセージのみ）。本番運用はこのまま維持してください。
- `true`: `is_from_me` の条件を外し、自分発信メッセージも取得対象にします。

### テスト手順

1. `.env` で以下を設定します（本番Webhookを叩かないよう `DRY_RUN=true` を推奨）。
   ```
   DRY_RUN=true
   INCLUDE_FROM_ME=true
   ```
2. `watcher.py` を起動します。
   ```bash
   python3 watcher.py
   ```
3. `MESSAGE_FILTER_VALUE`（例: `you@example.com`）宛に、自分自身からiMessageを送信します。
4. ターミナルに `[watcher] DRY_RUN payload=...` のログが出力されれば検知成功です。
5. テストが終わったら `.env` を本番設定（`DRY_RUN=false` / `INCLUDE_FROM_ME=false`）に戻してください。

## 既知の制限

- 一部のキャリア通知メッセージなど、Messagesが本文を `text` 列ではなく `attributedBody`（バイナリ）のみに格納する場合があります。`watcher.py` はその場合に簡易的なテキスト抽出を行いますが、完全なパーサーではないため一部欠落する可能性があります。実際の銀行系SMS（例: `Sample Merchant GEL12.34 ...`）は `text` 列に本文がそのまま入っており問題なく動作確認済みです。非ASCII文字（ジョージア語など）を含むメッセージが `attributedBody` 側に回った場合、この簡易抽出では該当部分が欠落します。
- グループチャットや添付ファイルのみのメッセージは想定していません。
- 本スクリプトは常駐化（launchd等）していません。手動起動・手動停止での運用です。

## 今回のスコープ外

- launchdによる自動起動/常駐化
- Google Sheetsへの登録
- AI分類 / Merchant解析 / Category判定
- GitHub公開用リファクタリング
