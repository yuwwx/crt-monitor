import yaml

from models import CompanyCertificate

from utils import normalize_serial


def load_company_certificates(path: str = "company_certs.yaml"):

    with open(path, encoding="utf-8") as f:

        data = yaml.safe_load(f)

    result = {}

    for item in data.get("certificates", []):

        serial = normalize_serial(item["serial"])

        result[serial] = CompanyCertificate(
            serial=serial, domain=item["domain"])

    return result
