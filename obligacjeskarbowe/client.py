from collections import OrderedDict
import logging
import operator
import time
from bs4 import BeautifulSoup
import requests
from obligacjeskarbowe import two_factor

from obligacjeskarbowe.parser import (
    PartialResponse,
    Redirect,
    extract_available_bonds,
    extract_balance,
    extract_bonds,
    extract_dane_dyspozycji,
    extract_data_przyjecia_zlecenia,
    extract_form_action_by_id,
    extract_javax_view_state,
    extract_purchase_step_title,
    parse_history,
    parse_xml_response,
)


log = logging.getLogger()

LOGIN_BATON = "Zaloguj"


class ObligacjeSkarbowe:
    def __init__(self, username, password, topic):
        self.base_url = "https://www.zakup.obligacjeskarbowe.pl"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0"
            }
        )

        self.balance = None
        self.bonds = None
        self.available_bonds = []
        # A lookup table from readable bond name into the internal identifier.
        self.available_bonds_lookup = OrderedDict()

        self.next_url = None
        self.view_state = None

        self.topic = topic

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
        prompt = bs.select('span[id="spanContent"]')[0].text.strip()

        if "Nie rozpoznaliśmy Twojego urządzenia." in prompt:
            token_stream = two_factor.wait_for_token(self.topic)

            open_event = next(token_stream)
            if not isinstance(open_event, (two_factor.Open,)):
                raise RuntimeError("Expected open event but got {open_event!r}")

            self.next_url = extract_form_action_by_id(bs, form_id="j_idt89")
            self.view_state = extract_javax_view_state(bs)

            s = "j_idt89:j_idt97"  # "Dostęp jednorazowy"
            u = "j_idt89"
            bs = self.__javax_post(s, u)

            with open("downloads/device_outcome.html", "w") as f:
                f.write(str(bs))

            two_factor_prompt = bs.select('span[id="spanContent"]')[0].text.strip()
            print(f"Two factor prompt: {two_factor_prompt!r}")

            s = "j_idt90:j_idt112"
            u = "j_idt90"

            print("Waiting for token...")

            token = next(token_stream)

            print(f"Received token {token!r}")

            time.sleep(5)

            ux_code = token.kod

            bs = self.__javax_post(
                s,
                u,
                extra_javax_kwargs={
                    "j_idt90:uxCode": f"{ux_code}",
                },
            )
            assert bs is not None

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

        maksymalnie = dane_dyspozycji.maksymalnie
        if maksymalnie is None:
            # ROS/ROD have a maximum monthly cap, but other's don't have so we need to calculate based on amounts provided.
            assert (
                dane_dyspozycji.saldo_srodkow_pienieznych.currency
                == dane_dyspozycji.wartosc_nominalna.currency
            )
            maksymalnie = (
                dane_dyspozycji.saldo_srodkow_pienieznych.amount
                / dane_dyspozycji.wartosc_nominalna.amount
            )

        if maksymalnie < amount:
            raise RuntimeError(
                f"Maksymalna dostępna ilość obligacji {dane_dyspozycji.kod_emisji} ({maksymalnie}) jest mniejsza niż oczekiwana ({amount})"
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

        return extract_dane_dyspozycji(bs)

    def history(self, from_date, to_date):
        """Retrieves a history of dispositions on your account."""
        r = self.session.get(self.base_url + "/historiaDyspozycji.html")
        r.raise_for_status()
        bs = BeautifulSoup(r.content, features="html.parser")
        self.next_url = extract_form_action_by_id(bs, form_id="datyHistorii")
        self.view_state = extract_javax_view_state(bs)

        s = "datyHistorii:ok"
        u = "datyHistorii"

        data_od = from_date.strftime("%Y-%m-%d")
        data_do = to_date.strftime("%Y-%m-%d")

        bs = self.__javax_post(
            s,
            u,
            extra_javax_kwargs={
                "datyHistorii:dataOd_input": data_od,
                "datyHistorii:dataDo_input": data_do,
            },
        )
        return parse_history(bs)

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

        print(f'{data!r}')

        r = self.session.post(self.base_url + self.next_url, data=data)
        r.raise_for_status()

        # Handle weird XML document with <redirect url=""> instead of 3xx response
        events = parse_xml_response(r.content)
        for event in events:
            print(f"Partial response event {event!r}")
            if isinstance(event, (Redirect,)):
                redirect_url = event.url
                r = self.session.get(self.base_url + redirect_url)
                r.raise_for_status()

                bs = BeautifulSoup(r.content, features="html.parser")
                self.view_state = extract_javax_view_state(bs)
                return bs

            elif isinstance(event, (PartialResponse,)):
                new_view_state = None
                for key, value in event.updates.items():
                    if key == "j_id1:javax.faces.ViewState:0":
                        new_view_state = value
                    else:
                        raise RuntimeError(f"Unexpected update field {event!r}")
                self.view_state = new_view_state

        # if redirect_url is None:
        #     print(f'Received partial update? {r.content!r}... Skipping')
        # else:
        #     r = self.session.get(self.base_url + redirect_url)
        #     r.raise_for_status()

        #     bs = BeautifulSoup(r.content, features="html.parser")
        #     self.view_state = extract_javax_view_state(bs)
        #     return bs
