"""Tests for the metadata features: made-for-kids, multi-playlist, description newlines."""

from __future__ import annotations

import io

import pytest

from youtube_upload import main as mainmod


def _opts(*args: str):
    """Parse args (plus a required video positional) into a Namespace."""
    return mainmod.build_parser().parse_args([*args, "v.mp4"])


# --- made-for-kids ----------------------------------------------------------


def test_made_for_kids_sets_true():
    body = mainmod.build_request_body(_opts("--title", "t", "--made-for-kids"), 0, 1)
    assert body["status"]["selfDeclaredMadeForKids"] is True


def test_not_made_for_kids_sets_false():
    body = mainmod.build_request_body(
        _opts("--title", "t", "--not-made-for-kids"), 0, 1
    )
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_default_omits_made_for_kids():
    body = mainmod.build_request_body(_opts("--title", "t"), 0, 1)
    assert "selfDeclaredMadeForKids" not in body["status"]


def test_made_for_kids_mutually_exclusive_raises():
    with pytest.raises(mainmod.OptionsError):
        mainmod.main(
            ["--title", "t", "--made-for-kids", "--not-made-for-kids", "v.mp4"]
        )


# --- description newlines (#243/#272/#355/#374) -----------------------------


def test_description_newline_interpretation(monkeypatch):
    captured = {}

    def fake_handler(options):
        captured["description"] = options.description
        raise mainmod.AuthenticationError("stop before upload")

    monkeypatch.setattr(mainmod, "get_youtube_handler", fake_handler)
    with pytest.raises(mainmod.AuthenticationError):
        mainmod.main(["--title", "t", "--description", r"line1\nline2", "v.mp4"])
    assert captured["description"] == "line1\nline2"


# --- multiple playlists (#169) ---------------------------------------------


def test_playlist_flag_is_repeatable():
    o = _opts("--title", "t", "--playlist", "A", "--playlist", "B")
    assert o.playlist == ["A", "B"]


def test_single_playlist_still_works_as_list():
    o = _opts("--title", "t", "--playlist", "Solo")
    assert o.playlist == ["Solo"]


def test_run_main_adds_video_to_each_playlist(monkeypatch):
    """run_main must call add_video_to_playlist once per --playlist."""
    added = []
    monkeypatch.setattr(
        mainmod.playlists,
        "add_video_to_playlist",
        lambda youtube, video_id, title, privacy: added.append(title),
    )
    monkeypatch.setattr(mainmod, "get_youtube_handler", lambda options: "FAKE_YT")
    monkeypatch.setattr(mainmod.upload_video, "upload", lambda *a, **k: "vidXYZ")

    options = _opts("--title", "t", "--playlist", "A", "--playlist", "B")
    out = io.StringIO()
    mainmod.run_main(mainmod.build_parser(), options, options.videos, output=out)

    assert added == ["A", "B"]
    assert out.getvalue().strip() == "vidXYZ"
