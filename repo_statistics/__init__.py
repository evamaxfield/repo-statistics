"""Top-level package for repo-statistics."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("repo-statistics")
except PackageNotFoundError:
    __version__ = "uninstalled"

__author__ = "Eva Maxfield Brown"
__email__ = "evamaxfieldbrown@gmail.com"

from .main import (
    DEFAULT_COILED_KWARGS,
    analyze_repositories,
    analyze_repository,
)

__all__ = [
    "analyze_repositories",
    "analyze_repository",
    "DEFAULT_COILED_KWARGS",
    __version__,
    __author__,
    __email__,
]
