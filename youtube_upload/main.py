#!/usr/bin/env python
"""Upload videos to YouTube from the command line using the Data API v3.

Example::

    $ youtube-upload --title="A. S. Mutter playing" \
                     --description="Anne Sophie Mutter plays Beethoven" \
                     --category=Music \
                     --tags="mutter, beethoven" \
                     --privacy=private \
                     anne_sophie_mutter.mp4
    pxzZ-fYjeYs
"""

from __future__ import annotations

import argparse
import collections
import sys
import webbrowser

import googleapiclient.errors
from tqdm import tqdm

from . import auth, categories, lib, playlists, upload_video

WATCH_VIDEO_URL = "https://www.youtube.com/watch?v={id}"

debug = lib.debug
ProgressInfo = collections.namedtuple("ProgressInfo", ["callback", "finish"])


class UploadError(Exception):
    """Raised when an upload fails for a non-retriable reason."""


class OptionsError(Exception):
    """Raised when required CLI options are missing or invalid."""


class InvalidCategory(Exception):
    """Raised when a category name is not recognized."""


class RequestError(Exception):
    """Raised when the YouTube API returns an error response."""


class AuthenticationError(Exception):
    """Raised when authentication to the YouTube API fails."""


# Maps an exception type raised anywhere in the flow to the process exit code
# used by ``lib.catch_exceptions``.
EXIT_CODES = {
    OptionsError: 2,
    InvalidCategory: 3,
    RequestError: 3,
    AuthenticationError: 4,
    NotImplementedError: 5,
}


def open_link(url: str) -> None:
    """Open ``url`` in the user's default web browser.

    :param url: the URL to open.
    """
    webbrowser.open(url)


def get_progress_info():
    """Return a ``(callback, finish)`` progress pair backed by ``tqdm``."""
    bar = tqdm(total=None, unit="B", unit_scale=True, desc="Uploading")

    def _callback(total_size, completed):
        if bar.total is None and total_size:
            bar.total = total_size
        # ``completed`` is an absolute byte offset; tqdm wants a delta.
        bar.update(completed - bar.n)

    def _finish():
        bar.close()

    return ProgressInfo(callback=_callback, finish=_finish)


def get_category_id(category: str | None) -> str | None:
    """Return the YouTube category ID for a human-readable ``category`` name.

    :param category: category name (e.g. ``"Music"``).
    :returns: the numeric category id as a string, or ``None`` if unset.
    :raises InvalidCategory: if the name is not a known category.
    """
    if category:
        if category in categories.IDS:
            debug(f"Using category: {category} (id={categories.IDS[category]})")
            return str(categories.IDS[category])
        raise InvalidCategory(f"{category} is not a valid category")
    return None


def build_request_body(options, index, total_videos):
    """Build the ``videos.insert`` request body from parsed CLI options."""
    u = lib.to_utf8
    title = u(options.title)
    description = options.description

    tags = [u(s.strip()) for s in (options.tags or "").split(",")]
    ns = dict(title=title, n=index + 1, total=total_videos)
    title_template = u(options.title_template)
    complete_title = title_template.format(**ns) if total_videos > 1 else title
    category_id = get_category_id(options.category)

    body = {
        "snippet": {
            "title": complete_title,
            "description": description,
            "categoryId": category_id,
            "tags": tags,
            "defaultLanguage": options.default_language,
            "defaultAudioLanguage": options.default_audio_language,
        },
        "status": {
            "embeddable": options.embeddable,
            "privacyStatus": ("private" if options.publish_at else options.privacy),
            "publishAt": options.publish_at,
            "license": options.license,
        },
        "recordingDetails": {
            "location": lib.string_to_dict(options.location),
            "recordingDate": options.recording_date,
        },
    }
    return body


def upload_youtube_video(youtube, options, video_path, total_videos, index):
    """Upload a single video and return its id."""
    request_body = build_request_body(options, index, total_videos)
    debug(f"Start upload: {video_path}")
    progress = get_progress_info()
    try:
        video_id = upload_video.upload(
            youtube,
            video_path,
            request_body,
            progress_callback=progress.callback,
            chunksize=options.chunksize,
        )
    finally:
        progress.finish()
    return video_id


def get_youtube_handler(options):
    """Return an authenticated YouTube API resource (or ``None``)."""
    # ``auth.get_resource`` resolves client-secrets/token paths hierarchically;
    # explicit flags are forwarded so they take precedence.
    return auth.get_resource(
        client_secrets_file=options.client_secrets,
        credentials_file=options.credentials_file,
        get_code_callback=(lambda *a, **kw: True) if options.auth_browser else None,
    )


def parse_options_error(parser, options):
    """Validate required options; raise ``OptionsError`` if any are missing."""
    required = ["title"]
    missing = [opt for opt in required if not getattr(options, opt, None)]
    if missing:
        parser.print_usage()
        raise OptionsError(
            "Some required options are missing: {}".format(", ".join(missing))
        )


