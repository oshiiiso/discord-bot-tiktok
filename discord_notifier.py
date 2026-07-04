from discord_webhook import DiscordWebhook
from config import WEBHOOK_URL

def send_message(message: str) -> bool:
    webhook = DiscordWebhook(
        url=WEBHOOK_URL,
        content=message,
    )

    response = webhook.execute()
    return response.ok
