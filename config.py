import yaml

from datetime import datetime

from models import (
    Config,
    MonitorConfig,
    CRLConfig,
    SourceConfig,
    ResolverConfig,
    TelegramConfig,
    LoggingConfig,
)


def load_config(path: str = "config.yaml") -> Config:

    with open(path, encoding="utf-8") as f:

        data = yaml.safe_load(f)

    config = Config(
        monitor=MonitorConfig(
            check_interval=data["monitor"]["check_interval"],
            tick_interval=data["monitor"]["tick_interval"],
            start_date=datetime.fromisoformat(
                data["monitor"]["start_date"].replace("Z", "+00:00")
            ),
        ),
        crl=CRLConfig(
            timeout=data["crl"]["timeout"],
            unavailable_interval=data["crl"]["unavailable_interval"],
        ),
        resolver=ResolverConfig(
            url=data["resolver"]["url"],
            timeout=data["resolver"]["timeout"],
            request_interval=data["resolver"]["request_interval"],
            enabled=data["resolver"].get("enabled", True),
        ),
        telegram=TelegramConfig(
            token=data["telegram"]["token"],
            chat_id=str(data["telegram"]["chat_id"]),
            company_chat_id=data["telegram"].get("company_chat_id"),
            send_all_to_company_chat_only=data["telegram"].get("send_all_to_company_chat_only", False),
        ),
        logging=LoggingConfig(level=data["logging"]["level"]),
        sources=[
            SourceConfig(name=item["name"], url=item["url"]) for item in data["sources"]
        ],
    )

    validate(config)

    return config


def validate(config: Config):

    if not config.sources:
        raise ValueError("CRL sources list is empty")

    if not config.telegram.token:
        raise ValueError("Telegram token is empty")

    if not config.telegram.chat_id:
        raise ValueError("Telegram chat id is empty")

    if config.telegram.send_all_to_company_chat_only and not config.telegram.company_chat_id:
        raise ValueError("send_all_to_company_chat_only is True but company_chat_id is not set")