def run_main(parser, options, args, output=sys.stdout):
    """Run the upload flow from already-parsed options/args."""
    parse_options_error(parser, options)
    youtube = get_youtube_handler(options)

    if not youtube:
        raise AuthenticationError("Cannot get YouTube resource")

    for index, video_path in enumerate(args):
        video_id = upload_youtube_video(youtube, options, video_path, len(args), index)
        video_url = WATCH_VIDEO_URL.format(id=video_id)
        debug(f"Video URL: {video_url}")
        if options.open_link:
            open_link(video_url)
        if options.thumb:
            youtube.thumbnails().set(
                videoId=video_id, media_body=options.thumb
            ).execute()
        if options.playlist:
            playlists.add_video_to_playlist(
                youtube,
                video_id,
                title=lib.to_utf8(options.playlist),
                privacy=options.privacy,
            )
        output.write(video_id + "\n")


def build_parser():
    """Construct and return the ``argparse`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="youtube-upload",
        description="Upload videos to YouTube from the command line.",
    )

    # Video metadata
    parser.add_argument("-t", "--title", dest="title", help="Video title")
    parser.add_argument(
        "-c", "--category", dest="category", help="Name of video category"
    )
    parser.add_argument(
        "-d", "--description", dest="description", help="Video description"
    )
    parser.add_argument(
        "--description-file",
        dest="description_file",
        default=None,
        help="Read video description from this file",
    )
    parser.add_argument(
        "--tags", dest="tags", help='Video tags (comma-separated: "tag1, tag2, ...")'
    )
    parser.add_argument(
        "--privacy",
        dest="privacy",
        default="public",
        help="Privacy status (public | unlisted | private)",
    )
    parser.add_argument(
        "--publish-at",
        dest="publish_at",
        default=None,
        metavar="datetime",
        help="Publish date (ISO 8601): YYYY-MM-DDThh:mm:ss.sZ",
    )
    parser.add_argument(
        "--license",
        dest="license",
        choices=("youtube", "creativeCommon"),
        default="youtube",
        help='License: "youtube" (default) or "creativeCommon"',
    )
    parser.add_argument(
        "--location",
        dest="location",
        default=None,
        metavar="latitude=VAL,longitude=VAL[,altitude=VAL]",
        help="Video location",
    )
    parser.add_argument(
        "--recording-date",
        dest="recording_date",
        default=None,
        metavar="datetime",
        help="Recording date (ISO 8601): YYYY-MM-DDThh:mm:ss.sZ",
    )
    parser.add_argument(
        "--default-language",
        dest="default_language",
        default=None,
        metavar="string",
        help="Default language (ISO 639-1: en | fr | de | ...)",
    )
    parser.add_argument(
        "--default-audio-language",
        dest="default_audio_language",
        default=None,
        metavar="string",
        help="Default audio language (ISO 639-1: en | fr | de | ...)",
    )
    parser.add_argument(
        "--thumbnail",
        dest="thumb",
        metavar="FILE",
        help="Image file to use as video thumbnail (JPEG or PNG)",
    )
    parser.add_argument(
        "--playlist",
        dest="playlist",
        help="Playlist title (created if it does not exist)",
    )
    parser.add_argument(
        "--title-template",
        dest="title_template",
        default="{title} [{n}/{total}]",
        metavar="string",
        help="Template for multiple videos (default: {title} [{n}/{total}])",
    )
    parser.add_argument(
        "--embeddable",
        dest="embeddable",
        action="store_true",
        default=True,
        help="Video is embeddable (default)",
    )

    # Authentication
    parser.add_argument(
        "--client-secrets", dest="client_secrets", help="OAuth client secrets JSON file"
    )
    parser.add_argument(
        "--credentials-file",
        dest="credentials_file",
        help="Persisted OAuth token JSON file",
    )
    parser.add_argument(
        "--auth-browser",
        dest="auth_browser",
        action="store_true",
        help="Automatically open a browser to authenticate (loopback redirect)",
    )

    # Additional options
    parser.add_argument(
        "--chunksize",
        dest="chunksize",
        type=int,
        default=1024 * 1024 * 8,
        help="Resumable upload chunk size in bytes (default: 8 MiB)",
    )
    parser.add_argument(
        "--open-link",
        dest="open_link",
        action="store_true",
        help="Open the uploaded video's URL in a web browser",
    )

    parser.add_argument(
        "videos",
        nargs="+",
        metavar="VIDEO",
        help="Path(s) to the video file(s) to upload",
    )
    return parser


def main(arguments):
    """Entry point: parse ``arguments`` and run the upload flow."""
    parser = build_parser()
    options = parser.parse_args(arguments)

    if options.description_file and options.description_file != "-":
        with open(options.description_file, encoding="utf-8") as fh:
            options.description = fh.read()

    try:
        run_main(parser, options, options.videos)
    except googleapiclient.errors.HttpError as error:
        response = bytes.decode(error.content, encoding=lib.get_encoding()).strip()
        raise RequestError(f"Server response: {response}") from error


def run():
    """Console-script entry point: run :func:`main` and exit with a status code."""
    sys.exit(lib.catch_exceptions(EXIT_CODES, main, sys.argv[1:]))


if __name__ == "__main__":
    run()
