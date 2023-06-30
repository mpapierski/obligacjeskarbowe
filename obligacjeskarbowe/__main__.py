from collections import OrderedDict
import dataclasses
from decimal import Decimal
import logging
import sys
import click

from tabulate import tabulate
from obligacjeskarbowe.client import ObligacjeSkarbowe
from obligacjeskarbowe.parser import DEFAULT_CURRENCY


def display_money(money):
    return f"{money.amount} {money.currency}"


def tabulate_bonds(bonds):
    rows = []
    for bond in bonds:
        d = dataclasses.asdict(bond, dict_factory=OrderedDict)
        d["nominalna"] = display_money(bond.nominalna)
        d["aktualna"] = display_money(bond.aktualna)
        d["oprocentowanie"] = f'{d["oprocentowanie"]:.02f}%'
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


@click.group()
def cli():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
def portfolio(username, password):
    client = ObligacjeSkarbowe(username, password)
    client.login()

    try:
        click.echo(
            f"Saldo środków pieniężnych: {client.balance.amount:.02f} {client.balance.currency}",
        )

        click.echo("Obligacje:")
        click.echo(tabulate_bonds(client.bonds))

    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option("--amount", required=True, type=Decimal)
def require_balance(username, password, amount):
    """Checks a balance to be exactly the expected amount. Exits if balance is invalid."""
    client = ObligacjeSkarbowe(username, password)
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
def bonds(username, password):
    """List all currently available bonds."""
    client = ObligacjeSkarbowe(username, password)
    client.login()
    try:
        available_bonds = client.list_bonds()
        click.echo("Zakup - dostępne emisje obligacji")
        click.echo(tabulate_available_bonds(available_bonds))
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
            sys.exit(1)

    finally:
        client.logout()


if __name__ == "__main__":
    cli()
