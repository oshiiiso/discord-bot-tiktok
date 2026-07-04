import os
from dotenv import load_dotenv

load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
