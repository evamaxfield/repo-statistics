"""Top-level package for repo-statistics."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("repo-statistics")
except PackageNotFoundError:
    __version__ = "uninstalled"

__author__ = "Eva Maxfield Brown"
__email__ = "evamaxfieldbrown@gmail.com"

from .main import analyze_repository  # noqa: F401
