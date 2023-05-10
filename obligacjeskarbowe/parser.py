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
    print("??")
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
    data_wykupu: date
    period: int
    interest: Decimal


def parse_tooltip(text):
    """This works well for ROD/RO"""
    if m := re.match(r"^okres (\d+) oprocentowanie (\d+\.\d+)%$", text):
        (okres, interest) = m.groups()
        return (int(okres), Decimal(interest))
    else:
        raise RuntimeError(f"Unable to parse tooltip {text}")


def extract_bonds(bs):
    tbody = bs.find_all("tbody", id="stanRachunku:j_idt140_data")
    assert len(tbody) == 1
    tbody = tbody[0]

    bonds = []

    tooltips = {}
    for tooltip in re.findall(
        r'forTarget: "(stanRachunku:j_idt140:\d+:nazwaSkrocona)", content: \{ text: (".+?") \}',
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
        (period, interest) = parse_tooltip(tooltip)
        bonds.append(
            Bond(
                emisja,
                dostepnych,
                zablokowanych,
                nominalna,
                aktualna,
                data_wykupu,
                period,
                interest,
            )
        )

    return bonds
