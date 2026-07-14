import logging
import requests

from models import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramNotifier:

    def __init__(self, config: TelegramConfig):

        self.url = f"https://api.telegram.org/" f"bot{config.token}/sendMessage"

        self.chat_id = config.chat_id

        self.company_chat_id = config.company_chat_id

    def send(self, message: str, company: bool = False):

        # основной чат получает все уведомления
        self._safe_send(self.chat_id, message)

        # company чат получает только company alerts
        if company and self.company_chat_id:

            self._safe_send(self.company_chat_id, message)

    def _safe_send(self, chat_id: str, message: str):

        try:

            self._send(chat_id, message)

        except Exception as e:

            logger.exception("Telegram send failed for chat %s: %s", chat_id, e)

    def _send(self, chat_id: str, message: str):

        response = requests.post(
            self.url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )

        logger.info(
            "Telegram response chat=%s: %s %s",
            chat_id,
            response.status_code,
            response.text,
        )

        response.raise_for_status()
