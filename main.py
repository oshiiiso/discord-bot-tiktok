from bot import bot
from config import DISCORD_TOKEN
from logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    logger.info("Application started")
    bot.run(DISCORD_TOKEN)
    logger.info("Application finished")


if __name__ == "__main__":
    setup_logging()
    main()
