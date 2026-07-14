from cryptography import x509
from cryptography.hazmat.backends import default_backend

from models import RevokedCertificate
from utils import normalize_serial


class CRLParser:

    def parse(self, data: bytes) -> list[RevokedCertificate]:

        crl = self.load(data)

        result = []

        for revoked in crl:

            serial = normalize_serial(format(revoked.serial_number, "X"))

            reason = None

            try:

                extension = revoked.extensions.get_extension_for_class(x509.CRLReason)

                reason = extension.value.reason.name

            except x509.ExtensionNotFound:

                pass

            result.append(
                RevokedCertificate(
                    serial=serial,
                    revocation_date=revoked.revocation_date_utc,
                    reason=reason,
                )
            )

        return result

    def load(self, data: bytes):

        if data.startswith(b"-----BEGIN"):

            return x509.load_pem_x509_crl(data, default_backend())

        return x509.load_der_x509_crl(data, default_backend())
