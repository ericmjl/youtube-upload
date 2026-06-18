import locale
import os
import signal
import sys
from collections.abc import Callable
from contextlib import contextmanager


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
