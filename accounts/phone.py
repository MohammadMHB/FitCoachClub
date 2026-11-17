"""Canonical Iranian mobile numbers for account lookup and SMS delivery."""
import re
from django.core.exceptions import ValidationError

DIGIT_TRANSLATION = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_mobile(value):
    value = str(value or '').translate(DIGIT_TRANSLATION).strip()
    value = re.sub(r'[\s\-()]', '', value)
    if value.startswith('0098'):
        value = '0' + value[4:]
    elif value.startswith('+98'):
        value = '0' + value[3:]
    elif value.startswith('98'):
        value = '0' + value[2:]
    if not re.fullmatch(r'09[0-9]{9}', value):
        raise ValidationError('شمارهٔ موبایل معتبر وارد کنید؛ مانند 09123456789.')
    return value
