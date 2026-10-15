from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock

from click.testing import CliRunner
import pytest

from obligacjeskarbowe.__main__ import cli
from obligacjeskarbowe.parser import Bonds, Money


@pytest.fixture
def verify_account(monkeypatch, tmp_path):
    config = tmp_path / "800plus.toml"
    config.write_text('[[kids]]\nname = "Test"\nbirth_date = "2024-01-01"\n')
    client = Mock()
    client.list_500plus_bonds.return_value = Bonds(
        saldo=Money(Decimal("11200.00"), "PLN"),
        emisje=[],
        wartosc_nominalna_800plus=Money(Decimal("68600.00"), "PLN"),
    )
    factory = Mock(return_value=client)
    calculator = Mock(return_value=Decimal("81950.10"))
    monkeypatch.setattr("obligacjeskarbowe.__main__.ObligacjeSkarbowe", factory)
    monkeypatch.setattr(
        "obligacjeskarbowe.__main__.calculate_total_compensation", calculator
    )
    args = ["verify-800plus", "--config", str(config)]
    return client, calculator, factory, args


@pytest.mark.parametrize(
    "balance,affordable,difference,shortfall",
    [
        ("11200.00", 112, "-2150.10", "2100.00"),
        ("13350.10", 133, "+0.00", "0.00"),
        ("14000.00", 133, "+649.90", "0.00"),
        ("50.10", 0, "-13300.00", "13249.90"),
        ("0.00", 0, "-13350.10", "13300.00"),
    ],
)
def test_verify_compares_expected_balance_with_cash_and_limit(
    verify_account, balance, affordable, difference, shortfall
):
    client, calculator, _, args = verify_account
    client.list_500plus_bonds.return_value.saldo = Money(Decimal(balance), "PLN")

    result = CliRunner().invoke(cli, args + ["--through-month", "2026-10"])

    assert result.exit_code == 0, result.output
    calculator.assert_called_once_with(
        {"kids": [{"name": "Test", "birth_date": "2024-01-01"}]},
        as_of=date(2026, 10, 31),
    )
    assert "Świadczenia uwzględnione do: 2026-10 (włącznie)" in result.output
    assert (
        "Wyliczona wartość należnych świadczeń 500+/800+: 81950.10 PLN" in result.output
    )
    assert (
        "Oczekiwane saldo (świadczenia minus zakupy ROS/ROD): 13350.10 PLN"
        in result.output
    )
    assert f"Saldo rzeczywiste rachunku: {balance} PLN" in result.output
    assert (
        f"Różnica (saldo rzeczywiste minus oczekiwane): {difference} PLN"
        in result.output
    )
    assert "Pozostały limit ROS/ROD: 133 szt. (13300.00 PLN)" in result.output
    assert (
        f"Możliwe do zakupu z obecnego salda i w ramach limitu: {affordable} szt."
        in result.output
    )
    assert f"Do zakupu całego limitu brakuje: {shortfall} PLN" in result.output
    client.restore_session.assert_called_once()
    client.persist_session.assert_called_once()
    client.list_500plus_bonds.assert_called_once()
    client.purchase.assert_not_called()


def test_verify_defaults_to_current_month(verify_account, monkeypatch):
    _, calculator, _, args = verify_account

    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 10, 15)

    monkeypatch.setattr("obligacjeskarbowe.__main__.datetime", FixedDatetime)

    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0, result.output
    assert calculator.call_args.kwargs["as_of"] == date(2026, 10, 15)


def test_verify_can_compare_with_benefits_through_previous_month(verify_account):
    _, calculator, _, args = verify_account
    calculator.return_value = Decimal("80350.10")

    result = CliRunner().invoke(cli, args + ["--through-month", "2026-09"])

    assert result.exit_code == 0, result.output
    assert calculator.call_args.kwargs["as_of"] == date(2026, 9, 30)
    assert (
        "Oczekiwane saldo (świadczenia minus zakupy ROS/ROD): 11750.10 PLN"
        in result.output
    )
    assert "Różnica (saldo rzeczywiste minus oczekiwane): -550.10 PLN" in result.output
    assert "Pozostały limit ROS/ROD: 117 szt." in result.output
    assert "Do zakupu całego limitu brakuje: 500.00 PLN" in result.output


def test_verify_dry_run_does_not_access_account(verify_account):
    _, _, factory, args = verify_account

    result = CliRunner().invoke(cli, args + ["--through-month", "2026-10", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert (
        "Wyliczona wartość należnych świadczeń 500+/800+: 81950.10 PLN" in result.output
    )
    assert "Saldo rzeczywiste" not in result.output
    factory.assert_not_called()
