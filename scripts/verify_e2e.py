#!/usr/bin/env python
"""End-to-end verification that the modernized youtube-upload actually works.

This uploads a real (private) 2-second test video through the *actual* CLI
(``python -m youtube_upload``), then verifies it via the YouTube Data API and
deletes it. It reuses the package's own auth + hierarchical credential
discovery, so it exercises the real code path end to end.

Requires a valid OAuth client-secret file at the canonical location
(``~/.config/youtube-upload/client_secrets.json``) or via the usual hierarchy.
The first run opens a browser once for OAuth consent and persists the token to
``~/.config/youtube-upload/token.json``; subsequent runs are non-interactive.

Run::

    uv run python scripts/verify_e2e.py

Exit code 0 = PASS (upload + verify + cleanup all succeeded).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from youtube_upload import auth

TITLE = "youtube-upload self-test (safe to delete)"


def make_test_video(path: Path) -> None:
    """Generate a tiny 2-second test video with ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=160x120:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def upload_via_cli(video: Path) -> tuple[int, str, str]:
    """Upload via the real CLI entry point; return (exit_code, stdout, stderr)."""
    # "line1\\nline2" is a literal backslash-n; the CLI converts it to a newline,
    # which lets us verify description-newline handling end to end.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "youtube_upload",
            "--title",
            TITLE,
            "--privacy",
            "private",
            "--auth-browser",
            "--made-for-kids",
            "--tags",
            "youtube-upload,selftest",
            "--description",
            "line1\\nline2",
            str(video),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "selftest.mp4"
        print(">> generating 2s test video with ffmpeg...")
        make_test_video(video)

        print(">> uploading (private) via the real CLI...")
        print("   (a browser will open ONCE for OAuth consent if no token exists)")
        code, out, err = upload_via_cli(video)
        if code != 0:
            print(f">> UPLOAD FAILED (exit {code})")
            print("--- stdout ---")
            print(out[-1500:])
            print("--- stderr (tail) ---")
            print(err[-2000:])
            return 1

        video_id = [ln for ln in out.splitlines() if ln.strip()][-1].strip()
        print(f">> uploaded; video id = {video_id}")

        print(">> verifying + cleaning up via the API (re-using package auth)...")
        try:
            youtube = auth.get_resource(get_code_callback=lambda *a, **k: True)
            info = youtube.videos().list(id=video_id, part="snippet,status").execute()
            if not info.get("items"):
                print(">> VERIFY FAILED: video not visible via API right after upload")
                return 1
            item = info["items"][0]
            snippet, status = item["snippet"], item["status"]
            desc = snippet.get("description", "")
            has_newline = "\n" in desc
            print(f">> title:       {snippet['title']}")
            print(f">> privacy:     {status['privacyStatus']}")
            print(f">> description: {desc!r} (newline present: {has_newline})")
            print(
                f">> made-for-kids (selfDeclaredMadeForKids): {status.get('selfDeclaredMadeForKids')}"
            )
            checks = {
                "title matches": snippet["title"] == TITLE,
                "privacy is private": status["privacyStatus"] == "private",
                "description has newline": "\n" in desc,
                "made-for-kids declared True": status.get("selfDeclaredMadeForKids")
                is True,
            }
        finally:
            try:
                youtube = auth.get_resource(get_code_callback=lambda *a, **k: True)
                youtube.videos().delete(id=video_id).execute()
                print(f">> deleted test video {video_id}")
            except Exception as exc:  # noqa: BLE001
                print(
                    f">> WARNING: cleanup delete failed ({exc}); remove manually: {video_id}"
                )

    print()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print(f">> RESULT: FAIL - checks failed: {failed}")
        return 1
    print(">> RESULT: PASS - end-to-end upload (auth + metadata + resumable) works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
