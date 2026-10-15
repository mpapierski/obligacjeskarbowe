from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, call

import click
from click.testing import CliRunner
import pytest

from obligacjeskarbowe.__main__ import cli
from obligacjeskarbowe.client import ObligacjeSkarbowe
from obligacjeskarbowe.parser import (
    AvailableBond,
    Bonds,
    DaneDyspozycji,
    Money,
    PurchaseConfirmation,
)


BUY_ARGS = ["buy", "--symbol", "ROD", "--amount", "2"]


@pytest.fixture
def purchase_client(monkeypatch):
    client = ObligacjeSkarbowe()
    client.session = Mock()
    client.restore_session = Mock()
    client.persist_session = Mock()
    client.list_bonds = Mock(
        return_value=Bonds(
            saldo=Money(Decimal("1000.00"), "PLN"),
            emisje=[
                AvailableBond(
                    emitent="Skarb Państwa",
                    rodzaj="12-letnie",
                    emisja="ROD1038",
                    okres_sprzedazy_od=date(2026, 10, 1),
                    okres_sprzedazy_do=date(2026, 10, 31),
                    oprocentowanie=Decimal("5.60"),
                    list_emisyjny="https://example.com/ROD1038",
                    wybierz={"s": "wybierz", "u": "dostepneEmisje"},
                    path="/zakupObligacji500Plus.html",
                )
            ],
            wartosc_nominalna_800plus=Money(Decimal("0.00"), "PLN"),
        )
    )
    steps = Mock()
    steps.select.return_value = DaneDyspozycji(
        kod_emisji="ROD1038",
        pelna_nazwa_emisji="Rodzinne dwunastoletnie obligacje skarbowe",
        oprocentowanie=Decimal("5.60"),
        wartosc_nominalna=Money(Decimal("100.00"), "PLN"),
        maksymalnie=10,
        saldo_srodkow_pienieznych=Money(Decimal("1000.00"), "PLN"),
        zgodnosc=True,
    )

    def commit():
        click.echo("TEST: zakup zatwierdzony")
        return PurchaseConfirmation(
            status="Zakup obligacji 800+ - Dyspozycja zapisana",
            data_przyjecia=datetime(2026, 10, 15, 23, 45, 12),
        )

    steps.commit.side_effect = commit
    client.purchase_step_1 = steps.select
    client.purchase_step_2 = steps.prepare
    client.purchase_step_3 = steps.commit
    monkeypatch.setattr("obligacjeskarbowe.__main__.ObligacjeSkarbowe", lambda: client)

    yield client, steps

    client.session.get.assert_not_called()
    client.session.post.assert_not_called()
    client.persist_session.assert_called_once()


@pytest.mark.parametrize(
    "input_text,completed_steps",
    [("n\n", 0), ("\n", 0), ("", 0), ("y\nn\n", 1), ("y\ny\nn\n", 2)],
)
def test_buy_cancels_before_unconfirmed_step(
    purchase_client, input_text, completed_steps
):
    _, steps = purchase_client

    result = CliRunner().invoke(cli, BUY_ARGS, input=input_text)

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert (
        steps.mock_calls
        == [
            call.select("ROD1038", force=False),
            call.prepare(2),
        ][:completed_steps]
    )
    assert "Potwierdzenie złożenia dyspozycji zakupu:" not in result.output


@pytest.mark.parametrize(
    "extra_args,input_text", [([], "y\ny\ny\n"), (["--force"], "")]
)
def test_buy_confirms_each_step_or_uses_force(purchase_client, extra_args, input_text):
    _, steps = purchase_client

    result = CliRunner().invoke(cli, BUY_ARGS + extra_args, input=input_text)

    assert result.exit_code == 0, result.output
    assert steps.mock_calls == [
        call.select("ROD1038", force=bool(extra_args)),
        call.prepare(2),
        call.commit(),
    ]
    assert result.output.count("[y/N]") == (0 if extra_args else 3)
    for detail in (
        "Kod emisji: ROD1038",
        "Pełna nazwa emisji: Rodzinne dwunastoletnie obligacje skarbowe",
        "Oprocentowanie: 5.60%",
        "Wartość nominalna jednej obligacji: 100.00 PLN",
        "Liczba zamawianych obligacji: 2 szt.",
        "Wartość zamawianych obligacji: 200.00 PLN",
        "Maksymalnie (limit serwisu): 10 szt.",
        "Możliwe do zakupu z obecnego salda i w ramach limitu: 10 szt.",
        "Saldo środków pieniężnych: 1000.00 PLN",
    ):
        assert detail in result.output
    if not extra_args:
        assert result.output.index("Krok 1/3:") < result.output.index("Dane zakupu:")
        assert result.output.index("Dane zakupu:") < result.output.index("Krok 2/3:")
    warning = "Nastąpi zakup 2 obligacji ROD1038 za 200.00 PLN. Ta operacja jest nieodwracalna."
    assert warning in result.output
    assert result.output.index(warning) < result.output.index(
        "TEST: zakup zatwierdzony"
    )
    assert result.output.index("TEST: zakup zatwierdzony") < result.output.index(
        "Potwierdzenie złożenia dyspozycji zakupu:"
    )
    summary = result.output.split("Potwierdzenie złożenia dyspozycji zakupu:", 1)[1]
    assert "Status: Zakup obligacji 800+ - Dyspozycja zapisana" in summary
    assert "Data i czas przyjęcia zlecenia: 2026-10-15 23:45:12" in summary
    assert "Kod emisji: ROD1038" in summary
    assert "Liczba obligacji: 2 szt." in summary
    assert "Wartość dyspozycji: 200.00 PLN" in summary
    assert "Oprocentowanie: 5.60%" in summary


