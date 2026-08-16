from datetime import date, datetime, timedelta
import logging
from pathlib import Path
import re

from config import LOG_LEVEL, LOG_RETENTION_DAYS

LOG_DIR = Path("logs")
LOG_FILENAME_PATTERN = re.compile(r"^\d{8}\.log$")

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


def _cleanup_old_logs(retention_days: int) -> None:
    """logs/yyyymmdd.log のうち、保存期限を過ぎたファイルを削除する。"""
    if not LOG_DIR.exists():
        return

    threshold = date.today() - timedelta(days=retention_days)

    for log_file in LOG_DIR.glob("*.log"):
        if not LOG_FILENAME_PATTERN.match(log_file.name):
            continue

        file_date = datetime.strptime(log_file.stem, "%Y%m%d").date()
        if file_date < threshold:
            try:
                log_file.unlink()
            except OSError as e:
                logging.getLogger(__name__).warning("古いログファイルの削除に失敗しました: %s (%s)", log_file, e)


class DailyFileHandler(logging.Handler):
    """日付が変わったら自動でファイルを切り替えるハンドラ。logs/yyyymmdd.log に出力する。"""

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

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{today:%Y%m%d}.log"

        self._file_handler = logging.FileHandler(log_file, encoding="utf-8")
        self._file_handler.setFormatter(self.formatter)
        self._current_date = today

        _cleanup_old_logs(LOG_RETENTION_DAYS)

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
