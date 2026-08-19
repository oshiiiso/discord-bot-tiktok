# Discord Bot - TikTok 配信通知

TikTok 配信の開始・終了を Discord に通知する Bot（Python + discord.py）

個人・身内利用向けに開発した Bot です。ソースは公開していますが、**不特定多数向けの配布・運用は想定していません**。使う場合は自分でセットアップするか、信頼できる人が管理するサーバーでのみ利用してください。

- リポジトリ: https://github.com/oshiiiso/discord-bot-tiktok
- 不具合・要望: [Issues](https://github.com/oshiiiso/discord-bot-tiktok/issues)
- 使い方: [docs/USER.md](docs/USER.md)

## 機能概要

- 登録した TikTok 配信者のライブ状態を定期チェック
- 配信開始・終了を Discord に Embed 通知（終了時は開始メッセージを編集）
- 常設パネルからメンバーが通知対象の配信者を選択（ロール連動）
- スラッシュコマンドで配信者の登録・テスト・再読み込み

## ディレクトリ構成

```
main.py                 # エントリーポイント
bot.py                  # Bot 本体・スラッシュコマンド
config.py               # 環境変数の読み込み
logging_config.py       # ログ設定
streamers.json          # 通知対象の配信者リスト
cogs/tiktok_watcher.py  # 配信監視ループ
services/               # 状態・配信者・TikTok 問い合わせ
ui/panel.py             # 配信者選択パネル
docs/USER.md            # セットアップ・運用ガイド
storage/                # 実行時データ（.gitignore）
logs/                   # ログ（.gitignore）
```

## 開発環境セットアップ

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # トークン等を編集
python main.py
```

詳細な手順・権限設定・コマンド一覧は [docs/USER.md](docs/USER.md) を参照。

### 環境変数（`.env`）

| 変数 | 説明 | デフォルト |
|---|---|---|
| `DISCORD_TOKEN` | Bot トークン | —（必須） |
| `GUILD_ID` | 動作させるサーバー ID | 未設定時はグローバル同期 |
| `NOTIFY_CHANNEL_ID` | 通知チャンネル ID | —（必須） |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR | `INFO` |
| `LOG_RETENTION_DAYS` | ログ保持日数 | `30` |
| `POLL_INTERVAL_SECONDS` | オフライン時のポーリング間隔（秒） | `60` |
| `LIVE_POLL_INTERVAL_SECONDS` | 配信中のポーリング間隔（秒） | `60` |
| その他 | ポーリング・バックオフ・パネル設定 | `.env.example` 参照 |

`.env` は Git に含めません。

## ブランチ運用

| ブランチ | 用途 |
|---------|------|
| **develop** | 日常の開発 |
| **main** | 確定版（develop からマージ。タグ `v*` で版を管理） |

### 普段の開発

```powershell
git checkout develop
# 作業 → commit → push
git push origin develop
```

### 確定版を出す（例: v0.1.0）

```powershell
git checkout main
git merge develop -m "release: v0.1.0"
git tag v0.1.0
git push origin main --tags
git checkout develop
```

## 注意事項

- TikTok の非公式 API／スクレイピングに依存しています。利用規約・障害・仕様変更のリスクは自己責任でください。
- 本 Bot は個人サーバー向けです。公開サービスとしての提供は想定していません。

## ライセンス

MIT License — Copyright (c) 2026 oshiiiso

詳細は [LICENSE](LICENSE) を参照。
