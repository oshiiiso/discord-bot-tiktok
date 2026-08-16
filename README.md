# Discord Bot - TikTok配信通知

登録したTikTok配信者のライブ配信状態を定期的にチェックし、配信の開始・終了をDiscordチャンネルへ
自動通知するBot
サーバーメンバーは常設パネルから、通知を受け取りたい配信者を自分で選択できる

## 機能

- 登録した配信者のTikTokライブ配信状態を定期チェック（ポーリング間隔はランダムに揺らして負荷・検知回避）
- 配信開始時に対象ロールへメンション付きでEmbed通知（タイトル・サムネイル画像つき）
- 配信終了時は開始通知メッセージを編集して「配信が終了しました」に更新（メッセージが増えない）
- ボタン1つで開く配信者選択パネル（押した本人だけに見えるエフェメラル表示）
- 選択した配信者に応じてDiscordロールを自動付与/解除し、通知対象を制御
- 通信エラー時は指数バックオフで再試行間隔を自動調整
- `/panel` で常設パネルを設置
- `/ping` でBotの死活確認
- `/streamers list` / `add` / `del` / `edit` で配信者の一覧表示・登録・削除・編集
- `/reload` でBotを再起動せずにTikTok監視Cogを再読み込み
- `/test start` / `/test end` で通知の送信テスト

## ディレクトリ構成

```
main.py                    # エントリーポイント
bot.py                     # Bot本体・コマンド定義
config.py                  # 設定・定数（環境変数の読み込み）
logging_config.py          # ロガー設定（日付ローテーション・自動削除）
streamers.json             # 通知対象の配信者リスト
cogs/
  tiktok_watcher.py         # 配信監視ループ・通知処理・テストコマンド
services/
  state.py                  # 配信中フラグの読み書き（storage/state.json）
  streamers.py               # streamers.json の読み込み
  tiktok_monitor.py          # TikTok側の配信状態・配信情報取得
ui/
  panel.py                   # 配信者選択パネル・常設ボタンView
storage/                    # 生成される保存データ(.gitignore対象)
logs/                       # ログファイル(.gitignore対象)
```

## セットアップ

