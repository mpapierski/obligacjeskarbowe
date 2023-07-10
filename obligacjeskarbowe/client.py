from collections import OrderedDict
import logging
import operator
from bs4 import BeautifulSoup
import requests

from obligacjeskarbowe.parser import (
    extract_available_bonds,
    extract_balance,
    extract_bonds,
    extract_dane_dyspozycji_500,
    extract_data_przyjecia_zlecenia,
    extract_form_action_by_id,
    extract_javax_view_state,
    extract_purchase_step_title,
    parse_xml_redirect,
)


log = logging.getLogger()

LOGIN_BATON = "Zaloguj"


class ObligacjeSkarbowe:
    def __init__(self, username, password):
        self.base_url = "https://www.zakup.obligacjeskarbowe.pl"
        self.username = username
        self.password = password
        self.session = requests.Session()

        self.balance = None
        self.bonds = None
        self.available_bonds = []
        # A lookup table from readable bond name into the internal identifier.
        self.available_bonds_lookup = OrderedDict()

        self.next_url = None
        self.view_state = None

    def login(self):
        """Performs a login procedure."""
        r = self.session.get(self.base_url + "/login.html")
        r.raise_for_status()
        form = {
            "username": self.username,
            "password": self.password,
            "baton": LOGIN_BATON,
        }
        r = self.session.post(self.base_url + "/login", data=form)
        r.raise_for_status()

        bs = BeautifulSoup(r.content, features="html.parser")
        self.balance = extract_balance(bs)
        self.bonds = extract_bonds(bs)
        self.session.cookies.set("obligacje_set", "none")
        log.info("Logged in")

    def __bonds_navigate(self, path):
        """Navigate bonds page, does not maintain internal lookup database."""
        r = self.session.get(f"{self.base_url}{path}")
        r.raise_for_status()
        bs = BeautifulSoup(r.content, features="html.parser")
        available_bonds = extract_available_bonds(bs, path)
        self.next_url = extract_form_action_by_id(bs, form_id="dostepneEmisje")
        self.view_state = extract_javax_view_state(bs)
        return available_bonds

    def __bonds(self, path):
        """Extracts list of bonds but also maintains a lookup database."""
        new_available_bonds = self.__bonds_navigate(path)
        self.available_bonds += new_available_bonds
        new_bonds_lookup = OrderedDict(
            [(bond.emisja, bond) for bond in self.available_bonds]
        )
        self.available_bonds_lookup.update(new_bonds_lookup)
        log.info(f"Found {len(new_bonds_lookup)} bonds at {path}")
        return new_available_bonds

    def list_bonds(self):
        """Lists available bonds"""
        bonds = []
        bonds += self.__bonds("/zakupObligacji500Plus.html")
        bonds += self.__bonds("/zakupObligacji.html")
        bonds.sort(
            key=operator.attrgetter(
                "dlugosc", "okres_sprzedazy_od", "oprocentowanie", "emisja"
            )
        )
        return bonds

    def purchase(self, emisja, amount):
        """Purchase a bond.

        Requires a prior call to `list_500plus` to obtain necessary information.

        :param str emisja: "Emisja" such as ROD1234
        :param int amount: Amount of bonds
        """

        # Step 1: "Wybierz" -> Dane dyspozycji

        dane_dyspozycji = self.purchase_step_1(emisja)

        if not dane_dyspozycji.kod_emisji.startswith(emisja):
            raise RuntimeError(
                f"Wybrano kod emisji {emisja}, ale system zwrócił nam {dane_dyspozycji.kod_emisji}"
            )

        expected_cost = amount * dane_dyspozycji.wartosc_nominalna.amount
        if dane_dyspozycji.saldo_srodkow_pienieznych.amount < expected_cost:
            raise RuntimeError(
                f"Dostępne saldo {dane_dyspozycji.saldo_srodkow_pienieznych.amount:.02f} {dane_dyspozycji.saldo_srodkow_pienieznych.currency} jest mniejsze niż oczekiwany koszt zakupu {expected_cost}"
            )

        if dane_dyspozycji.maksymalnie < amount:
            raise RuntimeError(
                f"Maksymalna dostępna ilość obligacji {dane_dyspozycji.kod_emisji} ({dane_dyspozycji.maksymalnie}) jest mniejsza niż oczekiwana ({amount})"
            )

        if not dane_dyspozycji.zgodnosc:
            raise RuntimeError("Transakcja nie jest zgodna z Grupą docelową!")

        # Step 2: "Dalej" -> Dane dyspozycji do zatwierdzenia

        self.purchase_step_2(amount)

        # Step 3: Zatwierdź dyspozycję

        self.purchase_step_3()

    def purchase_step_3(self):
        s = "zatwierdzenie1:ok"
        u = "zatwierdzenie1"

        bs = self.__javax_post(s, u)

        title = extract_purchase_step_title(bs)
        log.info(f"Krok 3: {title}...")
        data_przyjecia = extract_data_przyjecia_zlecenia(bs)
        log.info(f"Data i czas przyjęcia zlecenia: {data_przyjecia}")

    def purchase_step_2(self, amount):
        s = "daneDyspozycji:ok"
        u = "daneDyspozycji"
        bs = self.__javax_post(
            s,
            u,
            extra_javax_kwargs={
                "daneDyspozycji:liczbaZamiawianychObligacji": f"{amount}",
            },
        )
        self.next_url = extract_form_action_by_id(bs, form_id="zatwierdzenie1")

        title = extract_purchase_step_title(bs)
        log.info(f"Krok 2: {title}...")

    def purchase_step_1(self, emisja):
        # TODO: Remove `available_bonds_lookup`
        available_bond = self.available_bonds_lookup[emisja]  # dict(s, u)

        # Navigate to appropriate path for a given bond since the order of page visits matters.
        _available_bonds = self.__bonds_navigate(available_bond.path)

        wybierz = available_bond.wybierz
        bs = self.__javax_post(s=wybierz["s"], u=wybierz["u"])
        self.next_url = extract_form_action_by_id(bs, form_id="daneDyspozycji")

        title = extract_purchase_step_title(bs)
        log.info(f"Krok 1: {title}...")

        return extract_dane_dyspozycji_500(bs)

    def logout(self):
        """Logs out."""
        r = self.session.get(self.base_url + "/logout")
        r.raise_for_status()

    def __javax_post(self, s, u, extra_javax_kwargs=None):
        """Performs a "javax" POST request.

        Requires a `self.next_url` value extracted from a desired `<form action>` attribute.

        This will construct a javax POST request, it will handle weird XML document with a redirect information, and does some initial information extraction to maintain state.

        :param str s: aka "source"
        :param str u: aka "render" (?)
        :param dict extra_javax_kwargs: extra POST data to attach
        """
        assert self.next_url is not None, "Expected next_url to be set"
        assert self.view_state is not None, "Expected a view state to be set"

        if extra_javax_kwargs is None:
            extra_javax_kwargs = {}

        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": s,
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": u,
            s: s,
            u: u,
            "javax.faces.ViewState": self.view_state,
        }

        data.update(extra_javax_kwargs)

        r = self.session.post(self.base_url + self.next_url, data=data)
        r.raise_for_status()

        # Handle weird XML document with <redirect url=""> instead of 3xx response
        redirect_url = parse_xml_redirect(r.content)

        r = self.session.get(self.base_url + redirect_url)
        r.raise_for_status()

        bs = BeautifulSoup(r.content, features="html.parser")
        self.view_state = extract_javax_view_state(bs)
        return bs
