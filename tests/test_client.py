from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from requests import Response

from obligacjeskarbowe.client import BASE_URL, ObligacjeSkarbowe
from obligacjeskarbowe.parser import InterestPeriod, Money


TABLE_ID = "stanRachunku:j_idt197"


def portfolio_row(index):
    return f"""<tr>
        <td><span id="{TABLE_ID}:{index}:nazwaSkrocona">ROD{index:04d}</span>
            <script>PrimeFaces.cw("ExtTooltip", "tooltip{index}", {{
                forTarget:"{TABLE_ID}:{index}:nazwaSkrocona",
                content: {{text: "okres 1 oprocentowanie 5.5%"}}
            }});</script>
        </td>
        <td>10</td><td>0</td><td>1 000,00 PLN</td><td>1 055,00 PLN</td>
        <td>2038-10-01</td>
    </tr>"""


def response(body):
    result = Response()
    result.status_code = 200
    result.url = f"{BASE_URL}/stanRachunku.html"
    result._content = body.encode("utf-8")
    return result


def portfolio_update(rows, view_state, message_block):
    message_update = (
        f'<update id="messageBlock"><![CDATA[{message_block}]]></update>'
        if message_block is not None
        else ""
    )
    return response(
        f"""<partial-response id="j_id1"><changes>
            {message_update}
            <update id="{TABLE_ID}"><![CDATA[{rows}]]></update>
            <update id="j_id1:javax.faces.ViewState:0">{view_state}</update>
        </changes></partial-response>"""
    )


@pytest.mark.parametrize("message_block", [None, '<div id="messageBlock"></div>'])
def test_portfolio_pagination(message_block):
    client = ObligacjeSkarbowe()
    client.session = Mock()
    client.session.get.return_value = response(
        f"""<select id="{TABLE_ID}:j_id2"></select>
        <input name="javax.faces.ViewState" value="e1s1">
        <table><tbody id="{TABLE_ID}_data">
            {''.join(portfolio_row(index) for index in range(20))}
        </tbody></table>"""
    )
    client.session.post.side_effect = [
        portfolio_update(portfolio_row(20), "e1s2", message_block),
        portfolio_update(" ", "e1s3", message_block),
    ]

    bonds = client.list_portfolio()

    assert [bond.emisja for bond in bonds] == [f"ROD{index:04d}" for index in range(21)]
    assert all(bond.dostepnych == 10 and bond.zablokowanych == 0 for bond in bonds)
    assert all(bond.nominalna == Money(Decimal("1000.00"), "PLN") for bond in bonds)
    assert all(bond.aktualna == Money(Decimal("1055.00"), "PLN") for bond in bonds)
    assert all(bond.data_wykupu == date(2038, 10, 1) for bond in bonds)
    assert all(bond.okresy == [InterestPeriod(1, Decimal("5.5"))] for bond in bonds)

    calls = client.session.post.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["data"][f"{TABLE_ID}_first"] == "20"
    assert calls[1].kwargs["data"][f"{TABLE_ID}_first"] == "40"
    assert calls[0].kwargs["data"]["javax.faces.ViewState"] == "e1s1"
    assert calls[1].kwargs["data"]["javax.faces.ViewState"] == "e1s2"


def test_portfolio_reports_server_message():
    client = ObligacjeSkarbowe()
    client.session = Mock()
    client.session.get.return_value = response(
        f"""<select id="{TABLE_ID}:j_id2"></select>
        <input name="javax.faces.ViewState" value="e1s1">
        <table><tbody id="{TABLE_ID}_data">{portfolio_row(0)}</tbody></table>"""
    )
    client.session.post.return_value = portfolio_update(
        " ", "e1s2", '<div id="messageBlock"><span>Błąd pobierania danych</span></div>'
    )

    with pytest.raises(RuntimeError, match="Błąd pobierania danych"):
        client.list_portfolio()
