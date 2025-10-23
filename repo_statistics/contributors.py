#!/usr/bin/env python

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np
import polars as pl
from dataclasses_json import DataClassJsonMixin
from scipy.stats import entropy

from . import constants
from .gini import _compute_gini
from .utils import filter_changes_to_dt_range, parse_timedelta

###############################################################################


@dataclass
class ContributorCountMetrics(DataClassJsonMixin):
    total_contributor_count: int
    programming_contributor_count: int
    markup_contributor_count: int
    prose_contributor_count: int
    data_contributor_count: int
    unknown_contributor_count: int


def compute_contributor_counts(
    commits_df: pl.DataFrame,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> ContributorCountMetrics:
    # Parse datetimes and filter commits to range
    commits_df, _, _ = filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Get unique contributors for each file type
    contributor_counts: dict[str, int] = {}
    for file_subset in ["total", *[ft.value for ft in constants.FileTypes]]:
        subset_df = commits_df.filter(commits_df[f"{file_subset}_lines_changed"] > 0)
        unique_contributors = subset_df[contributor_name_col].unique()
        contributor_counts[f"{file_subset}_contributor_count"] = len(
            unique_contributors
        )

    return ContributorCountMetrics(**contributor_counts)


@dataclass
class ContributorStabilityMetrics(DataClassJsonMixin):
    stable_contributors_count: int
    transient_contributors_count: int
    median_contribution_span_days: float
    mean_contribution_span_days: float
    normalized_median_contribution_span: float
    normalized_mean_contribution_span: float


def compute_contributor_stability_metrics(
    commits_df: pl.DataFrame,
    period_span: str | float | timedelta,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> ContributorStabilityMetrics:
    # Parse period span and datetimes
    td = parse_timedelta(period_span)

    # Parse datetimes and filter commits to range
    commits_df, start_datetime_dt, end_datetime_dt = filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Calculate project duration in days
    project_duration = (end_datetime_dt - start_datetime_dt).days

    # Get contribution spans for each contributor
    contributor_spans = []
    contributor_stability = []
    for _, contributor_commits in commits_df.group_by(contributor_name_col):
        # Get first and last commit dates
        first_commit = contributor_commits[datetime_col].min()
        last_commit = contributor_commits[datetime_col].max()

        # Calculate contribution span in days
        span_days = (last_commit - first_commit).days
        contributor_spans.append(span_days)

        # Classify as stable/transient based on span compared to td
        if span_days >= td.days:
            contributor_stability.append("stable")
        else:
            contributor_stability.append("transient")

    # Calculate metrics
    stable_count = sum(1 for x in contributor_stability if x == "stable")
    transient_count = sum(1 for x in contributor_stability if x == "transient")

    # Calculate span statistics
    median_span = np.median(contributor_spans) if contributor_spans else 0
    mean_span = np.mean(contributor_spans) if contributor_spans else 0

    # Calculate normalized spans
    normalized_median = median_span / project_duration if project_duration > 0 else 0
    normalized_mean = mean_span / project_duration if project_duration > 0 else 0

    return ContributorStabilityMetrics(
        stable_contributors_count=stable_count,
        transient_contributors_count=transient_count,
        median_contribution_span_days=median_span,
        mean_contribution_span_days=mean_span,
        normalized_median_contribution_span=normalized_median,
        normalized_mean_contribution_span=normalized_mean,
    )


@dataclass
class ContributorAbsenceFactorMetrics(DataClassJsonMixin):
    total_contributor_absence_factor: int
    programming_contributor_absence_factor: int
    markup_contributor_absence_factor: int
    prose_contributor_absence_factor: int
    data_contributor_absence_factor: int
    unknown_contributor_absence_factor: int


def compute_contributor_absence_factor(
    commits_df: pl.DataFrame,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> ContributorAbsenceFactorMetrics:
    # Parse datetimes and filter commits to range
    commits_df, _, _ = filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Create list of lines changed by file type
    all_file_subsets_lines_change_per_contrib: dict[str, list[int]] = {}
    for _, contributor_group in commits_df.group_by(contributor_name_col):
        for file_subset in ["total", *[ft.value for ft in constants.FileTypes]]:
            lines_changed_col = f"{file_subset}_lines_changed"
            if file_subset not in all_file_subsets_lines_change_per_contrib:
                all_file_subsets_lines_change_per_contrib[file_subset] = []

            all_file_subsets_lines_change_per_contrib[file_subset].append(
                contributor_group[lines_changed_col].sum()
            )

    # Sort all lists, sum, get half, then find min number of contributors to reach half
    contrib_absence_factor_per_file_subset: dict[str, int] = {}
    for (
        file_subset,
        lines_changed_per_contrib,
    ) in all_file_subsets_lines_change_per_contrib.items():
        descending_lines_changed_per_contrib = sorted(
            lines_changed_per_contrib, reverse=True
        )
        lines_changed_sum = sum(descending_lines_changed_per_contrib)
        half_lines_changed_sum = lines_changed_sum / 2
        contributors_to_half = 0
        current_total = 0
        for contributor_lines_changed in descending_lines_changed_per_contrib:
            current_total += contributor_lines_changed
            contributors_to_half += 1
            if current_total >= half_lines_changed_sum:
                break

        contrib_absence_factor_per_file_subset[
            f"{file_subset}_contributor_absence_factor"
        ] = contributors_to_half

    return ContributorAbsenceFactorMetrics(**contrib_absence_factor_per_file_subset)


@dataclass
class SingleFileSubsetContributorDistributionMetrics(DataClassJsonMixin):
    contributors_per_file_entropy: float
    contributors_per_file_gini: float
    files_per_contributor_entropy: float
    files_per_contributor_gini: float
    simple_threshold_generalist_count: int
    simple_threshold_specialist_count: int
    median_threshold_generalist_count: int
    median_threshold_specialist_count: int
    twenty_fifth_percentile_threshold_generalist_count: int
    twenty_fifth_percentile_threshold_specialist_count: int


@dataclass
class ContributorDistributionMetrics(DataClassJsonMixin):
    total_contributors_per_file_entropy: float
    total_contributors_per_file_gini: float
    total_files_per_contributor_entropy: float
    total_files_per_contributor_gini: float
    total_simple_threshold_generalist_count: int
    total_simple_threshold_specialist_count: int
    total_median_threshold_generalist_count: int
    total_median_threshold_specialist_count: int
    total_twenty_fifth_percentile_threshold_generalist_count: int
    total_twenty_fifth_percentile_threshold_specialist_count: int
    programming_contributors_per_file_entropy: float
    programming_contributors_per_file_gini: float
    programming_files_per_contributor_entropy: float
    programming_files_per_contributor_gini: float
    programming_simple_threshold_generalist_count: int
    programming_simple_threshold_specialist_count: int
    programming_median_threshold_generalist_count: int
    programming_median_threshold_specialist_count: int
    programming_twenty_fifth_percentile_threshold_generalist_count: int
    programming_twenty_fifth_percentile_threshold_specialist_count: int
    markup_contributors_per_file_entropy: float
    markup_contributors_per_file_gini: float
    markup_files_per_contributor_entropy: float
    markup_files_per_contributor_gini: float
    markup_simple_threshold_generalist_count: int
    markup_simple_threshold_specialist_count: int
    markup_median_threshold_generalist_count: int
    markup_median_threshold_specialist_count: int
    markup_twenty_fifth_percentile_threshold_generalist_count: int
    markup_twenty_fifth_percentile_threshold_specialist_count: int
    prose_contributors_per_file_entropy: float
    prose_contributors_per_file_gini: float
    prose_files_per_contributor_entropy: float
    prose_files_per_contributor_gini: float
    prose_simple_threshold_generalist_count: int
    prose_simple_threshold_specialist_count: int
    prose_median_threshold_generalist_count: int
    prose_median_threshold_specialist_count: int
    prose_twenty_fifth_percentile_threshold_generalist_count: int
    prose_twenty_fifth_percentile_threshold_specialist_count: int
    data_contributors_per_file_entropy: float
    data_contributors_per_file_gini: float
    data_files_per_contributor_entropy: float
    data_files_per_contributor_gini: float
    data_simple_threshold_generalist_count: int
    data_simple_threshold_specialist_count: int
    data_median_threshold_generalist_count: int
    data_median_threshold_specialist_count: int
    data_twenty_fifth_percentile_threshold_generalist_count: int
    data_twenty_fifth_percentile_threshold_specialist_count: int
    unknown_contributors_per_file_entropy: float
    unknown_contributors_per_file_gini: float
    unknown_files_per_contributor_entropy: float
    unknown_files_per_contributor_gini: float
    unknown_simple_threshold_generalist_count: int
    unknown_simple_threshold_specialist_count: int
    unknown_median_threshold_generalist_count: int
    unknown_median_threshold_specialist_count: int
    unknown_twenty_fifth_percentile_threshold_generalist_count: int
    unknown_twenty_fifth_percentile_threshold_specialist_count: int


def _compute_single_file_subset_contributor_distribution(
    filetype_filtered_df: pl.DataFrame,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
) -> SingleFileSubsetContributorDistributionMetrics:
    # Handle files per contributor
    files_per_contributor_vector = []
    for _, contributor_group in filetype_filtered_df.group_by(contributor_name_col):
        # Add the number of unique files touched by this contributor
        files_per_contributor_vector.append(contributor_group["filename"].n_unique())

    # Handle contributors per file
    contributors_per_file_vector = []
    for _, file_group in filetype_filtered_df.group_by("filename"):
        # Add the number of unique contributors who touched this file
        contributors_per_file_vector.append(file_group[contributor_name_col].n_unique())

    # Handle single contributor case
    if len(files_per_contributor_vector) == 1:
        files_per_contributor_entropy = np.nan
    else:
        # Convert to probabilities
        files_per_contributor_vector_as_prob = np.array(
            files_per_contributor_vector
        ) / sum(files_per_contributor_vector)
        files_per_contributor_entropy = entropy(
            files_per_contributor_vector_as_prob, base=2
        )

    # Handle single file case
    if len(contributors_per_file_vector) == 1:
        contributors_per_file_entropy = np.nan
    else:
        # Convert to probabilities
        contributors_per_file_vector_as_prob = np.array(
            contributors_per_file_vector
        ) / sum(contributors_per_file_vector)
        contributors_per_file_entropy = entropy(
            contributors_per_file_vector_as_prob, base=2
        )

    # Compute Gini coefficients
    contributors_per_file_gini = _compute_gini(contributors_per_file_vector)
    files_per_contributor_gini = _compute_gini(files_per_contributor_vector)

    # Count specialists and generalists
    simple_threshold_generalist_count = 0
    simple_threshold_specialist_count = 0
    median_threshold_generalist_count = 0
    median_threshold_specialist_count = 0
    twenty_fifth_percentile_threshold_generalist_count = 0
    twenty_fifth_percentile_threshold_specialist_count = 0

    # Handle no files per contributor
    if len(files_per_contributor_vector) > 0:
        # Get the median number of files changed per contributor
        twenty_fifth_percentile_files_per_contributor = np.percentile(
            files_per_contributor_vector, 25
        )
        median_files_per_contributor = np.median(files_per_contributor_vector)

        for contributor_files_count in files_per_contributor_vector:
            # Handle simple threshold
            if contributor_files_count <= 3:
                simple_threshold_specialist_count += 1
            else:
                simple_threshold_generalist_count += 1

            # Handle median threshold
            if contributor_files_count <= median_files_per_contributor:
                median_threshold_specialist_count += 1
            else:
                median_threshold_generalist_count += 1

            # Handle 25th percentile threshold
            if contributor_files_count <= twenty_fifth_percentile_files_per_contributor:
                twenty_fifth_percentile_threshold_specialist_count += 1
            else:
                twenty_fifth_percentile_threshold_generalist_count += 1

    # Compile metrics for this file subset
    return SingleFileSubsetContributorDistributionMetrics(
        contributors_per_file_entropy=contributors_per_file_entropy,
        contributors_per_file_gini=contributors_per_file_gini,
        files_per_contributor_entropy=files_per_contributor_entropy,
        files_per_contributor_gini=files_per_contributor_gini,
        simple_threshold_generalist_count=simple_threshold_generalist_count,
        simple_threshold_specialist_count=simple_threshold_specialist_count,
        median_threshold_generalist_count=median_threshold_generalist_count,
        median_threshold_specialist_count=median_threshold_specialist_count,
        twenty_fifth_percentile_threshold_generalist_count=twenty_fifth_percentile_threshold_generalist_count,
        twenty_fifth_percentile_threshold_specialist_count=twenty_fifth_percentile_threshold_specialist_count,
    )


def compute_contributor_distribution_metrics(
    per_file_commit_deltas_df: pl.DataFrame,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> ContributorDistributionMetrics:
    # Parse datetimes and filter commits to range
    per_file_commit_deltas_df, _, _ = filter_changes_to_dt_range(
        changes_df=per_file_commit_deltas_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Make each calculation for all file types
    file_subset_metrics: dict[str, SingleFileSubsetContributorDistributionMetrics] = {}
    for file_subset in ["total", *[ft.value for ft in constants.FileTypes]]:
        # With "total" we use the whole per_file_commit_deltas_df
        # For other file types we filter down to just that file type
        if file_subset != "total":
            filetype_filtered_df = per_file_commit_deltas_df.filter(
                pl.col("filetype") == file_subset
            )
        else:
            filetype_filtered_df = per_file_commit_deltas_df

        # Store to dict
        file_subset_metrics[file_subset] = (
            _compute_single_file_subset_contributor_distribution(
                filetype_filtered_df=filetype_filtered_df,
                contributor_name_col=contributor_name_col,
            )
        )

    # Compile all file subset metrics into one dataclass
    return ContributorDistributionMetrics(
        **{
            f"{file_subset}_{metric_name}": metric_value
            for file_subset, file_subset_metrics in file_subset_metrics.items()
            for metric_name, metric_value in file_subset_metrics.to_dict().items()
        },
    )


@dataclass
class ContributorChangeMetrics(DataClassJsonMixin):
    diff_contributor_count: int
    same_contributor_count: int


def compute_contributor_change_metrics(
    commits_df: pl.DataFrame,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
) -> ContributorChangeMetrics:
    # Parse datetimes and filter commits to range
    commits_df, _, _ = filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Calculate commit count thresholds
    total_commits = len(commits_df)
    commit_threshold = int(total_commits * 0.2)

    # Get the set of contributors in the first 20% of commits
    initial_commits = commits_df.head(commit_threshold)

    # Ensure that we at least have 3 commits
    if len(initial_commits) < 3:
        initial_commits = commits_df.head(3)

    # Get contribs in the first 20%
    initial_contributors = set(initial_commits[contributor_name_col])

    # Get the set of contributors in the last 20% of commits
    most_recent_commits = commits_df.tail(commit_threshold)

    # Ensure that we at least have 3 commits
    if len(most_recent_commits) < 3:
        most_recent_commits = commits_df.tail(3)

    # Get contribs in the last 20%
    most_recent_contributors = set(most_recent_commits[contributor_name_col])

    # Get the difference
    return ContributorChangeMetrics(
        diff=len(initial_contributors.difference(most_recent_contributors)),
        same=len(initial_contributors.intersection(most_recent_contributors)),
    )
