import json
import logging
import re

import yaml

from utils import normalize_serial

logger = logging.getLogger(__name__)


class ConfigStorageMixin:

    def _save_cert(self, serial: str, domain: str):

        with open(self.certs_path, encoding="utf-8") as f:

            data = yaml.safe_load(f) or {}

        certs = data.setdefault("certificates", [])

        replaced = False

        for item in certs:

            if normalize_serial(str(item.get("serial", ""))) == serial:

                item["domain"] = domain

                replaced = True

                break

        if not replaced:

            certs.append({"serial": serial, "domain": domain})

        with open(self.certs_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _save_filter(self, pattern: str):

        with open(self.filters_path, encoding="utf-8") as f:

            data = yaml.safe_load(f) or {}

        filters = data.setdefault("filters", [])

        filters.append(pattern)

        with open(self.filters_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _save_source(self, name: str, url: str):

        with open(self.config_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, "sources")

        if bounds is None:

            data = yaml.safe_load(content) or {}

            data.setdefault("sources", []).append({"name": name, "url": url})

            with open(self.config_path, "w", encoding="utf-8") as f:

                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            return

        _, last_indented = bounds

        item = [
            f"  - name: {json.dumps(name, ensure_ascii=False)}\n",
            f"    url: {json.dumps(url, ensure_ascii=False)}\n",
        ]

        lines[last_indented + 1:last_indented + 1] = item

        with open(self.config_path, "w", encoding="utf-8") as f:

            f.write("".join(lines))

    @staticmethod
    def _source_item_starts(
        lines: list[str], start: int, last: int
    ) -> list[int]:

        return [
            i
            for i in range(start + 1, last + 1)
            if re.match(r"^[ \t]*-[ \t]", lines[i])
        ]

    def _set_source_option(self, index: int, key: str, value: bool):

        token = "true" if value else "false"

        with open(self.config_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, "sources")

        if bounds is None:

            self._rewrite_source_option(index, key, value)

            return

        start, last = bounds

        starts = self._source_item_starts(lines, start, last)

        if index >= len(starts):

            self._rewrite_source_option(index, key, value)

            return

        block_start = starts[index]

        block_end = (
            starts[index + 1]
            if index + 1 < len(starts)
            else last + 1
        )

        key_re = re.compile(
            rf"^([ \t]+{re.escape(key)}:[ \t]*)([^\s#]+)"
        )

        for i in range(block_start + 1, block_end):

            m = key_re.match(lines[i])

            if m:

                lines[i] = (
                    lines[i][: m.start(2)]
                    + token
                    + lines[i][m.end(2):]
                )

                break

        else:

            item_indent = re.match(
                r"^([ \t]*)", lines[block_start]
            ).group(1)

            lines.insert(block_end, f"{item_indent}  {key}: {token}\n")

        with open(self.config_path, "w", encoding="utf-8") as f:

            f.write("".join(lines))

    def _rewrite_source_option(self, index: int, key: str, value: bool):

        with open(self.config_path, encoding="utf-8") as f:

            data = yaml.safe_load(f) or {}

        sources = data.get("sources", [])

        if index >= len(sources):

            raise ValueError("Источник не найден")

        sources[index][key] = value

        with open(self.config_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _delete_source_from_file(self, index: int):

        with open(self.config_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, "sources")

        if bounds is not None:

            start, last = bounds

            starts = self._source_item_starts(lines, start, last)

            if index < len(starts):

                block_start = starts[index]

                block_end = (
                    starts[index + 1]
                    if index + 1 < len(starts)
                    else last + 1
                )

                del lines[block_start:block_end]

                with open(self.config_path, "w", encoding="utf-8") as f:

                    f.write("".join(lines))

                return

        data = yaml.safe_load(content) or {}

        sources = data.get("sources", [])

        if index < len(sources):

            del sources[index]

            with open(self.config_path, "w", encoding="utf-8") as f:

                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _delete_filter_from_file(self, pattern: str):

        with open(self.filters_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, "filters")

        if bounds is not None:

            start, last = bounds

            for i in range(start + 1, last + 1):

                m = re.match(r"^[ \t]*-[ \t]*(.+?)\s*$", lines[i])

                if not m:

                    continue

                value = m.group(1).strip()

                if (
                    value.startswith(("\"", "'"))
                    and value.endswith(value[0])
                ):

                    value = value[1:-1]

                if value.lower() == pattern.lower():

                    del lines[i]

                    with open(
                        self.filters_path, "w", encoding="utf-8"
                    ) as f:

                        f.write("".join(lines))

                    return

        data = yaml.safe_load(content) or {}

        data["filters"] = [
            item
            for item in data.get("filters", [])
            if str(item).lower() != pattern.lower()
        ]

        with open(self.filters_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _section_insert_point(self, lines: list[str], section: str):

        section_re = re.compile(rf"^{re.escape(section)}:(\s|$)")

        start = None

        for i, line in enumerate(lines):

            if section_re.match(line):

                start = i

                break

        if start is None:

            return None

        last_indented = start

        i = start + 1

        while i < len(lines):

            line = lines[i]

            if line.strip() == "":

                i += 1

                continue

            if not line[0].isspace():

                break

            last_indented = i

            i += 1

        return start, last_indented

    def _set_value(self, section: str, key: str, value: str):

        with open(self.config_path, encoding="utf-8") as f:

            content = f.read()

        lines = content.splitlines(keepends=True)

        bounds = self._section_insert_point(lines, section)

        if bounds is None:

            self._rewrite_value(content, section, key, value)

            return

        start, last_indented = bounds

        key_re = re.compile(
            rf"^([ \t]+{re.escape(key)}:[ \t]*)(\"[^\"]*\"|'[^']*'|[^\n#]*)"
        )

        replaced = False

        for i in range(start + 1, last_indented + 1):

            m = key_re.match(lines[i])

            if m:

                lines[i] = lines[i][: m.start(2)] + value + lines[i][m.end(2):]

                replaced = True

        if not replaced:

            lines.insert(last_indented + 1, f"  {key}: {value}\n")

        with open(self.config_path, "w", encoding="utf-8") as f:

            f.write("".join(lines))

    def _rewrite_value(self, content: str, section: str, key: str, value: str):

        data = yaml.safe_load(content) or {}

        data.setdefault(section, {})[key] = yaml.safe_load(value)

        with open(self.config_path, "w", encoding="utf-8") as f:

            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
