import html
import logging
import re

from models import CompanyCertificate, SourceConfig

from utils import normalize_serial

from .constants import (
    CALLBACK_ADD_CERT,
    CALLBACK_ADD_FILTER,
    CALLBACK_ADD_SOURCE,
    CALLBACK_BACK_TO_PANEL,
    CALLBACK_FILTER_CONFIRM,
    CALLBACK_FILTER_DELETE,
    CALLBACK_FILTERS_MENU,
    CALLBACK_FILTERS_PAGE,
    CALLBACK_SET_START_DATE_NOW,
    CALLBACK_SOURCE_ACTION,
    CALLBACK_SOURCE_DELETE,
    CALLBACK_SOURCE_DELETE_CONFIRM,
    CALLBACK_SOURCE_TOGGLE_COMPANY,
    CALLBACK_SOURCE_TOGGLE_RESOLVE,
    CALLBACK_SOURCES_MENU,
    CALLBACK_SOURCES_PAGE,
    CALLBACK_TOGGLE_NOTIFY_ONLY_COMPANY,
    CALLBACK_TOGGLE_RESOLVER,
    PENDING_ADD_CERT,
    PENDING_ADD_FILTER,
    PENDING_ADD_SOURCE,
    PENDING_PROMPTS,
)

logger = logging.getLogger(__name__)


