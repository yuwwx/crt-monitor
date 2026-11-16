from datetime import datetime, timezone


CALLBACK_SET_START_DATE_NOW = "set_start_date_now"
CALLBACK_TOGGLE_RESOLVER = "toggle_resolver_enabled"
CALLBACK_TOGGLE_NOTIFY_ONLY_COMPANY = "toggle_notify_only_company_certificates"
CALLBACK_ADD_CERT = "add_company_cert"
CALLBACK_ADD_FILTER = "add_company_filter"
CALLBACK_ADD_SOURCE = "add_source"
CALLBACK_BACK_TO_PANEL = "panel"
CALLBACK_SOURCES_MENU = "sources_menu"
CALLBACK_FILTERS_MENU = "filters_menu"
CALLBACK_SOURCE_ACTION = "source"
CALLBACK_SOURCE_TOGGLE_RESOLVE = "source_resolve"
CALLBACK_SOURCE_TOGGLE_COMPANY = "source_company"
CALLBACK_SOURCE_DELETE = "source_delete"
CALLBACK_SOURCE_DELETE_CONFIRM = "source_delete_yes"
CALLBACK_SOURCES_PAGE = "sources_page"
CALLBACK_FILTER_CONFIRM = "filter_confirm"
CALLBACK_FILTER_DELETE = "filter_delete"
CALLBACK_FILTERS_PAGE = "filters_page"

SOURCES_PAGE_SIZE = 6
FILTERS_PAGE_SIZE = 10

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
