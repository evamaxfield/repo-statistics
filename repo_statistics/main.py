#!/usr/bin/env python

import logging
import os
import traceback
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from itertools import cycle
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

import polars as pl
from dataclasses_json import DataClassJsonMixin
from gh_tokens_loader import GitHubTokensCycler
from git import Repo
from timeout_function_decorator import timeout
from tqdm import tqdm

from . import (
    classification,
    commits,
    contributors,
    documentation,
    platform,
    source,
    timeseries,
    utils,
)

###############################################################################

log = logging.getLogger(__name__)

###############################################################################


@dataclass
class CoiledConfig(DataClassJsonMixin):
    keepalive: str = "5m"
    cpu: tuple[int, int] = (2, 8)
    memory: tuple[str, str] = ("4GiB", "12GiB")
    disk_size: int = 24
    n_workers: tuple[int, int] = (1, 8)
    threads_per_worker: int = 1
    spot_policy: str = "spot_with_fallback"
    extra_kwargs: dict | None = None


DEFAULT_COILED_KWARGS = CoiledConfig(
    extra_kwargs={"package_sync_conda_extras": ["git"]}
).to_dict()

###############################################################################


@dataclass
class TrackedErrorResult(DataClassJsonMixin):
    repo_path: str | Path
    err: str
    tb: str


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
    bot_names: tuple[str, ...] | None = ("dependabot", "github"),
    bot_email_indicators: tuple[str, ...] | None = ("[bot]",),
    substantial_change_threshold_quantile: float = 0.1,
    compute_timeseries_metrics: bool = True,
    compute_contributor_stability_metrics: bool = True,
    compute_contributor_absence_factor: bool = True,
    compute_contributor_distribution_metrics: bool = True,
    compute_repo_linter_metrics: bool = True,
    compute_sloc_metrics: bool = True,
    compute_tag_metrics: bool = True,
    compute_platform_metrics: bool = True,
) -> dict:
    # Get processed at datetime
    processed_at_dt = datetime.now()

    # Parse repo
    parsed_repo = utils.parse_repo_from_path_or_url(repo_path=repo_path)

    # Parse commits
    parsed_commit_results = commits.parse_commits(repo_path=parsed_repo.repo)
    commits_df = parsed_commit_results.commit_summaries
    per_file_commit_deltas_df = parsed_commit_results.per_file_commit_deltas

    # If less than 5 commits, return None
    if len(commits_df) < 5:
        raise ValueError(
            f"Repository {parsed_repo.owner}/{parsed_repo.name} "
            f"has less than 5 commits."
        )

    # Parse and filter changes to datetime range
    # commits_df, start_datetime_dt, end_datetime_dt = utils.filter_changes_to_dt_range(
    #     changes_df=commits_df,
    #     start_datetime=start_datetime,
    #     end_datetime=end_datetime,
    #     datetime_col=datetime_col,
    # )
    # per_file_commit_deltas_df, _, _ = utils.filter_changes_to_dt_range(
    #     changes_df=per_file_commit_deltas_df,
    #     start_datetime=start_datetime,
    #     end_datetime=end_datetime,
    #     datetime_col=datetime_col,
    # )

    start_datetime_dt = commits_df[datetime_col].min()
    end_datetime_dt = commits_df[datetime_col].max()

    # Storage for all metrics
    all_metrics: dict[str, str | None | int | float | bool] = {
        "meta_repo_owner_and_name": f"{parsed_repo.owner}/{parsed_repo.name}".lower(),
        "meta_start_datetime": start_datetime_dt.isoformat(),
        "meta_end_datetime": end_datetime_dt.isoformat(),
        "meta_contributor_name_column": contributor_name_col,
        "meta_datetime_column": datetime_col,
        "meta_processed_at": processed_at_dt.isoformat(),
        "meta_bot_names": ("---".join(bot_names) if bot_names is not None else None),
        "meta_bot_email_indicators": (
            "---".join(bot_email_indicators)
            if bot_email_indicators is not None
            else None
        ),
    }

    # Normalize and drop bot changes
    log.debug("Removing bot changes")
    commits_df, bot_changes_count = commits.normalize_changes_df_and_remove_bot_changes(
        changes_df=commits_df,
        bot_names=bot_names,
        bot_email_indicators=bot_email_indicators,
    )
    per_file_commit_deltas_df, _ = commits.normalize_changes_df_and_remove_bot_changes(
        changes_df=per_file_commit_deltas_df,
        bot_names=bot_names,
        bot_email_indicators=bot_email_indicators,
    )
    all_metrics["bot_changes_count"] = bot_changes_count

    # Compute commit counts
    log.debug("Computing commit counts")
    commit_count_results = commits.compute_commit_counts(
        commits_df=commits_df,
        start_datetime=start_datetime_dt,
        end_datetime=end_datetime_dt,
        datetime_col=datetime_col,
    )
    all_metrics.update(commit_count_results.to_dict())

    # Get important change dates
    log.debug("Computing important change dates")
    important_change_date_results = commits.compute_important_change_dates(
        commits_df=commits_df,
        start_datetime=start_datetime_dt,
        end_datetime=end_datetime_dt,
        datetime_col=datetime_col,
        substantial_change_threshold_quantile=substantial_change_threshold_quantile,
    )
    all_metrics.update(important_change_date_results.to_dict())

    # Compute contributor counts
    log.debug("Computing contributor counts")
    contributor_count_results = contributors.compute_contributor_counts(
        commits_df=commits_df,
        start_datetime=start_datetime_dt,
        end_datetime=end_datetime_dt,
        contributor_name_col=contributor_name_col,
        datetime_col=datetime_col,
    )
    all_metrics.update(contributor_count_results.to_dict())

    # Compute timeseries and contributor stability metrics
    for period_span in period_spans:
        period_span_key = period_span.replace(" ", "_")

        if compute_timeseries_metrics:
            log.debug(f"Computing timeseries metrics for period span: {period_span}")
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
            log.debug(
                f"Computing contributor stability metrics "
                f"for period span: {period_span}"
            )
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
        log.debug("Computing contributor absence factor metrics")
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
        log.debug("Computing contributor distribution metrics")
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
        log.debug("Computing repo linter metrics")
        repo_linter_results = documentation.process_with_repo_linter(
            repo_path=repo_path,
            commits_df=commits_df,
            target_datetime=end_datetime,
            datetime_col=datetime_col,
        )

        all_metrics.update(repo_linter_results.to_dict())

    # Compute SLOC metrics
    if compute_sloc_metrics:
        log.debug("Computing SLOC metrics")
        sloc_results = source.compute_sloc_metrics(
            repo_path=repo_path,
            commits_df=commits_df,
            target_datetime=end_datetime,
            datetime_col=datetime_col,
        )

        all_metrics.update(sloc_results.to_dict())

    # Compute tag metrics
    if compute_tag_metrics:
        log.debug("Computing tag metrics")
        tag_metrics = source.compute_tag_metrics(
            repo_path=repo_path,
            commits_df=commits_df,
            target_datetime=end_datetime,
            datetime_col=datetime_col,
        )

        all_metrics.update(tag_metrics.to_dict())

    # Compute platform metrics
    if compute_platform_metrics:
        log.debug("Computing platform metrics")
        platform_metrics = platform.compute_platform_metrics(
            repo_path=repo_path,
            github_token=github_token,
        )

        all_metrics.update(platform_metrics.to_dict())

        # Also get classification of project type
        project_type_classification = classification.get_heuristic_project_type(
            starsgazers_count=platform_metrics.stargazers_count,
            total_contibutors_count=contributor_count_results.total_contributor_count,
        )
        all_metrics["project_type_heuristic_classification"] = (
            project_type_classification
        )

    return all_metrics


