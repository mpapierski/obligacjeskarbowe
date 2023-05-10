from collections import OrderedDict
import dataclasses
import os
import sys
import click

from tabulate import tabulate
from obligacjeskarbowe.client import ObligacjeSkarbowe
from obligacjeskarbowe.parser import DEFAULT_CURRENCY


def display_money(money):
    return f"{money.amount} {money.currency}"


def show_bonds(bonds):
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

    click.echo(tabulate(rows, headers, tablefmt="fancy_grid"))


@click.group()
def cli():
    pass


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
def portfolio(username, password):
    client = ObligacjeSkarbowe(username, password)
    client.login()

    try:
        click.echo(
            f"Saldo środków pieniężnych: {client.balance.amount:02f} {client.balance.currency}",
        )

        click.echo("Obligacje:")
        show_bonds(client.bonds)

    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
def family_500plus(username, password):
    """List family bonds for the 500+ program."""
    client = ObligacjeSkarbowe(username, password)
    client.login()
    try:
        available_bonds = client.list_500plus()
        click.echo("Zakup - dostępne emisje obligacji 500+")
        available_bonds = [
            [
                bond.rodzaj,
                bond.emisja,
                bond.okres_sprzedazy_od,
                bond.okres_sprzedazy_do,
                f"{bond.oprocentowanie:02f}%",
            ]
            for bond in available_bonds
        ]
        click.echo(
            tabulate(available_bonds, ["Rodzaj", "Emisja", "Od", "Do"], tablefmt="fancy_grid")
        )
    finally:
        client.logout()


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option("--symbol", required=True)
@click.option("--amount", required=True, type=int)
def buy(username, password, symbol, amount):
    """Performs automatic purchase of a most recent bond i.e. "ROD" buys current RODXY bond."""
    client = ObligacjeSkarbowe(username, password)
    client.login()
    try:
        if client.balance.amount == 0:
            click.echo('Your balance is zero. Unable to proceed.', err=True)
            sys.exit(1)

        expanded_symbol = None
        for available_bond in client.list_500plus():
            if available_bond.emisja.startswith(symbol):
                click.echo(f'Found a matching bond {available_bond.emisja} with an interest of {available_bond.oprocentowanie:02f}')
                expanded_symbol = available_bond.emisja
                break

        client.purchase(expanded_symbol, amount)

    finally:
        client.logout()


if __name__ == "__main__":
    cli()
