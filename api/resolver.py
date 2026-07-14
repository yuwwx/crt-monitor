import time
import logging

import requests

from models import ResolverConfig

logger = logging.getLogger(__name__)


class CertificateResolver:

    def __init__(self, config: ResolverConfig):

        self.config = config

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
            }
        )

        self.last_request = 0

    def resolve(self, serial: str) -> str | None:

        self.wait_rate_limit()

        try:

            url = f"{self.config.url}/{serial}"

            logger.info("Resolving certificate CN: %s", serial)

            response = self.session.get(url, timeout=self.config.timeout)

            if response.status_code == 404:

                logger.warning("Certificate not found in resolver: %s", serial)

                return None

            response.raise_for_status()

            data = response.json()

            certificate = data.get("certificate")

            if not certificate:

                logger.warning("Empty certificate response for %s", serial)

                return None

            common_name = certificate.get("commonName")

            if common_name:

                logger.info("Resolved CN %s -> %s", serial, common_name)

            else:

                logger.warning("CN not found for %s", serial)

            return common_name

        except requests.RequestException as e:

            logger.warning("Resolver request failed %s: %s", serial, e)

            return None

        except Exception as e:

            logger.exception("Resolver error for %s", serial)

            return None

    def wait_rate_limit(self):

        now = time.time()

        diff = now - self.last_request

        if diff < self.config.request_interval:

            time.sleep(self.config.request_interval - diff)

        self.last_request = time.time()
