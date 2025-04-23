from dataclasses import dataclass
import json
import operator
import re
from datetime import date, datetime
from decimal import Decimal
from typing import List

from bs4 import BeautifulSoup


DEFAULT_CURRENCY = "PLN"


def parse_balance(balance):
    balance = balance.replace("\xa0", " ")
    assert (
        DEFAULT_CURRENCY in balance
    ), f"Expected PLN currency but found balance {balance!r}"
    balance = balance.replace(DEFAULT_CURRENCY, "")
    balance = balance.replace(" ", "")
    balance = balance.replace(",", ".")
    return Money(Decimal(balance), DEFAULT_CURRENCY)


def extract_balance(bs):
    items = bs.select("span.formfield-base")
    if len(items) != 1:
        raise RuntimeError(f"Expected 1 item but found {len(items)}")
    span = items[0]
    return parse_balance(span.text)


def html_to_string(html):
    soup = BeautifulSoup(html, features="html.parser")
    return soup.get_text("\n")


@dataclass
class Money:
    amount: Decimal
    currency: str


@dataclass
class InterestPeriod:
    okres: int
    oprocentowanie: Decimal


@dataclass
class Bond:
    """Zakupiona obligacja."""

    emisja: str
    dostepnych: int
    zablokowanych: int
    nominalna: Money
    aktualna: Money
    okresy: List[InterestPeriod]
    data_wykupu: date


@dataclass
class Bonds:
    """Zakupione obligacje."""

    # Saldo środków pieniężnych
    saldo: Money
    # Dostępne emisje obligacji
    emisje: List[Bond]
    # Wartość nominalna dotychczas zakupionych obligacji za środki przyznane w ramach programów wsparcia rodziny wynosi: XYZ
    wartosc_nominalna_800plus: Money


def parse_tooltip(text):
    """This works well for ROD/RO"""
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if m := re.match(r"^okres (\d+) oprocentowanie (\d+(?:\.\d+)?)%$", line):
            (okres, oprocentowanie) = m.groups()
            okres = int(okres)
            oprocentowanie = Decimal(oprocentowanie)
            interest_period = InterestPeriod(okres=okres, oprocentowanie=oprocentowanie)
            results += [interest_period]
        else:
            raise RuntimeError(f"Unable to parse tooltip {line!r}")

    if not results:
        raise RuntimeError(
            f"There should be at least one interest period parsed in {text!r}"
        )

    assert results[0].okres == 1, "First interest period should be marked as 1"
    assert sorted(map(operator.attrgetter("okres"), results))
    assert len(results) / 2 * (results[0].okres + results[-1].okres) == sum(
        map(operator.attrgetter("okres"), results)
    )

    return results


def extract_bonds(bs):
    tbody = bs.select('tbody[id^="stanRachunku:j_idt"]')  # Match only beggining
    # assert len(tbody) == 1, f'{len(tbody)}', list(map(lambda tb: tb.attrs['id'], bs.find_all('tbody')))
    tbody = tbody[0]

    bonds = []

    tooltips = {}
    for tooltip in re.findall(
        r'forTarget:\s*"(stanRachunku:j_idt\d+:\d+:nazwaSkrocona)",\s*content:\s*\{\s*text:\s*(".+?")\s*\}',
        str(bs),
    ):
        (for_target, content) = tooltip
        raw_html = json.loads(content)
        tooltips[for_target] = html_to_string(raw_html)

    for row in tbody.find_all("tr"):
        tds = row.find_all("td")

        tooltip_id = tds[0].find("span").attrs["id"]
        tooltip = tooltips.pop(tooltip_id)

        emisja = tds[0].text.strip()
        dostepnych = int(tds[1].text.strip())
        zablokowanych = int(tds[2].text.strip())
        nominalna = parse_balance(tds[3].text.strip())
        aktualna = parse_balance(tds[4].text.strip())
        data_wykupu = date.fromisoformat(tds[5].text.strip())
        okresy_oprocentowania = parse_tooltip(tooltip)
        bonds.append(
            Bond(
                emisja=emisja,
                dostepnych=dostepnych,
                zablokowanych=zablokowanych,
                nominalna=nominalna,
                aktualna=aktualna,
                data_wykupu=data_wykupu,
                okresy=okresy_oprocentowania,
            )
        )

    return bonds


@dataclass
class AvailableBond:
    emitent: str
    rodzaj: str
    emisja: str
    okres_sprzedazy_od: date
    okres_sprzedazy_do: date
    oprocentowanie: Decimal
    list_emisyjny: str
    wybierz: str
    path: str

    @property
    def dlugosc(self):
        return parse_duration(self.rodzaj)


