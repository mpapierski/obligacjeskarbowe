from decimal import Decimal
from unittest.mock import Mock

from bs4 import BeautifulSoup
from click.testing import CliRunner
import pytest
from requests import Response

from obligacjeskarbowe.__main__ import cli
from obligacjeskarbowe.client import BASE_URL, ObligacjeSkarbowe
from obligacjeskarbowe.parser import Bonds, Money, extract_available_bonds


PATH = "/zakupObligacji500Plus.html"
ARGS = ["buy", "--symbol", "ROD", "--amount", "128"]

OFFERS = """<span id="spanContent">
<form id="dostepneEmisje" action="/zakupObligacji500Plus.html?execution=e1s1">
<input type="hidden" name="javax.faces.ViewState" value="e1s1">
<table><tbody id="dostepneEmisje:j_idt176_data"><tr>
<td>12-letnie: ROD1038</td>
<td>od 2026-10-01 do 2026-10-31</td><td>5,60%</td>
<td><a href="https://example.com/ROD1038">pokaż</a></td>
<td><a onclick='PrimeFaces.ab({s:"dostepneEmisje:j_idt176:1:wybierz",f:"dostepneEmisje",u:"dostepneEmisje"});return false;'>wybierz</a></td>
</tr></tbody></table></form></span>"""

MIFID = """<div id="content"><h3>Zakup obligacji 800+ - propozycja wypełnienia ankiety MiFID</h3>
<span id="spanContent">
<form id="propozycjaWypelnieniaAnkietyMIFID" action="/zakupObligacji500Plus.html?execution=e2s1">
Przed wykonaniem operacji sugerujemy wypełnienie ankiety MiFID. Czy chcesz ją wypełnić?
<input type="hidden" name="propozycjaWypelnieniaAnkietyMIFID" value="propozycjaWypelnieniaAnkietyMIFID">
<input type="submit" name="propozycjaWypelnieniaAnkietyMIFID:tak" value="Tak">
<input type="submit" name="propozycjaWypelnieniaAnkietyMIFID:nie" value="Nie">
<input type="hidden" name="javax.faces.ViewState" value="e2s1">
</form></span></div>"""

DETAILS = """<div id="content"><h3>Zakup obligacji 800+ - dane dyspozycji</h3>
<span id="spanContent"><form id="daneDyspozycji" action="/zakupObligacji500Plus.html?execution=e2s2">
<input type="hidden" name="javax.faces.ViewState" value="e2s2">
<span class="formlabel-230 formlabel-base">Kod emisji</span><span>ROD1038</span>
<span class="formlabel-230 formlabel-base">Pełna nazwa emisji</span><span>Rodzinne dwunastoletnie</span>
<span class="formlabel-230 formlabel-base"> </span><span>oszczędnościowe obligacje skarbowe</span>
<span class="formlabel-230 formlabel-base">Oprocentowanie</span><span>5,60%</span>
<span class="formlabel-230 formlabel-base">Wartość nominalna jednej obligacji</span><span>100,00 PLN</span>
<span class="formlabel-230 formlabel-base">Maksymalnie</span><span>128 szt</span>
<span class="formlabel-230 formlabel-base">Saldo środków pieniężnych</span><span>11 200,00 PLN</span>
<span class="formlabel-230 formlabel-base">Dyspozycja jest składana na instrument finansowy dla którego Klient znajduje się w grupie docelowej</span><span>Na podstawie danych z wypełnionej ankiety PKO BP BM informuje, że zlecenie jest składane na instrument, dla którego klient znajduje się w grupie docelowej.</span>
</form></span></div>"""

REDIRECT = """<partial-response id="j_id1"><redirect url="/zakupObligacji500Plus.html?execution=e2s1"/></partial-response>"""


def response(body, execution="e2s1", status=200):
    result = Response()
    result.status_code = status
    result.url = f"{BASE_URL}{PATH}?execution={execution}"
    result._content = body.encode("utf-8")
    return result


