import shutil
import os
import tomllib
from collections import OrderedDict
import dataclasses
from datetime import datetime
import logging
import sys
import click
from tablib import Dataset

from tabulate import tabulate
from obligacjeskarbowe.client import ObligacjeSkarbowe
from obligacjeskarbowe.parser import DEFAULT_CURRENCY
from dateutil.relativedelta import relativedelta
from obligacjeskarbowe.family800plus import (
    calculate_total_compensation,
    calculate_available_bonds,
)


def display_money(money):
    return f"{money.amount} {money.currency}"


def tabulate_bonds(bonds, expand):
    rows = []
    for bond in bonds:
        d = dataclasses.asdict(bond, dict_factory=OrderedDict)
        d["nominalna"] = display_money(bond.nominalna)
        d["aktualna"] = display_money(bond.aktualna)
        d["okres"] = d["okresy"][-1]["okres"]
        if expand:
            d["oprocentowanie"] = "\n".join(
                f"{item['okres']}: {item['oprocentowanie']:.02f}%"
                for item in d["okresy"]
            )
        else:
            d["oprocentowanie"] = f'{d["okresy"][-1]["oprocentowanie"]:.02f}%'

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
@click.option("--verbose", is_eager=True, default=False)
def cli(verbose):
    if verbose:
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


@cli.command()
@click.option("--username", required=True, envvar="OBLIGACJESKARBOWE_USERNAME")
@click.option("--password", required=True, envvar="OBLIGACJESKARBOWE_PASSWORD")
@click.option(
    "--ntfy-topic", required=True, type=str, envvar="OBLIGACJESKARBOWE_NTFY_TOPIC"
)
def login(username, password, ntfy_topic):
    """Login to Obligacje Skarbowe."""
    client = ObligacjeSkarbowe()
    try:
        client.restore_session()
    except Exception as e:
        click.echo(f"Session restore failed: {e}")

    login_info = client.login(username, password, topic=ntfy_topic)

    client.persist_session()
    click.echo("OK")
    click.echo(f"🔒 Zalogowany użytkownik {login_info.username}")
    click.echo(f"Ostatnie udane logowanie: {login_info.ostatnie_udane_logowanie}")
    click.echo(f"Ostatnie nieudane logowanie: {login_info.ostatnie_nieudane_logowanie}")


@cli.command()
def logout():
    """Logout from Obligacje Skarbowe."""
    client = ObligacjeSkarbowe()
    client.logout()
    client.clear_session()
    click.echo("OK")


@cli.command()
@click.option("--expand", is_flag=True, default=True)
def portfolio(expand):
    """List all bonds in your portfolio."""
    client = ObligacjeSkarbowe()
    client.restore_session()
    try:
        bonds = client.list_portfolio()
        click.echo("Obligacje:")
        click.echo(tabulate_bonds(bonds, expand))
    finally:
        client.persist_session()


@cli.command()
def bonds():
    """List all currently available bonds."""
    client = ObligacjeSkarbowe()
    client.restore_session()
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
        client.persist_session()


@cli.command()
@click.option("--symbol", required=True)
@click.option("--amount", required=True, type=int)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Do not perform any action, just print what would be done. Validates the purchase parameters.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force purchase, even if it is not possible. Will create an unpaid order that you have to pay for. If set to False, the purchase will be made only if there are enough funds on the account.",
)
def buy(symbol, amount, dry_run, force):
    """Performs automatic purchase of a most recent bond i.e. "ROD" buys current RODXY bond."""
    client = ObligacjeSkarbowe()
    client.restore_session()
    try:
        expanded_symbol = None

        bonds_list = client.list_bonds()
        for available_bond in bonds_list.emisje:
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
            client.purchase(expanded_symbol, amount, force)
        except Exception as error:
            click.echo(f"Wystąpił błąd: {error}")
            raise

    finally:
        client.persist_session()


@cli.command()
@click.option(
    "--from-date",
    type=click.DateTime(["%Y-%m-%d"]),
    default=datetime.now() - relativedelta(months=3),
)
@click.option("--to-date", type=click.DateTime(["%Y-%m-%d"]), default=datetime.now())
@click.option("--format", type=click.Choice(["csv", "xlsx", "json"]))
@click.option("--output", type=click.File("w"), default=sys.stdout)
def history(from_date, to_date, format, output):
    """History of dispositions on your account."""
    client = ObligacjeSkarbowe()
    client.restore_session()
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
        client.persist_session()


@cli.command()
@click.option("--dry-run", is_flag=True)
@click.option("--config", type=click.Path(exists=True), default="800plus.toml")
def verify_800plus(dry_run, config):
    """Verifies if you can buy 800+ bonds.

    This command will calculate the total compensation you received from the 800+ program and display the expected amount of ROS/ROD bonds you can buy. This value has to match your bank statements.
    """
    with open(config, "rb") as f:
        config = tomllib.load(f)

    # This has to be equal to a bank statement. Always
    total_compensation = calculate_total_compensation(config)

    if dry_run:
        return

    client = ObligacjeSkarbowe()
    client.restore_session()
    try:
        available_bonds = client.list_bonds()
        click.echo(
            f"Wartość dotychczas otrzymanego świadczenia rodzinnego 800+: {total_compensation}"
        )
        click.echo(
            f"Wartość nominalna dotychczas zakupionych obligacji za środki przyznane w ramach programów wsparcia rodziny wynosi: {available_bonds.wartosc_nominalna_800plus.amount:.02f} {available_bonds.wartosc_nominalna_800plus.currency}"
        )
        buy_amount = calculate_available_bonds(
            total_compensation, available_bonds.wartosc_nominalna_800plus.amount
        )
        click.echo(f"Ilość obligacji gotowych do zakupu: {buy_amount}")
        click.echo(
            f"Kwota wymagana do dokonania zakupu za cały limit: {buy_amount * 100} {DEFAULT_CURRENCY}"
        )
    finally:
        client.persist_session()


@cli.command()
@click.argument("name")
@click.option("--path", type=click.Path(exists=True), default=".")
def download_pdf(name, path):
    """Download a PDF file for a given bond name."""
    client = ObligacjeSkarbowe()
    filename = f"{path}/{name.upper()}.pdf"
    if os.path.exists(filename):
        click.echo(f"File {filename} already exists, skipping...")
    else:
        click.echo(f"Downloading {name} to {filename}")
        name_tokens = name.split()
        output = client.download_pdf(name_tokens[0])
        with open(filename, "wb") as out:
            shutil.copyfileobj(output, out)


@cli.command()
@click.option("--path", type=click.Path(exists=True), default=".")
def download_archive(path):
    """Download all available PDFs from the bonds archive."""
    client = ObligacjeSkarbowe()

    queue = []

    for bond_type, data in client.archive().items():

        click.echo(f"{bond_type}: {data["name"]}")
        for bond in data["bonds"]:
            click.echo(f"  {bond['name']}: {bond['url']}")
            queue.append((bond["name"], bond["url"]))

    with click.progressbar(queue, label="Downloading PDFs") as bar:
        for name, url in bar:
            filename = f"{path}/{name.upper()}.pdf"
            if os.path.exists(filename):
                click.echo(f"File {filename} already exists, skipping...")
            else:
                click.echo(f"Downloading {name} to {filename}")
                bar.label = f"Downloading {name}"
                name_tokens = name.split()
                output = client.download_pdf(name_tokens[0])
                with open(filename, "wb") as out:
                    shutil.copyfileobj(output, out)


if __name__ == "__main__":
    cli()
