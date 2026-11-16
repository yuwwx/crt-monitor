import threading

from .api import TelegramApiMixin
from .filter_handlers import FilterHandlersMixin
from .handlers import TelegramHandlersMixin
from .settings_handlers import SettingsHandlersMixin
from .source_handlers import SourceHandlersMixin
from .storage import ConfigStorageMixin
from .views import TelegramViewsMixin


class TelegramBot(
    TelegramApiMixin,
    TelegramViewsMixin,
    ConfigStorageMixin,
    TelegramHandlersMixin,
    SourceHandlersMixin,
    FilterHandlersMixin,
    SettingsHandlersMixin,
):

    def __init__(
        self,
        config,
        company_certs: dict,
        company_filters,
        config_path: str = "config.yaml",
        certs_path: str = "company_certs.yaml",
        filters_path: str = "company_filters.yaml",
        state=None,
    ):

        self.config = config

        self.company_certs = company_certs

        self.company_filters = company_filters

        self.config_path = config_path

        self.certs_path = certs_path

        self.filters_path = filters_path

        self.state = state

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
