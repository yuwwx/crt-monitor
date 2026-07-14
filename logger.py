import logging

from logging.handlers import RotatingFileHandler


def setup_logger(level="INFO"):

    logger = logging.getLogger()

    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | " "%(levelname)s | " "%(name)s | " "%(message)s"
    )

    console = logging.StreamHandler()

    console.setFormatter(formatter)

    file = RotatingFileHandler(
        "logs/crl-monitor.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file.setFormatter(formatter)

    logger.addHandler(console)

    logger.addHandler(file)

    return logger
