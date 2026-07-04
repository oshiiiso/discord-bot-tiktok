from datetime import datetime
import logging
from pathlib import Path

from config import LOG_LEVEL


def setup_logging() -> None:
    """ロギングを初期化する"""

    today = datetime.now()

    log_dir = Path("logs") / f"{today:%Y}"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{today:%m%d}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # 重複登録防止
    if root_logger.handlers:
        return

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """ロガーを取得する"""
    return logging.getLogger(name)
