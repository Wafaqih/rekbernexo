# This file is kept for compatibility but functionality has been moved to bot.py
# The pyTelegramBotAPI library uses decorators instead of separate handler functions
import logging

logger = logging.getLogger(__name__)
logger.info("Handler functions are now defined in bot.py using decorators")