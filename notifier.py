# notifier.py
import requests
from loguru import logger

# Эти переменные будут импортироваться из config.py
TELEGRAM_BOT_TOKEN = "8678375056:AAGxkGR7ZjDmCtOIGV_kYPlVh4pJqZPB5Ws"
TELEGRAM_CHAT_ID = "703529738"

def send_notification(text: str):
    """Отправляет сообщение в Telegram"""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram токен или chat_id не настроены")
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Ошибка Telegram: {response.text}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление: {e}")