"""Wordmark package."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("wordmark")
except PackageNotFoundError:  # pragma: no cover - fallback for non-installed source usage
    __version__ = "0+unknown"
