from logging_config import get_logger, setup_logging
from discord_notifier import send_message

logger = get_logger(__name__)


def main() -> None:
    logger.info("Application started")

    success = send_message("Bot起動テスト")

    if success:
        logger.info("Discord notification succeeded")
    else:
        logger.error("Discord notification failed")

    logger.info("Application finished")


if __name__ == "__main__":
    setup_logging()
    main()
