import html
import logging

from models import SourceConfig

from .constants import (
    CALLBACK_ADD_CERT,
    CALLBACK_ADD_FILTER,
    CALLBACK_ADD_SOURCE,
    CALLBACK_BACK_TO_PANEL,
    CALLBACK_FILTER_CONFIRM,
    CALLBACK_FILTERS_MENU,
    CALLBACK_FILTERS_PAGE,
    CALLBACK_SET_START_DATE_NOW,
    CALLBACK_SOURCE_ACTION,
    CALLBACK_SOURCE_DELETE,
    CALLBACK_SOURCE_TOGGLE_COMPANY,
    CALLBACK_SOURCE_TOGGLE_RESOLVE,
    CALLBACK_SOURCES_MENU,
    CALLBACK_SOURCES_PAGE,
    CALLBACK_TOGGLE_NOTIFY_ONLY_COMPANY,
    CALLBACK_TOGGLE_RESOLVER,
    FILTERS_PAGE_SIZE,
    SOURCES_PAGE_SIZE,
    format_dt,
)

logger = logging.getLogger(__name__)


class TelegramViewsMixin:

    def _send_panel(self, chat_id: str):

        sent = self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": self._panel_text(),
                "parse_mode": "HTML",
                "reply_markup": self._panel_keyboard(),
            },
        )

        if sent:

            self.panel_messages[chat_id] = sent

    def _panel_text(self, status: str | None = None) -> str:

        resolver_state = "✅ включён" if self.config.resolver.enabled else "❌ отключён"

        notify_state = (
            "только корпоративные"
            if self.config.telegram.notify_only_company_certificates
            else "все"
        )

        text = "<b>CRL Monitor — управление</b>\n\n"

        text += f"🕐 start_date: <code>{format_dt(self.config.monitor.start_date)}</code>\n"

        text += f"🔧 Resolver API: {resolver_state}\n"

        text += f"🔔 Уведомления: {notify_state}\n"

        text += f"📜 Сертификатов: {len(self.company_certs)}\n"

        text += f"🔎 Фильтров: {len(self.company_filters.filters)}\n"

        text += f"🌐 CRL-источников: {len(self.config.sources)}\n"

        if status:

            text += f"\n{status}"

        return text

    def _panel_keyboard(self) -> dict:

        resolver_label = (
            "🔧 Resolver API: ✅ вкл"
            if self.config.resolver.enabled
            else "🔧 Resolver API: ❌ выкл"
        )

        notify_label = (
            "🔔 Только корп. уведомления: ✅ вкл"
            if self.config.telegram.notify_only_company_certificates
            else "🔔 Только корп. уведомления: ❌ выкл"
        )

        return {
            "inline_keyboard": [
                [
                    {
                        "text": "🕐 start_date = сейчас (UTC)",
                        "callback_data": CALLBACK_SET_START_DATE_NOW,
                    }
                ],
                [
                    {
                        "text": resolver_label,
                        "callback_data": CALLBACK_TOGGLE_RESOLVER,
                    }
                ],
                [
                    {
                        "text": notify_label,
                        "callback_data": CALLBACK_TOGGLE_NOTIFY_ONLY_COMPANY,
                    }
                ],
                [
                    {
                        "text": f"🌐 Источники ({len(self.config.sources)})",
                        "callback_data": CALLBACK_SOURCES_MENU,
                    },
                    {
                        "text": f"🔎 Фильтры ({len(self.company_filters.filters)})",
                        "callback_data": CALLBACK_FILTERS_MENU,
                    },
                ],
                [
                    {
                        "text": "➕ Сертификат",
                        "callback_data": CALLBACK_ADD_CERT,
                    },
                    {
                        "text": "➕ Фильтр",
                        "callback_data": CALLBACK_ADD_FILTER,
                    },
                ],
                [
                    {
                        "text": "➕ CRL источник",
                        "callback_data": CALLBACK_ADD_SOURCE,
                    }
                ],
            ]
        }

    @staticmethod
    def _callback_int(data: str, position: int, default: int = 0) -> int:

        parts = data.split(":")

        try:

            return int(parts[position])

        except (IndexError, ValueError):

            return default

    @staticmethod
    def _clamp_page(count: int, page: int, size: int) -> tuple[int, int]:

        total_pages = max(1, (count + size - 1) // size)

        return max(0, min(page, total_pages - 1)), total_pages

    @staticmethod
    def _truncate(text: str, limit: int = 40) -> str:

        if len(text) <= limit:

            return text

        return text[: limit - 1] + "…"

    @staticmethod
    def _page_nav_row(page: int, total_pages: int, prefix: str) -> list[dict]:

        if total_pages <= 1:

            return []

        row = []

        if page > 0:

            row.append(
                {"text": "⬅️", "callback_data": f"{prefix}:{page - 1}"}
            )

        row.append(
            {
                "text": f"{page + 1}/{total_pages}",
                "callback_data": f"{prefix}:{page}",
            }
        )

        if page < total_pages - 1:

            row.append(
                {"text": "➡️", "callback_data": f"{prefix}:{page + 1}"}
            )

        return row

    def _render_view(
        self,
        callback_query: dict,
        text: str,
        keyboard: dict,
        toast: str | None = None,
    ):

        try:

            self._edit_message(
                callback_query["message"], text, reply_markup=keyboard
            )

        finally:

            self._answer_callback(callback_query["id"], toast or "OK")

    def _source_at(self, index: int) -> SourceConfig:

        if not 0 <= index < len(self.config.sources):

            raise ValueError("Источник не найден")

        return self.config.sources[index]

    def _sources_menu_text(self, status: str | None = None) -> str:

        text = (
            "<b>🌐 CRL-источники</b>\n\n"
            f"Всего: {len(self.config.sources)}\n"
            "Выберите источник для управления.\n\n"
            "🔧 — resolver включён, 🚫 — выключен\n"
            "🔔 — только корпоративные уведомления"
        )

        if status:

            text += f"\n\n{status}"

        return text

    def _sources_menu_keyboard(self, page: int) -> dict:

        page, total_pages = self._clamp_page(
            len(self.config.sources), page, SOURCES_PAGE_SIZE
        )

        start = page * SOURCES_PAGE_SIZE

        items = self.config.sources[start: start + SOURCES_PAGE_SIZE]

        rows = []

        for offset, source in enumerate(items):

            index = start + offset

            flags = "🔧" if source.resolve else "🚫"

            if source.notify_only_company_certificates:

                flags += " 🔔"

            rows.append(
                [
                    {
                        "text": f"{flags} {self._truncate(source.name)}",
                        "callback_data": (
                            f"{CALLBACK_SOURCE_ACTION}:{index}:{page}"
                        ),
                    }
                ]
            )

        nav = self._page_nav_row(page, total_pages, CALLBACK_SOURCES_PAGE)

        if nav:

            rows.append(nav)

        rows.append(
            [
                {
                    "text": "➕ Источник",
                    "callback_data": CALLBACK_ADD_SOURCE,
                },
                {
                    "text": "← Назад",
                    "callback_data": CALLBACK_BACK_TO_PANEL,
                },
            ]
        )

        return {"inline_keyboard": rows}

    def _source_detail_text(self, index: int) -> str:

        source = self._source_at(index)

        resolve_state = "✅ включён" if source.resolve else "❌ отключён"

        company_state = (
            "✅ да"
            if source.notify_only_company_certificates
            else "❌ нет"
        )

        return (
            f"<b>🌐 {html.escape(source.name)}</b>\n\n"
            f"URL: <code>{html.escape(source.url)}</code>\n"
            f"🔧 Resolver: {resolve_state}\n"
            f"🔔 Только корпоративные: {company_state}"
        )

    def _source_detail_keyboard(self, index: int, page: int) -> dict:

        source = self._source_at(index)

        resolve_label = (
            "🔧 Отключить resolver"
            if source.resolve
            else "🔧 Включить resolver"
        )

        company_label = (
            "🔔 Отключить company-only"
            if source.notify_only_company_certificates
            else "🔔 Включить company-only"
        )

        return {
            "inline_keyboard": [
                [
                    {
                        "text": resolve_label,
                        "callback_data": (
                            f"{CALLBACK_SOURCE_TOGGLE_RESOLVE}:"
                            f"{index}:{page}"
                        ),
                    }
                ],
                [
                    {
                        "text": company_label,
                        "callback_data": (
                            f"{CALLBACK_SOURCE_TOGGLE_COMPANY}:"
                            f"{index}:{page}"
                        ),
                    }
                ],
                [
                    {
                        "text": "🗑 Удалить источник",
                        "callback_data": (
                            f"{CALLBACK_SOURCE_DELETE}:{index}:{page}"
                        ),
                    }
                ],
                [
                    {
                        "text": "← К списку",
                        "callback_data": (
                            f"{CALLBACK_SOURCES_PAGE}:{page}"
                        ),
                    }
                ],
            ]
        }

    def _filters_menu_text(self, status: str | None = None) -> str:

        text = (
            "<b>🔎 Фильтры компаний</b>\n\n"
            f"Всего: {len(self.company_filters.filters)}\n"
            "Совпадение ищется по CN и DNS-именам сертификата.\n"
            "Нажмите на фильтр, чтобы удалить его."
        )

        if status:

            text += f"\n\n{status}"

        return text

    def _filters_menu_keyboard(self, page: int) -> dict:

        page, total_pages = self._clamp_page(
            len(self.company_filters.filters), page, FILTERS_PAGE_SIZE
        )

        start = page * FILTERS_PAGE_SIZE

        items = self.company_filters.filters[
            start: start + FILTERS_PAGE_SIZE
        ]

        rows = []

        for offset, pattern in enumerate(items):

            index = start + offset

            rows.append(
                [
                    {
                        "text": f"🗑 {self._truncate(pattern)}",
                        "callback_data": (
                            f"{CALLBACK_FILTER_CONFIRM}:{index}:{page}"
                        ),
                    }
                ]
            )

        nav = self._page_nav_row(page, total_pages, CALLBACK_FILTERS_PAGE)

        if nav:

            rows.append(nav)

        rows.append(
            [
                {
                    "text": "➕ Фильтр",
                    "callback_data": CALLBACK_ADD_FILTER,
                },
                {
                    "text": "← Назад",
                    "callback_data": CALLBACK_BACK_TO_PANEL,
                },
            ]
        )

        return {"inline_keyboard": rows}

    def _render_panel(self, message: dict, status: str | None = None):

        self._edit_message(
            message,
            self._panel_text(status),
            reply_markup=self._panel_keyboard(),
        )

    def _refresh_panel(self, chat_id: str):

        panel = self.panel_messages.get(chat_id)

        if not panel:

            return

        try:

            self._edit_message(
                panel,
                self._panel_text(),
                reply_markup=self._panel_keyboard(),
            )

        except Exception:

            logger.debug("Panel refresh failed for chat %s", chat_id)
