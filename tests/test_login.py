from datetime import date
from unittest.mock import Mock, call

from click.testing import CliRunner
import pytest
from requests import HTTPError, Response

from obligacjeskarbowe import two_factor
from obligacjeskarbowe.__main__ import cli
from obligacjeskarbowe.client import BASE_URL, ObligacjeSkarbowe


USER_INFO = """<form id="userInfoForm">
    Zalogowany użytkownik: TEST USER<br>
    Ostatnie udane logowanie: 2026-10-15 23:00:00<br>
    Ostatnie nieudane logowanie: 2026-10-01 12:00:00
</form>"""

AUTH_PROMPT = """<span id="spanContent">
Podaj kod jednorazowy dla operacji nr 1 z 15-10-2026
<form id="auth" action="/auth2fa.html?execution=e1s1">
    <input name="javax.faces.ViewState" value="e1s1">
    <button id="auth:ok"></button>
</form></span>"""


def response(path, body="", status_code=200):
    result = Response()
    result.status_code = status_code
    result.url = BASE_URL + path
    result._content = body.encode("utf-8")
    return result


@pytest.fixture
def login_client(monkeypatch):
    client = ObligacjeSkarbowe()
    client.session = Mock()
    client.restore_session = Mock()
    client.persist_session = Mock()
    client.clear_session = Mock()
    client.session.get.side_effect = [
        response("/login.html"),
        response("/stanRachunku.html", USER_INFO),
    ]
    client.session.post.side_effect = [
        response("/auth2fa.html", AUTH_PROMPT),
        response("/mojeObligacje.html", USER_INFO),
    ]
    monkeypatch.setattr(
        "obligacjeskarbowe.client.two_factor.wait_for_token",
        Mock(
            return_value=iter(
                [two_factor.Open(), two_factor.Token(1, date(2026, 10, 15), 123456)]
            )
        ),
    )
    monkeypatch.setattr("obligacjeskarbowe.client.time.sleep", lambda _: None)
    return client


@pytest.mark.parametrize("status_code", [401, 403])
def test_login_replaces_rejected_session_before_authenticating(
    login_client, monkeypatch, status_code
):
    fresh_session = login_client.session
    rejected_session = Mock()
    rejected_session.get.return_value = response(
        "/daneRachunku.html", "Forbidden", status_code
    )
    login_client.session = rejected_session
    factory = Mock(return_value=fresh_session)
    monkeypatch.setattr("obligacjeskarbowe.client.preconfigured_session", factory)

    info = login_client.login("test-user", "test-password", "test-topic")

    assert info.username == "TEST USER"
    assert login_client.session is fresh_session
    factory.assert_called_once()
    rejected_session.post.assert_not_called()
    assert fresh_session.get.call_args_list == [
        call(BASE_URL + "/daneRachunku.html"),
        call(BASE_URL + "/stanRachunku.html"),
    ]
    assert fresh_session.post.call_count == 2


def test_login_verifies_already_authenticated_session(login_client):
    login_client.session.get.side_effect = [
        response("/daneRachunku.html", USER_INFO),
        response("/stanRachunku.html", USER_INFO),
    ]

    info = login_client.login("test-user", "test-password", "test-topic")

    assert info.username == "TEST USER"
    login_client.session.post.assert_not_called()
    assert login_client.session.get.call_args_list[-1] == call(
        BASE_URL + "/stanRachunku.html"
    )


@pytest.mark.parametrize("status_code", [401, 403])
def test_login_does_not_report_success_or_save_unusable_session(
    login_client, monkeypatch, status_code
):
    login_client.session.get.side_effect = [
        response("/login.html"),
        response("/stanRachunku.html", "Forbidden", status_code),
    ]
    monkeypatch.setattr(
        "obligacjeskarbowe.__main__.ObligacjeSkarbowe", lambda: login_client
    )

    result = CliRunner().invoke(
        cli,
        [
            "login",
            "--username",
            "test-user",
            "--password",
            "test-password",
            "--ntfy-topic",
            "test-topic",
        ],
    )

    assert result.exit_code == 1
    assert f"HTTP {status_code}" in str(result.exception)
    assert "OK" not in result.output.splitlines()
    login_client.persist_session.assert_not_called()
    login_client.clear_session.assert_called_once()


def test_login_rejects_redirect_to_unfinished_authentication(login_client):
    login_client.session.get.side_effect = [
        response("/login.html"),
        response("/auth2fa.html", USER_INFO),
    ]

    with pytest.raises(RuntimeError, match="Login incomplete"):
        login_client.login("test-user", "test-password", "test-topic")


def test_forbidden_response_clears_persisted_session(monkeypatch, tmp_path):
    session_file = tmp_path / "session.pickle"
    monkeypatch.setattr("obligacjeskarbowe.client.SESSION_FILE", str(session_file))
    client = ObligacjeSkarbowe()
    client.next_url = "/stanRachunku.html"
    client.view_state = "old-state"
    client.persist_session()

    with pytest.raises(RuntimeError, match="HTTP 403"):
        client.ensure_session_exists(response("/stanRachunku.html", "Forbidden", 403))

    assert not session_file.exists()
    assert client.session is None
    assert client.next_url is None
    assert client.view_state is None


def test_forbidden_final_purchase_is_not_retried(login_client):
    login_client.next_url = "/zatwierdzenie.html"
    login_client.view_state = "e1s2"
    login_client.session.post.side_effect = None
    login_client.session.post.return_value = response(
        "/zatwierdzenie.html", "Forbidden", 403
    )

    with pytest.raises(RuntimeError, match="HTTP 403"):
        login_client.purchase_step_3()

    login_client.session.post.assert_called_once()
    login_client.session.get.assert_not_called()
    login_client.clear_session.assert_called_once()


@pytest.mark.parametrize("status_code", [400, 404, 409, 429, 499])
def test_other_client_errors_preserve_session_and_include_path(
    login_client, status_code
):
    rejected = response("/stanRachunku.html?execution=e1s1", status_code=status_code)

    with pytest.raises(
        HTTPError, match=f"HTTP {status_code} for /stanRachunku.html"
    ) as error:
        login_client.ensure_session_exists(rejected)

    assert error.value.response is rejected
    login_client.clear_session.assert_not_called()


def test_server_error_preserves_session(login_client):
    with pytest.raises(HTTPError):
        login_client.ensure_session_exists(
            response("/stanRachunku.html", status_code=500)
        )

    login_client.clear_session.assert_not_called()
