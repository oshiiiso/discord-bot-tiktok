from discord_webhook import DiscordWebhook

from config import WEBHOOK_URL
from logging_config import get_logger

logger = get_logger(__name__)

def send_message(message: str) -> bool:
    webhook = DiscordWebhook(
        url=WEBHOOK_URL,
        content=message,
    )

    response = webhook.execute()

    if response.ok:
        logger.info("Discord通知成功")
        return True
    else:
        logger.error(
            "Discord通知失败: %s",
            response.status_code,
        )
        return False
