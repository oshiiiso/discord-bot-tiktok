# TikTok 配信通知 Bot 使い方

登録した TikTok 配信者のライブ開始・終了を Discord チャンネルへ通知します。  
サーバーメンバーは常設パネルから、通知を受け取りたい配信者を自分で選べます。

> **個人・身内利用向け**  
> 信頼できるサーバーでのみ運用してください。不具合・要望は [Issues](https://github.com/oshiiiso/discord-bot-tiktok/issues) へ。

---

## セットアップ

### 1. Discord Bot の準備

1. [Discord Developer Portal](https://discord.com/developers/applications) で Bot を作成
2. **Bot** タブで **SERVER MEMBERS INTENT** と **MESSAGE CONTENT INTENT** を有効化
3. **OAuth2 URL Generator** で `bot` と `applications.commands` を選択
4. Bot 権限の例:
   - メッセージを送る / 管理 / リンクを埋め込み / メッセージ履歴を読む
   - ロールの管理
5. サーバーに Bot を招待

### 2. 環境構築

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env` を編集（最低限）:

- `DISCORD_TOKEN` … Bot トークン
- `GUILD_ID` … サーバー ID（推奨。即時にスラッシュコマンドが反映される）
- `NOTIFY_CHANNEL_ID` … 通知を送るチャンネル ID

### 3. 配信者の登録

`streamers.json` に追記するか、起動後に `/streamers add` で登録します。

```json
{
  "streamers": [
    {
      "label": "配信者の表示名",
      "role_id": "通知に使う Discord ロールの ID",
      "tiktok_id": "TikTok のユニーク ID（@ なし）"
    }
  ]
}
```

### 4. 起動

```powershell
python main.py
```

通知チャンネルで `/panel` を実行し、常設パネルを設置します。

---

## コマンド一覧

| コマンド | 説明 | 権限 |
|---|---|---|
| `/panel` | 配信通知設定の常設パネルを設置 | manage_roles |
| `/ping` | 応答確認 | 誰でも |
| `/streamers list` | 登録済み配信者一覧 | manage_roles |
| `/streamers add` | 配信者を追加 | manage_roles |
| `/streamers del` | 配信者を削除 | manage_roles |
| `/streamers edit` | 配信者情報を編集 | manage_roles |
| `/reload` | 監視 Cog を再読み込み | Bot 所有者 |
| `/test start` / `/test end` | 通知のテスト送信 | manage_roles |

パネルのボタンは全員が押せます。表示される配信者選択は**押した本人だけ**に見えます。

---

## よくある質問

**Q. メンバーは何をすればいい？**  
A. `/panel` で設置したボタンから、通知したい配信者を選ぶだけです。

**Q. スラッシュコマンドが出ない**  
A. `GUILD_ID` を `.env` に設定して Bot を再起動してください。グローバル同期のみの場合、反映に時間がかかることがあります。

**Q. 通知が来ない**  
A. `streamers.json` の `tiktok_id`、ロール ID、`NOTIFY_CHANNEL_ID` を確認してください。ログは `logs/` に出力されます。

**Q. 複数サーバーで使える？**  
A. 本 Bot は個人サーバー向けに 1 サーバー前提で運用する想定です。

---

## 問い合わせ

不具合・要望は GitHub の [Issues](https://github.com/oshiiiso/discord-bot-tiktok/issues) からお願いします。

- **トークンや `.env` の内容は Issue に貼らないでください**
- ログを添える場合は個人情報・トークンを除いてください

---

## 注意

- TikTok 側の仕様変更で動かなくなる可能性があります
- ポーリング間隔は `.env` で調整できます。過度なアクセスは避けてください
