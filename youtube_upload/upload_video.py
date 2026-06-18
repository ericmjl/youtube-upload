"""Resumable chunked video upload with automatic retry.

The upload uses YouTube's resumable-upload protocol: the file is sent in chunks
(via :class:`googleapiclient.http.MediaFileUpload` with ``resumable=True``) and
``request.next_chunk()`` is called repeatedly until the server returns the
video id. Transient failures (5xx, 429, transport errors, quota/rate-limit
reasons) are retried with exponential backoff via :mod:`tenacity`.

Resume works for free: re-invoking ``next_chunk()`` on the same request object
makes ``googleapiclient`` re-query the upload session URI and resume from the
last byte the server acknowledged, so a retry continues the upload rather than
restarting it.
"""

from __future__ import annotations

import json
import logging
import ssl
from collections.abc import Callable
from http.client import IncompleteRead
from typing import Any

import googleapiclient.errors
import httplib2
import tenacity
from googleapiclient.http import MediaFileUpload

from .lib import debug

logger = logging.getLogger(__name__)

# HTTP statuses that are always worth retrying.
RETRIABLE_HTTP_STATUSES = {500, 502, 503, 504, 429}

# YouTube API "reason" strings (inside a 403) that indicate a transient
# rate/quota condition rather than a hard permission denial.
RETRIABLE_HTTP_REASONS = {
    "backendError",
    "quotaExceeded",
    "rateLimitExceeded",
    "userRateLimitExceeded",
}

# Transport-level exceptions that are always retriable. ``OSError`` covers
# ``ConnectionError``/``BrokenPipeError``/``TimeoutError``/``socket.error``.
TRANSPORT_EXCEPTIONS = (
    OSError,
    ssl.SSLError,
    IncompleteRead,
    httplib2.HttpLib2Error,
)

# Exponential backoff with full jitter, capped so a flaky link never stalls for
# minutes on end (the legacy uncapped ``2**retry`` could sleep ~17 min).
RETRY_WAIT = tenacity.wait_exponential_jitter(initial=1, max=60)


class UploadError(Exception):
    """Raised when a completed upload response lacks a video id."""


def _http_error_reason(exc: googleapiclient.errors.HttpError) -> str | None:
    """Extract the YouTube API error ``reason`` from an ``HttpError``.

    :param exc: the HttpError raised by googleapiclient.
    :returns: the reason string, or ``None`` if it cannot be parsed.
    """
    try:
        data = json.loads(exc.content.decode("utf-8"))
        return data["error"]["errors"][0]["reason"]
    except Exception:
        return None


def is_retriable(exc: BaseException) -> bool:
    """Return whether ``exc`` is a transient error worth retrying.

    Retries transport errors, HTTP 5xx, HTTP 429, and 403 responses whose reason
    is a rate/quota limit. Never retries genuine client errors (other 4xx).

    :param exc: the exception raised while uploading.
    :returns: True if the error is transient and the upload should resume.
    """
    if isinstance(exc, TRANSPORT_EXCEPTIONS):
        return True
    if isinstance(exc, googleapiclient.errors.HttpError):
        # ResumableUploadError is a subclass of HttpError and is covered here.
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in RETRIABLE_HTTP_STATUSES:
            return True
        if status == 403 and _http_error_reason(exc) in RETRIABLE_HTTP_REASONS:
            return True
    return False


def _before_sleep(retry_state: tenacity.RetryCallState) -> None:
    """Log each retry attempt (mirrors the legacy debug messages)."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    debug(
        "[retry {n}] {etype}: {msg}".format(
            n=retry_state.attempt_number,
            etype=type(exc).__name__ if exc else "-",
            msg=(str(exc) or "-") if exc else "-",
        )
    )


def _upload_to_request(
    request: Any,
    progress_callback: Callable[[int, int], None] | None = None,
    max_attempts: int = 10,
    wait: tenacity.wait.wait_base = RETRY_WAIT,
) -> str:
    """Drive the resumable upload, retrying transient failures via tenacity.

    :param request: a ``videos().insert(...)`` request with a resumable
        ``media_body``.
    :param progress_callback: optional ``callback(total_bytes, completed_bytes)``.
    :param max_attempts: total attempts per chunk before giving up.
    :param wait: tenacity wait strategy (overridable for tests).
    :returns: the newly uploaded video id.
    :raises UploadError: if the final response lacks an ``id``.
    """
    retrying = tenacity.Retrying(
        retry=tenacity.retry_if_exception(is_retriable),
        wait=wait,
        stop=tenacity.stop_after_attempt(max_attempts),
        before_sleep=_before_sleep,
        reraise=True,
    )
    while True:
        # Each ``next_chunk()`` is retried independently; on a transient failure
        # tenacity re-invokes it on the SAME request, which resumes the upload.
        status, response = retrying(request.next_chunk)
        if status and progress_callback:
            progress_callback(status.total_size, status.resumable_progress)
        if response:
            if "id" in response:
                return response["id"]
            raise UploadError(f"Upload completed without a video id: {response}")


def upload(
    resource: Any,
    path: str,
    body: dict,
    chunksize: int = 8 * 1024 * 1024,
    progress_callback: Callable[[int, int], None] | None = None,
    max_attempts: int = 10,
) -> str:
    """Upload a video file to YouTube and return the new video id.

    Uses resumable chunked uploads. ``chunksize`` must be a multiple of 256 KiB;
    the default is 8 MiB (a good balance of throughput and resume granularity).

    :param resource: an authenticated YouTube API resource.
    :param path: path to the video file.
    :param body: the ``videos.insert`` request body.
    :param chunksize: resumable chunk size in bytes.
    :param progress_callback: optional ``callback(total_bytes, completed_bytes)``.
    :param max_attempts: total attempts per chunk before giving up.
    :returns: the newly uploaded video id.
    """
    body_keys = ",".join(body.keys())
    media = MediaFileUpload(
        path, chunksize=chunksize, resumable=True, mimetype="application/octet-stream"
    )
    request = resource.videos().insert(part=body_keys, body=body, media_body=media)
    return _upload_to_request(request, progress_callback, max_attempts=max_attempts)
