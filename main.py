import time
import signal
import logging


from config import load_config

from company import load_company_certificates

from company_filters import load_company_filters

from state import StateManager


from api.resolver import CertificateResolver

from notify.telegram import TelegramNotifier

from notify.bot import TelegramBot

from monitor import CRLMonitor

from logger import setup_logger

running = True


def shutdown_handler(signum, frame):

    global running

    running = False


def main():

    config = load_config()

    logger = setup_logger(config.logging.level)

    state = StateManager("state.json")

    state.load()

    company_certs = load_company_certificates()

    company_filters = load_company_filters()

    resolver = CertificateResolver(config.resolver)

    notifier = TelegramNotifier(config.telegram)

    notifier.send("Script started!")

    monitor = CRLMonitor(config, state, company_certs,
                         company_filters, resolver, notifier)

    bot = TelegramBot(config, company_certs, company_filters, state=state)

    bot.start()

    # signal.signal(signal.SIGINT, shutdown_handler)

    # signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("CRL Monitor started")

    while running:

        try:

            monitor.tick()

            state.save()

        except Exception as e:

            logger.exception("Monitor error")

            notifier.send(f"🚨 Monitor error\n\n{e}")

        time.sleep(config.monitor.tick_interval)

    bot.stop()

    state.save()

    logger.info("CRL Monitor stopped")


if __name__ == "__main__":

    main()
