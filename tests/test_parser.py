import datetime
from decimal import Decimal
import json

from bs4 import BeautifulSoup
from obligacjeskarbowe.parser import (
    AvailableBond,
    Bond,
    PartialResponse,
    DaneDyspozycji,
    History,
    InterestPeriod,
    Money,
    Redirect,
    extract_available_bonds,
    extract_balance,
    extract_bonds,
    extract_dane_dyspozycji,
    extract_data_przyjecia_zlecenia,
    extract_form_action_by_id,
    extract_javax_view_state,
    extract_purchase_step_title,
    emisje_parse_saldo_srodkow_pienieznych,
    emisje_parse_wartosc_nominalna_800plus,
    html_to_string,
    parse_duration,
    parse_history,
    parse_szt,
    parse_tak_nie,
    parse_tooltip,
    parse_xml_response,
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
        r"""<tbody id="stanRachunku:j_idt171_data" class="ui-datatable-data ui-widget-content"><tr data-ri="0" class="ui-widget-content ui-datatable-even"><td role="gridcell"><span id="stanRachunku:j_idt171:0:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: left; width: 100%; display: inline-block; white-space: nowrap;">ZXCV4567</span><script id="stanRachunku:j_idt171:0:j_idt185_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_stanRachunku_j_idt171_0_j_idt185",{id:"stanRachunku:j_idt171:0:j_idt185",global:false,shared:false,autoShow:false,forTarget:"stanRachunku:j_idt171:0:nazwaSkrocona",content: {text: "okres 1 oprocentowanie 12.55%<\/br>okres 2 oprocentowanie 5.55%<\/br>"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">999</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">0</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">11 1111,11 PLN</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">33 3333,33 PLN</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">2033-08-01</span></td></tr><tr data-ri="1" class="ui-widget-content ui-datatable-odd"><td role="gridcell"><span id="stanRachunku:j_idt171:1:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: left; width: 100%; display: inline-block; white-space: nowrap;">ASDF5555</span><script id="stanRachunku:j_idt171:1:j_idt185_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_stanRachunku_j_idt171_1_j_idt185",{id:"stanRachunku:j_idt171:1:j_idt185",global:false,shared:false,autoShow:false,forTarget:"stanRachunku:j_idt171:1:nazwaSkrocona",content: {text: "okres 1 oprocentowanie 7.5%<\/br>okres 2 oprocentowanie 69%<\/br>okres 3 oprocentowanie 6.05%<\/br>"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">666</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">0</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">55 5555,55 PLN</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: right; width: 100%; display: inline-block; white-space: nowrap;">99 999,99 PLN</span></td><td role="gridcell"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">2043-10-25</span></td></tr></tbody>""",
        features="html.parser",
    )
    bonds = extract_bonds(bs)
    print(bonds)

    assert bonds == [
        Bond(
            emisja="ZXCV4567",
            dostepnych=999,
            zablokowanych=0,
            nominalna=Money(amount=Decimal("111111.11"), currency="PLN"),
            aktualna=Money(amount=Decimal("333333.33"), currency="PLN"),
            okresy=[
                InterestPeriod(okres=1, oprocentowanie=Decimal("12.55")),
                InterestPeriod(okres=2, oprocentowanie=Decimal("5.55")),
            ],
            data_wykupu=datetime.date(2033, 8, 1),
        ),
        Bond(
            emisja="ASDF5555",
            dostepnych=666,
            zablokowanych=0,
            nominalna=Money(amount=Decimal("555555.55"), currency="PLN"),
            aktualna=Money(amount=Decimal("99999.99"), currency="PLN"),
            okresy=[
                InterestPeriod(okres=1, oprocentowanie=Decimal("7.5")),
                InterestPeriod(okres=2, oprocentowanie=Decimal("69")),
                InterestPeriod(okres=3, oprocentowanie=Decimal("6.05")),
            ],
            data_wykupu=datetime.date(2043, 10, 25),
        ),
    ]