def parse_emisja(text):
    try:
        (rodzaj, emisja) = re.split(r":\s+", text)
        return (rodzaj.strip(), emisja.strip())
    except ValueError:
        raise RuntimeError(f"Expected two tokens, received {text!r}")


def parse_okres_sprzedazy(text):
    if m := re.match(r"od\s+(\d{4}-\d{2}-\d{2})\s*do\s+(\d{4}-\d{2}-\d{2})", text):
        (od, do) = m.groups()
        return (date.fromisoformat(od), date.fromisoformat(do))
    else:
        raise RuntimeError(f"Expected valid period of time but received {text!r}")


def parse_oprocentowanie(text):
    if m := re.match(r"(\d+,\d+)%", text):
        (oprocentowanie,) = m.groups()
        oprocentowanie = oprocentowanie.replace(",", ".")
        return Decimal(oprocentowanie)
    else:
        raise RuntimeError(f"Expected percentage but found {text!r}")


def parse_wybierz_onclick(text):
    if m := re.match(
        r'PrimeFaces.ab\(\{s:"(dostepneEmisje:j_idt\d+:\d+:wybierz)",f:"(.+?)",u:"(.+?)"\}\);return false;',
        text,
    ):
        (source, _f, render) = m.groups()
        return {
            "s": source,
            "u": render,
        }
    else:
        raise RuntimeError(f"Unexpected onclick code found {text!r}")


def extract_available_bonds(bs, path):
    tbody = bs.select('tbody[id^="dostepneEmisje:j_idt"]')  # Match only beggining

    tbody = tbody[0]

    available = []
    for row in tbody.find_all("tr"):
        tds = row.find_all("td")

        emitent = tds[0].text
        if emitent == "Skarb Państwa":
            td_idx = 1
        else:
            emitent = "Skarb Państwa"
            td_idx = 0

        (rodzaj, emisja) = parse_emisja(tds[td_idx + 0].text)
        (okres_sprzedazy_od, okres_sprzedazy_do) = parse_okres_sprzedazy(
            tds[td_idx + 1].text.strip()
        )
        oprocentowanie = parse_oprocentowanie(tds[td_idx + 2].text)
        if tds[td_idx + 3].text != "pokaż":
            raise RuntimeError(f"Invalid link found {tds[td_idx + 3]})")
        list_emisyjny = tds[td_idx + 3].find("a").attrs["href"]

        wybierz_onclick = tds[td_idx + 4].find("a").attrs["onclick"]
        wybierz = parse_wybierz_onclick(wybierz_onclick)

        available.append(
            AvailableBond(
                emitent=emitent,
                rodzaj=rodzaj,
                emisja=emisja,
                okres_sprzedazy_od=okres_sprzedazy_od,
                okres_sprzedazy_do=okres_sprzedazy_do,
                oprocentowanie=oprocentowanie,
                list_emisyjny=list_emisyjny,
                wybierz=wybierz,
                path=path,
            )
        )

    return available


@dataclass
class XMLResponse:
    pass


@dataclass
class Redirect(XMLResponse):
    url: str


@dataclass
class PartialResponse:
    id: str
    updates: dict


def parse_xml_response(html):
    bs = BeautifulSoup(html, features="xml")
    try:
        if redirect := bs.find("redirect"):
            yield Redirect(url=redirect.attrs["url"])
        elif partial_response := bs.find("partial-response"):
            updates = {}
            if changes := partial_response.find("changes"):
                for update in changes.find_all("update"):
                    updates[update.attrs["id"]] = update.text
            yield PartialResponse(id=partial_response.attrs["id"], updates=updates)

    except AttributeError:
        print(f"{html}")


def extract_form_action_by_id(bs, form_id):
    return bs.select(f'form[id="{form_id}"]')[0].attrs["action"]


def extract_javax_view_state(bs):
    return bs.select('input[name="javax.faces.ViewState"]')[0].attrs["value"]


@dataclass
class DaneDyspozycji:
    kod_emisji: str
    pelna_nazwa_emisji: str
    oprocentowanie: Decimal
    wartosc_nominalna: Money
    maksymalnie: int
    saldo_srodkow_pienieznych: Money
    zgodnosc: bool  # "Czy transakcja jest zgodna z Grupą docelową?"


def parse_szt(text):
    if m := re.match(r"^(\d+) szt$", text):
        (szt,) = m.groups()
        return int(szt)
    else:
        raise RuntimeError(f"Unable to parse szt {text!r}")


def parse_tak_nie(text):
    if text == "TAK":
        return True
    elif text == "NIE":
        return False
    else:
        raise RuntimeError(f"Expected TAK or NIE but received {text}")


def emisje_parse_saldo_srodkow_pienieznych(bs):
    """Only for zakupObligacji.html"""
    node = bs.select("span.formfield-base")[0]
    assert (
        node.previous_sibling.text == "Saldo środków pieniężnych"
    ), f"Unexpected label: {node.previous_sibling.text}"
    return parse_balance(node.text)


