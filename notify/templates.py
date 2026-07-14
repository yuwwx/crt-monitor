def warning(crl_name, serial, revocation_date, reason=None, cn=None):

    certificate = f"CN: {cn}" if cn else f"Serial: {serial}"

    return f"""

<b>⚠️ Новый отозванный сертификат</b>

CRL:
{crl_name}

Сертификат:
{certificate}

Дата отзыва:
{revocation_date}

Причина:
{reason or "Unknown"}
""".strip()


def corporate_alert(crl_name, serial, domain, revocation_date, reason=None):

    return f"""
<b>🚨 Сертификат компании отозван!</b>

CRL:
{crl_name}

Домен:
{domain}

Сертификат:
{serial}

Дата отзыва:
{revocation_date}

Причина:
{reason or "Unknown"}
""".strip()


def crl_down(name):

    return f"""
🚨 Ошибка

CRL недоступен

Источник:
{name}
""".strip()


def crl_recovered(name, downtime):

    return f"""
ℹ️ Информационное сообщение

CRL восстановлен

Источник:
{name}

Время недоступности:
{downtime}
""".strip()
