# youtube-upload

<!-- Badges placeholder: add CI, PyPI version, license, Python versions badges here. -->
<!-- e.g. ![CI](https://github.com/ericmjl/youtube-upload/actions/workflows/pr-tests.yaml/badge.svg) -->

> Command-line tool to upload videos to YouTube using the [YouTube Data API v3](https://developers.google.com/youtube/v3/).

A modernized fork of [`tokland/youtube-upload`](https://github.com/tokland/youtube-upload), maintained by [ericmjl](https://github.com/ericmjl).

## What's new in this fork

- **Python 3.10+ only** — dropped legacy Python 2 / old Python 3 support.
- **Modern auth stack** — `google-auth` and `google-auth-oauthlib` replace the deprecated `oauth2client`.
- **Loopback OAuth** — the dead OOB ("copy/paste a code") flow is gone; authorization uses a `localhost` redirect.
- **Refreshable tokens** — the OAuth token is persisted and refreshed, so automation no longer re-authorizes every hour.
- **`tqdm` progress bar** during upload.
- **Resumable, chunked uploads** with automatic retry and exponential backoff on transient errors.
- **Hierarchical credential discovery** (flag → env var → local file → global default).
- **`--made-for-kids`** support and the ability to target **multiple `--playlist`** values.
- **Multi-line descriptions** — use `\n` (literal backslash-n) in `--description` to insert newlines (useful for chapters).

## Installation

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install youtube-upload
```

With pip:

```bash
pip install youtube-upload
```

Or run it one-off without installing:

```bash
uv run --from youtube-upload -- youtube-upload --help
```

## Authentication setup

This tool uses OAuth 2.0; there is no username/password option. Create your own
OAuth credentials (Google revoked the bundled default long ago — it no longer
works):

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create (or select) a project and enable the **YouTube Data API v3**.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
4. Create an **"Installed" / "Desktop"** application client (a **"Web application"** client also works with the loopback flow).
5. **Download the JSON** (`client_secret_….json`) and save it as your client secrets file.

Place the downloaded file at the default location, or point the tool at it with
`--client-secrets` (see [Credential & token file resolution](#credential--token-file-resolution)):

```bash
mkdir -p ~/.config/youtube-upload
cp client_secret_*.json ~/.config/youtube-upload/client_secrets.json
```

## Credential & token file resolution

The client-secrets file (the JSON you downloaded) and the token file (the
refreshable credential this tool generates on first run) are found in this
order, highest precedence first:

| Source | Client secrets | Token |
| --- | --- | --- |
| CLI flag | `--client-secrets PATH` | `--credentials-file PATH` |
| Environment variable | `YOUTUBE_UPLOAD_CLIENT_SECRETS` | `YOUTUBE_UPLOAD_TOKEN` |
| Current directory | `./client_secrets.json` | `./token.json` |
| Global default | `~/.config/youtube-upload/client_secrets.json` | `~/.config/youtube-upload/token.json` |

> **Note:** `client_secrets.json` is the file you download from Google Cloud.
> The *token* file is auto-generated after the first successful authorization.
> Never commit either file — both are gitignored.

## First-run authentication

On first run a local server listens on `http://localhost:8080` and your browser
opens to complete consent. After authorizing, a refreshable token is saved so
subsequent runs (including on servers) do not need a browser.

**Headless machines:** run the tool once on a browser-capable machine, then copy
the generated token file (e.g. `~/.config/youtube-upload/token.json`) to the
headless host.

## Usage

Upload a video:

```bash
youtube-upload --title="A.S. Mutter playing" anne_sophie_mutter.flv
```

Upload with metadata, a private video, and made-for-kids set:

```bash
youtube-upload \
  --title="A.S. Mutter playing" \
  --description="Anne-Sophie Mutter plays Beethoven" \
  --category="Music" \
  --tags="mutter, beethoven" \
  --privacy=private \
  --made-for-kids \
  --playlist="My favorite music" \
  anne_sophie_mutter.flv
```

Other useful options: `--privacy (public|unlisted|private)`,
`--publish-at (ISO 8601 datetime)`, `--location (lat=LON,lon=VAL[,alt=VAL])`,
`--thumbnail FILE`, `--default-language`, `--default-audio-language`.

## Made-for-kids

YouTube requires some channels to explicitly declare whether each video is
"made for kids". Use `--made-for-kids` to mark a video as directed at children,
or omit it otherwise. This is a legal/COPPA requirement, not an aesthetic flag.

## Chapters

Add video chapters by putting timestamps in the description. YouTube's rules:

- The first timestamp **must** be `0:00`.
- Provide **at least 3** chapters.
- Each chapter must be **at least 10 seconds** long.

Example (pass `\n` for line breaks in `--description`):

```
0:00 Intro
0:15 Allegro
1:30 Adagio
```

## "Locked as private" / API audit

If your uploads come back **locked as private**, this is a Google-side policy,
**not a bug** in `youtube-upload`. API projects created after
**2020-07-28** that have not passed Google's audit cannot publish public videos;
uploads are force-set to private. To request an audit for your project, submit
the [YouTube API Audit form](https://support.google.com/youtube/contact/yt_api_form).

## Development

```bash
uv sync --extra dev          # install dev dependencies
uv run pytest                # run the test suite
uv run ruff check            # lint
uv run ruff format           # format
pre-commit install           # enable pre-commit hooks
```

### Verifying a real upload end to end

The unit suite (`uv run pytest`) verifies all logic offline. For a live
round-trip against the YouTube API, run:

```bash
uv run python scripts/verify_e2e.py
```

It uploads a private 2-second test clip through the real CLI, verifies it via
the API (including the `--made-for-kids` and description-newline handling), then
deletes it. The first run opens a browser once for OAuth consent; afterwards the
token persists and uploads run unattended. Exit code `0` means PASS.

## Credits

Forked from [`tokland/youtube-upload`](https://github.com/tokland/youtube-upload)
by **Arnau Sanchez** (`pyarnau@gmail.com`). Licensed under the
[GNU General Public License v3](./LICENSE) (GPL-3.0-or-later).
