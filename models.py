from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CRLConfig:
    timeout: int
    unavailable_interval: int


@dataclass
class SourceConfig:
    name: str
    url: str
    resolve: bool = True
    notify_only_company_certificates: bool = False


@dataclass
class ResolverConfig:
    url: str
    timeout: int
    request_interval: float
    enabled: bool = True


@dataclass
class TelegramConfig:
    token: str
    chat_id: str
    company_chat_id: str | None = None
    notify_only_company_certificates: bool = False


@dataclass
class MonitorConfig:
    check_interval: int
    tick_interval: int
    start_date: datetime


@dataclass
class LoggingConfig:
    level: str


@dataclass
class Config:

    monitor: MonitorConfig
    crl: CRLConfig
    resolver: ResolverConfig
    telegram: TelegramConfig
    logging: LoggingConfig
    sources: list[SourceConfig]


@dataclass
class CompanyCertificate:

    serial: str
    domain: str


@dataclass
class RevokedCertificate:

    serial: str
    revocation_date: datetime
    reason: str | None = None


@dataclass
class SourceState:

    status: str = "available"

    processed: set[str] = field(default_factory=set)

    last_success: datetime | None = None

    unavailable_since: datetime | None = None

    next_check: datetime | None = None

    # количество неуспешных циклов проверки
    failed_attempts: int = 0

    # отправляли ли уже alert
    alert_sent: bool = False
