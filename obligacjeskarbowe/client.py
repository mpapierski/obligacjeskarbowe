from collections import OrderedDict
from datetime import date
import io
import logging
import operator
import os
import pickle
import re
import tempfile
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
from obligacjeskarbowe import two_factor

from obligacjeskarbowe.parser import (
    Bonds,
    PartialResponse,
    Redirect,
    extract_available_bonds,
    extract_bonds,
    extract_dane_dyspozycji,
    extract_data_przyjecia_zlecenia,
    extract_form_action_by_id,
    extract_javax_view_state,
    extract_purchase_step_title,
    emisje_parse_wartosc_nominalna_800plus,
    emisje_parse_saldo_srodkow_pienieznych,
    parse_history,
    parse_login_info,
    parse_xml_response,
)


log = logging.getLogger()

LOGIN_BATON = "Zaloguj"

SESSION_FILE = "obligacjeskarbowe.pickle"
BASE_URL = "https://www.zakup.obligacjeskarbowe.pl"


def preconfigured_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0"
        }
    )
    return session


class ObligacjeSkarbowe:
    def __init__(self):
        self.session = preconfigured_session()
        self.available_bonds = []
        # A lookup table from readable bond name into the internal identifier.
        self.available_bonds_lookup = OrderedDict()

        self.next_url = None
        self.view_state = None

    def persist_session(self):
        """Persists the session to a file."""
        if self.session is None:
            print("No session to persist, skipping")
        else:
            with open(os.path.join(tempfile.gettempdir(), SESSION_FILE), "wb") as f:
                pickle.dump((self.session, self.next_url, self.view_state), f)

    def clear_session(self):
        """Clears the session."""
        try:
            os.remove(os.path.join(tempfile.gettempdir(), SESSION_FILE))
        except FileNotFoundError:
            pass
        self.session = None
        self.view_state = None
        self.next_url = None

    def restore_session(self):
        """Restores the session from a file."""
        filename = os.path.join(tempfile.gettempdir(), SESSION_FILE)
        try:
            with open(filename, "rb") as f:
                (session, next_url, view_state) = pickle.load(f)
                self.session = session
                self.next_url = next_url
                self.view_state = view_state
        except FileNotFoundError:
            raise RuntimeError("Session file not found")
        except EOFError:
            raise RuntimeError("Session file is empty")
        except Exception as e:
            raise RuntimeError(f"Failed to restore session {filename}: {e}")

    def login(self, username, password, topic):
        """Performs a login procedure.

        :param str username: Username
        :param str password: Password
        :param str topic: Topic for two factor authentication
        :raises RuntimeError: If the login fails
        """

        r = self.session.get(BASE_URL + "/daneRachunku.html")
        r.raise_for_status()
        o = urlparse(r.url)
        if o.path == "/daneRachunku.html":
            print("Already logged in, skipping login")
            bs = BeautifulSoup(r.content, features="html.parser")
            login_info = parse_login_info(bs)
            return login_info

        assert o.path == "/login.html", f"Unexpected path {o.path!r}"
        print("Session expired, or not logged in")
        form = {
            "username": username,
            "password": password,
            "baton": LOGIN_BATON,
        }
        r = self.session.post(BASE_URL + "/login", data=form)
        r.raise_for_status()

        bs = BeautifulSoup(r.content, features="html.parser")
        prompt = bs.select('span[id="spanContent"]')[0].text.strip()

        print(f"Login prompt: {prompt!r}")

        prompt_lines = prompt.splitlines()

        if m := re.match(
            r"^Podaj kod jednorazowy dla operacji nr (\d+) z (\d{2})-(\d{2})-(\d{4})$",
            prompt_lines[0],
        ):
            (
                operacja_nr,
                dzien,
                miesiac,
                rok,
            ) = m.groups()

            data_kodu = date(
                int(rok),
                int(miesiac),
                int(dzien),
            )

            print(
                f"Potwierdzenie danych logowania: Czekanie na kod nr {operacja_nr} z dnia {data_kodu}..."
            )

            # "Nie rozpoznaliśmy Twojego urządzenia." in prompt or:
            token_stream = two_factor.wait_for_token(topic)

            open_event = next(token_stream)

            if not isinstance(open_event, (two_factor.Open,)):
                raise RuntimeError("Expected open event but got {open_event!r}")

            self.next_url = extract_form_action_by_id(bs, form_id="j_idt101")
            print(f"Next URL: {self.next_url!r}")
            self.view_state = extract_javax_view_state(bs)
            print(f"View state: {self.view_state!r}")

            print("Waiting for token...")

            token = next(token_stream)

            print(f"Received token {token!r}")

            time.sleep(5)

            r = self.session.post(
                BASE_URL + self.next_url,
                data={
                    "j_idt101": "j_idt101",
                    "j_idt101:uxCode": token.kod,
                    "j_idt101:j_idt123": "",
                    "javax.faces.ViewState": self.view_state,
                },
            )
            r.raise_for_status()
            bs = BeautifulSoup(r.content, features="html.parser")

        elif "Nie rozpoznaliśmy Twojego urządzenia." in prompt:
            token_stream = two_factor.wait_for_token(topic)

            open_event = next(token_stream)
            if not isinstance(open_event, (two_factor.Open,)):
                raise RuntimeError("Expected open event but got {open_event!r}")

            self.next_url = extract_form_action_by_id(bs, form_id="j_idt89")
            self.view_state = extract_javax_view_state(bs)

            s = "j_idt89:j_idt97"  # "Dostęp jednorazowy"
            u = "j_idt89"
            bs = self.__javax_post(s, u)

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

        else:
            raise RuntimeError(
                f"Unexpected login prompt {prompt!r}. Expected 'Podaj kod jednorazowy dla operacji nr ...'"
            )
        self.session.cookies.set("obligacje_set", "none")
        log.info("Logged in")
        return parse_login_info(bs)

    def __bonds_navigate(self, path):
        """Navigate bonds page, does not maintain internal lookup database."""
        r = self.session.get(f"{BASE_URL}{path}")
        r.raise_for_status()
        self.ensure_session_exists(r)
        bs = BeautifulSoup(r.content, features="html.parser")

        available_bonds = extract_available_bonds(bs, path)
        self.next_url = extract_form_action_by_id(bs, form_id="dostepneEmisje")
        self.view_state = extract_javax_view_state(bs)
        return (available_bonds, bs)

    def __extract_available_bonds(self, path):
        """Extracts list of bonds but also maintains a lookup database."""
        (new_available_bonds, bs) = self.__bonds_navigate(path)
        self.available_bonds += new_available_bonds
        new_bonds_lookup = OrderedDict(
            [(bond.emisja, bond) for bond in self.available_bonds]
        )
        self.available_bonds_lookup.update(new_bonds_lookup)
        log.info(f"Found {len(new_bonds_lookup)} bonds at {path}")
        return (new_available_bonds, bs)

    def __bonds_800plus(self):
        (new_available_bonds, bs) = self.__extract_available_bonds(
            "/zakupObligacji500Plus.html"
        )
        saldo = emisje_parse_saldo_srodkow_pienieznych(bs)
        wartosc_nominalna = emisje_parse_wartosc_nominalna_800plus(bs)
        return Bonds(
            saldo=saldo,
            emisje=new_available_bonds,
            wartosc_nominalna_800plus=wartosc_nominalna,
        )

    def __bonds(self):
        """Returns a list of bonds available for purchase."""
        (new_available_bonds, bs) = self.__extract_available_bonds(
            "/zakupObligacji.html"
        )
        saldo = emisje_parse_saldo_srodkow_pienieznych(bs)
        return Bonds(
            saldo=saldo, emisje=new_available_bonds, wartosc_nominalna_800plus=None
        )

    def list_500plus_bonds(self):
        """Lists available bonds for 500+ program"""
        return self.__bonds_800plus()

    def list_bonds(self):
        """Lists available bonds"""
        bonds_800plus = self.__bonds_800plus()
        assert bonds_800plus.wartosc_nominalna_800plus is not None
        bonds = self.__bonds()

        assert (
            bonds_800plus.saldo == bonds.saldo
        ), f"Saldo does not match {bonds_800plus.saldo} != {bonds.saldo}"

        all_bonds = Bonds(
            saldo=bonds_800plus.saldo,
            emisje=bonds.emisje + bonds_800plus.emisje,
            wartosc_nominalna_800plus=bonds_800plus.wartosc_nominalna_800plus,
        )

        all_bonds.emisje.sort(
            key=operator.attrgetter(
                "dlugosc", "okres_sprzedazy_od", "oprocentowanie", "emisja"
            )
        )
        return all_bonds

    def ensure_session_exists(self, response):
        o = urlparse(response.url)
        if o.path == "/login.html":
            self.clear_session()
            raise RuntimeError("Session expired, please login again")

    def list_portfolio(self):
        all_portfolio = []
        r = self.session.get(f"{BASE_URL}/stanRachunku.html")
        r.raise_for_status()
        self.ensure_session_exists(r)

        bs = BeautifulSoup(r.content, features="html.parser")

        # Figure out "idt" number based on the <select> element of the form we're interested in to submit.
        # This seems to change from time to time, so we need to extract it dynamically.
        idt_number = None
        select_elem = bs.find(
            "select", id=re.compile(r"^stanRachunku:j_idt(\d+):j_id\d+$")
        )
        if select_elem:
            match = re.match(r"^stanRachunku:j_idt(\d+):j_id\d+$", select_elem["id"])
            if match:
                idt_number = match.group(1)
                print("Extracted idt_number:", idt_number)
        if idt_number is None:
            raise RuntimeError("Could not extract idt_number from select element")

        self.view_state = extract_javax_view_state(bs)

        first = 20
        per_page = 20

        # Serves as a set of already known bonds to ensure there are no errors while peforming requests.
        bonds_already_known = set()

        while True:
            portfolio = extract_bonds(bs)
            if not portfolio:
                print(f"Done because of empty page {first} {per_page}")
                break

            # Check for duplicates in the portfolio to ensure there are no errors while performing requests.
            for bond in portfolio:
                if bond.emisja in bonds_already_known:
                    raise RuntimeError(
                        f"Duplicate bond found in portfolio: {bond.emisja!r} at {first} {per_page}"
                    )
                bonds_already_known.add(bond.emisja)

            all_portfolio += portfolio
            r = self.session.post(
                f"{BASE_URL}/stanRachunku.html?execution={self.view_state}",
                data={
                    "javax.faces.partial.ajax": "true",
                    "javax.faces.source": f"stanRachunku:j_idt{idt_number}",
                    "javax.faces.partial.execute": f"stanRachunku:j_idt{idt_number}",
                    "javax.faces.partial.render": f"stanRachunku:j_idt{idt_number}",
                    f"stanRachunku:j_idt{idt_number}": f"stanRachunku:j_idt{idt_number}",
                    f"stanRachunku:j_idt{idt_number}_pagination": "true",
                    f"stanRachunku:j_idt{idt_number}_first": f"{first}",
                    f"stanRachunku:j_idt{idt_number}_rows": f"{per_page}",
                    f"stanRachunku:j_idt{idt_number}_skipChildren": "true",
                    f"stanRachunku:j_idt{idt_number}_encodeFeature": "true",
                    "stanRachunku": "stanRachunku",
                    # "stanRachunku:j_idt171_rppDD": [
                    #    "20",
                    #    "20"
                    # ] wtf?
                    "javax.faces.ViewState": self.view_state,
                },
            )
            r.raise_for_status()
            self.ensure_session_exists(r)

            events = parse_xml_response(r.content)
            for event in events:
                if isinstance(event, (PartialResponse,)):
                    for key, value in event.updates.items():
                        if key == f"stanRachunku:j_idt{idt_number}":
                            if value == " ":
                                print(f"Done {first} {per_page}")
                                return all_portfolio
                            else:
                                print(f"{first} Partial update {key!r} {value!r}")
                                element = bs.find(
                                    "tbody", id=f"stanRachunku:j_idt{idt_number}_data"
                                )
                                element.replace_with(
                                    BeautifulSoup(
                                        f'<tbody id="stanRachunku:j_idt{idt_number}_data">{value}</tbody>',
                                        features="html.parser",
                                    )
                                )
                        elif key == "j_id1:javax.faces.ViewState:0":
                            self.view_state = value
                        else:
                            raise RuntimeError(
                                f"Unexpected update field {key!r} {value!r}"
                            )
                else:
                    raise RuntimeError(f"Unexpected event {event!r} in portfolio list")
            first += 20

        return all_portfolio

    def purchase(self, emisja, amount, force):
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
        if (
            not force
            and dane_dyspozycji.saldo_srodkow_pienieznych.amount < expected_cost
        ):
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
        available_bond = self.available_bonds_lookup[emisja]

        # Navigate to appropriate path for a given bond since the order of page visits matters.
        _available_bonds = self.__bonds_navigate(available_bond.path)
        del _available_bonds

        wybierz = available_bond.wybierz
        bs = self.__javax_post(s=wybierz["s"], u=wybierz["u"])

        title = extract_purchase_step_title(bs)
        self.next_url = extract_form_action_by_id(bs, form_id="daneDyspozycji")
        title = extract_purchase_step_title(bs)
        print(f"Krok 1: {title}...")
        return extract_dane_dyspozycji(bs)

    def history(self, from_date, to_date):
        """Retrieves a history of dispositions on your account."""
        r = self.session.get(BASE_URL + "/historiaDyspozycji.html")
        r.raise_for_status()
        self.ensure_session_exists(r)
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
        r = self.session.get(BASE_URL + "/logout")
        r.raise_for_status()

    def download_pdf_from_mf(self, bond_name):
        r = self.session.get(
            "https://www.finanse.mf.gov.pl/dlug-publiczny/bony-i-obligacje-hurtowe/wyszukiwarka-listow-emisyjnych"
        )
        r.raise_for_status()
        params = {
            "p_p_id": "securityissueviewportlet_WAR_mfportalsecuritiestradingportlet",
            "p_p_lifecycle": "2",
            "p_p_state": "normal",
            "p_p_mode": "view",
            "p_p_cacheability": "cacheLevelPage",
            "p_p_col_id": "column-1",
            "p_p_col_pos": "1",
            "p_p_col_count": "2",
        }

        match = re.match(r"([A-Za-z]+)(\d+)$", bond_name)
        if match:
            prefix = match.group(1)
            numeric_part = int(match.group(2))
        else:
            raise ValueError(f"bond_name {bond_name!r} does not match expected format")

        data = f"GET_ISSUES\n{prefix}\n{prefix}{numeric_part:04d}\n\n"
        print(
            f"Getting PDF for obsolete bond {bond_name} from finanse.mf.gov.pl: {data!r}"
        )
        r = self.session.post(
            "https://www.finanse.mf.gov.pl/dlug-publiczny/bony-i-obligacje-hurtowe/wyszukiwarka-listow-emisyjnych",
            params=params,
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
                "Connection": "keep-alive",
            },
            data=data,
        )
        r.raise_for_status()
        json_data = r.json()
        if len(json_data) == 0:
            raise RuntimeError(
                f"Bond letter of issuance for {bond_name} not found in finanse.mf.gov.pl"
            )
        if len(json_data) > 1:
            raise RuntimeError(
                f"Multiple bond letters of issuance for {bond_name} found in finanse.mf.gov.pl"
            )

        bond = json_data[0]
        if len(bond["letters"]) != 1:
            raise RuntimeError(
                f"Multiple bond letters of issuance for {bond_name} found in finanse.mf.gov.pl"
            )

        url = bond["letters"][0]

        params = {
            "p_p_id": "securityissueviewportlet_WAR_mfportalsecuritiestradingportlet",
            "p_p_lifecycle": "2",
            "p_p_state": "normal",
            "p_p_mode": "view",
            "p_p_cacheability": "cacheLevelPage",
            "p_p_col_id": "column-1",
            "p_p_col_pos": "1",
            "p_p_col_count": "2",
            "fileName": url,  # the pdf file name is provided in the "url" variable
            "time": str(int(time.time() * 1000)),
        }
        pdf_response = self.session.get(
            "https://www.finanse.mf.gov.pl/dlug-publiczny/bony-i-obligacje-hurtowe/wyszukiwarka-listow-emisyjnych",
            params=params,
        )
        pdf_response.raise_for_status()
        print(f"Getting PDF for obsolete bond {bond_name} from finanse.mf.gov.pl")
        return io.BytesIO(pdf_response.content)

    def download_pdf(self, bond_name):
        """Downloads a bond letter of issue by name.

        :param str bond_name: Name of the bond
        :param str path: Path to save the bond
        """
        session = preconfigured_session()
        params = {"id": bond_name.lower()}
        r = session.get(
            "https://www.obligacjeskarbowe.pl/listy-emisyjne/", params=params
        )
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(
                    f"Bond letter of issuance for {bond_name} not found in obligacjeskarbowe.pl"
                )
                return self.download_pdf_from_mf(bond_name)
            else:
                raise
        soup = BeautifulSoup(r.content, "html.parser")
        a_tag = soup.find("a", class_="files__item issue-letter__file")
        try:
            if a_tag:
                pdf_url = a_tag.get("href")
                if not pdf_url.startswith("http"):
                    pdf_url = "https://www.obligacjeskarbowe.pl" + pdf_url
                pdf_response = session.get(pdf_url)
                pdf_response.raise_for_status()
                return io.BytesIO(pdf_response.content)
            else:
                raise RuntimeError(
                    f"Bond letter of issuance for {bond_name} not found in obligacjeskarbowe.pl"
                )
        except (RuntimeError, requests.exceptions.HTTPError) as e:
            print(f"Error downloading PDF for {bond_name}: {e}")
            return self.download_pdf_from_mf(bond_name)

    def archive(self):
        """List of all bonds in the archive."""
        response = self.session.get(
            "https://www.obligacjeskarbowe.pl/archiwum-listow-emisyjnych/"
        )
        response.raise_for_status()

        # Bond types that are no longer searchable although they're still listed on the page source.
        OBSOLETE_BONDS = {
            "tz": "Obligacje 3-letnie TZ",
            "sp": "Obligacje 5-letnie SP",
        }

        bs = BeautifulSoup(response.content, features="html.parser")
        select_element = bs.find("select", id="id_type_bonds")
        if not select_element:
            raise RuntimeError('Select element with id "id_type_bonds" not found.')
        bonds_options = OrderedDict()
        for option in select_element.find_all("option"):
            bonds_options[option.get("value")] = option.get_text(strip=True)

        issue_select = bs.find("select", id="id_issue_bonds")
        if not issue_select:
            raise RuntimeError('Select element with id "id_issue_bonds" not found.')
        issue_bonds = OrderedDict()
        for option in issue_select.find_all("option"):
            data_id = option.get("data-id")
            if data_id is not None:
                url = option.get("value")
                text = option.get_text(strip=True)
                if data_id not in issue_bonds:
                    issue_bonds[data_id] = []
                issue_bonds[data_id].append({"url": url, "name": text})

        collected_data = OrderedDict()
        for data_id, bonds in issue_bonds.items():
            issues = []
            for bond in bonds:
                issues.append(
                    {
                        "url": bond["url"],
                        "name": bond["name"],
                    }
                )

            bond_name = bonds_options.get(data_id)
            if bond_name is None:
                bond_name = OBSOLETE_BONDS.get(data_id)
            if bond_name is None:
                raise RuntimeError(f"Bond name not found for {data_id!r}")

            collected_data[data_id] = {
                "name": bond_name,
                "bonds": issues,
            }

        return collected_data

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
            "javax.faces.ViewState": self.view_state,
        }

        if u is not None:
            data[u] = u

        data.update(extra_javax_kwargs)

        print(f"POST data {data!r}")

        r = self.session.post(
            BASE_URL + self.next_url,
            data=data,
        )
        r.raise_for_status()
        self.ensure_session_exists(r)
        print(f"Response headers {r.headers!r}")

        # Handle weird XML document with <redirect url=""> instead of 3xx response
        events = parse_xml_response(r.content)

        for event in events:
            print(f"Partial response event {event!r}")
            if isinstance(event, (Redirect,)):
                redirect_url = event.url
                r = self.session.get(BASE_URL + redirect_url)
                r.raise_for_status()
                self.ensure_session_exists(r)

                bs = BeautifulSoup(r.content, features="html.parser")
                self.view_state = extract_javax_view_state(bs)
                return bs

            elif isinstance(event, (PartialResponse,)):
                new_view_state = None
                for key, value in event.updates.items():
                    if key == "j_id1:javax.faces.ViewState:0":
                        new_view_state = value
                    elif key == "j_idt100":
                        continue
                    elif key == "j_idt101":
                        continue
                    else:
                        raise RuntimeError(f"Unexpected update field {key!r} {value!r}")
                self.view_state = new_view_state
            else:
                raise RuntimeError(f"Unexpected event {event!r}")
