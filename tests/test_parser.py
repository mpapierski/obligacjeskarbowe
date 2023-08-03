import datetime
from decimal import Decimal

from bs4 import BeautifulSoup
from obligacjeskarbowe.parser import (
    AvailableBond,
    Bond,
    DaneDyspozycji,
    History,
    Money,
    extract_available_bonds,
    extract_balance,
    extract_bonds,
    extract_dane_dyspozycji,
    extract_data_przyjecia_zlecenia,
    extract_form_action_by_id,
    extract_javax_view_state,
    extract_purchase_step_title,
    parse_duration,
    parse_history,
    parse_szt,
    parse_tak_nie,
    parse_xml_redirect,
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
        r"""<tbody id="dostepneEmisje:j_idt138_data"
    class="ui-datatable-data ui-widget-content">
    <tr data-ri="0" class="ui-widget-content ui-datatable-even" role="row">
        <td role="gridcell" style="white-space: normal;"><span
                id="dostepneEmisje:j_idt138:0:nazwaSkrocona"
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">6-letnie:
                ROS0529</span>
            <script id="dostepneEmisje:j_idt138:0:j_idt140_s"
                type="text/javascript">$(function () { PrimeFaces.cw("ExtTooltip", "widget_dostepneEmisje_j_idt138_0_j_idt140", { id: "dostepneEmisje:j_idt138:0:j_idt140", global: false, shared: false, autoShow: false, forTarget: "dostepneEmisje:j_idt138:0:nazwaSkrocona", content: { text: "RODZINNYCH SZEŚCIOLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH" }, style: { widget: true }, show: { event: 'mouseenter', delay: 0, effect: function () { $(this).fadeIn(500); } }, hide: { event: 'mouseleave', delay: 0, fixed: false, effect: function () { $(this).fadeOut(500); } }, position: { at: 'bottom right', my: 'top left', adjust: { x: 0, y: 0 }, viewport: $(window) } }); });</script>
        </td>
        <td role="gridcell" style="white-space: normal; text-align: center;"><span
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od
                2023-05-01 <br /> do 2023-05-31</span></td>
        <td role="gridcell" style="white-space: normal;"><span
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">7,20%</span>
        </td>
        <td role="gridcell" style="white-space: normal; text-align: center;"><a
                href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROS0529"
                style="font-size: 0.875em;" target="_blank">pokaż</a></td>
        <td role="gridcell" style="text-align: center; font-size: 0.875em;"><a
                id="dostepneEmisje:j_idt138:0:wybierz" href="#"
                class="ui-commandlink ui-widget"
                onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt138:0:wybierz&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a>
        </td>
    </tr>
    <tr data-ri="1" class="ui-widget-content ui-datatable-odd" role="row">
        <td role="gridcell" style="white-space: normal;"><span
                id="dostepneEmisje:j_idt138:1:nazwaSkrocona"
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">12-letnie:
                ROD0535</span>
            <script id="dostepneEmisje:j_idt138:1:j_idt140_s"
                type="text/javascript">$(function () { PrimeFaces.cw("ExtTooltip", "widget_dostepneEmisje_j_idt138_1_j_idt140", { id: "dostepneEmisje:j_idt138:1:j_idt140", global: false, shared: false, autoShow: false, forTarget: "dostepneEmisje:j_idt138:1:nazwaSkrocona", content: { text: "RODZINNYCH DWUNASTOLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH" }, style: { widget: true }, show: { event: 'mouseenter', delay: 0, effect: function () { $(this).fadeIn(500); } }, hide: { event: 'mouseleave', delay: 0, fixed: false, effect: function () { $(this).fadeOut(500); } }, position: { at: 'bottom right', my: 'top left', adjust: { x: 0, y: 0 }, viewport: $(window) } }); });</script>
        </td>
        <td role="gridcell" style="white-space: normal; text-align: center;"><span
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od
                2023-05-01 <br /> do 2023-05-31</span></td>
        <td role="gridcell" style="white-space: normal;"><span
                style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">7,50%</span>
        </td>
        <td role="gridcell" style="white-space: normal; text-align: center;"><a
                href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROD0535"
                style="font-size: 0.875em;" target="_blank">pokaż</a></td>
        <td role="gridcell" style="text-align: center; font-size: 0.875em;"><a
                id="dostepneEmisje:j_idt138:1:wybierz" href="#"
                class="ui-commandlink ui-widget"
                onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt138:1:wybierz&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a>
        </td>
    </tr>
</tbody>""",
        features="html.parser",
    )
    extracted_bonds = extract_available_bonds(bs, path="/foo.html")
    assert extracted_bonds == [
        AvailableBond(
            rodzaj="6-letnie",
            emisja="ROS0529",
            okres_sprzedazy_od=datetime.date(2023, 5, 1),
            okres_sprzedazy_do=datetime.date(2023, 5, 31),
            oprocentowanie=Decimal("7.20"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROS0529",
            wybierz={"s": "dostepneEmisje:j_idt138:0:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            rodzaj="12-letnie",
            emisja="ROD0535",
            okres_sprzedazy_od=datetime.date(2023, 5, 1),
            okres_sprzedazy_do=datetime.date(2023, 5, 31),
            oprocentowanie=Decimal("7.50"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROD0535",
            wybierz={"s": "dostepneEmisje:j_idt138:1:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
    ]
    assert extracted_bonds[0].dlugosc == 6 * 12
    assert extracted_bonds[1].dlugosc == 12 * 12


def test_parse_redirect():
    url = parse_xml_redirect(
        r"""<?xml version='1.0' encoding='UTF-8'?>
<partial-response id="j_id1"><redirect url="/zakupObligacji500Plus.html?execution=e2s2"></redirect></partial-response>"""
    )
    assert url == "/zakupObligacji500Plus.html?execution=e2s2"


def test_extract_form_action():
    bs = BeautifulSoup(
        """<form id="daneDyspozycji" name="daneDyspozycji" method="post" action="/zakupObligacji500Plus.html?execution=e2s2" enctype="application/x-www-form-urlencoded">""",
        features="html.parser",
    )
    url = extract_form_action_by_id(bs, form_id="daneDyspozycji")
    assert url == "/zakupObligacji500Plus.html?execution=e2s2"


def test_extract_view_state():
    bs = BeautifulSoup(
        """<input type="hidden" name="javax.faces.ViewState" id="javax.faces.ViewState" value="e2s2" />""",
        features="html.parser",
    )
    value = extract_javax_view_state(bs)
    assert value == "e2s2"


def test_parse_szt():
    assert parse_szt("123 szt") == 123
    assert parse_szt("10 szt") == 10


def test_parse_tak_nie():
    assert parse_tak_nie("TAK") == True
    assert parse_tak_nie("NIE") == False


def test_extract_dane_dyspozycji_500():
    bs = BeautifulSoup(
        r"""<h4><strong>Obligacje</strong></h4>
<span class="formlabel-230 formlabel-base">Kod emisji</span><span class="formfield-base"
    style="font-weight: bold;">QWER0101</span>
<br />

<span class="formlabel-230 formlabel-base">Pełna nazwa emisji</span><span class="formfield-base"
    style="font-weight: bold;">asdf zxcv </span>
<br />

<span class="formlabel-230 formlabel-base"> </span><span class="formfield-base" style="font-weight: bold;">qwer </span>
<br />

<span class="formlabel-230 formlabel-base">Oprocentowanie</span><span class="formfield-base"
    style="font-weight: bold;">99,99%</span>
<br />

<span class="formlabel-230 formlabel-base">Wartość nominalna jednej obligacji</span><span class="formfield-base"
    style="font-weight: bold;">999,99 PLN</span>
<br />

<hr class="append-bottom prepend-top" />

<h4><strong>Uzupełnij informacje</strong></h4>

<script type="text/javascript">
    function updateWartoscZamawianychObligacji(value) {
        if (!isNaN(value)) {
            var wartoscZamawianychObligacji = document.getElementById('daneDyspozycji:uxWartoscZamawianychObligacji');
            var cenaSprzedazy = document.getElementById('daneDyspozycji:uxCenaSprzedazy');
            wartoscZamawianychObligacji.textContent = (value * cenaSprzedazy.textContent).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$& ').replace('.', ',') + ' PLN';
        }
    };
</script><label id="daneDyspozycji:uxCenaSprzedazy"
    class="ui-outputlabel ui-widget ui-helper-hidden">100</label><label id="daneDyspozycji:j_idt146"
    class="ui-outputlabel ui-widget formlabelXXL text" for="daneDyspozycji:liczbaZamiawianychObligacji">Liczba
    zamawianych obligacji</label><input id="daneDyspozycji:liczbaZamiawianychObligacji"
    name="daneDyspozycji:liczbaZamiawianychObligacji" type="text" autocomplete="off" maxlength="7"
    onkeyup="updateWartoscZamawianychObligacji(this.value);" style="float: none"
    class="ui-inputfield ui-inputtext ui-widget ui-state-default ui-corner-all span-6" />
<script id="daneDyspozycji:liczbaZamiawianychObligacji_s"
    type="text/javascript">PrimeFaces.cw("InputText", "widget_daneDyspozycji_liczbaZamiawianychObligacji", { id: "daneDyspozycji:liczbaZamiawianychObligacji" });</script>
szt
<div id="daneDyspozycji:j_idt148" aria-live="polite" class="error errorBlock noerrorlabelXXL ui-message"></div>
<br />
<span class="formlabel-230 formlabel-base">Wartość zamawianych obligacji PLN</span><span
    id="daneDyspozycji:uxWartoscZamawianychObligacji" class="formfield-base" style="font-weight: bold;">0,00 PLN</span>
<br />

<span class="formlabel-230 formlabel-base">Maksymalnie</span><span class="formfield-base"
    style="font-weight: bold;">123456789 szt</span><span id="daneDyspozycji:uxDeclarationAmount"></span>

<hr class="append-bottom prepend-top" />
<h4><strong>Gotówka</strong></h4>
<span class="formlabel-230 formlabel-base">Saldo środków pieniężnych</span><span class="formfield-base"
    style="font-weight: bold;">1 000 000,00 PLN</span>
<hr class="space" />
<hr class="append-bottom prepend-top" />

<span class="formlabel-230 formlabel-base">Czy transakcja jest zgodna z Grupą docelową?</span><span
    class="formfield-base" style="font-weight: bold; vertical-align: top;">TAK</span>
<br />

<span class="formlabel-230 formlabel-base" style="vertical-align: top;">Koszt transakcji:</span><span
    class="formfield-base" style="font-weight: bold; width: 330px;">Klient nie ponosi opłat przy zakupie
    obligacji.<br /> Wysokość opłaty za przedterminowy wykup obligacji określa List emisyjny danej emisji
    obligacji.</span>
<br />


""",
        features="html.parser",
    )
    dane = extract_dane_dyspozycji(bs)
    assert dane == DaneDyspozycji(
        kod_emisji="QWER0101",
        pelna_nazwa_emisji="asdf zxcv qwer",
        oprocentowanie=Decimal("99.99"),
        wartosc_nominalna=Money(amount=Decimal("999.99"), currency="PLN"),
        maksymalnie=123456789,
        saldo_srodkow_pienieznych=Money(amount=Decimal("1000000.00"), currency="PLN"),
        zgodnosc=True,
    )


def test_extract_dane_dyspozycji():
    bs = bs = BeautifulSoup(
        r"""<h4><strong>Obligacje</strong></h4>
				<span class="formlabel-230 formlabel-base">Kod emisji</span><span class="formfield-base" style="font-weight: bold;">QWER0101</span>
				<br />

				<span class="formlabel-230 formlabel-base">Pełna nazwa emisji</span><span class="formfield-base" style="font-weight: bold;">EMERYTALNYCH DZIESIĘCIOLETNICH OSZCZĘDNOŚCIOWYCH </span>
				<br />

				<span class="formlabel-230 formlabel-base"> </span><span class="formfield-base" style="font-weight: bold;">OBLIGACJI SKARBOWYCH</span>
				<br />

				<span class="formlabel-230 formlabel-base">Oprocentowanie</span><span class="formfield-base" style="font-weight: bold;">999,99%</span>
				<br />

				<span class="formlabel-230 formlabel-base">Wartość nominalna jednej obligacji</span><span id="daneDyspozycji:testWartosc" class="formfield-base" style="font-weight: bold;">555,55 PLN</span>
				<br />

				<hr class="append-bottom prepend-top" />

				<h4><strong>Uzupełnij informacje</strong></h4>

				<script type="text/javascript">
					function updateWartoscZamawianychObligacji(value){
						if(!isNaN(value)) {
							var wartoscZamawianychObligacji = document.getElementById('daneDyspozycji:uxWartoscZamawianychObligacji');
							var cenaSprzedazy = document.getElementById('daneDyspozycji:uxCenaSprzedazy');
							wartoscZamawianychObligacji.textContent = (value * cenaSprzedazy.textContent).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$& ').replace('.',',') + ' PLN';
						}
					};
				</script><label id="daneDyspozycji:uxCenaSprzedazy" class="ui-outputlabel ui-widget ui-helper-hidden">100</label><label id="daneDyspozycji:j_idt140" class="ui-outputlabel ui-widget formlabelXXL text" for="daneDyspozycji:liczbaZamiawianychObligacji">Liczba zamawianych obligacji<span class="ui-outputlabel-rfi">*</span></label><input id="daneDyspozycji:liczbaZamiawianychObligacji" name="daneDyspozycji:liczbaZamiawianychObligacji" type="text" autocomplete="off" maxlength="7" onkeyup="updateWartoscZamawianychObligacji(this.value);" style="float: none" aria-required="true" class="ui-inputfield ui-inputtext ui-widget ui-state-default ui-corner-all span-6" /><script id="daneDyspozycji:liczbaZamiawianychObligacji_s" type="text/javascript">PrimeFaces.cw("InputText","widget_daneDyspozycji_liczbaZamiawianychObligacji",{id:"daneDyspozycji:liczbaZamiawianychObligacji"});</script> szt.
				<div id="daneDyspozycji:j_idt142" aria-live="polite" class="error errorBlock noerrorlabelXXL ui-message"></div>
				<br />
                <span class="formlabel-230 formlabel-base">Wartość zamawianych obligacji PLN</span><span id="daneDyspozycji:uxWartoscZamawianychObligacji" class="formfield-base" style="font-weight: bold;">0,00 PLN</span>

				<hr class="append-bottom prepend-top" />
				<h4><strong>Gotówka</strong></h4>
				<span class="formlabel-230 formlabel-base">Saldo środków pieniężnych</span><span class="formfield-base" style="font-weight: bold;">66 6666,42 PLN</span>
				<hr class="space" />
                    <hr class="append-bottom prepend-top" />

                    <span class="formlabel-230 formlabel-base">Czy transakcja jest zgodna z Grupą docelową?</span><span class="formfield-base" style="font-weight: bold; vertical-align: top;">TAK</span>
                    <br />

                    <span class="formlabel-230 formlabel-base" style="vertical-align: top;">Koszt transakcji:</span><span class="formfield-base" style="font-weight: bold; width: 330px;">Klient nie ponosi opłat przy zakupie obligacji.<br/>                                      Wysokość opłaty za przedterminowy wykup obligacji                                      określa List emisyjny danej emisji obligacji.</span>
                    <br />""",
        features="html.parser",
    )
    dane = extract_dane_dyspozycji(bs)
    assert dane == DaneDyspozycji(
        kod_emisji="QWER0101",
        pelna_nazwa_emisji="EMERYTALNYCH DZIESIĘCIOLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH",
        oprocentowanie=Decimal("999.99"),
        wartosc_nominalna=Money(amount=Decimal("555.55"), currency="PLN"),
        maksymalnie=None,
        saldo_srodkow_pienieznych=Money(amount=Decimal("666666.42"), currency="PLN"),
        zgodnosc=True,
    )


def test_extract_purchase_step_title():
    assert (
        extract_purchase_step_title(
            BeautifulSoup(
                """<div id="content" class="span-18 last">

		<h3>Zakup obligacji 500+ - Dyspozycja zapisana</h3>

        		<noscript>
			<h3 style="color:red">
				Serwis transakcyjny Obligacje Skarbowe wymaga włączonej obsługi JavaScript.<br />
				W używanej przeglądarce internetowej zablokowana jest możliwość wykonywania JavaScript.
				Prosimy włączyć obsługę JavaScript w przeglądarce!
			</h3>
		</noscript>
			<span id="spanContent" style="display: none">

        <span class="formlabel-230 formlabel-base">Biuro Maklerskie PKO Banku Polskiego</span><span class="formfield-base"> </span>
        <br />

        </div>
""",
                features="html.parser",
            )
        )
        == "Zakup obligacji 500+ - Dyspozycja zapisana"
    )


def test_extract_data_przyjecia():
    timestamp = extract_data_przyjecia_zlecenia(
        BeautifulSoup(
            r"""
        <span class="formlabel-230 formlabel-base">Data i czas przyjęcia zlecenia: </span><span class="formfield-base" style="font-weight: bold;">2023-05-10 18:03:47</span>
        <br />""",
            features="html.parser",
        )
    )
    assert timestamp == datetime.datetime(2023, 5, 10, 18, 3, 47)


def test_parse_duration():
    DATA = [
        ("3-miesięczne", 3),
        ("3-miesięczne", 3),
        ("roczne", 12),
        ("roczne", 12),
        ("1-miesięczne", 1),
        ("1-letnia", 12),
        ("2-letnie", 24),
        ("2-letnie", 24),
        ("2-letnia", 24),
        ("2-letnia", 24),
        ("3-letnie", 36),
        ("3-letnie", 36),
        ("4-letnie", 48),
        ("4-letnie", 48),
        ("10-letnia", 120),
        ("10-letnia", 120),
        ("6-letnie", 72),
        ("6-letnie", 72),
        ("12-letnie", 144),
        ("12-letnie", 144),
        ("1234523-miesięczne", 1234523),
        ("1234523-letnia", 1234523 * 12),
    ]
    for input, output in DATA:
        assert parse_duration(input) == output


def test_parse_history():
    bs = BeautifulSoup(
        r"""<tbody class="ui-datatable-data ui-widget-content" id="historia:tbl_data">
										<tr class="ui-widget-content ui-datatable-even" data-ri="0" role="row">
											<td role="gridcell">2010-01-23</td>
											<td role="gridcell">dyspozycja zakupu</td>
											<td role="gridcell">FOO123</td>
											<td role="gridcell">9999</td>
											<td role="gridcell">50</td>
											<td role="gridcell">10</td>
											<td role="gridcell">33335</td>
											<td role="gridcell">zrealizowana</td>
											<td role="gridcell"></td>
										</tr>
															<tr class="ui-widget-content ui-datatable-even" data-ri="0" role="row">
											<td role="gridcell">2010-01-24</td>
											<td role="gridcell">zakup papierów</td>
											<td role="gridcell">FOO123</td>
											<td role="gridcell">9999</td>
											<td role="gridcell">50</td>
											<td role="gridcell">10</td>
											<td role="gridcell">33335</td>
											<td role="gridcell">zrealizowana</td>
											<td role="gridcell">tu są uwagi</td>
										</tr>
                       </tbody>""",
        features="html.parser",
    )
    history = parse_history(bs)
    assert history == [
        History(
            data_dyspozycji=datetime.date(2010, 1, 23),
            rodzaj_dyspozycji="dyspozycja zakupu",
            kod_obligacji="FOO123",
            nr_zapisu=9999,
            seria=50,
            liczba_obligacji=10,
            kwota_operacji=Decimal("33335"),
            status="zrealizowana",
            uwagi="",
        ),
        History(
            data_dyspozycji=datetime.date(2010, 1, 24),
            rodzaj_dyspozycji="zakup papierów",
            kod_obligacji="FOO123",
            nr_zapisu=9999,
            seria=50,
            liczba_obligacji=10,
            kwota_operacji=Decimal("33335"),
            status="zrealizowana",
            uwagi="tu są uwagi",
        ),
    ]
