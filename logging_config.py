from datetime import datetime
import logging
from pathlib import Path

from config import LOG_LEVEL

# DEBUG_MODE時でも詳細ログを抑制したい外部ライブラリのロガー名。
# httpx/httpcore は TikTokLive が内部で使うHTTPクライアントで、
# 1回のリクエストだけでTCP接続やヘッダー等、十数行のDEBUGログを出す。
# 自前のアプリケーションコード（get_logger(__name__)経由）のログレベルには影響しない。
_NOISY_LOGGER_NAMES = (
    "httpx",
    "httpcore",       # httpcore.connection / httpcore.http11 等の子ロガーにも伝播する
    "asyncio",
    "websockets",
    "urllib3",
)


def _suppress_noisy_loggers() -> None:
    """外部ライブラリの過剰なDEBUGログを抑制する（WARNING以上のみ通す）。"""
    for name in _NOISY_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)


class DailyFileHandler(logging.Handler):
    """日付が変わったタイミングで自動的に新しいログファイルに切り替えるハンドラ。

    logs/{年}/{月日}.log の形式でファイルを分割する。
    Botのように日をまたいで動き続けるプロセスでも、再起動なしで
    正しい日付のファイルにログを出力し続けられる。
    """

    def __init__(self, formatter: logging.Formatter):
        super().__init__()
        self.setFormatter(formatter)
        self._current_date = None
        self._file_handler: logging.FileHandler | None = None
        self._rotate_if_needed()

    def _rotate_if_needed(self) -> None:
        today = datetime.now().date()
        if today == self._current_date:
            return

        if self._file_handler is not None:
            self._file_handler.close()

        log_dir = Path("logs") / f"{today:%Y}"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{today:%m%d}.log"

        self._file_handler = logging.FileHandler(log_file, encoding="utf-8")
        self._file_handler.setFormatter(self.formatter)
        self._current_date = today

    def emit(self, record: logging.LogRecord) -> None:
        self._rotate_if_needed()
        self._file_handler.emit(record)


def setup_logging() -> None:
    """ロギングを初期化する"""

    root_logger = logging.getLogger()

    # 重複登録防止
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    daily_file_handler = DailyFileHandler(formatter)

    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(daily_file_handler)

    _suppress_noisy_loggers()


def get_logger(name: str) -> logging.Logger:
    """ロガーを取得する"""
    return logging.getLogger(name)
