import html
import logging

from .constants import (
    CALLBACK_SOURCE_ACTION,
    CALLBACK_SOURCE_DELETE_CONFIRM,
    SOURCES_PAGE_SIZE,
)

logger = logging.getLogger(__name__)


class SourceHandlersMixin:

    def _show_sources_menu(
        self, callback_query: dict, page: int, status: str | None = None
    ):

        page, _ = self._clamp_page(
            len(self.config.sources), page, SOURCES_PAGE_SIZE
        )

        self._render_view(
            callback_query,
            self._sources_menu_text(status),
            self._sources_menu_keyboard(page),
            "Источники",
        )

    def _show_source_detail(self, callback_query: dict, data: str):

        index = self._callback_int(data, 1)

        page = self._callback_int(data, 2)

        try:

            self._render_view(
                callback_query,
                self._source_detail_text(index),
                self._source_detail_keyboard(index, page),
                "Источник",
            )

        except Exception as e:

            logger.exception("Failed to render source detail")

            self._show_sources_menu(
                callback_query, page, f"⛔ Ошибка: {html.escape(str(e))}"
            )

    def _toggle_source_option(
        self, callback_query: dict, data: str, key: str
    ):

        index = self._callback_int(data, 1)

        page = self._callback_int(data, 2)

        try:

            source = self._source_at(index)

            new_value = not getattr(source, key)

            self._set_source_option(index, key, new_value)

            setattr(source, key, new_value)

            if key == "resolve":

                toast = (
                    f"Resolver {'включён' if new_value else 'отключён'}"
                )

            else:

                toast = (
                    "Company-only "
                    f"{'включён' if new_value else 'отключён'}"
                )

            self._render_view(
                callback_query,
                self._source_detail_text(index),
                self._source_detail_keyboard(index, page),
                toast,
            )

            logger.info(
                "CRL source option changed via Telegram bot: %s %s=%s",
                source.name,
                key,
                new_value,
            )

        except Exception as e:

            logger.exception("Failed to toggle source option")

            self._show_sources_menu(
                callback_query, page, f"⛔ Ошибка: {html.escape(str(e))}"
            )

    def _confirm_delete_source(self, callback_query: dict, data: str):

        index = self._callback_int(data, 1)

        page = self._callback_int(data, 2)

        try:

            source = self._source_at(index)

        except Exception as e:

            self._show_sources_menu(
                callback_query, page, f"⛔ {html.escape(str(e))}"
            )

            return

        text = (
            "<b>🗑 Удаление источника</b>\n\n"
            f"{html.escape(source.name)}\n"
            f"<code>{html.escape(source.url)}</code>\n\n"
            "Источник и его состояние будут удалены."
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Да, удалить",
                        "callback_data": (
                            f"{CALLBACK_SOURCE_DELETE_CONFIRM}:"
                            f"{index}:{page}"
                        ),
                    }
                ],
                [
                    {
                        "text": "← Отмена",
                        "callback_data": (
                            f"{CALLBACK_SOURCE_ACTION}:{index}:{page}"
                        ),
                    }
                ],
            ]
        }

        self._render_view(
            callback_query, text, keyboard, "Подтвердите удаление"
        )

    def _delete_source(self, callback_query: dict, data: str):

        index = self._callback_int(data, 1)

        page = self._callback_int(data, 2)

        try:

            source = self._source_at(index)

            name = source.name

            self._delete_source_from_file(index)

            del self.config.sources[index]

            if self.state is not None:

                self.state.sources.pop(name, None)

        except Exception as e:

            logger.exception("Failed to delete CRL source")

            self._show_sources_menu(
                callback_query, page, f"⛔ Ошибка: {html.escape(str(e))}"
            )

            return

        page, _ = self._clamp_page(
            len(self.config.sources), page, SOURCES_PAGE_SIZE
        )

        self._show_sources_menu(
            callback_query, page, f"✅ Источник удалён: {html.escape(name)}"
        )

        logger.info("CRL source deleted via Telegram bot: %s", name)
