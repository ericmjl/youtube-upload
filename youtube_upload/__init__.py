"""youtube-upload package."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    VERSION = _pkg_version("youtube-upload")
except PackageNotFoundError:  # pragma: no cover - running from source without install
    VERSION = "0.0.0"
