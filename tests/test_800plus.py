from decimal import Decimal
from obligacjeskarbowe.family800plus import special_round_up


def test_special_rounding():
    value = (Decimal(29) / Decimal(30)) * Decimal(500)
    assert special_round_up(value) == Decimal("483.4")
