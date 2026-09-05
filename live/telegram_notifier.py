import requests
import logging
import config.settings as config

logger = logging.getLogger(__name__)

def send_telegram_message(message: str):
    """
    Sends a message to the configured Telegram chat.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.debug("Telegram credentials not found. Skipping notification.")
        return False
        
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
