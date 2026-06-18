"""Smoke tests that do not require network access or OAuth credentials.

These tests guard the package's import graph and declared entry points so the
modernized tool is installable and importable in CI without any secrets. They do
not exercise the live YouTube API.
"""

from __future__ import annotations


def test_top_level_package_imports() -> None:
    """The top-level package imports and exposes a non-empty VERSION string."""
    import youtube_upload

    assert hasattr(youtube_upload, "VERSION")
    assert isinstance(youtube_upload.VERSION, str)
    assert youtube_upload.VERSION  # non-empty


def test_auth_module_imports() -> None:
    """The modernized auth module imports cleanly via the google-auth stack."""
    import youtube_upload.auth as auth

    assert auth.SCOPES  # non-empty scope list


def test_main_exposes_entrypoints() -> None:
    """The CLI module exposes ``main`` and ``run`` callables.

    This guards the script entry point declared in ``pyproject.toml``
    (``youtube-upload = "youtube_upload.main:run"``).
    """
    from youtube_upload import main as main_module

    assert callable(main_module.main)
    assert callable(main_module.run)
