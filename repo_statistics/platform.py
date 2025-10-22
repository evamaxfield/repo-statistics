#!/usr/bin/env python

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import backoff
from dataclasses_json import DataClassJsonMixin
from ghapi.all import GhApi
from git import Repo

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
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    # Get the origin / remote URL
    remote_url = repo.remote().url

    # Example remote URL format:
    # git@github.com:evamaxfield/rs-graph.git
    # RegEx parse to get owner and repo name
    parsed_owner_and_name = re.match(
        r"(?:git@github\.com:|https://github\.com/)(?P<owner>[^/]+)/(?P<repo>.+)",
        remote_url,
    )
    if parsed_owner_and_name is None:
        raise ValueError(
            f"Could not parse GitHub owner and repo name from remote URL: {remote_url}"
        )

    repo_owner = parsed_owner_and_name.group("owner")
    repo_name = parsed_owner_and_name.group("repo").removesuffix(".git")

    # Request platform metrics with backoff
    return _request_platform_metrics_with_backoff(
        github_token=github_token,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
