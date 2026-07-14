import json
import yaml
import sys
from datetime import datetime, timezone


def is_active(cert):
    now = datetime.now(timezone.utc)

    not_before = datetime.fromisoformat(cert["notBefore"].replace("Z", "+00:00"))

    not_after = datetime.fromisoformat(cert["notAfter"].replace("Z", "+00:00"))

    return not_before <= now <= not_after


def convert_json_to_yaml(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = []

    for cert in data.get("results", []):
        if not is_active(cert):
            continue

        result.append(
            {
                "serial": cert.get("serialNumber").lower(),
                "domain": cert.get("commonName"),
            }
        )

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert.py input.json output.yaml")
        sys.exit(1)

    convert_json_to_yaml(sys.argv[1], sys.argv[2])
