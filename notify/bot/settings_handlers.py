import logging

from datetime import datetime, timezone

from .constants import format_dt

logger = logging.getLogger(__name__)


class SettingsHandlersMixin:

    def _callback_set_start_date(self, callback_query: dict):

        try:

            old_value = self.config.monitor.start_date

            new_value = datetime.now(timezone.utc).replace(microsecond=0)

            self._set_value("monitor", "start_date", f'"{format_dt(new_value)}"')

            self.config.monitor.start_date = new_value

            status = (
                f"✅ start_date: <code>{format_dt(old_value)}</code> → "
                f"<code>{format_dt(new_value)}</code>"
            )

            self._render_panel(callback_query["message"], status)

            self._answer_callback(callback_query["id"], "Обновлено")

            logger.info(
                "start_date updated via Telegram bot: %s -> %s",
                format_dt(old_value),
                format_dt(new_value),
            )

        except Exception as e:

            logger.exception("Failed to update start_date")

            self._answer_callback(callback_query["id"], f"Ошибка: {e}")

    def _callback_toggle(
        self,
        callback_query: dict,
        enabled: bool,
        enable_status: str,
        disable_status: str,
        enable_toast: str,
        disable_toast: str,
        apply,
    ):

        try:

            new_value = not enabled

            apply(new_value)

            status = enable_status if new_value else disable_status

            self._render_panel(callback_query["message"], status)

            self._answer_callback(
                callback_query["id"], enable_toast if new_value else disable_toast
            )

            logger.info("Setting toggled via Telegram bot: %s", status)

        except Exception as e:

            logger.exception("Failed to toggle setting")

            self._answer_callback(callback_query["id"], f"Ошибка: {e}")

    def _apply_resolver_enabled(self, value: bool):

        self._set_value("resolver", "enabled", "true" if value else "false")

        self.config.resolver.enabled = value

    def _apply_notify_only_company(self, value: bool):

        self._set_value(
            "telegram",
            "notify_only_company_certificates",
            "true" if value else "false",
        )

        self.config.telegram.notify_only_company_certificates = value
