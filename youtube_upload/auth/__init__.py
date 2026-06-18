"""Google OAuth2 authentication for YouTube uploads.

Modernized to use ``google-auth`` / ``google-auth-oauthlib`` instead of the
deprecated ``oauth2client``. Supports both "installed" (Desktop) and "web"
OAuth client types and persists a refreshable token so automation does not
need to re-authorize on every run (fixes the 1-hour-token class of bugs).

Credential/token files are discovered hierarchically (highest precedence
first):

1. ``--client-secrets`` / ``--credentials-file`` CLI flag
2. ``YOUTUBE_UPLOAD_CLIENT_SECRETS`` / ``YOUTUBE_UPLOAD_TOKEN`` env var
3. ``./client_secrets.json`` / ``./token.json`` in the current directory
4. ``~/.config/youtube-upload/client_secrets.json`` / ``token.json`` (global)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import googleapiclient.discovery
import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow

from .. import lib

# Both scopes are requested: ``youtube.upload`` for the upload itself and the
# broader ``youtube`` scope for playlist / thumbnail / caption management.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

DEFAULT_CLIENT_SECRETS = "~/.config/youtube-upload/client_secrets.json"
DEFAULT_TOKEN = "~/.config/youtube-upload/token.json"
ENV_CLIENT_SECRETS = "YOUTUBE_UPLOAD_CLIENT_SECRETS"
ENV_TOKEN = "YOUTUBE_UPLOAD_TOKEN"

# These are the loopback redirect URIs registered in the Google Cloud Console.
# ``run_local_server`` always binds ``http://localhost:<port>``.
DEFAULT_OAUTH_PORT = 8080


def _expand(path: str) -> str:
    """Expand ``~`` and environment variables in a path."""
    return os.path.expandvars(os.path.expanduser(path))


def resolve_path(
    cli_arg: str | None,
    env_var: str,
    default: str,
    local_filename: str | None = None,
) -> str:
    """Resolve a file path using the hierarchical discovery rules.

    Order (highest precedence first): explicit CLI arg, env var, a file named
    ``local_filename`` in the current working directory, then the global
    default.

    :param cli_arg: value passed via the CLI flag (``None`` if not given).
    :param env_var: name of the environment variable to consult.
    :param default: the global default path (may start with ``~``).
    :param local_filename: filename to look for in the CWD as a local override.
    :returns: the resolved filesystem path.
    """
    if cli_arg:
        return _expand(cli_arg)
    env_value = os.environ.get(env_var)
    if env_value:
        return _expand(env_value)
    if local_filename is not None and Path(local_filename).exists():
        return str(Path(local_filename).resolve())
    return _expand(default)


def _save_credentials(credentials: Credentials, token_path: str) -> None:
    """Persist credentials to ``token_path`` with restrictive permissions."""
    path = Path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json())
    # The token contains a refresh_token; keep it private.
    path.chmod(0o600)


def _load_or_authorize(
    client_secrets_file: str,
    token_file: str,
    open_browser: bool,
) -> Credentials:
    """Load a valid token from disk, refreshing/authorizing as needed."""
    token_path = Path(token_file)
    credentials: Credentials | None = None
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except ValueError:
            # An old/incompatible token format (e.g. from oauth2client); fall
            # through to a fresh authorization.
            credentials = None

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.refresh_token:
        credentials.refresh(Request())
        _save_credentials(credentials, token_file)
        return credentials

    # No usable token: run the OAuth loopback flow.
    lib.debug("Authorizing: open the printed URL in a browser if needed.")
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    credentials = flow.run_local_server(
        host="localhost",
        port=DEFAULT_OAUTH_PORT,
        open_browser=open_browser,
        access_type="offline",
        prompt="consent",
        include_granted_scopes=True,
    )
    _save_credentials(credentials, token_file)
    return credentials


def get_resource(
    client_secrets_file: str | None = None,
    credentials_file: str | None = None,
    get_code_callback: Callable[..., str] | None = None,
):
    """Authenticate and return a ``googleapiclient`` YouTube Resource.

    The signature is preserved from the legacy ``oauth2client`` implementation
    so callers (``main.get_youtube_handler``) do not change. ``get_code_callback``
    is now interpreted as a boolean hint: a truthy value means "open a browser
    automatically"; falsy/None prints the URL for the user to open manually.

    :param client_secrets_file: optional path to the OAuth client secrets JSON.
    :param credentials_file: optional path to the persisted token JSON.
    :param get_code_callback: when truthy, the loopback server auto-opens the
        user's browser.
    :returns: an authenticated ``googleapiclient.discovery.Resource`` for the
        YouTube Data API v3.
    """
    client_secrets = resolve_path(
        client_secrets_file,
        ENV_CLIENT_SECRETS,
        DEFAULT_CLIENT_SECRETS,
        local_filename="client_secrets.json",
    )
    token = resolve_path(
        credentials_file, ENV_TOKEN, DEFAULT_TOKEN, local_filename="token.json"
    )
    lib.debug(f"Using client secrets: {client_secrets}")
    lib.debug(f"Using credentials file: {token}")
    open_browser = bool(get_code_callback)
    credentials = _load_or_authorize(client_secrets, token, open_browser)
    # Build the HTTP transport explicitly so we can patch the 308 redirect quirk.
    return _build_youtube_resource(credentials)


def _build_youtube_resource(credentials: Credentials):
    """Build an authenticated YouTube resource with the httplib2 308 fix applied.

    ``httplib2`` (<=0.31) classifies HTTP 308 — the resumable-upload "resume
    here" signal — as a redirect and tries to follow a ``Location`` header,
    crashing with ``RedirectMissingLocation`` (upstream #293). Removing 308 from
    the redirect set lets the 308 reach googleapiclient, which reads the
    ``Range`` header to resume the upload.

    :param credentials: authorized google-auth ``Credentials``.
    :returns: an authenticated YouTube Data API v3 Resource.
    """
    http = httplib2.Http()
    http.redirect_codes = http.redirect_codes - {308}
    authorized_http = AuthorizedHttp(credentials, http=http)
    return googleapiclient.discovery.build(
        "youtube",
        "v3",
        http=authorized_http,
        cache_discovery=False,
    )