def test_available_bonds():
    bs = BeautifulSoup(
        r"""<tbody id="dostepneEmisje:j_idt190_data" class="ui-datatable-data ui-widget-content"><tr data-ri="0" class="ui-widget-content ui-datatable-even"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:0:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">6-letnie: ROS0431</span><script id="dostepneEmisje:j_idt190:0:j_idt192_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_0_j_idt192",{id:"dostepneEmisje:j_idt190:0:j_idt192",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:0:nazwaSkrocona",content: {text: "RODZINNYCH SZEŚCIOLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">6,50%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROS0431" style="font-size: 0.875em;" target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em;"><a id="dostepneEmisje:j_idt190:0:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:0:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:0:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_0_wybierz",{id:"dostepneEmisje:j_idt190:0:wybierz"});});</script></td></tr><tr data-ri="1" class="ui-widget-content ui-datatable-odd"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:1:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">12-letnie: ROD0437</span><script id="dostepneEmisje:j_idt190:1:j_idt192_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_1_j_idt192",{id:"dostepneEmisje:j_idt190:1:j_idt192",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:1:nazwaSkrocona",content: {text: "RODZINNYCH DWUNASTOLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">6,80%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROD0437" style="font-size: 0.875em;" target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em;"><a id="dostepneEmisje:j_idt190:1:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:1:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:1:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_1_wybierz",{id:"dostepneEmisje:j_idt190:1:wybierz"});});</script></td></tr></tbody>""",
        features="html.parser",
    )
    extracted_bonds = extract_available_bonds(bs, path="/foo.html")
    print(extracted_bonds)
    assert extracted_bonds == [
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="6-letnie",
            emisja="ROS0431",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("6.50"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROS0431",
            wybierz={"s": "dostepneEmisje:j_idt190:0:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="12-letnie",
            emisja="ROD0437",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("6.80"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROD0437",
            wybierz={"s": "dostepneEmisje:j_idt190:1:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
    ]

    assert extracted_bonds[0].dlugosc == 6 * 12
    assert extracted_bonds[1].dlugosc == 12 * 12


def test_available_bonds_skarb_panstwa():
    bs = BeautifulSoup(
        r"""<tbody id="dostepneEmisje:j_idt190_data" class="ui-datatable-data ui-widget-content"><tr data-ri="0" class="ui-widget-content ui-datatable-even"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:0:nazwaEmitenta" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">Skarb Państwa</span></td><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:0:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">3-miesięczne: OTS0725</span><script id="dostepneEmisje:j_idt190:0:j_idt193_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_0_j_idt193",{id:"dostepneEmisje:j_idt190:0:j_idt193",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:0:nazwaSkrocona",content: {text: "TRZYMIESIĘCZNYCH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH O OPROCENTOWANIU STAŁYM"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">3,00%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=OTS0725" style="font-size: 0.875em; " target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em; "><a id="dostepneEmisje:j_idt190:0:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:0:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:0:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_0_wybierz",{id:"dostepneEmisje:j_idt190:0:wybierz"});});</script></td></tr><tr data-ri="1" class="ui-widget-content ui-datatable-odd"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:1:nazwaEmitenta" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">Skarb Państwa</span></td><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:1:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">roczne: ROR0426</span><script id="dostepneEmisje:j_idt190:1:j_idt193_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_1_j_idt193",{id:"dostepneEmisje:j_idt190:1:j_idt193",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:1:nazwaSkrocona",content: {text: "ROCZNYCH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH O ZMIENNEJ STOPIE PROCENTOWEJ"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">5,75%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROR0426" style="font-size: 0.875em; " target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em; "><a id="dostepneEmisje:j_idt190:1:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:1:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:1:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_1_wybierz",{id:"dostepneEmisje:j_idt190:1:wybierz"});});</script></td></tr><tr data-ri="2" class="ui-widget-content ui-datatable-even"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:2:nazwaEmitenta" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">Skarb Państwa</span></td><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:2:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">2-letnie: DOR0427</span><script id="dostepneEmisje:j_idt190:2:j_idt193_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_2_j_idt193",{id:"dostepneEmisje:j_idt190:2:j_idt193",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:2:nazwaSkrocona",content: {text: "DWULETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH O ZMIENNEJ STOPIE PROCENTOWEJ"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">5,90%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=DOR0427" style="font-size: 0.875em; " target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em; "><a id="dostepneEmisje:j_idt190:2:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:2:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:2:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_2_wybierz",{id:"dostepneEmisje:j_idt190:2:wybierz"});});</script></td></tr><tr data-ri="3" class="ui-widget-content ui-datatable-odd"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:3:nazwaEmitenta" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">Skarb Państwa</span></td><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:3:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">3-letnie: TOS0428</span><script id="dostepneEmisje:j_idt190:3:j_idt193_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_3_j_idt193",{id:"dostepneEmisje:j_idt190:3:j_idt193",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:3:nazwaSkrocona",content: {text: "TRZYLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH O OPROCENTOWANIU STAŁYM"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">5,95%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=TOS0428" style="font-size: 0.875em; " target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em; "><a id="dostepneEmisje:j_idt190:3:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:3:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:3:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_3_wybierz",{id:"dostepneEmisje:j_idt190:3:wybierz"});});</script></td></tr><tr data-ri="4" class="ui-widget-content ui-datatable-even"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:4:nazwaEmitenta" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">Skarb Państwa</span></td><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:4:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">4-letnie: COI0429</span><script id="dostepneEmisje:j_idt190:4:j_idt193_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_4_j_idt193",{id:"dostepneEmisje:j_idt190:4:j_idt193",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:4:nazwaSkrocona",content: {text: "CZTEROLETNICH INDEKSOWANYCH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">6,30%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=COI0429" style="font-size: 0.875em; " target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em; "><a id="dostepneEmisje:j_idt190:4:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:4:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:4:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_4_wybierz",{id:"dostepneEmisje:j_idt190:4:wybierz"});});</script></td></tr><tr data-ri="5" class="ui-widget-content ui-datatable-odd"><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:5:nazwaEmitenta" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">Skarb Państwa</span></td><td role="gridcell" style="white-space: normal;"><span id="dostepneEmisje:j_idt190:5:nazwaSkrocona" style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block;">10-letnie: EDO0435</span><script id="dostepneEmisje:j_idt190:5:j_idt193_s" type="text/javascript">$(function(){PrimeFaces.cw("ExtTooltip","widget_dostepneEmisje_j_idt190_5_j_idt193",{id:"dostepneEmisje:j_idt190:5:j_idt193",global:false,shared:false,autoShow:false,forTarget:"dostepneEmisje:j_idt190:5:nazwaSkrocona",content: {text: "EMERYTALNYCH DZIESIĘCIOLETNICH OSZCZĘDNOŚCIOWYCH OBLIGACJI SKARBOWYCH"},style: {widget:true},show:{event:'mouseenter',delay:0,effect:function(){$(this).fadeIn(500);}},hide:{event:'mouseleave',delay:0,fixed:false,effect:function(){$(this).fadeOut(500);}},position: {at:'bottom right',my:'top left',adjust:{x:0,y:0},viewport:$(window)}});});</script></td><td role="gridcell" style="white-space: normal; text-align: center;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">od 2025-04-01 <br/> do 2025-04-30</span></td><td role="gridcell" style="white-space: normal;"><span style="font-size: 0.875em; font-style: normal; text-align: center; width: 100%; display: inline-block; white-space: nowrap;">6,55%</span></td><td role="gridcell" style="white-space: normal; text-align: center;"><a href="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=EDO0435" style="font-size: 0.875em; " target="_blank">pokaż</a></td><td role="gridcell" style="text-align: center; font-size: 0.875em; "><a id="dostepneEmisje:j_idt190:5:wybierz" href="#" class="ui-commandlink ui-widget" onclick="PrimeFaces.ab({s:&quot;dostepneEmisje:j_idt190:5:wybierz&quot;,f:&quot;dostepneEmisje&quot;,u:&quot;dostepneEmisje&quot;});return false;">wybierz</a><script id="dostepneEmisje:j_idt190:5:wybierz_s" type="text/javascript">$(function(){PrimeFaces.cw("CommandLink","widget_dostepneEmisje_j_idt190_5_wybierz",{id:"dostepneEmisje:j_idt190:5:wybierz"});});</script></td></tr>""",
        features="html.parser",
    )
    extracted_bonds = extract_available_bonds(bs, path="/foo.html")
    print(extracted_bonds)
    assert extracted_bonds == [
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="3-miesięczne",
            emisja="OTS0725",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("3.00"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=OTS0725",
            wybierz={"s": "dostepneEmisje:j_idt190:0:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="roczne",
            emisja="ROR0426",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("5.75"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=ROR0426",
            wybierz={"s": "dostepneEmisje:j_idt190:1:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="2-letnie",
            emisja="DOR0427",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("5.90"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=DOR0427",
            wybierz={"s": "dostepneEmisje:j_idt190:2:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="3-letnie",
            emisja="TOS0428",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("5.95"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=TOS0428",
            wybierz={"s": "dostepneEmisje:j_idt190:3:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="4-letnie",
            emisja="COI0429",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("6.30"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=COI0429",
            wybierz={"s": "dostepneEmisje:j_idt190:4:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
        AvailableBond(
            emitent="Skarb Państwa",
            rodzaj="10-letnie",
            emisja="EDO0435",
            okres_sprzedazy_od=datetime.date(2025, 4, 1),
            okres_sprzedazy_do=datetime.date(2025, 4, 30),
            oprocentowanie=Decimal("6.55"),
            list_emisyjny="http://www.obligacjeskarbowe.pl/listy-emisyjne/?id=EDO0435",
            wybierz={"s": "dostepneEmisje:j_idt190:5:wybierz", "u": "dostepneEmisje"},
            path="/foo.html",
        ),
    ]
    assert extracted_bonds[0].dlugosc == 3
    assert extracted_bonds[1].dlugosc == 12
    assert extracted_bonds[2].dlugosc == 24
    assert extracted_bonds[3].dlugosc == 36
    assert extracted_bonds[4].dlugosc == 48
    assert extracted_bonds[5].dlugosc == 120


def test_parse_redirect():
    commands = list(
        parse_xml_response(
            r"""<?xml version='1.0' encoding='UTF-8'?>
<partial-response id="j_id1"><redirect url="/zakupObligacji500Plus.html?execution=e2s2"></redirect></partial-response>"""
        )
    )
    assert commands == [Redirect(url="/zakupObligacji500Plus.html?execution=e2s2")]


def test_parse_partial_update_of_view_state():
    commands = list(
        parse_xml_response(
            "<?xml version='1.0' encoding='UTF-8'?>\n<partial-response id=\"j_id1\"><changes><update id=\"j_id1:javax.faces.ViewState:0\"><![CDATA[e1s1]]></update></changes></partial-response>"
        )
    )
    assert commands == [
        PartialResponse(id="j_id1", updates={"j_id1:javax.faces.ViewState:0": "e1s1"})
    ]


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


def test_html_to_string():
    assert html_to_string("foo</br>bar") == "foo\nbar"
    assert html_to_string("foo<br/>bar") == "foo\nbar"
    assert html_to_string("foo<br>bar") == "foo\nbar"
    assert html_to_string("foo<br />bar") == "foo\nbar"
    assert html_to_string("foo<br/>bar</br>baz</br></br>") == "foo\nbar\nbaz"


def test_parse_tooltip():
    assert parse_tooltip("okres 1 oprocentowanie 7.5%") == [
        InterestPeriod(1, Decimal("7.5"))
    ]
    assert parse_tooltip("okres 1 oprocentowanie 7.5%\n") == [
        InterestPeriod(1, Decimal("7.5"))
    ]
    assert parse_tooltip(
        "okres 1 oprocentowanie 7.5%\nokres 2 oprocentowanie 15.0%\n"
    ) == [InterestPeriod(1, Decimal("7.5")), InterestPeriod(2, Decimal("15.0"))]
    assert parse_tooltip(
        "okres 1 oprocentowanie 7.5%\nokres 2 oprocentowanie 15.0%"
    ) == [InterestPeriod(1, Decimal("7.5")), InterestPeriod(2, Decimal("15.0"))]
    assert parse_tooltip(
        "okres 1 oprocentowanie 7.5%\nokres 2 oprocentowanie 15.0%\n\n"
    ) == [InterestPeriod(1, Decimal("7.5")), InterestPeriod(2, Decimal("15.0"))]
    # assert parse_tooltip('')


def test_parse_saldo_and_wartosc():
    bs = BeautifulSoup(
        r"""<span class="formlabel-230 formlabel-base">Saldo środków pieniężnych</span><span class="formfield-base" style="font-weight: bold;">1 000 000,00 PLN</span><span class="formfield-base">Wartość nominalna dotychczas zakupionych obligacji za środki przyznane w ramach programów wsparcia rodziny wynosi: 69420.99</span>""",
        features="html.parser",
    )
    assert emisje_parse_saldo_srodkow_pienieznych(bs), Money(
        amount=Decimal("1000000.00"), currency="PLN"
    )
    assert emisje_parse_wartosc_nominalna_800plus(bs), Decimal("69420.99")
