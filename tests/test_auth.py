"""Tests for the hierarchical credential/token path resolution in ``auth``."""

from __future__ import annotations

import os
from pathlib import Path

from youtube_upload import auth


def test_cli_flag_takes_precedence(tmp_path, monkeypatch):
    """An explicit CLI arg wins over env var, local file, and global default."""
    cli_file = tmp_path / "from_cli.json"
    cli_file.write_text("{}")
    env_file = tmp_path / "from_env.json"
    env_file.write_text("{}")
    monkeypatch.setenv(auth.ENV_CLIENT_SECRETS, str(env_file))
    assert auth.resolve_path(
        str(cli_file), auth.ENV_CLIENT_SECRETS, "/never/used"
    ) == str(cli_file)


def test_env_var_beats_default(tmp_path, monkeypatch):
    """Env var is used when no CLI arg is given (no local file present)."""
    env_file = tmp_path / "from_env.json"
    monkeypatch.setenv(auth.ENV_CLIENT_SECRETS, str(env_file))
    assert auth.resolve_path(
        None, auth.ENV_CLIENT_SECRETS, "/global/default.json"
    ) == str(env_file)


def test_local_cwd_override_beats_global_default(tmp_path, monkeypatch):
    """A file named ``client_secrets.json`` in the CWD overrides the global default."""
    monkeypatch.chdir(tmp_path)
    local = tmp_path / "client_secrets.json"
    local.write_text("{}")
    monkeypatch.delenv(auth.ENV_CLIENT_SECRETS, raising=False)
    resolved = auth.resolve_path(
        None,
        auth.ENV_CLIENT_SECRETS,
        "/global/default.json",
        local_filename="client_secrets.json",
    )
    assert Path(resolved).resolve() == local.resolve()


def test_global_default_used_when_nothing_else(monkeypatch):
    """The global default path is returned (with ``~`` expanded) as the fallback."""
    monkeypatch.delenv(auth.ENV_CLIENT_SECRETS, raising=False)
    monkeypatch.chdir("/tmp")  # ensure no local client_secrets.json interferes
    resolved = auth.resolve_path(
        None,
        auth.ENV_CLIENT_SECRETS,
        "~/config/x.json",
        local_filename="client_secrets.json",
    )
    assert resolved == os.path.expanduser("~/config/x.json")


def test_default_resolves_to_real_global_credentials(monkeypatch):
    """The shipped global default points at the canonical credentials location."""
    monkeypatch.delenv(auth.ENV_CLIENT_SECRETS, raising=False)
    resolved = auth.resolve_path(
        None, auth.ENV_CLIENT_SECRETS, auth.DEFAULT_CLIENT_SECRETS
    )
    assert resolved == os.path.expanduser(
        "~/.config/youtube-upload/client_secrets.json"
    )


def test_web_and_installed_client_types_both_accepted(tmp_path):
    """``InstalledAppFlow.from_client_secrets_file`` accepts both client types.

    This is a regression guard for the modernization: the legacy ``oauth2client``
    code only worked with specific shapes. We assert the flow object builds
    without raising for both a ``web`` and an ``installed`` (fake) client config.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    fake_installed = {
        "installed": {
            "client_id": "x.apps.googleusercontent.com",
            "client_secret": "secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    fake_web = {
        "web": {
            "client_id": "x.apps.googleusercontent.com",
            "client_secret": "secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", "http://localhost:8080"],
        }
    }
    for label, cfg in (("installed", fake_installed), ("web", fake_web)):
        path = tmp_path / f"cs_{label}.json"
        path.write_text(__import__("json").dumps(cfg))
        # Must not raise for either client type.
        flow = InstalledAppFlow.from_client_secrets_file(str(path), auth.SCOPES)
        assert flow is not None
