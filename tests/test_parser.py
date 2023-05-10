import datetime
from decimal import Decimal

from bs4 import BeautifulSoup
from obligacjeskarbowe.parser import (
    AvailableBond,
    Bond,
    Money,
    extract_available_bonds,
    extract_balance,
    extract_bonds,
    parse_redirect,
)


def test_extract_balance():
    bs = BeautifulSoup(
        r"""<h4><strong>Gotówka</strong></h4>
			<span class="formlabel-230 formlabel-base">Saldo środków pieniężnych</span><span class="formfield-base" style="font-weight: bold;">42 4242,42 PLN</span>
			<br />
""",
        features="html.parser",
    )
    balance = extract_balance(bs)
    assert balance.amount == Decimal(424242) + (Decimal(42) / Decimal(100))
    assert balance.currency == "PLN"


def test_extract_bonds():
    bs = BeautifulSoup(
        r"""<tbody id="stanRachunku:j_idt140_data" class="ui-datatable-data ui-widget-content">
    <tr data-ri="0" class="ui-widget-content ui-datatable-even" role="row">
        <td role="gridcell"><span id="stanRachunku:j_idt140:0:nazwaSkrocona"
                style="font-size: 0.875em; font-style: normal; text-align: left; width: 100%; display: inline-block; white-space: nowrap;">ZXCV4567</span>
            <script id="stanRachunku:j_idt140:0:j_idt154_s"
                type="text/javascript">$(function () { PrimeFaces.cw("ExtTooltip", "widget_stanRachunku_j_idt140_0_j_idt154", { id: "stanRachunku:j_idt140:0:j_idt154", global: false, shared: false, autoShow: false, forTarget: "stanRachunku:j_idt140:0:nazwaSkrocona", content: { text: "okres 1 oprocentowanie 7.5%<\/br>" }, style: { widget: true }, show: { event: 'mouseenter', delay: 0, effect: function () { $(this).fadeIn(500); } }, hide: { event: 'mouseleave', delay: 0, fixed: false, effect: function () { $(this).fadeOut(500); } }, position: { at: 'bottom right', my: 'top left', adjust: { x: 0, y: 0 }, viewport: $(window) } }); });</script>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">5253</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">53</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">123 000,00 PLN</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">456 111,22 PLN</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">2074-10-25</span>
        </td>
    </tr>
    <tr data-ri="1" class="ui-widget-content ui-datatable-odd" role="row">
        <td role="gridcell"><span id="stanRachunku:j_idt140:1:nazwaSkrocona"
                style="font-size: 0.875em; font-style: normal; text-align: left; width: 100%; display: inline-block; white-space: nowrap;">ASDF1234</span>
            <script id="stanRachunku:j_idt140:1:j_idt154_s"
                type="text/javascript">$(function () { PrimeFaces.cw("ExtTooltip", "widget_stanRachunku_j_idt140_1_j_idt154", { id: "stanRachunku:j_idt140:1:j_idt154", global: false, shared: false, autoShow: false, forTarget: "stanRachunku:j_idt140:1:nazwaSkrocona", content: { text: "okres 1 oprocentowanie 7.5%<\/br>" }, style: { widget: true }, show: { event: 'mouseenter', delay: 0, effect: function () { $(this).fadeIn(500); } }, hide: { event: 'mouseleave', delay: 0, fixed: false, effect: function () { $(this).fadeOut(500); } }, position: { at: 'bottom right', my: 'top left', adjust: { x: 0, y: 0 }, viewport: $(window) } }); });</script>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">999</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">998</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">456 789,99 PLN</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">987 654,60 PLN</span>
        </td>
        <td role="gridcell"><span
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">3011-01-01</span>
        </td>
    </tr>
</tbody>""",
        features="html.parser",
    )
    bonds = extract_bonds(bs)

    assert bonds == [
        Bond(
            emisja="ZXCV4567",
            dostepnych=5253,
            zablokowanych=53,
            nominalna=Money(amount=Decimal("123000.00"), currency="PLN"),
            aktualna=Money(amount=Decimal("456111.22"), currency="PLN"),
            data_wykupu=datetime.date(2074, 10, 25),
            okres=1,
            oprocentowanie=Decimal("7.5"),
        ),
        Bond(
            emisja="ASDF1234",
            dostepnych=999,
            zablokowanych=998,
            nominalna=Money(amount=Decimal("456789.99"), currency="PLN"),
            aktualna=Money(amount=Decimal("987654.60"), currency="PLN"),
            data_wykupu=datetime.date(3011, 1, 1),
            okres=1,
            oprocentowanie=Decimal("7.5"),
        ),
    ]


def test_available_bonds():
    bs = BeautifulSoup(
        open("zakupObligacji500Plus.html").read(), features="html.parser"
    )
    print(extract_available_bonds(bs))
    assert extract_available_bonds(bs) == [
        AvailableBond(
            rodzaj="6-letnie",
            emisja="ROS0529",
            okres_sprzedazy_od=datetime.date(2023, 5, 1),
            okres_sprzedazy_do=datetime.date(2023, 5, 31),
            oprocentowanie=Decimal("7.20"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROS0529",
            wybierz={"s": "dostepneEmisje:j_idt138:0:wybierz", "u": "dostepneEmisje"},
        ),
        AvailableBond(
            rodzaj="12-letnie",
            emisja="ROD0535",
            okres_sprzedazy_od=datetime.date(2023, 5, 1),
            okres_sprzedazy_do=datetime.date(2023, 5, 31),
            oprocentowanie=Decimal("7.50"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROD0535",
            wybierz={"s": "dostepneEmisje:j_idt138:1:wybierz", "u": "dostepneEmisje"},
        ),
    ]


def test_parse_redirect():
    url = parse_redirect(
        r"""<?xml version='1.0' encoding='UTF-8'?>
<partial-response id="j_id1"><redirect url="/zakupObligacji500Plus.html?execution=e2s2"></redirect></partial-response>"""
    )
    assert url == "/zakupObligacji500Plus.html?execution=e2s2"
