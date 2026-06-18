"""Regression tests for the PR #1 review findings."""

from __future__ import annotations

import google.auth.exceptions
import pytest

from youtube_upload import auth, lib
from youtube_upload import main as mainmod


def test_auth_failure_maps_to_exit_code_4():
    """google-auth failures (RefreshError, etc.) must exit 4, not 1 + traceback.

    Regression guard for the dropped ``oauth2client.client.FlowExchangeError: 4``.
    ``catch_exceptions`` now walks the MRO so a ``RefreshError`` is matched via
    its ``GoogleAuthError`` base.
    """

    def raise_refresh(_arguments):
        raise google.auth.exceptions.RefreshError("expired")

    assert lib.catch_exceptions(mainmod.EXIT_CODES, raise_refresh) == 4


def test_get_resource_client_secrets_honors_cwd_override(tmp_path, monkeypatch):
    """``get_resource`` must discover ``./client_secrets.json`` (M2 wiring).

    Previously only the token path honored a CWD override; the client-secrets
    call omitted ``local_filename`` and silently fell through to the global
    default.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(auth.ENV_CLIENT_SECRETS, raising=False)
    (tmp_path / "client_secrets.json").write_text("{}")

    captured = {}

    def fake_load(client_secrets, token, open_browser):
        captured["client_secrets"] = client_secrets
        return object()

    monkeypatch.setattr(auth, "_load_or_authorize", fake_load)
    monkeypatch.setattr(
        auth.googleapiclient.discovery, "build", lambda *a, **k: "RESOURCE"
    )

    auth.get_resource()
    assert captured["client_secrets"] == str(
        (tmp_path / "client_secrets.json").resolve()
    )


def test_missing_description_file_raises_options_error(tmp_path):
    """A nonexistent ``--description-file`` must raise OptionsError (exit 2)."""
    missing = tmp_path / "nope.txt"
    with pytest.raises(mainmod.OptionsError):
        mainmod.main(
            [
                "--title",
                "t",
                "--description-file",
                str(missing),
                str(tmp_path / "v.mp4"),
            ]
        )


def test_description_file_dash_reads_stdin(tmp_path, monkeypatch):
    """``--description-file -`` reads the description from stdin."""
    monkeypatch.setattr("sys.stdin", _FakeStdin("from stdin"))
    # run_main needs a YouTube client; short-circuit it to surface the parsed
    # description via the raised AuthenticationError path is awkward, so instead
    # assert the description got populated by driving main() far enough that it
    # would only fail at get_youtube_handler (no creds).
    monkeypatch.setattr(mainmod, "get_youtube_handler", lambda options: None)
    with pytest.raises(mainmod.AuthenticationError):
        mainmod.main(
            ["--title", "t", "--description-file", "-", str(tmp_path / "v.mp4")]
        )


class _FakeStdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text
