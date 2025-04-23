from collections import OrderedDict
import dataclasses
from datetime import datetime
from decimal import Decimal
import logging
import sys
import click
from tablib import Dataset

from tabulate import tabulate
from obligacjeskarbowe.client import ObligacjeSkarbowe
from obligacjeskarbowe.parser import DEFAULT_CURRENCY
from dateutil.relativedelta import relativedelta


def display_money(money):
    return f"{money.amount} {money.currency}"


def tabulate_bonds(bonds):
    rows = []
    for bond in bonds:
        d = dataclasses.asdict(bond, dict_factory=OrderedDict)
        d["nominalna"] = display_money(bond.nominalna)
        d["aktualna"] = display_money(bond.aktualna)
        d["okres"] = d["okresy"][-1]["okres"]
        oprocentowanie = d["okresy"][-1]["oprocentowanie"]
        d["oprocentowanie"] = f"{oprocentowanie:.02f}%"
        del d["okresy"]
        rows.append(d)

    razem = sum([bond.dostepnych for bond in bonds])
    zablokowanych = sum([bond.zablokowanych for bond in bonds])
    nominalna = sum([bond.nominalna.amount for bond in bonds])
    aktualna = sum([bond.aktualna.amount for bond in bonds])

    rows.append(
        OrderedDict(
            [
                ("emisja", "Razem"),
                ("dostepnych", razem),
                ("zablokowanych", zablokowanych),
                ("nominalna", f"{nominalna} {DEFAULT_CURRENCY}"),
                ("aktualna", f"{aktualna} {DEFAULT_CURRENCY}"),
                ("okres", ""),
                ("oprocentowanie", ""),
                ("data_wykupu", ""),
            ]
        )
    )

    headers = OrderedDict(
        [
            ("emisja", "Emisja"),
            ("dostepnych", "Dostępnych"),
            ("zablokowanych", "Zablokowanych"),
            ("nominalna", "Wartość"),
            ("aktualna", "Aktualna"),
            ("data_wykupu", "Data Wykupu"),
            ("okres", "Okres"),
            ("oprocentowanie", "Oprocentowanie"),
        ]
    )

    return tabulate(rows, headers, tablefmt="fancy_grid")


def tabulate_available_bonds(available_bonds):
    available_bonds = [
        [
            f"{bond.dlugosc} ({bond.rodzaj})",
            bond.emisja,
            bond.okres_sprzedazy_od,
            bond.okres_sprzedazy_do,
            f"{bond.oprocentowanie:.02f}%",
        ]
        for bond in available_bonds
    ]
    return tabulate(
        available_bonds,
        ["Długość (mc)", "Emisja", "Od", "Do", "Oprocentowanie"],
        tablefmt="fancy_grid",
    )


HISTORY_COLUMNS = (
    "Data dyspozycji",
    "Rodzaj dyspozycji",
    "Kod obligacji",
    "Numer zapisu",
    "Seria",
    "Liczba obligacji",
    "Kwota operacji",
    "Status",
    "Uwagi",
)


def tabulate_history(history):
    rows = []
    for item in history:
        d = dataclasses.asdict(item, dict_factory=OrderedDict)
        rows.append(d)

    attrs = (
        "data_dyspozycji",
        "rodzaj_dyspozycji",
        "kod_obligacji",
        "nr_zapisu",
        "seria",
        "liczba_obligacji",
        "kwota_operacji",
        "status",
        "uwagi",
    )

    headers = OrderedDict(
        zip(attrs, HISTORY_COLUMNS),
    )

    return tabulate(rows, headers, tablefmt="fancy_grid")


@click.group()
def cli():
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option(
    "--ntfy-topic", required=True, type=str, envvar="OBLIGACJESKARBOWE_NTFY_TOPIC"
)
def portfolio(username, password, ntfy_topic):
    client = ObligacjeSkarbowe(username, password, topic=ntfy_topic)
    client.login()

    try:
        bonds = client.list_portfolio()
        # click.echo(
        #     f"Saldo środków pieniężnych: {client.balance.amount:.02f} {client.balance.currency}",
        # )

        click.echo("Obligacje:")
        click.echo(tabulate_bonds(bonds))

    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option("--amount", required=True, type=Decimal)
