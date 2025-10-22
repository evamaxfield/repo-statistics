#!/usr/bin/env python

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import backoff
from dataclasses_json import DataClassJsonMixin
from ghapi.all import GhApi
from git import Repo

from .utils import parse_repo_from_path_or_url

###############################################################################

log = logging.getLogger(__name__)

###############################################################################


@dataclass
class PlatformMetrics(DataClassJsonMixin):
    primary_programming_language: str | None
    stargazers_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
)
def _request_platform_metrics_with_backoff(
    github_token: str | None,
    repo_owner: str,
    repo_name: str,
) -> PlatformMetrics:
    # Init API
    if github_token is not None:
        api = GhApi(token=github_token)
    else:
        api = GhApi()

    # Sleep to avoid rate limits
    if github_token is None:
        # Alert that we are unauthenticated and need to be careful about rate limits
        log.warning(
            "Unauthenticated GitHub API requests have string rate limits. "
            "You will likely hit these limits if you are using this library "
            "to process multiple repositories quickly. "
            "Consider providing a GitHub token to increase your rate limits."
        )

    time.sleep(0.85)

    # Request
    repo_data = api.repos.get(
        owner=repo_owner,
        repo=repo_name,
    )

    return PlatformMetrics(
        stargazers_count=repo_data["stargazers_count"],
        forks_count=repo_data["forks_count"],
        watchers_count=repo_data["watchers_count"],
        open_issues_count=repo_data["open_issues_count"],
        primary_programming_language=repo_data["language"],
    )


def compute_platform_metrics(
    repo_path: str | Path | Repo,
    github_token: str | None,
) -> PlatformMetrics:
    # Parse repo info
    parsed_repo = parse_repo_from_path_or_url(repo_path=repo_path)

    # Request platform metrics with backoff
    return _request_platform_metrics_with_backoff(
        github_token=github_token,
        repo_owner=parsed_repo.owner,
        repo_name=parsed_repo.name,
    )