def analyze_repository(
    repo_path: str | Path,
    github_token: str | None = None,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
    period_spans: tuple[str, ...] | list[str] = ("1 week", "4 weeks"),
    bot_names: tuple[str, ...] | None = ("dependabot", "github"),
    bot_email_indicators: tuple[str, ...] | None = ("[bot]",),
    substantial_change_threshold_quantile: float = 0.1,
    compute_timeseries_metrics: bool = True,
    compute_contributor_stability_metrics: bool = True,
    compute_contributor_absence_factor: bool = True,
    compute_contributor_distribution_metrics: bool = True,
    compute_repo_linter_metrics: bool = True,
    compute_sloc_metrics: bool = True,
    compute_tag_metrics: bool = True,
    compute_platform_metrics: bool = True,
    clone_timeout_seconds: int = 60,
    analyze_timeout_seconds: int = 600,
) -> dict | TrackedErrorResult:
    # Wrap private analyze function with timeout
    @timeout(analyze_timeout_seconds)
    def _analyze_repository_with_timeout(
        **kwargs: Any,
    ) -> dict:
        return _analyze_repository(
            **kwargs,
        )

    @timeout(clone_timeout_seconds)
    def _clone_repository_with_timeout(
        repo_path: str | Path,
        to_path: str | Path,
    ) -> Repo:
        repo = Repo.clone_from(
            repo_path,
            to_path=to_path,
        )

        return repo

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
            try:
                repo = _clone_repository_with_timeout(
                    repo_path=repo_path,
                    to_path=tmpdir,
                )
            except Exception as e:
                return TrackedErrorResult(
                    repo_path=repo_path,
                    err=str(e),
                    tb=traceback.format_exc(),
                )

            try:
                metrics = _analyze_repository_with_timeout(
                    repo_path=repo,
                    github_token=github_token,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    contributor_name_col=contributor_name_col,
                    datetime_col=datetime_col,
                    period_spans=period_spans,
                    bot_names=bot_names,
                    bot_email_indicators=bot_email_indicators,
                    substantial_change_threshold_quantile=substantial_change_threshold_quantile,
                    compute_timeseries_metrics=compute_timeseries_metrics,
                    compute_contributor_stability_metrics=compute_contributor_stability_metrics,
                    compute_contributor_absence_factor=compute_contributor_absence_factor,
                    compute_contributor_distribution_metrics=compute_contributor_distribution_metrics,
                    compute_repo_linter_metrics=compute_repo_linter_metrics,
                    compute_sloc_metrics=compute_sloc_metrics,
                    compute_tag_metrics=compute_tag_metrics,
                    compute_platform_metrics=compute_platform_metrics,
                )
            except Exception as e:
                return TrackedErrorResult(
                    repo_path=repo_path,
                    err=str(e),
                    tb=traceback.format_exc(),
                )

    else:
        try:
            metrics = _analyze_repository_with_timeout(
                repo_path=repo_path,
                github_token=github_token,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                contributor_name_col=contributor_name_col,
                datetime_col=datetime_col,
                period_spans=period_spans,
                bot_names=bot_names,
                bot_email_indicators=bot_email_indicators,
                substantial_change_threshold_quantile=substantial_change_threshold_quantile,
                compute_timeseries_metrics=compute_timeseries_metrics,
                compute_contributor_stability_metrics=compute_contributor_stability_metrics,
                compute_contributor_absence_factor=compute_contributor_absence_factor,
                compute_contributor_distribution_metrics=compute_contributor_distribution_metrics,
                compute_repo_linter_metrics=compute_repo_linter_metrics,
                compute_sloc_metrics=compute_sloc_metrics,
                compute_tag_metrics=compute_tag_metrics,
                compute_platform_metrics=compute_platform_metrics,
            )
        except Exception as e:
            return TrackedErrorResult(
                repo_path=repo_path,
                err=str(e),
                tb=traceback.format_exc(),
            )

    # Store the original path of the repo
    if isinstance(metrics, dict):
        metrics["repo_path"] = str(repo_path)

    return metrics


