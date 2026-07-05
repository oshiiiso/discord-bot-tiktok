import os
from dotenv import load_dotenv

load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# デバッグモード時はログレベルを強制的にDEBUGにする
if DEBUG_MODE:
    LOG_LEVEL = "DEBUG"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# TikTok配信通知を送信するチャンネルのID
# 環境変数が未設定・空文字の場合は 0 として扱う（getenv の第2引数は
# キー自体が存在しない場合にのみ使われ、空文字列では使われないため注意）
NOTIFY_CHANNEL_ID = int(os.getenv("NOTIFY_CHANNEL_ID") or "0")

# TikTok配信状態のポーリング間隔（秒）。オフライン時（配信していない時）に
# 「配信が始まっていないか」を確認する基本間隔。
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS") or "60")

# ライブ中（配信を検知した後）のポーリング間隔（秒）。
# 配信中は「終了したかどうか」だけ分かればよく、開始検知ほど即時性は不要なため、
# 通常は POLL_INTERVAL_SECONDS より長めの値にしてTikTok側への負荷を下げる。
LIVE_POLL_INTERVAL_SECONDS = int(os.getenv("LIVE_POLL_INTERVAL_SECONDS") or "60")

# ポーリング間隔に加えるランダムな揺らぎの比率（0.1 = ±10%）。
# 全配信者・全回が全く同じ間隔で機械的にアクセスすると検知されやすくなるため、
# 毎回わずかに間隔をランダム化する（例: 基本60秒 → 54〜66秒の範囲でばらつく）。
POLL_JITTER_RATIO = float(os.getenv("POLL_JITTER_RATIO") or "0.1")

# 通信エラー等でチェックに失敗した場合の最大バックオフ秒数。
# エラーが連続するたびに待機時間を指数的に伸ばすが、この値を上限とする。
MAX_BACKOFF_SECONDS = int(os.getenv("MAX_BACKOFF_SECONDS") or "600")

# ポーリングスケジューラの実行間隔（秒）。この値自体が各配信者のチェック間隔では
# なく、「各配信者ごとの次回チェック時刻を過ぎていないか」を確認する解像度。
# 短くしておくことで、配信者ごとに異なるタイミングでチェックが分散される。
SCHEDULER_TICK_SECONDS = int(os.getenv("SCHEDULER_TICK_SECONDS") or "5")
