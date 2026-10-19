import html
import json
import logging
import re
import threading

from datetime import datetime, timezone

import requests
import yaml

from models import CompanyCertificate, SourceConfig

from utils import normalize_serial

logger = logging.getLogger(__name__)

CALLBACK_SET_START_DATE_NOW = "set_start_date_now"
CALLBACK_TOGGLE_RESOLVER = "toggle_resolver_enabled"
CALLBACK_TOGGLE_NOTIFY_ONLY_COMPANY = "toggle_notify_only_company_certificates"
CALLBACK_ADD_CERT = "add_company_cert"
CALLBACK_ADD_FILTER = "add_company_filter"
CALLBACK_ADD_SOURCE = "add_source"

PENDING_ADD_CERT = "add_cert"
PENDING_ADD_FILTER = "add_filter"
PENDING_ADD_SOURCE = "add_source"

PENDING_PROMPTS = {
    PENDING_ADD_CERT: (
        "➕ <b>Добавление сертификата компании</b>\n\n"
        "Отправьте следующим сообщением:\n"
        "<code>SERIAL domain</code>\n\n"
        "Например:\n"
        "<code>2edde3c5977410db7fa7a6b9607b4ec mail2.example.com</code>\n\n"
        "/cancel — отмена"
    ),
    PENDING_ADD_FILTER: (
        "➕ <b>Добавление фильтра компании</b>\n\n"
        "Отправьте следующим сообщением подстроку домена, например:\n"
        "<code>example.com</code>\n\n"
        "/cancel — отмена"
    ),
    PENDING_ADD_SOURCE: (
        "➕ <b>Добавление CRL-источника</b>\n\n"
        "Отправьте следующим сообщением:\n"
        "<code>НАЗВАНИЕ url</code>\n\n"
        "Например:\n"
        "<code>DigiCert G3 http://crl3.digicert.com/office.crl</code>\n\n"
        "Название может содержать пробелы, url — последнее слово.\n"
        "/cancel — отмена"
    ),
}


def format_dt(value: datetime | None) -> str:

    if value is None:

        return "не задано"

    if value.tzinfo is not None:

        value = value.astimezone(timezone.utc)

    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class TelegramBot:

    def __init__(
        self,
        config,
        company_certs: dict,
        company_filters,
        config_path: str = "config.yaml",
        certs_path: str = "company_certs.yaml",
        filters_path: str = "company_filters.yaml",
    ):

        self.config = config

        self.company_certs = company_certs

        self.company_filters = company_filters

        self.config_path = config_path

        self.certs_path = certs_path

        self.filters_path = filters_path

        self.base_url = f"https://api.telegram.org/bot{config.telegram.token}"

        self.allowed_chats = {str(config.telegram.chat_id)}

        if config.telegram.company_chat_id:

            self.allowed_chats.add(str(config.telegram.company_chat_id))

        self.pending: dict[str, str] = {}

        self.panel_messages: dict[str, dict] = {}

        self.offset = 0

        self.stop_event = threading.Event()

        self.thread = threading.Thread(target=self._poll_loop, daemon=True)

    def start(self):

        self.thread.start()

    def stop(self):

        self.stop_event.set()

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

    def _handle_callback(self, callback_query: dict):

        chat_id = str(callback_query["message"]["chat"]["id"])

        data = callback_query.get("data")

        if chat_id not in self.allowed_chats:

            self._answer_callback(callback_query["id"], "⛔ Нет доступа")

            return

        if callback_query.get("message"):

            self.panel_messages[chat_id] = callback_query["message"]

        if data == CALLBACK_SET_START_DATE_NOW:

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

    def _save_cert(self, serial: str, domain: str):

        with open(self.certs_path, encoding="utf-8") as f:

            data = yaml.safe_load(f) or {}

        certs = data.setdefault("certificates", [])

        replaced = False

        for item in certs:

            if normalize_serial(str(item.get("serial", ""))) == serial:

                item["domain"] = domain

                replaced = True

                break

        if not replaced:

            certs.append({"serial": serial, "domain": domain})

        with open(self.certs_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _save_filter(self, pattern: str):

        with open(self.filters_path, encoding="utf-8") as f:

            data = yaml.safe_load(f) or {}

        filters = data.setdefault("filters", [])

        filters.append(pattern)

        with open(self.filters_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _save_source(self, name: str, url: str):

        with open(self.config_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, "sources")

        if bounds is None:

            data = yaml.safe_load(content) or {}

            data.setdefault("sources", []).append({"name": name, "url": url})

            with open(self.config_path, "w", encoding="utf-8") as f:

                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            return

        _, last_indented = bounds

        item = [
            f"  - name: {json.dumps(name, ensure_ascii=False)}\n",
            f"    url: {json.dumps(url, ensure_ascii=False)}\n",
        ]

        lines[last_indented + 1:last_indented + 1] = item

        with open(self.config_path, "w", encoding="utf-8") as f:

            f.write("".join(lines))

    def _section_insert_point(self, lines: list[str], section: str):

        section_re = re.compile(rf"^{re.escape(section)}:(\s|$)")

        start = None

        for i, line in enumerate(lines):

            if section_re.match(line):

                start = i

                break

        if start is None:

            return None

        last_indented = start

        i = start + 1

        while i < len(lines):

            line = lines[i]

            if line.strip() == "":

                i += 1

                continue

            if not line[0].isspace():

                break

            last_indented = i

            i += 1

        return start, last_indented

    def _set_value(self, section: str, key: str, value: str):

        with open(self.config_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, section)

        if bounds is None:

            self._rewrite_value(content, section, key, value)

            return

        start, last_indented = bounds

        key_re = re.compile(
            rf"^([ \t]+{re.escape(key)}:[ \t]*)(\"[^\"]*\"|'[^']*'|[^\n#]*)"
        )

        replaced = False

        for i in range(start + 1, last_indented + 1):

            m = key_re.match(lines[i])

            if m:

                lines[i] = lines[i][: m.start(2)] + value + lines[i][m.end(2):]

                replaced = True

        if not replaced:

            lines.insert(last_indented + 1, f"  {key}: {value}\n")

        with open(self.config_path, "w", encoding="utf-8") as f:

            f.write("".join(lines))

    def _rewrite_value(self, content: str, section: str, key: str, value: str):

        data = yaml.safe_load(content) or {}

        data.setdefault(section, {})[key] = yaml.safe_load(value)

        with open(self.config_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

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

    def _edit_message(self, message: dict, text: str, reply_markup: dict | None = None):

        payload = {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": text,
            "parse_mode": "HTML",
        }

        if reply_markup:

            payload["reply_markup"] = reply_markup

        self._call("editMessageText", payload)

    def _answer_callback(self, callback_query_id: str, text: str):

        try:

            self._call(
                "answerCallbackQuery",
                {"callback_query_id": callback_query_id, "text": text},
            )

        except Exception:

            logger.exception("answerCallbackQuery failed")