class TelegramHandlersMixin:

    def _handle_update(self, update: dict):

        message = update.get("message")

        callback_query = update.get("callback_query")

        if message:

            self._handle_message(message)

        elif callback_query:

            self._handle_callback(callback_query)

    def _handle_message(self, message: dict):

        chat_id = str(message["chat"]["id"])

        if chat_id not in self.allowed_chats:

            logger.warning("Telegram bot: ignored chat %s", chat_id)

            return

        text = (message.get("text") or "").strip()

        if not text:

            return

        if text.startswith("/"):

            command = text.split()[0].split("@")[0]

            if command == "/cancel":

                cancelled = self.pending.pop(chat_id, None)

                if cancelled:

                    self._reply(message, "⛔ Отменено")

            elif command in ("/start", "/help", "/settings", "/start_date"):

                self._send_panel(chat_id)

            return

        mode = self.pending.pop(chat_id, None)

        if mode == PENDING_ADD_CERT:

            self._process_cert_input(message, text)

        elif mode == PENDING_ADD_FILTER:

            self._process_filter_input(message, text)

        elif mode == PENDING_ADD_SOURCE:

            self._process_source_input(message, text)

    def _handle_callback(self, callback_query: dict):

        chat_id = str(callback_query["message"]["chat"]["id"])

        data = callback_query.get("data")

        if chat_id not in self.allowed_chats:

            self._answer_callback(callback_query["id"], "⛔ Нет доступа")

            return

        if callback_query.get("message"):

            self.panel_messages[chat_id] = callback_query["message"]

        if data == CALLBACK_BACK_TO_PANEL:

            self._render_panel(callback_query["message"])

            self._answer_callback(callback_query["id"], "Главное меню")

        elif data == CALLBACK_SOURCES_MENU:

            self._show_sources_menu(callback_query, 0)

        elif data == CALLBACK_FILTERS_MENU:

            self._show_filters_menu(callback_query, 0)

        elif data and data.startswith(CALLBACK_SOURCES_PAGE + ":"):

            self._show_sources_menu(
                callback_query, self._callback_int(data, 1)
            )

        elif data and data.startswith(CALLBACK_SOURCE_TOGGLE_RESOLVE + ":"):

            self._toggle_source_option(callback_query, data, "resolve")

        elif data and data.startswith(CALLBACK_SOURCE_TOGGLE_COMPANY + ":"):

            self._toggle_source_option(
                callback_query, data, "notify_only_company_certificates"
            )

        elif data and data.startswith(CALLBACK_SOURCE_DELETE_CONFIRM + ":"):

            self._delete_source(callback_query, data)

        elif data and data.startswith(CALLBACK_SOURCE_DELETE + ":"):

            self._confirm_delete_source(callback_query, data)

        elif data and data.startswith(CALLBACK_SOURCE_ACTION + ":"):

            self._show_source_detail(callback_query, data)

        elif data and data.startswith(CALLBACK_FILTERS_PAGE + ":"):

            self._show_filters_menu(
                callback_query, self._callback_int(data, 1)
            )

        elif data and data.startswith(CALLBACK_FILTER_DELETE + ":"):

            self._delete_filter(callback_query, data)

        elif data and data.startswith(CALLBACK_FILTER_CONFIRM + ":"):

            self._confirm_delete_filter(callback_query, data)

        elif data == CALLBACK_SET_START_DATE_NOW:

            self._callback_set_start_date(callback_query)

        elif data == CALLBACK_TOGGLE_RESOLVER:

            self._callback_toggle(
                callback_query,
                enabled=self.config.resolver.enabled,
                enable_status="✅ Resolver API включён",
                disable_status="✅ Resolver API отключён",
                enable_toast="Resolver API включён",
                disable_toast="Resolver API отключён",
                apply=lambda value: self._apply_resolver_enabled(value),
            )

        elif data == CALLBACK_TOGGLE_NOTIFY_ONLY_COMPANY:

            if not self.config.telegram.company_chat_id:

                self._answer_callback(
                    callback_query["id"], "⚠️ company_chat_id не задан"
                )

                return

            self._callback_toggle(
                callback_query,
                enabled=self.config.telegram.notify_only_company_certificates,
                enable_status="✅ Уведомления: только корпоративные",
                disable_status="✅ Уведомления: все",
                enable_toast="Уведомления: только корпоративные",
                disable_toast="Уведомления: все",
                apply=lambda value: self._apply_notify_only_company(value),
            )

        elif data == CALLBACK_ADD_CERT:

            self.pending[chat_id] = PENDING_ADD_CERT

            self._render_panel(
                callback_query["message"], PENDING_PROMPTS[PENDING_ADD_CERT]
            )

            self._answer_callback(callback_query["id"], "Жду serial и domain")

        elif data == CALLBACK_ADD_FILTER:

            self.pending[chat_id] = PENDING_ADD_FILTER

            self._render_panel(
                callback_query["message"], PENDING_PROMPTS[PENDING_ADD_FILTER]
            )

            self._answer_callback(callback_query["id"], "Жду фильтр")

        elif data == CALLBACK_ADD_SOURCE:

            self.pending[chat_id] = PENDING_ADD_SOURCE

            self._render_panel(
                callback_query["message"], PENDING_PROMPTS[PENDING_ADD_SOURCE]
            )

            self._answer_callback(callback_query["id"], "Жду название и url")

        else:

            self._answer_callback(callback_query["id"], "Неизвестное действие")

    def _process_cert_input(self, message: dict, text: str):

        chat_id = str(message["chat"]["id"])

        try:

            parts = text.split()

            if len(parts) != 2:

                raise ValueError(
                    "Нужны ровно два значения через пробел: SERIAL domain"
                )

            serial = normalize_serial(parts[0])

            domain = parts[1]

            if not re.fullmatch(r"[0-9A-F]+", serial):

                raise ValueError(f"Serial должен быть hex-строкой: {serial}")

            existed = serial in self.company_certs

            self._save_cert(serial, domain)

            self.company_certs[serial] = CompanyCertificate(
                serial=serial, domain=domain
            )

            action = "обновлён" if existed else "добавлен"

            self._reply(
                message,
                f"✅ Сертификат {action}:\n"
                f"<code>{html.escape(serial)}</code> → "
                f"<code>{html.escape(domain)}</code>",
            )

            self._refresh_panel(chat_id)

            logger.info(
                "Company certificate %s via Telegram bot: %s -> %s",
                action,
                serial,
                domain,
            )

        except Exception as e:

            self._reply(message, f"⛔ Ошибка: {html.escape(str(e))}")

    def _process_filter_input(self, message: dict, text: str):

        chat_id = str(message["chat"]["id"])

        try:

            pattern = text.strip()

            if not pattern or len(pattern.split()) != 1:

                raise ValueError("Фильтр должен быть одним словом без пробелов")

            existing = [f.lower() for f in self.company_filters.filters]

            if pattern.lower() in existing:

                raise ValueError("Такой фильтр уже существует")

            self._save_filter(pattern)

            self.company_filters.filters.append(pattern.lower())

            self._reply(
                message,
                f"✅ Фильтр добавлен: <code>{html.escape(pattern)}</code>",
            )

            self._refresh_panel(chat_id)

            logger.info(
                "Company filter added via Telegram bot: %s", pattern
            )

        except Exception as e:

            self._reply(message, f"⛔ Ошибка: {html.escape(str(e))}")

    def _process_source_input(self, message: dict, text: str):

        chat_id = str(message["chat"]["id"])

        try:

            parts = text.split()

            if len(parts) < 2:

                raise ValueError("Нужно: НАЗВАНИЕ url (url — последнее слово)")

            url = parts[-1]

            name = " ".join(parts[:-1])

            if not re.match(r"^https?://", url, re.IGNORECASE):

                raise ValueError(f"URL должен начинаться с http:// или https://: {url}")

            existing = [s.name.lower() for s in self.config.sources]

            if name.lower() in existing:

                raise ValueError(f"Источник с именем '{name}' уже существует")

            self._save_source(name, url)

            self.config.sources.append(SourceConfig(name=name, url=url))

            self._reply(
                message,
                f"✅ CRL-источник добавлен:\n"
                f"{html.escape(name)}\n"
                f"<code>{html.escape(url)}</code>",
            )

            self._refresh_panel(chat_id)

            logger.info(
                "CRL source added via Telegram bot: %s -> %s", name, url
            )

        except Exception as e:

            self._reply(message, f"⛔ Ошибка: {html.escape(str(e))}")
