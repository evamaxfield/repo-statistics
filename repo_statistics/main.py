#!/usr/bin/env python

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from git import Repo

from . import commits, contributors, documentation, platform, source, timeseries

###############################################################################


def analyze_repository(  # noqa: C901
    repo_path: str | Path | Repo,
    github_token: str | None = None,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    period_spans: tuple[str, ...] | list[str] = ("1 week", "4 weeks"),
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
    compute_timeseries_metrics: bool = True,
    compute_contributor_stability_metrics: bool = True,
    compute_contributor_absence_factor: bool = True,
    compute_contributor_distribution_metrics: bool = True,
    compute_repo_linter_metrics: bool = True,
    compute_sloc_metrics: bool = True,
    compute_tag_metrics: bool = True,
    compute_platform_metrics: bool = True,
) -> dict:
    # TODO: Handle clone

    # Parse commits
    parsed_commit_results = commits.parse_commits(repo_path=repo_path)
    commits_df = parsed_commit_results.commit_summaries
    per_file_commit_deltas_df = parsed_commit_results.per_file_commit_deltas

    # Storage for all metrics
    # TODO: store basic processing metadata
    # e.g., the repo_path, start and end datetimes used, etc.
    # include "processed_at" datetime
    all_metrics = {}

    # Compute timeseries and contributor stability metrics
    for period_span in period_spans:
        if compute_timeseries_metrics:
            timeseries_metrics = timeseries.compute_timeseries_metrics(
                commits_df=commits_df,
                period_span=period_span,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                datetime_col=datetime_col,
            )

            for key, value in timeseries_metrics.to_dict().items():
                all_metrics[f"{period_span}_{key}"] = value

        if compute_contributor_stability_metrics:
            contributor_stability_metrics = (
                contributors.compute_contributor_stability_metrics(
                    commits_df=commits_df,
                    period_span=period_span,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    contributor_name_col=contributor_name_col,
                    datetime_col=datetime_col,
                )
            )

            for key, value in contributor_stability_metrics.to_dict().items():
                all_metrics[f"{period_span}_{key}"] = value

    # Compute other contributor metrics
    if compute_contributor_absence_factor:
        contributor_absence_factor_metrics = (
            contributors.compute_contributor_absence_factor(
                commits_df=commits_df,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                contributor_name_col=contributor_name_col,
                datetime_col=datetime_col,
            )
        )

        all_metrics.update(contributor_absence_factor_metrics.to_dict())

    # Compute contributor distribution metrics
    if compute_contributor_distribution_metrics:
        contributor_distribution_metrics = (
            contributors.compute_contributor_distribution_metrics(
                per_file_commit_deltas_df=per_file_commit_deltas_df,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                contributor_name_col=contributor_name_col,
                datetime_col=datetime_col,
            )
        )

        all_metrics.update(contributor_distribution_metrics.to_dict())

    # Compute repo linter metrics
    if compute_repo_linter_metrics:
        repo_linter_results = documentation.process_with_repo_linter(
            repo_path=repo_path,
            commits_df=commits_df,
            target_datetime=end_datetime,
            datetime_col=datetime_col,
        )

        # TODO: add in documentation total (sum of binary results)
        all_metrics.update(repo_linter_results.to_dict())

    # Compute SLOC metrics
    if compute_sloc_metrics:
        sloc_results = source.compute_sloc_metrics(
            repo_path=repo_path,
            commits_df=commits_df,
            target_datetime=end_datetime,
            datetime_col=datetime_col,
        )

        all_metrics.update(sloc_results.to_dict())

    # Compute tag metrics
    if compute_tag_metrics:
        tag_metrics = source.compute_tag_metrics(
            repo_path=repo_path,
            commits_df=commits_df,
            target_datetime=end_datetime,
            datetime_col=datetime_col,
        )

        all_metrics.update(tag_metrics.to_dict())

    # Compute platform metrics
    if compute_platform_metrics:
        platform_metrics = platform.compute_platform_metrics(
            repo_path=repo_path,
            github_token=github_token,
        )

        all_metrics.update(platform_metrics.to_dict())

    return all_metrics
