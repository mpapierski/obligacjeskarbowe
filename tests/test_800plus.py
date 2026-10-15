from datetime import date
from decimal import Decimal

import pytest

from obligacjeskarbowe.family800plus import (
    calculate_available_bonds,
    calculate_total_compensation,
    special_round_up,
)


def test_special_rounding():
    value = (Decimal(29) / Decimal(30)) * Decimal(500)
    assert special_round_up(value) == Decimal("483.4")


@pytest.mark.parametrize(
    "total,purchased,expected",
    [
        ("81950.10", "68600", "133"),
        ("81350.10", "68600", "127"),
        ("68699.99", "68600", "0"),
        ("68600", "68600", "0"),
        ("68500", "68600", "0"),
        ("11200", "0", "112"),
    ],
)
def test_available_bonds_rounds_down_and_never_returns_negative(
    total, purchased, expected
):
    assert calculate_available_bonds(Decimal(total), Decimal(purchased)) == Decimal(
        expected
    )


@pytest.mark.parametrize(
    "birth,as_of,expected",
    [
        ("2023-12-01", date(2023, 12, 31), "500"),
        ("2023-12-01", date(2024, 1, 1), "1300"),
        ("2023-12-01", date(2024, 2, 29), "2100"),
        ("2023-12-31", date(2024, 1, 31), "816.20"),
        ("2024-01-01", date(2024, 1, 1), "800"),
        ("2024-01-01", date(2024, 2, 29), "1600"),
        ("2024-01-31", date(2024, 1, 31), "25.90"),
        ("2024-01-31", date(2024, 2, 29), "825.90"),
        ("2024-02-29", date(2024, 3, 1), "827.60"),
        ("2025-02-01", date(2026, 3, 15), "11200"),
        ("2024-01-31", date(2024, 1, 30), "0"),
    ],
)
def test_total_benefits_includes_selected_month_and_handles_rate_change(
    birth, as_of, expected
):
    config = {"kids": [{"name": "Test", "birth_date": birth}]}

    assert calculate_total_compensation(config, as_of=as_of) == Decimal(expected)


def test_total_benefits_for_multiple_children():
    config = {
        "kids": [
            {"name": "First", "birth_date": "2022-01-01"},
            {"name": "Second", "birth_date": "2024-01-01"},
        ]
    }

    assert calculate_total_compensation(config, as_of=date(2024, 2, 29)) == Decimal(
        "15200"
    )