@pytest.mark.parametrize(
    "maximum,balance,expected",
    [(10, "250.50", 2), (1, "1000.00", 1), (None, "250.50", 2), (None, "0.00", 0)],
)
def test_purchase_details_show_whole_bonds_affordable_with_cash_and_limit(
    purchase_client, maximum, balance, expected
):
    _, steps = purchase_client
    steps.select.return_value.maksymalnie = maximum
    steps.select.return_value.saldo_srodkow_pienieznych = Money(Decimal(balance), "PLN")

    result = CliRunner().invoke(cli, BUY_ARGS, input="y\nn\n")

    assert result.exit_code == 1
    assert (
        f"Możliwe do zakupu z obecnego salda i w ramach limitu: {expected} szt."
        in result.output
    )
    server_limit = f"{maximum} szt." if maximum is not None else "nie podano"
    assert f"Maksymalnie (limit serwisu): {server_limit}" in result.output
    assert f"Saldo środków pieniężnych: {balance} PLN" in result.output
    assert steps.mock_calls == [call.select("ROD1038", force=False)]


@pytest.mark.parametrize("extra_args", [[], ["--force"]])
@pytest.mark.parametrize(
    "field,value,error",
    [
        (
            "saldo_srodkow_pienieznych",
            Money(Decimal("100.00"), "PLN"),
            "Dostępne saldo",
        ),
        ("maksymalnie", 1, "Maksymalna dostępna ilość"),
        ("zgodnosc", False, "Transakcja nie jest zgodna"),
        ("kod_emisji", "ROS1032", "system zwrócił nam"),
    ],
)
def test_force_preserves_purchase_validation(
    purchase_client, extra_args, field, value, error
):
    _, steps = purchase_client
    setattr(steps.select.return_value, field, value)

    result = CliRunner().invoke(cli, BUY_ARGS + extra_args, input="y\n")

    assert result.exit_code == 1
    assert error in result.output
    assert steps.mock_calls == [call.select("ROD1038", force=bool(extra_args))]


@pytest.mark.parametrize("maximum", [10, None])
@pytest.mark.parametrize(
    "extra_args,input_text", [([], "y\ny\ny\n"), (["--force"], "")]
)
def test_allow_unpaid_is_separate_from_force(
    purchase_client, maximum, extra_args, input_text
):
    _, steps = purchase_client
    steps.select.return_value.saldo_srodkow_pienieznych = Money(Decimal("0.00"), "PLN")
    steps.select.return_value.maksymalnie = maximum

    result = CliRunner().invoke(
        cli, BUY_ARGS + ["--allow-unpaid"] + extra_args, input=input_text
    )

    assert result.exit_code == 0, result.output
    assert steps.mock_calls == [
        call.select("ROD1038", force=bool(extra_args)),
        call.prepare(2),
        call.commit(),
    ]
    assert result.output.count("[y/N]") == (0 if extra_args else 3)


def test_allow_unpaid_preserves_issuer_limit(purchase_client):
    _, steps = purchase_client
    steps.select.return_value.maksymalnie = 1

    result = CliRunner().invoke(cli, BUY_ARGS + ["--allow-unpaid", "--force"])

    assert result.exit_code == 1
    assert "Maksymalna dostępna ilość" in result.output
    assert steps.mock_calls == [call.select("ROD1038", force=True)]


def test_failed_preparation_prevents_final_purchase(purchase_client):
    _, steps = purchase_client
    steps.prepare.side_effect = RuntimeError("Błąd przygotowania dyspozycji")

    result = CliRunner().invoke(cli, BUY_ARGS + ["--force"])

    assert result.exit_code == 1
    assert "Błąd przygotowania dyspozycji" in result.output
    assert steps.mock_calls == [call.select("ROD1038", force=True), call.prepare(2)]


def test_failed_final_submission_does_not_report_confirmation(purchase_client):
    _, steps = purchase_client
    steps.commit.side_effect = RuntimeError("Brak potwierdzenia przyjęcia zlecenia")

    result = CliRunner().invoke(cli, BUY_ARGS + ["--force"])

    assert result.exit_code == 1
    assert "Brak potwierdzenia przyjęcia zlecenia" in result.output
    assert "Potwierdzenie złożenia dyspozycji zakupu:" not in result.output
    steps.commit.assert_called_once()


@pytest.mark.parametrize("extra_args", [[], ["--force"]])
def test_dry_run_does_not_start_purchase_steps(purchase_client, extra_args):
    _, steps = purchase_client

    result = CliRunner().invoke(cli, BUY_ARGS + ["--dry-run"] + extra_args)

    assert result.exit_code == 0, result.output
    assert steps.mock_calls == []
    assert "[y/N]" not in result.output
    assert "Nastąpi zakup" not in result.output


@pytest.mark.parametrize("amount", ["0", "-1"])
def test_buy_requires_positive_amount(amount, monkeypatch):
    factory = Mock()
    monkeypatch.setattr("obligacjeskarbowe.__main__.ObligacjeSkarbowe", factory)

    result = CliRunner().invoke(cli, ["buy", "--symbol", "ROD", "--amount", amount])

    assert result.exit_code == 2
    factory.assert_not_called()
