import locale
import os
import random
import signal
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager

import googleapiclient.errors


@contextmanager
def default_sigint():
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)


def get_encoding():
    return locale.getpreferredencoding()


def to_utf8(s):
    """Re-encode string from the default system encoding to UTF-8."""
    current = locale.getpreferredencoding()
    if hasattr(s, "decode"):  # Python 3 workaround
        return s.decode(current).encode("UTF-8") if s and current != "UTF-8" else s
    elif isinstance(s, bytes):
        return bytes.decode(s)
    else:
        return s


def debug(obj, fd=sys.stderr):
    """Write obj to standard error."""
    print(obj, file=fd)


def catch_exceptions(
    exit_codes: dict[type[BaseException], int],
    fun: Callable[[list[str]], object],
    arguments: list[str] | None = None,
) -> int:
    """Run ``fun(arguments)`` and return the mapped exit code on a known exception.

    Matches the raised exception against ``exit_codes`` by walking its MRO, so a
    subclass (e.g. ``RefreshError``) is correctly mapped via a registered base
    class (e.g. ``GoogleAuthError``). Returns 0 if no exception is raised.

    :param exit_codes: mapping of exception type -> exit code.
    :param fun: callable invoked as ``fun(arguments)``.
    :param arguments: argument list forwarded to ``fun`` (e.g. ``sys.argv[1:]``).
    :returns: the mapped exit code, or 0 on success.
    """
    try:
        fun(list(arguments or []))
        return 0
    except tuple(exit_codes.keys()) as exc:
        for exc_type in type(exc).__mro__:
            if exc_type in exit_codes:
                debug(f"[{exc_type.__name__}] {exc}")
                return exit_codes[exc_type]
        return 1  # pragma: no cover - unreachable: exc is guaranteed in keys


def first(it):
    """Return first element in iterable."""
    return it.next()


def string_to_dict(string):
    """Return dictionary from string "key1=value1, key2=value2"."""
    if string:
        pairs = [s.strip() for s in string.split(",")]
        return dict(pair.split("=") for pair in pairs)


def get_first_existing_filename(prefixes, relative_path):
    """Get the first existing filename of relative_path seeking on prefixes directories."""
    for prefix in prefixes:
        path = os.path.join(prefix, relative_path)
        if os.path.exists(path):
            return path


def retriable_exceptions(fun, retriable_exceptions, max_retries=None):
    """Run function and retry on some exceptions (with exponential backoff)."""
    retry = 0
    while 1:
        try:
            return fun()
        except tuple(retriable_exceptions) as exc:
            retry += 1
            if type(exc) not in retriable_exceptions:
                raise exc
            # we want to retry 5xx errors only
            elif (
                isinstance(exc, googleapiclient.errors.HttpError)
                and exc.resp.status < 500
            ):
                raise exc
            elif max_retries is not None and retry > max_retries:
                debug("[Retryable errors] Retry limit reached")
                raise exc
            else:
                seconds = random.uniform(0, 2**retry)
                message = (
                    "[Retryable error {current_retry}/{total_retries}] "
                    + "{error_type} ({error_msg}). Wait {wait_time} seconds"
                ).format(
                    current_retry=retry,
                    total_retries=max_retries or "-",
                    error_type=type(exc).__name__,
                    error_msg=str(exc) or "-",
                    wait_time=f"{seconds:.1f}",
                )
                debug(message)
                time.sleep(seconds)