@dataclass
class AnalyzeRepositoriesResults:
    metrics_df: pl.DataFrame
    errors_df: pl.DataFrame


def _one_by_one_processing(
    batch_repo_paths: list[str | Path],
    github_token_cycler: Iterator[str | None],
    **analyze_repository_kwargs: Any,
) -> tuple[list[dict], list[TrackedErrorResult]]:
    batch_results = []
    batch_errors = []

    # Analyze batch
    for repo_path in tqdm(
        batch_repo_paths,
        desc="Analyzing repositories",
        unit="repo",
        leave=False,
    ):
        result = analyze_repository(
            repo_path=repo_path,
            github_token=next(github_token_cycler),
            **analyze_repository_kwargs,
        )

        if isinstance(result, TrackedErrorResult):
            batch_errors.append(result.to_dict())
        else:
            batch_results.append(result)

    return batch_results, batch_errors


def _multiple_threads_processing(
    batch_repo_paths: list[str | Path],
    github_token_cycler: Iterator[str | None],
    n_threads: int | None = None,
    **analyze_repository_kwargs: Any,
) -> tuple[list[dict], list[TrackedErrorResult]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    batch_results = []
    batch_errors = []

    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        future_to_repo_path = {
            executor.submit(
                analyze_repository,
                repo_path=repo_path,
                github_token=next(github_token_cycler),
                **analyze_repository_kwargs,
            ): repo_path
            for repo_path in batch_repo_paths
        }

        for future in tqdm(
            as_completed(future_to_repo_path),
            total=len(batch_repo_paths),
            desc="Analyzing repositories (multi-threaded)",
            unit="repo",
            leave=False,
        ):
            repo_path = future_to_repo_path[future]
            try:
                result = future.result()
                if isinstance(result, TrackedErrorResult):
                    batch_errors.append(result.to_dict())
                else:
                    batch_results.append(result)

            except Exception as e:
                batch_errors.append(
                    TrackedErrorResult(
                        repo_path=repo_path,
                        err=str(e),
                        tb=traceback.format_exc(),
                    ).to_dict()
                )

    return batch_results, batch_errors


def _coiled_processing(
    batch_repo_paths: list[str | Path],
    github_token_cycler: Iterator[str | None],
    coiled_kwargs: dict | None = None,
    **analyze_repository_kwargs: Any,
) -> tuple[list[dict], list[TrackedErrorResult]]:
    try:
        import coiled
    except ImportError as e:
        raise ImportError(
            "Coiled is not installed. Please install coiled to use this feature."
        ) from e

    batch_results = []
    batch_errors = []

    # Always add git to coiled kwargs
    if coiled_kwargs is None:
        prepped_coiled_kwargs = {
            "extra_kwargs": {"package_sync_conda_extras": ["git"]},
        }
    else:
        prepped_coiled_kwargs = coiled_kwargs
        if "extra_kwargs" in prepped_coiled_kwargs:
            if "package_sync_conda_extras" in prepped_coiled_kwargs["extra_kwargs"]:
                if (
                    "git"
                    not in prepped_coiled_kwargs["extra_kwargs"][
                        "package_sync_conda_extras"
                    ]
                ):
                    prepped_coiled_kwargs["extra_kwargs"][
                        "package_sync_conda_extras"
                    ].append("git")
            else:
                prepped_coiled_kwargs["extra_kwargs"]["package_sync_conda_extras"] = [
                    "git"
                ]
        else:
            prepped_coiled_kwargs["extra_kwargs"] = {
                "package_sync_conda_extras": ["git"]
            }

    # Create coiled function
    @coiled.function(**prepped_coiled_kwargs)
    def _analyze_repository_coiled(
        repo_path: str | Path,
        github_token: str | None = None,
        **analyze_repository_kwargs: Any,
    ) -> dict | TrackedErrorResult:
        return analyze_repository(
            repo_path=repo_path,
            github_token=github_token,
            **analyze_repository_kwargs,
        )

    # Submit coiled jobs
    futures = {
        _analyze_repository_coiled.submit(
            repo_path=repo_path,
            github_token=next(github_token_cycler),
            **analyze_repository_kwargs,
        ): repo_path
        for repo_path in batch_repo_paths
    }

    for future in tqdm(
        futures,
        total=len(batch_repo_paths),
        desc="Analyzing repositories (coiled)",
        unit="repo",
        leave=False,
    ):
        repo_path = futures[future]
        try:
            result = future.result()
            if isinstance(result, TrackedErrorResult):
                batch_errors.append(result.to_dict())
            else:
                batch_results.append(result)

        except Exception as e:
            batch_errors.append(
                TrackedErrorResult(
                    repo_path=repo_path,
                    err=str(e),
                    tb=traceback.format_exc(),
                ).to_dict()
            )

    return batch_results, batch_errors


def analyze_repositories(  # noqa: C901
    repo_paths: list[str | Path],
    github_tokens: list[str | None] | str | Path | None = None,
    cache_results_path: str | Path | None = None,
    cache_errors_path: str | Path | None = None,
    ignore_cached_results: bool = False,
    batch_size: int | float = 10,
    use_multithreading: bool = False,
    n_threads: int | None = None,
    use_coiled: bool = False,
    coiled_kwargs: dict | None = None,
    **analyze_repository_kwargs: Any,
) -> AnalyzeRepositoriesResults:
    # Cannot use multiple processes and coiled at the same time
    if use_multithreading and use_coiled:
        raise ValueError("Cannot use multiple processes and coiled at the same time.")

    # Lowercase all repo paths for consistency
    repo_paths = [str(rp).lower().strip() for rp in repo_paths]

    # Check for prior cached results
    if (
        not ignore_cached_results
        and cache_results_path is not None
        and Path(cache_results_path).exists()
    ):
        log.info(f"Loading cached results from {cache_results_path}")
        previously_processed_repo_metrics = pl.read_parquet(cache_results_path)
        previously_processed_repo_paths = previously_processed_repo_metrics[
            "repo_path"
        ].to_list()
        results = previously_processed_repo_metrics.to_dicts()
    else:
        previously_processed_repo_paths = []
        results = []

    # Check for prior errored results
    if (
        not ignore_cached_results
        and cache_errors_path is not None
        and Path(cache_errors_path).exists()
    ):
        log.info(f"Loading cached errors from {cache_errors_path}")
        previously_errored_repos = pl.read_parquet(cache_errors_path)
        previously_processed_errors_repo_paths = previously_errored_repos[
            "repo_path"
        ].to_list()
        errors = previously_errored_repos.to_dicts()
    else:
        previously_processed_errors_repo_paths = []
        errors = []

    # Combine previously processed repo paths and error repo paths
    all_previously_processed_or_errored_repo_paths = {
        *previously_processed_repo_paths,
        *previously_processed_errors_repo_paths,
    }

    # Log the count of previously processed repos we are skipping
    log.info(
        f"Skipping {len(all_previously_processed_or_errored_repo_paths)} "
        f"previously processed or errored repositories."
    )

    # Remove previously processed repos from repo_paths
    to_process_repo_paths = [
        rp
        for rp in repo_paths
        if rp not in all_previously_processed_or_errored_repo_paths
    ]

    # Prepare GitHub tokens
    if github_tokens is None:
        github_tokens = [None]
    if isinstance(github_tokens, str):
        # Doesn't look like a file path
        # User provided a single token
        if not Path(github_tokens).exists():
            github_tokens = [github_tokens]

    # Check for GitHub tokens file
    if isinstance(github_tokens, (str, Path)):
        # Read with gh tokens loader
        gh_tokens_cycler = GitHubTokensCycler(github_tokens)
    elif isinstance(github_tokens, list):
        # Convert to token cycler
        gh_tokens_cycler = cycle(github_tokens)
    else:
        raise ValueError(
            "github_tokens must be None, a single str token,"
            "a list of str tokens, or a str or path to a tokens file. "
            f"Got: {type(github_tokens)}"
        )

    # Determine batch size
    if isinstance(batch_size, float):
        # Round to nearest int
        int_batch_size = round(len(to_process_repo_paths) * batch_size)
    else:
        int_batch_size = batch_size

    # Calculate total number of batches
    total_batches = (len(to_process_repo_paths) + int_batch_size - 1) // int_batch_size

    # Do not ask for credentials interactively
    os.environ["GIT_TERMINAL_PROMPT"] = "0"

    # Process in batches
    for batch_start_idx in tqdm(
        range(0, len(to_process_repo_paths), int_batch_size),
        total=total_batches,
        desc="Processing repositories in batches",
        unit="batch",
    ):
        # Get batch repo paths
        batch_repo_paths = to_process_repo_paths[
            batch_start_idx : batch_start_idx + int_batch_size
        ]

        # Use multiple threads
        if use_multithreading:
            batch_results, batch_errors = _multiple_threads_processing(
                batch_repo_paths=batch_repo_paths,
                github_token_cycler=gh_tokens_cycler,
                n_threads=n_threads,
                **analyze_repository_kwargs,
            )

        # Use coiled
        elif use_coiled:
            batch_results, batch_errors = _coiled_processing(
                batch_repo_paths=batch_repo_paths,
                github_token_cycler=gh_tokens_cycler,
                coiled_kwargs=coiled_kwargs,
                **analyze_repository_kwargs,
            )

        # Single process
        else:
            batch_results, batch_errors = _one_by_one_processing(
                batch_repo_paths=batch_repo_paths,
                github_token_cycler=gh_tokens_cycler,
                **analyze_repository_kwargs,
            )

        results.extend(batch_results)
        errors.extend(batch_errors)

        # Cache intermediate results
        if cache_results_path is not None and len(results) > 0:
            pl.DataFrame(results).write_parquet(cache_results_path)
        if cache_errors_path is not None and len(errors) > 0:
            pl.DataFrame(errors).write_parquet(cache_errors_path)

    # Unset the env var
    if "GIT_TERMINAL_PROMPT" in os.environ:
        del os.environ["GIT_TERMINAL_PROMPT"]

    return AnalyzeRepositoriesResults(
        metrics_df=pl.DataFrame(results),
        errors_df=pl.DataFrame(errors),
    )
