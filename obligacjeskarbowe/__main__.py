from collections import OrderedDict
import dataclasses
import os

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

    print(tabulate(rows, headers, tablefmt="fancy_grid"))
    # print(tabulate()


def main():
    username = os.environ["OBLIGACJESKARBOWE_USERNAME"]
    password = os.environ["OBLIGACJESKARBOWE_PASSWORD"]
    client = ObligacjeSkarbowe(username, password)
    client.login()

    try:
        print(
            f"Saldo środków pieniężnych: {client.balance}",
        )

        print("Obligacje:")
        show_bonds(client.bonds)

        available_bonds = client.list_500plus()

        for available_bond in available_bonds:
            print(available_bond)

        # client.purchase('ROD0535', amount=10)

    finally:
        client.logout()


if __name__ == "__main__":
    main()
