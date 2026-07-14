def warning(crl_name, serial, revocation_date, reason=None, cn=None):

    cn_text = f"CN: {cn}\n" if cn else ""

    return f"""

<b>⚠️ Новый отозванный сертификат</b>

CRL:
{crl_name}

Сертификат:
{cn_text}Serial: {serial}

Дата отзыва:
{revocation_date}

Причина:
{reason or "Не указана"}
""".strip()


def corporate_alert(crl_name, serial, domain, revocation_date, reason=None):

    return f"""
<b>🚨 Сертификат компании отозван!</b>

CRL:
{crl_name}

Сертификат:
CN:
{domain}
Serial:
{serial}

Дата отзыва:
{revocation_date}

Причина:
{reason or "Не указана"}
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