@click.option(
    "--ntfy-topic", required=True, type=str, envvar="OBLIGACJESKARBOWE_NTFY_TOPIC"
)
def require_balance(username, password, amount, ntfy_topic):
    """Checks a balance to be exactly the expected amount. Exits if balance is invalid."""
    client = ObligacjeSkarbowe(username, password, ntfy_topic)
    client.login()
    try:
        if client.balance.amount != amount:
            click.echo(
                f"Your balance is expected to be {amount:.02f} {DEFAULT_CURRENCY} but your balance is currently {client.balance.amount:02f} {client.balance.currency}.",
                err=True,
            )
            sys.exit(1)
    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option(
    "--ntfy-topic", required=True, type=str, envvar="OBLIGACJESKARBOWE_NTFY_TOPIC"
)
def bonds(username, password, ntfy_topic):
    """List all currently available bonds."""
    client = ObligacjeSkarbowe(username, password, topic=ntfy_topic)
    client.login()
    try:
        available_bonds = client.list_bonds()
        click.echo("Zakup - dostępne emisje obligacji")
        click.echo(
            f"Saldo środków pieniężnych: {available_bonds.saldo.amount:.02f} {available_bonds.saldo.currency}"
        )
        click.echo(
            f"Wartość nominalna dotychczas zakupionych obligacji za środki przyznane w ramach programów wsparcia rodziny wynosi: {available_bonds.wartosc_nominalna_800plus.amount:.02f} {available_bonds.wartosc_nominalna_800plus.currency}"
        )
        click.echo(tabulate_available_bonds(available_bonds.emisje))
    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option("--symbol", required=True)
@click.option("--amount", required=True, type=int)
@click.option("--dry-run", is_flag=True)
def buy(username, password, symbol, amount, dry_run):
    """Performs automatic purchase of a most recent bond i.e. "ROD" buys current RODXY bond."""
    client = ObligacjeSkarbowe(username, password)
    client.login()
    try:
        expanded_symbol = None

        bonds_list = client.list_bonds()
        for available_bond in bonds_list:
            if available_bond.emisja.startswith(symbol):
                click.echo(
                    f"Found a matching bond {available_bond.emisja} with an interest of {available_bond.oprocentowanie:.02f}%"
                )
                expanded_symbol = available_bond.emisja
                break

        if expanded_symbol is None:
            click.echo(f"Symbol {symbol} not found. Available bonds:", err=True)
            click.echo(tabulate_available_bonds(bonds_list), err=True)
            sys.exit(1)
            return

        click.echo(f"Matched {expanded_symbol}")

        if dry_run:
            click.echo("Bye...")
            return

        try:
            client.purchase(expanded_symbol, amount)
        except Exception as error:
            click.echo(f"Wystąpił błąd: {error}")
            raise

    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option(
    "--from-date",
    type=click.DateTime(["%Y-%m-%d"]),
    default=datetime.now() - relativedelta(months=3),
)
@click.option("--to-date", type=click.DateTime(["%Y-%m-%d"]), default=datetime.now())
@click.option("--format", type=click.Choice(["csv", "xlsx", "json"]))
@click.option("--output", type=click.File("w"), default=sys.stdout)
def history(username, password, from_date, to_date, format, output):
    """History of dispositions on your account."""
    client = ObligacjeSkarbowe(username, password)
    client.login()
    try:
        history = client.history(from_date=from_date, to_date=to_date)
        if format is None:
            click.echo(tabulate_history(history), err=True)
        else:
            dataset = Dataset()
            dataset.headers = HISTORY_COLUMNS
            for row in history:
                row_value = dataclasses.astuple(row)
                dataset.append(row_value)
            exported = dataset.export(format)
            output.write(exported)
    finally:
        client.logout()


if __name__ == "__main__":
    cli()
