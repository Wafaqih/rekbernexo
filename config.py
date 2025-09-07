import os
import logging

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
BOT_USERNAME = os.getenv("BOT_USERNAME")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
TESTIMONI_CHANNEL = os.getenv("TESTIMONI_CHANNEL", "@TESTIJASAREKBER")
ADMIN_ID = 7058869200

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Bot settings
MAX_MESSAGE_LENGTH = 4096
RETRY_ATTEMPTS = 3