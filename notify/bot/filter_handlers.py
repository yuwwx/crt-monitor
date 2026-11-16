import html
import logging

from .constants import (
    CALLBACK_FILTER_DELETE,
    CALLBACK_FILTERS_PAGE,
    FILTERS_PAGE_SIZE,
)

logger = logging.getLogger(__name__)


class FilterHandlersMixin:

    def _show_filters_menu(
        self, callback_query: dict, page: int, status: str | None = None
    ):

        page, _ = self._clamp_page(
            len(self.company_filters.filters), page, FILTERS_PAGE_SIZE
        )

        self._render_view(
            callback_query,
            self._filters_menu_text(status),
            self._filters_menu_keyboard(page),
            "Фильтры",
        )

    def _confirm_delete_filter(self, callback_query: dict, data: str):

        index = self._callback_int(data, 1)

        page = self._callback_int(data, 2)

        filters = self.company_filters.filters

        if not 0 <= index < len(filters):

            self._show_filters_menu(
                callback_query, page, "⛔ Фильтр не найден"
            )

            return

        pattern = filters[index]

        text = (
            "<b>🗑 Удаление фильтра</b>\n\n"
            f"<code>{html.escape(pattern)}</code>"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Удалить",
                        "callback_data": (
                            f"{CALLBACK_FILTER_DELETE}:{index}:{page}"
                        ),
                    }
                ],
                [
                    {
                        "text": "← Назад",
                        "callback_data": (
                            f"{CALLBACK_FILTERS_PAGE}:{page}"
                        ),
                    }
                ],
            ]
        }

        self._render_view(
            callback_query, text, keyboard, "Подтвердите удаление"
        )

    def _delete_filter(self, callback_query: dict, data: str):

        index = self._callback_int(data, 1)

        page = self._callback_int(data, 2)

        filters = self.company_filters.filters

        if not 0 <= index < len(filters):

            self._show_filters_menu(
                callback_query, page, "⛔ Фильтр не найден"
            )

            return

        pattern = filters[index]

        try:

            self._delete_filter_from_file(pattern)

            filters.pop(index)

        except Exception as e:

            logger.exception("Failed to delete company filter")

            self._show_filters_menu(
                callback_query, page, f"⛔ Ошибка: {html.escape(str(e))}"
            )

            return

        page, _ = self._clamp_page(
            len(filters), page, FILTERS_PAGE_SIZE
        )

        self._show_filters_menu(
            callback_query,
            page,
            f"✅ Фильтр удалён: <code>{html.escape(pattern)}</code>",
        )

        logger.info(
            "Company filter deleted via Telegram bot: %s", pattern
        )
