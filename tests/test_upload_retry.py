"""Tests for the tenacity-based resumable upload + retry logic."""

from __future__ import annotations

import json

import googleapiclient.errors
import httplib2
import pytest
import tenacity

from youtube_upload import auth, upload_video


def _http_error(
    status: int, reason: str = "unspecified"
) -> googleapiclient.errors.HttpError:
    """Build an HttpError with a given status and a parseable error reason."""
    content = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()
    resp = httplib2.Response({"status": status})
    return googleapiclient.errors.HttpError(resp, content)


# --- is_retriable -----------------------------------------------------------


@pytest.mark.parametrize(
    "exc, expected",
    [
        (_http_error(500), True),
        (_http_error(502), True),
        (_http_error(503), True),
        (_http_error(504), True),
        (_http_error(429), True),
        (_http_error(404), False),
        (_http_error(403, "forbidden"), False),
        (_http_error(403, "rateLimitExceeded"), True),
        (_http_error(403, "userRateLimitExceeded"), True),
        (_http_error(403, "quotaExceeded"), True),
        (ConnectionError("broken pipe"), True),
        (TimeoutError("slow"), True),
        (httplib2.HttpLib2Error("lib2"), True),
        (ValueError("not retriable"), False),
    ],
)
def test_is_retriable(exc, expected):
    assert upload_video.is_retriable(exc) is expected


def test_is_retriable_resumable_upload_error_is_covered():
    """ResumableUploadError is an HttpError subclass; a 5xx one must retry."""
    err = googleapiclient.errors.ResumableUploadError(
        httplib2.Response({"status": 503}), b"{}"
    )
    assert upload_video.is_retriable(err) is True


# --- _upload_to_request retry behavior --------------------------------------


class _FakeRequest:
    """Mimics a googleapiclient resumable request's ``next_chunk``."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        if not self._behaviors:
            raise AssertionError("FakeRequest exhausted")
        item = self._behaviors.pop(0)
        if isinstance(item, BaseException):
            raise item
        # item is (status, response); status None means "still uploading".
        return item


_NOWAIT = tenacity.wait_none()


def test_upload_retries_then_succeeds():
    req = _FakeRequest([_http_error(503), _http_error(503), (None, {"id": "vid123"})])
    vid = upload_video._upload_to_request(req, wait=_NOWAIT, max_attempts=5)
    assert vid == "vid123"
    assert req.calls == 3  # two retries + final success


def test_upload_nonretriable_raises_immediately():
    req = _FakeRequest([_http_error(404)])
    with pytest.raises(googleapiclient.errors.HttpError):
        upload_video._upload_to_request(req, wait=_NOWAIT, max_attempts=5)
    assert req.calls == 1  # no retries on a hard 4xx


def test_upload_exhausts_attempts_then_reraises():
    req = _FakeRequest([_http_error(503)] * 10)
    with pytest.raises(googleapiclient.errors.HttpError):
        upload_video._upload_to_request(req, wait=_NOWAIT, max_attempts=3)
    assert req.calls == 3  # gave up after 3 attempts


def test_upload_progress_callback_invoked():
    seen = []

    def cb(total, completed):
        seen.append((total, completed))

    # First chunk reports progress (status present), second returns the id.
    req = _FakeRequest(
        [
            (_FakeStatus(1000, 512), None),
            (None, {"id": "abc"}),
        ]
    )
    vid = upload_video._upload_to_request(req, progress_callback=cb, wait=_NOWAIT)
    assert vid == "abc"
    assert seen == [(1000, 512)]


class _FakeStatus:
    def __init__(self, total_size, resumable_progress):
        self.total_size = total_size
        self.resumable_progress = resumable_progress


def test_upload_missing_id_raises_upload_error():
    req = _FakeRequest([(None, {"no": "id"})])
    with pytest.raises(upload_video.UploadError):
        upload_video._upload_to_request(req, wait=_NOWAIT)


# --- httplib2 308 regression (#293) -----------------------------------------


def test_build_youtube_resource_removes_308_redirect(monkeypatch):
    """The AuthorizedHttp transport must not treat 308 as a redirect (#293)."""
    fake_creds = object()
    captured = {}

    def fake_build(service, version, http=None, **kwargs):
        captured["http"] = http
        return "RESOURCE"

    monkeypatch.setattr(auth.googleapiclient.discovery, "build", fake_build)
    auth._build_youtube_resource(fake_creds)
    authorized_http = captured["http"]
    # AuthorizedHttp stores the underlying httplib2.Http on ``.http``.
    underlying = getattr(authorized_http, "http", authorized_http)
    assert 308 not in underlying.redirect_codes
    # Sanity: 308 is still a redirect on a fresh Http (proves the fix is real).
    assert 308 in httplib2.Http().redirect_codes
