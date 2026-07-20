import logging

from datetime import datetime, timezone, timedelta


from crl.client import CRLClient, CRLDownloadError

from crl.parser import CRLParser


from notify.templates import warning, corporate_alert, crl_down, crl_recovered

logger = logging.getLogger(__name__)


class CRLMonitor:

    def __init__(self, config, state, company_certs, company_filters, resolver, notifier):

        self.config = config

        self.state = state

        self.company_certs = company_certs

        self.company_filters = company_filters

        self.resolver = resolver

        self.notifier = notifier

        self.client = CRLClient(config.crl)

        self.parser = CRLParser()

    def tick(self):

        now = datetime.now(timezone.utc)

        for source in self.config.sources:

            source_state = self.state.get(source.name)

            if source_state.next_check is None or now >= source_state.next_check:

                self.check_source(source)

    def check_source(self, source):

        state = self.state.get(source.name)

        try:

            data = self.client.download(source)

            logger.info("CRL downloaded: %s, size=%s bytes",
                        source.name, len(data))

        except CRLDownloadError as e:

            logger.warning("CRL unavailable: %s: %s", source.name, e)

            self.handle_unavailable(source, state)

            return

        self.handle_available(source, state, data)

    def handle_unavailable(self, source, state):

        now = datetime.now(timezone.utc)

        state.failed_attempts += 1

        logger.warning("%s unavailable. Attempt %s",
                       source.name, state.failed_attempts)

        if state.status != "unavailable":

            state.status = "unavailable"

            state.unavailable_since = now

        if state.failed_attempts >= 3 and not state.alert_sent:

            self.notifier.send(crl_down(source.name))

            state.alert_sent = True

        if state.failed_attempts >= 3:

            interval = self.config.crl.unavailable_interval

        else:

            interval = self.config.monitor.check_interval

        state.next_check = now + timedelta(seconds=interval)

    def handle_available(self, source, state, data):

        now = datetime.now(timezone.utc)

        if state.status == "unavailable":

            downtime = now - state.unavailable_since

            self.notifier.send(crl_recovered(source.name, str(downtime)))

        state.status = "available"

        state.unavailable_since = None

        state.failed_attempts = 0

        state.alert_sent = False

        state.last_success = now

        state.next_check = now + \
            timedelta(seconds=self.config.monitor.check_interval)

        self.process_crl(source, state, data)

    def process_crl(self, source, state, data):

        logger.info("Parsing CRL: %s", source.name)

        revoked_certificates = self.parser.parse(data)

        total = len(revoked_certificates)

        skipped_old = 0

        skipped_processed = 0

        new_certificates = 0

        logger.info("CRL %s contains %s revoked certificates",
                    source.name, total)

        for cert in revoked_certificates:

            if cert.revocation_date < self.config.monitor.start_date:

                skipped_old += 1

                continue

            serial = cert.serial

            if serial in state.processed:

                skipped_processed += 1

                continue

            new_certificates += 1

            logger.warning(
                "New revoked certificate found: %s (date=%s, reason=%s)",
                serial,
                cert.revocation_date,
                cert.reason,
            )

            self.process_new_certificate(source, cert)

            state.processed.add(serial)

            self.state.save()

        logger.info(
            "CRL %s processing completed: total=%s, new=%s, old_skipped=%s, already_processed=%s",
            source.name,
            total,
            new_certificates,
            skipped_old,
            skipped_processed,
        )

    def process_new_certificate(self, source, cert):

        serial = cert.serial

        # 1. Проверяем точное совпадение по serial

        company_cert = self.company_certs.get(serial)

        if company_cert:

            logger.error(
                "Corporate certificate detected by serial: %s",
                serial
            )

            self.notifier.send(

                corporate_alert(
                    source.name,
                    serial,
                    company_cert.domain,
                    cert.revocation_date,
                    cert.reason,
                ),

                company=True
            )

            return

        # 2. Получаем информацию через API

        cert_info = self.resolver.resolve(serial)

        cn = None

        values = []

        if cert_info:

            cn = cert_info.common_name

            if cert_info.common_name:

                values.append(
                    cert_info.common_name
                )

            values.extend(
                cert_info.dns_names
            )

        # 3. Проверяем по фильтрам

        company_match = None

        if values:

            company_match = self.company_filters.match(
                values
            )

        if company_match:

            logger.error(
                "Corporate certificate detected by filter '%s': serial=%s values=%s",
                company_match,
                serial,
                values
            )

            self.notifier.send(

                corporate_alert(
                    source.name,
                    serial,
                    cn or company_match,
                    cert.revocation_date,
                    cert.reason,
                ),

                company=True
            )

            return

        # 4. Обычный warning

        logger.warning(
            "New revoked certificate: serial=%s CN=%s",
            serial,
            cn
        )

        self.notifier.send(

            warning(
                source.name,
                serial,
                cert.revocation_date,
                cert.reason,
                cn
            )
        )
