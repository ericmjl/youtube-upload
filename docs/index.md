# youtube-upload

Command-line tool to upload videos to YouTube using the
[YouTube Data API v3](https://developers.google.com/youtube/v3/).

This is a modernized fork of
[`tokland/youtube-upload`](https://github.com/tokland/youtube-upload), maintained
by [ericmjl](https://github.com/ericmjl): Python 3.10+, modern `google-auth` /
`google-auth-oauthlib`, loopback OAuth with refreshable tokens, `tqdm` progress,
resumable chunked uploads, and hierarchical credential discovery.

## Installation

```bash
uv tool install youtube-upload
# or
pip install youtube-upload
```

## Authentication setup

Create OAuth credentials in the [Google Cloud Console](https://console.cloud.google.com/):

1. Enable the **YouTube Data API v3**.
2. **Credentials → Create Credentials → OAuth client ID**.
3. Create an **"Installed"/"Desktop"** (or "Web application") client.
4. **Download the JSON** and save it as your client secrets file.

```bash
mkdir -p ~/.config/youtube-upload
cp client_secret_*.json ~/.config/youtube-upload/client_secrets.json
```

## Credential & token file resolution

Sources are consulted highest-precedence first:

| Source | Client secrets | Token |
| --- | --- | --- |
| CLI flag | `--client-secrets` | `--credentials-file` |
| Env var | `YOUTUBE_UPLOAD_CLIENT_SECRETS` | `YOUTUBE_UPLOAD_TOKEN` |
| Current dir | `./client_secrets.json` | `./token.json` |
| Global default | `~/.config/youtube-upload/client_secrets.json` | `~/.config/youtube-upload/token.json` |

On first run a browser opens at `http://localhost:8080`; the resulting refreshable
token is saved so later runs (including headless) need no browser.

## Usage

```bash
youtube-upload \
  --title="A.S. Mutter playing" \
  --description="Anne-Sophie Mutter plays Beethoven" \
  --category="Music" \
  --tags="mutter, beethoven" \
  --privacy=private \
  --made-for-kids \
  anne_sophie_mutter.flv
```

## Made-for-kids

YouTube requires some channels to declare whether each video is "made for kids"
(COPPA). Use `--made-for-kids` to mark a video as directed at children.

## Chapters

Add timestamps in the description to create chapters. Rules: the first timestamp
must be `0:00`, at least 3 chapters, each at least 10 seconds. Use `\n` for line
breaks in `--description`:

```
0:00 Intro
0:15 Allegro
1:30 Adagio
```

## "Locked as private"?

API projects created after **2020-07-28** that haven't passed Google's audit get
uploads force-locked to private — this is a Google-side policy, not a bug. Submit
the [YouTube API Audit form](https://support.google.com/youtube/contact/yt_api_form).
