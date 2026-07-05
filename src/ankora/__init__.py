"""ankora: local-first, CI-native regression testing for LLM applications."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ankora")
except PackageNotFoundError:  # pragma: no cover - only when running from a non-installed tree
    __version__ = "0.0.0"
