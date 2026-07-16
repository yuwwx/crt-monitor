import logging
import yaml

logger = logging.getLogger(__name__)


class CompanyFilters:

    def __init__(self, filters: list[str]):

        self.filters = [
            item.lower()
            for item in filters
        ]

    def match(
            self,
            values: list[str]
    ) -> str | None:

        for value in values:

            if not value:
                continue

            value = value.lower()

            for pattern in self.filters:

                if pattern in value:

                    return pattern

        return None


def load_company_filters(path: str = "company_filters.yaml"):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        data = yaml.safe_load(file)

    return CompanyFilters(
        data.get("filters", [])
    )
