def normalize_serial(value: str) -> str:

    return str(value).upper().replace(":", "").lstrip("0")
