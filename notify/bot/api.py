import logging

import requests

logger = logging.getLogger(__name__)


class TelegramApiMixin:

    def _poll_loop(self):

        logger.info("Telegram bot polling started")

        while not self.stop_event.is_set():

            try:

                updates = self._get_updates()

                for update in updates:

                    self.offset = update["update_id"] + 1

                    try:

                        self._handle_update(update)

                    except Exception:

                        logger.exception("Telegram bot update error")

            except Exception as e:

                logger.warning("Telegram bot polling error: %s", e)

                self.stop_event.wait(5)

        logger.info("Telegram bot polling stopped")

    def _get_updates(self):

        response = requests.post(
            f"{self.base_url}/getUpdates",
            json={
                "timeout": 25,
                "offset": self.offset,
                "allowed_updates": ["message", "callback_query"],
            },
            timeout=35,
        )

        data = response.json()

        if not data.get("ok"):

            raise RuntimeError(f"getUpdates failed: {data}")

        return data.get("result", [])

    def _call(self, method: str, payload: dict):

        response = requests.post(
            f"{self.base_url}/{method}", json=payload, timeout=15
        )

        data = response.json()

        if not data.get("ok"):

            raise RuntimeError(f"{method} failed: {data}")

        return data.get("result")

    def _reply(self, message: dict, text: str):

        self._call(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": text,
                "parse_mode": "HTML",
                "reply_to_message_id": message["message_id"],
            },
        )

    def _edit_message(self, message: dict, text: str, reply_markup: dict | None = None):

        payload = {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": text,
            "parse_mode": "HTML",
        }

        if reply_markup:

            payload["reply_markup"] = reply_markup

        try:

            self._call("editMessageText", payload)

        except RuntimeError as e:

            if "message is not modified" in str(e):

                return

            raise

    def _answer_callback(self, callback_query_id: str, text: str):

        try:

            self._call(
                "answerCallbackQuery",
                {"callback_query_id": callback_query_id, "text": text},
            )

        except Exception:

            logger.exception("answerCallbackQuery failed")