@pytest.fixture
def purchase_flow(monkeypatch):
    client = ObligacjeSkarbowe()
    client.session = Mock()
    client.restore_session = Mock()
    client.persist_session = Mock()
    client.clear_session = Mock()
    client.purchase_step_2 = Mock()
    client.purchase_step_3 = Mock()
    bond = extract_available_bonds(BeautifulSoup(OFFERS, "html.parser"), PATH)[0]
    client.available_bonds_lookup[bond.emisja] = bond
    client.list_bonds = Mock(
        return_value=Bonds(
            saldo=Money(Decimal("11200"), "PLN"),
            emisje=[bond],
            wartosc_nominalna_800plus=Money(Decimal("68600"), "PLN"),
        )
    )
    client.session.get.side_effect = [response(OFFERS, "e1s1"), response(MIFID)]
    client.session.post.side_effect = [response(REDIRECT), response(DETAILS, "e2s2")]
    monkeypatch.setattr("obligacjeskarbowe.__main__.ObligacjeSkarbowe", lambda: client)

    yield client

    client.purchase_step_2.assert_not_called()
    client.purchase_step_3.assert_not_called()
    for post in client.session.post.call_args_list:
        data = post.kwargs["data"]
        assert "daneDyspozycji:liczbaZamiawianychObligacji" not in data
        assert not any(key.startswith("zatwierdzenie") for key in data)


@pytest.mark.parametrize("extra_args,input_text", [([], "y\ny\n"), (["--force"], "")])
def test_buy_handles_mifid_offer_and_still_checks_balance(
    purchase_flow, extra_args, input_text
):
    result = CliRunner().invoke(cli, ARGS + extra_args, input=input_text)

    assert result.exit_code == 1
    assert (
        "Dostępne saldo 11200.00 PLN jest mniejsze niż oczekiwany koszt zakupu 12800"
        in result.output
    )
    assert "Kod emisji: ROD1038" in result.output
    assert "Maksymalnie (limit serwisu): 128 szt." in result.output
    assert result.output.count("[y/N]") == (0 if extra_args else 2)
    posts = purchase_flow.session.post.call_args_list
    assert len(posts) == 2
    assert posts[1].kwargs["data"] == {
        "propozycjaWypelnieniaAnkietyMIFID": "propozycjaWypelnieniaAnkietyMIFID",
        "propozycjaWypelnieniaAnkietyMIFID:nie": "Nie",
        "javax.faces.ViewState": "e2s1",
    }
    assert purchase_flow.view_state == "e2s2"
    assert purchase_flow.next_url == PATH + "?execution=e2s2"


def test_buy_can_stop_at_details_after_mifid_without_submitting_order(purchase_flow):
    purchase_flow.session.post.side_effect = [
        response(REDIRECT),
        response(DETAILS.replace("11 200,00", "12 800,00"), "e2s2"),
    ]

    result = CliRunner().invoke(cli, ARGS, input="y\ny\nn\n")

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert (
        "Możliwe do zakupu z obecnego salda i w ramach limitu: 128 szt."
        in result.output
    )
    assert "Krok 2/3:" in result.output
    assert "Krok 3/3:" not in result.output


def test_buy_can_decline_continuing_without_questionnaire(purchase_flow):
    result = CliRunner().invoke(cli, ARGS, input="y\nn\n")

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert (
        "Kontynuować do danych zakupu bez wypełniania ankiety MiFID?" in result.output
    )
    purchase_flow.session.post.assert_called_once()


def test_buy_still_handles_direct_purchase_details(purchase_flow):
    purchase_flow.session.get.side_effect = [
        response(OFFERS, "e1s1"),
        response(DETAILS.replace("11 200,00", "12 800,00"), "e2s2"),
    ]
    purchase_flow.session.post.side_effect = [response(REDIRECT)]

    result = CliRunner().invoke(cli, ARGS, input="y\nn\n")

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert "Kod emisji: ROD1038" in result.output
    assert "Serwis proponuje" not in result.output
    purchase_flow.session.post.assert_called_once()


def test_buy_reports_mifid_prompt_that_did_not_advance(purchase_flow):
    purchase_flow.session.post.side_effect = [response(REDIRECT), response(MIFID)]

    result = CliRunner().invoke(cli, ARGS, input="y\ny\n")

    assert result.exit_code == 1
    assert (
        "Serwis nie pozwolił przejść do danych zakupu bez ankiety MiFID"
        in result.output
    )
    assert purchase_flow.session.post.call_count == 2


def test_buy_does_not_retry_rejected_mifid_submission(purchase_flow):
    purchase_flow.session.post.side_effect = [
        response(REDIRECT),
        response("Forbidden", status=403),
    ]

    result = CliRunner().invoke(cli, ARGS, input="y\ny\n")

    assert result.exit_code == 1
    assert "HTTP 403" in result.output
    assert purchase_flow.session.post.call_count == 2
    purchase_flow.clear_session.assert_called_once()
