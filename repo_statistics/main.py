#!/usr/bin/env python

from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from git import Repo
from timeout_function_decorator import timeout

from . import commits, contributors, documentation, platform, source, timeseries, utils

###############################################################################


def _analyze_repository(  # noqa: C901
    repo_path: str | Path | Repo,
    github_token: str | None = None,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
    period_spans: tuple[str, ...] | list[str] = ("1 week", "4 weeks"),
    compute_timeseries_metrics: bool = True,
    compute_contributor_stability_metrics: bool = True,
    compute_contributor_absence_factor: bool = True,
    compute_contributor_distribution_metrics: bool = True,
    compute_repo_linter_metrics: bool = True,
    compute_sloc_metrics: bool = True,
    compute_tag_metrics: bool = True,
    compute_platform_metrics: bool = True,
) -> dict:
    # Parse repo
    parsed_repo = utils.parse_repo_from_path_or_url(repo_path=repo_path)

    # Parse commits
    parsed_commit_results = commits.parse_commits(repo_path=parsed_repo.repo)
    commits_df = parsed_commit_results.commit_summaries
    per_file_commit_deltas_df = parsed_commit_results.per_file_commit_deltas

    # Parse and filter changes to datetime range
    commits_df, start_datetime_dt, end_datetime_dt = utils.filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )
    per_file_commit_deltas_df, _, _ = utils.filter_changes_to_dt_range(
        changes_df=per_file_commit_deltas_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Get processed at datetime
    processed_at_dt = datetime.now()

    # Storage for all metrics
    all_metrics = {
        "repo_owner_and_name": f"{parsed_repo.owner}/{parsed_repo.name}".lower(),
        "start_datetime": start_datetime_dt.isoformat(),
        "end_datetime": end_datetime_dt.isoformat(),
        "contributor_name_column": contributor_name_col,
        "datetime_column": datetime_col,
        "processed_at": processed_at_dt.isoformat(),
    }

    # Compute timeseries and contributor stability metrics
    for period_span in period_spans:
        period_span_key = period_span.replace(" ", "_")

        if compute_timeseries_metrics:
            timeseries_metrics = timeseries.compute_timeseries_metrics(
                commits_df=commits_df,
                period_span=period_span,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                datetime_col=datetime_col,
            )

            for key, value in timeseries_metrics.to_dict().items():
                all_metrics[f"{period_span_key}_{key}"] = value

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
                all_metrics[f"{period_span_key}_{key}"] = value

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


def analyze_repository(
    repo_path: str | Path | Repo,
    github_token: str | None = None,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
    period_spans: tuple[str, ...] | list[str] = ("1 week", "4 weeks"),
    compute_timeseries_metrics: bool = True,
    compute_contributor_stability_metrics: bool = True,
    compute_contributor_absence_factor: bool = True,
    compute_contributor_distribution_metrics: bool = True,
    compute_repo_linter_metrics: bool = True,
    compute_sloc_metrics: bool = True,
    compute_tag_metrics: bool = True,
    compute_platform_metrics: bool = True,
    clone_timeout_seconds: int = 120,
    analyze_timeout_seconds: int = 300,
) -> dict:
    # Wrap private analyze function with timeout
    @timeout(analyze_timeout_seconds)
    def _analyze_repository_with_timeout(
        repo_path: str | Path | Repo,
        github_token: str | None = None,
        start_datetime: str | date | datetime | None = None,
        end_datetime: str | date | datetime | None = None,
        contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
        datetime_col: Literal[
            "authored_datetime", "committed_datetime"
        ] = "authored_datetime",
        period_spans: tuple[str, ...] | list[str] = ("1 week", "4 weeks"),
        compute_timeseries_metrics: bool = True,
        compute_contributor_stability_metrics: bool = True,
        compute_contributor_absence_factor: bool = True,
        compute_contributor_distribution_metrics: bool = True,
        compute_repo_linter_metrics: bool = True,
        compute_sloc_metrics: bool = True,
        compute_tag_metrics: bool = True,
        compute_platform_metrics: bool = True,
    ) -> dict:
        return _analyze_repository(
            repo_path=repo_path,
            github_token=github_token,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            contributor_name_col=contributor_name_col,
            datetime_col=datetime_col,
            period_spans=period_spans,
            compute_timeseries_metrics=compute_timeseries_metrics,
            compute_contributor_stability_metrics=compute_contributor_stability_metrics,
            compute_contributor_absence_factor=compute_contributor_absence_factor,
            compute_contributor_distribution_metrics=compute_contributor_distribution_metrics,
            compute_repo_linter_metrics=compute_repo_linter_metrics,
            compute_sloc_metrics=compute_sloc_metrics,
            compute_tag_metrics=compute_tag_metrics,
            compute_platform_metrics=compute_platform_metrics,
        )

    @timeout(clone_timeout_seconds)
    def _clone_repository_with_timeout(
        repo_path: str | Path | Repo,
        to_path: str | Path,
    ) -> Repo:
        return Repo.clone_from(
            repo_path,
            to_path=to_path,
        )

    # Determine clone or path
    if isinstance(repo_path, str) and any(
        repo_path.startswith(remote_repo_prefix)
        for remote_repo_prefix in [
            "http://",
            "https://",
            "git@",
            "ssh://",
            "ftp://",
        ]
    ):
        with TemporaryDirectory() as tmpdir:
            repo = _clone_repository_with_timeout(
                repo_path=repo_path,
                to_path=tmpdir,
            )

            return _analyze_repository_with_timeout(
                repo_path=repo,
                github_token=github_token,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                contributor_name_col=contributor_name_col,
                datetime_col=datetime_col,
                period_spans=period_spans,
                compute_timeseries_metrics=compute_timeseries_metrics,
                compute_contributor_stability_metrics=compute_contributor_stability_metrics,
                compute_contributor_absence_factor=compute_contributor_absence_factor,
                compute_contributor_distribution_metrics=compute_contributor_distribution_metrics,
                compute_repo_linter_metrics=compute_repo_linter_metrics,
                compute_sloc_metrics=compute_sloc_metrics,
                compute_tag_metrics=compute_tag_metrics,
                compute_platform_metrics=compute_platform_metrics,
            )

    return _analyze_repository_with_timeout(
        repo_path=repo_path,
        github_token=github_token,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        contributor_name_col=contributor_name_col,
        datetime_col=datetime_col,
        period_spans=period_spans,
        compute_timeseries_metrics=compute_timeseries_metrics,
        compute_contributor_stability_metrics=compute_contributor_stability_metrics,
        compute_contributor_absence_factor=compute_contributor_absence_factor,
        compute_contributor_distribution_metrics=compute_contributor_distribution_metrics,
        compute_repo_linter_metrics=compute_repo_linter_metrics,
        compute_sloc_metrics=compute_sloc_metrics,
        compute_tag_metrics=compute_tag_metrics,
        compute_platform_metrics=compute_platform_metrics,
    )