1. Discord Botを `Discord Developer Portal` で作成し下記を設定
    1. `Bot` タブで Privileged Gateway Intents の `SERVER MEMBERS INTENT` と
       `MESSAGE CONTENT INTENT` を有効化
    2. `Oauth2` の`OAuth2 URLジェネレーターのスコープ `bot` と `applications.commands` を選択
       （スラッシュコマンドを使うには `applications.commands` スコープが必須）
    3. Botの権限で下記を設定
    ```
    テキストの権限
    - メッセージを送る
    - メッセージを管理
    - リンクを埋め込み
    - メッセージ履歴を読む

    サーバー全体の権限
    - ロールの管理
    ```
    4. Botを自身のサーバーへ追加する

2. 依存パッケージのインストール

    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3. プロジェクトルートに`.env.example` ファイルから `.env` をコピー

    ```
    DISCORD_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxx

    LOG_LEVEL=INFO
    LOG_RETENTION_DAYS=30

    GUILD_ID=xxxxxxxxxxxxxxxxxxx

    NOTIFY_CHANNEL_ID=xxxxxxxxxxxxxxxxxxx

    POLL_INTERVAL_SECONDS=60
    LIVE_POLL_INTERVAL_SECONDS=60
    POLL_JITTER_RATIO=0.1
    MAX_BACKOFF_SECONDS=600
    SCHEDULER_TICK_SECONDS=5
    MIN_REQUEST_GAP_SECONDS=0.5
    MAX_REQUEST_GAP_SECONDS=2.0
    PANEL_VIEW_TIMEOUT_SECONDS=120
    ```

    - `DISCORD_TOKEN`
      - Discord Botのトークン
    - `LOG_LEVEL`
      - 出力するログレベル(DEBUG、INFO、WARNING、ERROR)(未設定: `INFO`)
    - `LOG_RETENTION_DAYS`
      - ログファイルの保持日数
        ログは日付ごとに自動でローテーションされ、この日数を超えた古いログファイルは自動削除(未設定: 30日)
    - `GUILD_ID`
      - Botを動作させるサーバーのID(未設定: グローバル同期)
    - `NOTIFY_CHANNEL_ID`
      - 配信通知を送信するDiscordチャンネルのID
    - `POLL_INTERVAL_SECONDS`
      - オフライン時（配信していない時）の基本ポーリング間隔・秒(未設定: 60秒)
    - `LIVE_POLL_INTERVAL_SECONDS`
      - 配信中（終了検知用）の基本ポーリング間隔・秒(未設定: 60秒)
    - `POLL_JITTER_RATIO`
      - ポーリング間隔に加えるランダムな揺らぎの比率(未設定: 0.1 = ±10%)
    - `MAX_BACKOFF_SECONDS`
      - 通信エラー連続時の最大バックオフ秒数(未設定: 600秒)
    - `SCHEDULER_TICK_SECONDS`
      - 各配信者の次回チェック時刻を確認するスケジューラの実行間隔・秒(未設定: 5秒)
    - `MIN_REQUEST_GAP_SECONDS` / `MAX_REQUEST_GAP_SECONDS`
      - 配信者を1人ずつ処理する際にリクエストの間へ挟むランダムな待機時間の範囲・秒
        (未設定: 0.5〜2.0秒)
    - `PANEL_VIEW_TIMEOUT_SECONDS`
      - 配信者選択パネル（エフェメラルメッセージ）のタイムアウト秒数(未設定: 120秒)

4. 通知先のDiscordチャンネルを1つ作成し、そのIDを`.env`の`NOTIFY_CHANNEL_ID`に設定

5. `streamers.json` に通知対象の配信者を登録

    ```json
    {
      "streamers": [
        {
          "label": "配信者の表示名",
          "role_id": "通知に使うDiscordロールのID",
          "tiktok_id": "TikTokのユニークID（@なし）"
        }
      ]
    }
    ```

6. Botを起動

    ```powershell
    python main.py
    ```

7. 通知したいチャンネルで `/panel` を実行し、常設の設定パネルを設置
   （スラッシュコマンドはBot招待直後、グローバル反映まで最大1時間程度かかる場合がある）

## コマンド一覧

すべてスラッシュコマンド（`/`）として提供される。

| コマンド | 説明 | 権限 |
|---|---|---|
| `/panel` | 配信通知設定の常設パネルをこのチャンネルに設置 | manage_roles |
| `/ping` | Botの応答速度を確認 | 誰でも |
| `/streamers list` | streamers.json に登録されている配信者一覧を表示 | manage_roles |
| `/streamers add <label> <role_id> <tiktok_id>` | 配信者を追加 | manage_roles |
| `/streamers del <tiktok_id>` | 配信者を削除 | manage_roles |
| `/streamers edit <tiktok_id> [label] [role_id] [new_tiktok_id]` | 登録済み配信者の情報を編集 | manage_roles |
| `/reload` | TikTokWatcher Cogを再読み込み（再起動不要で設定を反映） | Bot所有者 |
| `/test start <tiktok_id>` | 配信開始通知のテスト送信（実際の状態は変更しない） | manage_roles |
| `/test end <tiktok_id>` | 配信終了通知のテスト送信（実際の状態は変更しない） | manage_roles |

`/panel` で設置したパネルのボタンは全員が押せて、押した本人だけに見える配信者選択メニューが開く。

## 動作の仕組み（概要）

1. `check_streams` ループ（[cogs/tiktok_watcher.py](cogs/tiktok_watcher.py)）が `SCHEDULER_TICK_SECONDS`
   間隔で起動し、各配信者の次回チェック時刻が到来しているか確認する
2. 到来している配信者だけを直列に、ランダムな間隔を空けてTikTokへ問い合わせる
3. 配信開始を検知すると対象ロールへメンション付きでEmbed通知を送信し、メッセージIDを状態として保存
4. 配信終了を検知すると、保存しておいたメッセージIDを使って開始通知を編集し「配信が終了しました」に更新
5. 通信エラー時は指数バックオフで次回チェックを遅らせ、TikTok側への負荷や誤検知を抑える