def emisje_parse_wartosc_nominalna_800plus(bs):
    """Only for zakupObligacji500Plus.html"""
    node = bs.select("span.formfield-base")[1]
    if m := re.match(
        r"^Wartość nominalna dotychczas zakupionych obligacji za środki przyznane w ramach programów wsparcia rodziny wynosi: (\d+\.\d{2})$",
        node.text,
    ):
        (wartosc,) = m.groups()
        wartosc = wartosc.replace(",", ".")
        return Money(Decimal(wartosc), DEFAULT_CURRENCY)
    else:
        raise RuntimeError(f"Unexpected value for wartosc nominalna: {node.text!r}")


def extract_dane_dyspozycji(bs):
    text = dict(extract_two_columns(bs))
    pelna_nazwa_emisji_1 = text.pop("Pełna nazwa emisji").strip()
    pelna_nazwa_emisji_2 = text.pop("").strip()
    oprocentowanie = parse_oprocentowanie(text.pop("Oprocentowanie"))
    wartosc_nominalna = parse_balance(text.pop("Wartość nominalna jednej obligacji"))

    if maksymalnie_text := text.get("Maksymalnie"):
        maksymalnie = parse_szt(maksymalnie_text)
    else:
        maksymalnie = None

    saldo_srodkow_pienieznych = parse_balance(text.pop("Saldo środków pieniężnych"))
    zgodnosc = parse_tak_nie(text.pop("Czy transakcja jest zgodna z Grupą docelową?"))

    return DaneDyspozycji(
        kod_emisji=text.pop("Kod emisji"),
        pelna_nazwa_emisji=f"{pelna_nazwa_emisji_1} {pelna_nazwa_emisji_2}",
        oprocentowanie=oprocentowanie,
        wartosc_nominalna=wartosc_nominalna,
        maksymalnie=maksymalnie,
        saldo_srodkow_pienieznych=saldo_srodkow_pienieznych,
        zgodnosc=zgodnosc,
    )


def extract_two_columns(bs):
    text = []

    # Gather all the spans with descriptions from left and right column.
    for span in bs.select(".formlabel-230.formlabel-base"):
        left_column = span.text.strip()
        right_column = span.find_next("span").text
        right_column = " ".join(
            map(lambda line: line.strip(), right_column.splitlines())
        )

        assert left_column not in dict(text)
        text.append([left_column, right_column])

    return text


def extract_purchase_step_title(bs):
    return bs.select("div#content > h3")[0].text


def extract_data_przyjecia_zlecenia(bs):
    text = dict(extract_two_columns(bs))
    data_przyjecia = text["Data i czas przyjęcia zlecenia:"]
    return datetime.fromisoformat(data_przyjecia)


DURATION_REGEXP = re.compile(r"(\d+)-(miesięczne|letni[ea])$")


def parse_duration(input_text):
    if m := DURATION_REGEXP.match(input_text):
        (months, duration) = m.groups()
        months = int(months)
        if duration == "miesięczne":
            multiplier = 1
        elif duration.startswith("letni"):
            multiplier = 12
        else:
            raise ValueError("Unable to recognize duration multiplier")
        return months * multiplier
    elif input_text == "roczne":
        return 12
    else:
        raise ValueError("Unable to parse duration")


RE_KOD_NUMER = re.compile(r"^(\w{3}\d{4})/(\d+)$")


@dataclass
class History:
    data_dyspozycji: datetime
    rodzaj_dyspozycji: str
    kod_obligacji: str
    nr_zapisu: int
    seria: int
    liczba_obligacji: int
    kwota_operacji: Decimal
    status: str
    uwagi: str


def parse_history(bs):
    tbody = bs.select('tbody[id="historia:tbl_data"]')[0]
    history = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        data_dyspozycji = date.fromisoformat(tds[0].text)
        rodzaj_dyspozycji = tds[1].text
        kod_obligacji = tds[2].text  # XYZ1234/6666
        numer_zapisu = int(tds[3].text)
        seria = int(tds[4].text)
        liczba_obligacji = int(tds[5].text)
        kwota = Decimal(tds[6].text)
        status = tds[7].text
        uwagi = tds[8].text
        history += [
            History(
                data_dyspozycji=data_dyspozycji,
                rodzaj_dyspozycji=rodzaj_dyspozycji,
                kod_obligacji=kod_obligacji,
                nr_zapisu=numer_zapisu,
                seria=seria,
                liczba_obligacji=liczba_obligacji,
                kwota_operacji=kwota,
                status=status,
                uwagi=uwagi,
            )
        ]
    return history
