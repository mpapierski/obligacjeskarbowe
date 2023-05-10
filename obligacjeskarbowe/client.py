from collections import OrderedDict
from bs4 import BeautifulSoup
import requests

from obligacjeskarbowe.parser import (
    extract_available_bonds,
    extract_balance,
    extract_bonds,
    parse_redirect,
)


LOGIN_BATON = "Zaloguj"


class ObligacjeSkarbowe:
    def __init__(self, username, password):
        self.base_url = "https://www.zakup.obligacjeskarbowe.pl"
        self.username = username
        self.password = password
        self.session = requests.Session()

        self.balance = None
        self.bonds = None
        self.available_bonds = None
        self.available_bonds_lookup = None

        self.next_url = None
        self.view_state = None

    def login(self):
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

    def list_500plus(self):
        r = self.session.get(self.base_url + "/zakupObligacji500Plus.html")
        r.raise_for_status()

        bs = BeautifulSoup(r.content, features="html.parser")
        self.available_bonds = extract_available_bonds(bs)

        self.next_url = bs.select('form[id="dostepneEmisje"]')[0].attrs["action"]
        self.view_state = bs.select('input[name="javax.faces.ViewState"]')[0].attrs[
            "value"
        ]

        self.available_bonds_lookup = OrderedDict(
            [(bond.emisja, bond.wybierz) for bond in self.available_bonds]
        )

        return self.available_bonds

    def purchase(self, emisja, amount):
        wybierz = self.available_bonds_lookup[emisja]  # dict(s, u)

        s = wybierz["s"]
        u = wybierz["u"]

        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": s,
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": u,
            s: s,
            u: u,
            "javax.faces.ViewState": self.view_state,
        }

        # Step 1
        # "Wybierz" -> Dane dyspozycji
        r = self.session.post(self.base_url + self.next_url, data=data)
        r.raise_for_status()

        # Handle weird XML document with <redirect url=""> instead of 3xx response
        redirect_url = parse_redirect(r.content)
        r = self.session.get(self.base_url + redirect_url)
        r.raise_for_status()

        bs = BeautifulSoup(r.content, features="html.parser")
        self.next_url = bs.select('form[id="daneDyspozycji"]')[0].attrs["action"]
        self.view_state = bs.select('input[name="javax.faces.ViewState"]')[0].attrs[
            "value"
        ]

        # "Dalej" -> Dane dyspozycji do zatwierdzenia

        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "daneDyspozycji:ok",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "daneDyspozycji",
            "daneDyspozycji:ok": "daneDyspozycji:ok",
            "daneDyspozycji": "daneDyspozycji",
            "daneDyspozycji:liczbaZamiawianychObligacji": str(amount),
            "javax.faces.ViewState": self.view_state,
        }
        r = self.session.post(self.base_url + self.next_url, data=data)
        r.raise_for_status()
        print("daneDyspozycji", r.content)
        redirect_url = parse_redirect(r.content)
        r = self.session.get(self.base_url + redirect_url)
        r.raise_for_status()

        bs = BeautifulSoup(r.content, features="html.parser")
        self.next_url = bs.select('form[id="zatwierdzenie1"]')[0].attrs["action"]
        self.view_state = bs.select('input[name="javax.faces.ViewState"]')[0].attrs[
            "value"
        ]

        # Zatwierdź dyspozycję

        s = "zatwierdzenie1:ok"
        u = "zatwierdzenie1"

        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "daneDyspozycji:ok",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": u,
            s: s,
            u: u,
            "javax.faces.ViewState": self.view_state,
        }
        r = self.session.post(self.base_url + self.next_url, data=data)
        r.raise_for_status()
        print("potwierdzenie1", r.content)
        redirect_url = parse_redirect(r.content)
        r = self.session.get(self.base_url + redirect_url)
        r.raise_for_status()

    def logout(self):
        r = self.session.get(self.base_url + "/logout")
        r.raise_for_status()
