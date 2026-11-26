"""Input validation shared by the Member 1 CLI and service layer."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation


class ValidationError(ValueError):
    """An input cannot be accepted; safe to display in the member CLI."""


def required_text(value: object, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.")
    result = value.strip()
    if not result or len(result) > max_length or any(ord(c) < 32 for c in result):
        raise ValidationError(
            f"{field} must contain 1 to {max_length} printable characters."
        )
    return result


def optional_text(value: object, field: str, max_length: int) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return required_text(value, field, max_length)


def email_address(value: object) -> str:
    result = required_text(value, "Email", 255).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", result):
        raise ValidationError("Enter a valid email address, such as name@example.com.")
    return result


def calendar_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        raise ValidationError(f"{field} must be a date, not a timestamp.")
    if isinstance(value, date):
        return value
    try:
        return (
            date.fromisoformat(value)
            if isinstance(value, str)
            else _invalid_date(field)
        )
    except ValueError as exc:
        raise ValidationError(f"{field} must use YYYY-MM-DD.") from exc


def _invalid_date(field: str):
    raise ValidationError(f"{field} must use YYYY-MM-DD.")


def birth_date(value: object) -> date:
    result = calendar_date(value, "Date of birth")
    if result > datetime.now(UTC).date():
        raise ValidationError("Date of birth cannot be in the future.")
    return result


def positive_id(value: object, field: str = "Member ID") -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > 2147483647
    ):
        raise ValidationError(f"{field} must be a positive 32-bit integer.")
    return value


def measurement(value: object, field: str, maximum: int) -> Decimal:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number.")
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not (0 < result <= maximum):
            raise ValidationError(
                f"{field} must be greater than 0 and at most {maximum}."
            )
        rounded = result.quantize(Decimal("0.01"))
        if rounded != result:
            raise ValidationError(f"{field} supports at most two decimal places.")
        return rounded
    except (InvalidOperation, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"{field} must be a finite number.") from exc


def heart_rate(value: object) -> int:
    result = measurement(value, "Heart rate (bpm)", 300)
    if result != result.to_integral_value():
        raise ValidationError("Heart rate must be a whole number.")
    return int(result)


def metric_timestamp(value: object = None) -> datetime:
    now = datetime.now(UTC)
    if value is None:
        return now
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as exc:
        raise ValidationError(
            "Timestamp must be ISO 8601 with a timezone offset."
        ) from exc
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise ValidationError(
            "Timestamp requires a timezone offset, for example +00:00."
        )
    result = result.astimezone(UTC)
    if result > now:
        raise ValidationError("Health measurements cannot be dated in the future.")
    return result
