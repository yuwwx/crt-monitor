import time
import logging

import requests

from models import SourceConfig, CRLConfig

logger = logging.getLogger(__name__)


class CRLDownloadError(Exception):

    pass


class CRLClient:

    def __init__(self, config: CRLConfig):

        self.config = config

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
            }
        )

    def download(self, source: SourceConfig) -> bytes:

        try:

            logger.info("Downloading CRL: %s", source.name)

            response = self.session.get(source.url, timeout=self.config.timeout)

            response.raise_for_status()

            if len(response.content) < 100:

                raise Exception("CRL content too small")

            return response.content

        except Exception as e:

            logger.warning("CRL download failed: %s: %s", source.name, e)

            raise CRLDownloadError(str(e))
