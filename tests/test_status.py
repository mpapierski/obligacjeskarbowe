from unittest.mock import Mock

from click.testing import CliRunner
import pytest
from requests import Response

from obligacjeskarbowe.__main__ import cli
from obligacjeskarbowe.client import BASE_URL, ObligacjeSkarbowe


@pytest.fixture
def status_client(monkeypatch):
    client = ObligacjeSkarbowe()
    client.session = Mock()
    client.restore_session = Mock()
    client.persist_session = Mock()
    client.clear_session = Mock()
    monkeypatch.setattr("obligacjeskarbowe.__main__.ObligacjeSkarbowe", lambda: client)
    return client


@pytest.mark.parametrize(
    "balance,expected",
    [("1 234\xa0567,89 PLN", "1234567.89 PLN"), ("0,00 PLN", "0.00 PLN")],
)
def test_status_shows_cash_available_for_purchases(status_client, balance, expected):
    response = Response()
    response.status_code = 200
    response.url = f"{BASE_URL}/zakupObligacji.html"
    response._content = (
        '<span class="formlabel-230 formlabel-base">Saldo środków pieniężnych</span>'
        f'<span class="formfield-base">{balance}</span>'
    ).encode("utf-8")
    status_client.session.get.return_value = response

    result = CliRunner().invoke(cli, ["status"])

    assert result.exit_code == 0, result.output
    assert result.output == f"Saldo dostępne na zakup obligacji: {expected}\n"
    status_client.restore_session.assert_called_once()
    status_client.persist_session.assert_called_once()
    status_client.session.get.assert_called_once_with(response.url)
    status_client.session.post.assert_not_called()


@pytest.mark.parametrize(
    "status_code,path,error",
    [
        (200, "/login.html", "Session expired, please login again"),
        (401, "/zakupObligacji.html", "HTTP 401"),
        (403, "/zakupObligacji.html", "HTTP 403"),
    ],
)
def test_status_rejects_expired_session(status_client, status_code, path, error):
    response = Response()
    response.status_code = status_code
    response.url = BASE_URL + path
    response._content = b"<form>Login</form>"
    status_client.session.get.return_value = response

    result = CliRunner().invoke(cli, ["status"])

    assert result.exit_code == 1
    assert error in str(result.exception)
    assert "Saldo" not in result.output
    status_client.clear_session.assert_called_once()
    status_client.persist_session.assert_called_once()
    status_client.session.post.assert_not_called()
