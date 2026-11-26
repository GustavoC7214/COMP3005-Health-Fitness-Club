"""Input edge cases run without a database; these do not prove persistence."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.utils import validators as v


@pytest.mark.parametrize(
    "value", ["bad", "a@", "@b.com", "a b@c.com", "a@b@c.com", "a@b", None]
)
def test_email_rejects_invalid_values(value):
    with pytest.raises(v.ValidationError):
        v.email_address(value)


def test_email_and_names_are_normalized():
    assert v.email_address(" Benson@Example.COM ") == "benson@example.com"
    assert v.required_text(" 李 ", "Name", 100) == "李"
    assert v.optional_text(" ", "Phone", 30) is None


@pytest.mark.parametrize("value", [True, 0, -1, 1.5, "1", None, 2147483648])
def test_member_id_rejects_invalid_values(value):
    with pytest.raises(v.ValidationError):
        v.positive_id(value)


@pytest.mark.parametrize(
    "value", [True, -1, 0, "NaN", "Infinity", "x", "75.123", 501, None]
)
def test_weight_rejects_invalid_values(value):
    with pytest.raises(v.ValidationError):
        v.measurement(value, "Weight", 500)


def test_valid_measurements_and_dates():
    assert v.measurement("75.20", "Weight", 500) == Decimal("75.20")
    assert v.heart_rate("70") == 70
    assert v.birth_date("2000-02-29") == date(2000, 2, 29)
    assert v.metric_timestamp("2020-01-01T08:00:00-05:00") == datetime(
        2020, 1, 1, 13, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "value", ["2001-02-29", "2999-01-01", None, datetime(2000, 1, 1)]
)
def test_invalid_birth_dates(value):
    with pytest.raises(v.ValidationError):
        v.birth_date(value)


@pytest.mark.parametrize(
    "value", ["bad", "2020-01-01T12:00:00", "2999-01-01T12:00:00+00:00", 123]
)
def test_invalid_timestamps(value):
    with pytest.raises(v.ValidationError):
        v.metric_timestamp(value)
