from dataclasses import dataclass
import json
import re
from datetime import date
from decimal import Decimal
import sys

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
    assert len(items) == 1, f"Expected 1 item but found {len(items)}"
    span = items[0]
    return parse_balance(span.text)


def html_to_string(html):
    return BeautifulSoup(html, features="html.parser").text


@dataclass
class Money:
    amount: Decimal
    currency: str


@dataclass
class Bond:
    """Zakupiona obligacja."""

    emisja: str
    dostepnych: int
    zablokowanych: int
    nominalna: Money
    aktualna: Money
    okres: int
    oprocentowanie: Decimal
    data_wykupu: date


def parse_tooltip(text):
    """This works well for ROD/RO"""
    if m := re.match(r"^okres (\d+) oprocentowanie (\d+\.\d+)%$", text):
        (okres, oprocentowanie) = m.groups()
        return (int(okres), Decimal(oprocentowanie))
    else:
        raise RuntimeError(f"Unable to parse tooltip {text}")


def extract_bonds(bs):
    # tbody = bs.find_all("tbody", id="stanRachunku:j_idt140_data")
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
        (okres, oprocentowanie) = parse_tooltip(tooltip)
        bonds.append(
            Bond(
                emisja=emisja,
                dostepnych=dostepnych,
                zablokowanych=zablokowanych,
                nominalna=nominalna,
                aktualna=aktualna,
                data_wykupu=data_wykupu,
                okres=okres,
                oprocentowanie=oprocentowanie,
            )
        )

    return bonds


@dataclass
class AvailableBond:
    rodzaj: str
    emisja: str
    okres_sprzedazy_od: date
    okres_sprzedazy_do: date
    oprocentowanie: Decimal
    list_emisyjny: str
    wybierz: str


def parse_emisja(text):
    return text.split(": ")


def parse_okres_sprzedazy(text):
    if m := re.match(r"od (\d{4}-\d{2}-\d{2})\s*do\s*(\d{4}-\d{2}-\d{2})", text):
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
        r'PrimeFaces.ab\(\{s:"(dostepneEmisje:j_idt\d+:\d+:wybierz)",u:"(.+?)"\}\);return false;',
        text,
    ):
        (source, render) = m.groups()
        return {
            "s": source,
            "u": render,
        }
    else:
        raise RuntimeError(f"Unexpected onclick code found {text!r}")


def extract_available_bonds(bs):
    tbody = bs.select('tbody[id^="dostepneEmisje:j_idt"]')  # Match only beggining

    available = []
    for row in tbody[0].find_all("tr"):
        tds = row.find_all("td")
        (rodzaj, emisja) = parse_emisja(tds[0].text)
        (okres_sprzedazy_od, okres_sprzedazy_do) = parse_okres_sprzedazy(
            tds[1].text.strip()
        )
        oprocentowanie = parse_oprocentowanie(tds[2].text)
        if tds[3].text != "pokaż":
            raise RuntimeError(f"Invalid link found {tds[3]})")
        list_emisyjny = tds[3].find("a").attrs["href"]

        wybierz = tds[4].find("a").attrs["onclick"]

        url = bs.select('form[name="dostepneEmisje"]')[0].attrs["action"]

        wybierz = parse_wybierz_onclick(wybierz)

        # wybierz['url'] =

        available.append(
            AvailableBond(
                rodzaj,
                emisja,
                okres_sprzedazy_od,
                okres_sprzedazy_do,
                oprocentowanie,
                list_emisyjny,
                wybierz,
            )
        )

    return available


def parse_redirect(html):
    bs = BeautifulSoup(html, features="xml")
    return bs.find("redirect").attrs["url"]
