# Expense Tracker（日本語版）

メール・SMS/iMessageなど複数のチャネルから届く決済通知をLLMで解析し、安定したイベントIDで重複登録を防いだ上でGoogle Sheetsへ自動記録します。既知のマーチャントはカテゴリを自動再利用し、未知のマーチャントが現れたときだけLINEでカテゴリをワンタップ選択します。

*(English README: [README.md](README.md))*

## 概要

Expense Trackerは複数の入力チャネルを監視し、それぞれの決済通知を単一のGoogle Sheetsへ正規化された1行として記録します。

- **Gmail** — Wiseの決済確認メール
- **macOS Messages / SMS** — 銀行のSMS通知（例: Bank of Georgia）。ローカルで動くPythonポーラーが転送します
- **Make.com Custom Webhook** — ローカルポーラーと解析・記録の自動化をつなぐ連携ポイント

新しい入力チャネル（別の銀行、CSVインポート、別のチャットプラットフォームなど）を追加する際も、解析・重複判定・カテゴリ選択のロジックはそのまま再利用できるよう、入力元に依存しない設計にしています。全体構成は [`docs/architecture.md`](docs/architecture.md) を参照してください。

## 主な機能

- Gmail経由のトランザクション取り込み（Wise決済メール）
- macOS Messages監視によるSMS/iMessage経由の取り込み
- メール以外のソース向けのMake.com Webhook連携
- OpenAIによるトランザクション解析（マーチャント・金額・通貨・カテゴリ）
- 取引単位の重複登録防止 — 各取引はGmailメッセージID / MessagesのGUIDなど安定した`Source Event ID`を持ち、記録前にチェックされるため、通常のGmail再配信・watcher再起動・Scenario手動再実行による重複登録を防止する
- 既知マーチャントのカテゴリ再利用 — 上記のチェックとは別に、既に記録済みのマーチャントはカテゴリを自動的に再利用する。本当に新規のマーチャントのみLINEでワンタップのカテゴリ選択を促す
- Google Sheetsを単一の記録先として使用
- ローカルのMessagesデータベースへは読み取り専用でアクセス。Webhookへ転送するのは送信者・メッセージ本文・メッセージGUIDのみ。詳しくは[プライバシー / データの扱い](#プライバシー--データの扱い)を参照

## リポジトリ構成

```text
expense-tracker/
├── messages_watcher/      # ローカルPythonポーラー: macOS Messages → Make Webhook
├── make/
│   ├── examples/          # サニタイズ済みMake Blueprintのエクスポート（安全に閲覧・Import可能）
│   └── *.blueprint.json   # 実際の認証情報を含むBlueprint（gitignore対象）
├── docs/
│   ├── architecture.md
│   └── setup.md
├── samples/
│   └── sample_bog_sms.txt # テスト用のダミーSMSペイロード
└── README.md
```

## セットアップ

セットアップ手順（Google Sheetsの構成、Make Blueprintのインポート、`messages_watcher`の設定、`curl`によるエンドツーエンドテストを含む）は [`docs/setup.md`](docs/setup.md) を参照してください。

## セキュリティ

- ローカルのMessagesデータベース（`chat.db`）は**読み取り専用**（`mode=ro`）で開きます。`messages_watcher`が書き込みを行うことはありません
- Webhook URL・APIキー・接続情報は`.env`ファイルで管理し、コミット対象には含めません。想定される形式は`messages_watcher/.env.example`を参照してください
- 実際の財務データ、スプレッドシートのエクスポート、実際のWebhook/Connection IDを含む実Make Blueprintはこのリポジトリに含まれません。`make/examples/`にはID・トークンをすべてプレースホルダーへ置き換え、プロンプト内の例もすべて架空データに置き換えたサニタイズ版を参考として同梱しています
- メールアドレス・電話番号・実際のトランザクションなどの個人情報はこのリポジトリに含まれません

## プライバシー / データの扱い

このプロジェクトは実際の取引データ（マーチャント名・金額、WiseのP2P送金の場合は個人名を含むことがあります）を複数の外部サービス経由で処理します。「一切保存されない」といった単純化はせず、実際に何が起きるかを正確に記載します。

- **OpenAI** には、解析対象としてメール本文（Wise）またはSMS本文（BOG）全体がプロンプトの一部として送信されます。同梱のBlueprintではOpenAIモジュールの`store`・`createConversation`をいずれも`false`に設定しており、このプロジェクト側からOpenAIの保存済みResponseオブジェクトや永続的な会話スレッドとしての保持を要求することはありません。ただし、これはOpenAI自身がAPIレイヤーで行う標準的なデータ取り扱い（不正利用監視目的の短期保持など）を変更するものではなく、その点はこのプロジェクトの制御範囲外です。詳細が必要な場合はOpenAI自身のAPIデータ利用ポリシーを確認してください。
- **Make.com** はシナリオの実行履歴（各モジュールの入出力。生のメール/SMS本文や解析後の取引情報を含む）を、契約しているMakeプランに応じた期間保持します。このプロジェクトはその履歴を消去・無効化していません。実際の取引データが残り得る場所として扱ってください。
- **Google Sheets** が恒久的な保存先です。記録された各取引（`ID`・`Date`・金額・`Merchant`・`Category`・`Status`・`Source Event ID`）は、自分で削除しない限りスプレッドシートに残り続けます。
- **LINE** 通知には、カテゴリ選択が必要なマーチャントについて、マーチャント名と金額が含まれます。これは自分自身のLINE Botとのトーク履歴に残るものであり、他者に送信されることはありません。
- **`messages_watcher`のローカル処理** は、Webhookへ転送する内容(送信者・メッセージ本文・GUID)よりも多くのフィールドを`chat.db`から読み取ります。送信者フィルタの判定に使う`is_from_me`などもローカルで読み取り、直近処理済みの`ROWID`をローカルの状態ファイル(`messages_watcher/state/`、git管理外)へ保存して再開位置を管理します。これらローカル限定の情報がどこかへ送信されることはありません。

## 対象範囲 / 対象外

これは個人用の自動化プロジェクトであり、パッケージ化された製品ではありません。現時点では以下を前提としています。

- 単一ユーザー・単一のGoogle Sheets・単一のLINE通知先
- `messages_watcher`は手動起動・手動停止（launchdなどの常駐化は含みません）
- SMSの例としてはBank of Georgiaの1銀行のフォーマットのみを対象。他銀行フォーマットへの対応はOpenAIプロンプトの調整で可能ですが、自動化はしていません

## ライセンス

[MIT](LICENSE)
