#!/usr/bin/env python

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import numpy as np
import polars as pl
from dataclasses_json import DataClassJsonMixin
from scipy.stats import entropy

from . import constants
from .gini import _compute_gini
from .utils import parse_timedelta

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
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> ContributorCountMetrics:

    # Get unique contributors for each file type
    contributor_counts: dict[str, int] = {}
    for file_subset in ["total", *[ft.value for ft in constants.FileTypes]]:
        subset_df = commits_df.filter(pl.col(f"{file_subset}_lines_changed") > 0)
        n_unique_contributors = (
            subset_df[contributor_name_col].str.to_lowercase().str.strip_chars().n_unique()
        )
        contributor_counts[f"{file_subset}_contributor_count"] = n_unique_contributors

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
    start_datetime: datetime,
    end_datetime: datetime,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> ContributorStabilityMetrics:
    # Parse period span and datetimes
    td = parse_timedelta(period_span)

    # Fast exit if no commits
    if len(commits_df) == 0:
        return ContributorStabilityMetrics(
            stable_contributors_count=0,
            transient_contributors_count=0,
            median_contribution_span_days=0,
            mean_contribution_span_days=0,
            normalized_median_contribution_span=0,
            normalized_mean_contribution_span=0,
        )

    # Calculate project duration in days
    project_duration = (end_datetime - start_datetime).days

    # Get contribution spans for each contributor
    spans_df = (
        commits_df.group_by(contributor_name_col)
        .agg(
            pl.col(datetime_col).min().alias("first_commit"),
            pl.col(datetime_col).max().alias("last_commit"),
        )
        .with_columns(
            (pl.col("last_commit") - pl.col("first_commit")).dt.total_days().alias("span_days")
        )
    )
    contributor_spans = spans_df["span_days"].to_list()

    # Calculate metrics
    stable_count = int((spans_df["span_days"] >= td.days).sum())
    transient_count = int((spans_df["span_days"] < td.days).sum())

    # Calculate span statistics (convert numpy types to Python floats)
    median_span = float(np.median(contributor_spans)) if contributor_spans else 0.0
    mean_span = float(np.mean(contributor_spans)) if contributor_spans else 0.0

    # Calculate normalized spans
    normalized_median = median_span / project_duration if project_duration > 0 else 0.0
    normalized_mean = mean_span / project_duration if project_duration > 0 else 0.0

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
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> ContributorAbsenceFactorMetrics:

    if len(commits_df) == 0:
        return ContributorAbsenceFactorMetrics(
            total_contributor_absence_factor=0,
            programming_contributor_absence_factor=0,
            markup_contributor_absence_factor=0,
            prose_contributor_absence_factor=0,
            data_contributor_absence_factor=0,
            unknown_contributor_absence_factor=0,
        )

    # Aggregate lines changed per contributor for all file subsets in one pass
    file_subsets = ["total", *[ft.value for ft in constants.FileTypes]]
    sums_df = commits_df.group_by(contributor_name_col).agg(
        [pl.col(f"{fs}_lines_changed").sum().alias(fs) for fs in file_subsets]
    )

    # For each file subset, find the minimum number of contributors that account for >= 50%
    contrib_absence_factor_per_file_subset: dict[str, int] = {}
    for fs in file_subsets:
        col = sums_df[fs].sort(descending=True)
        total = col.sum()
        if total == 0:
            absence_factor = 0
        else:
            cumsum = col.cum_sum()
            absence_factor = int((cumsum < total / 2).sum()) + 1
        contrib_absence_factor_per_file_subset[f"{fs}_contributor_absence_factor"] = (
            absence_factor
        )

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
    files_per_contributor_vector = (
        filetype_filtered_df.group_by(contributor_name_col)
        .agg(pl.col("filename").n_unique().alias("n"))["n"]
        .to_list()
    )

    # Handle contributors per file
    contributors_per_file_vector = (
        filetype_filtered_df.group_by("filename")
        .agg(pl.col(contributor_name_col).n_unique().alias("n"))["n"]
        .to_list()
    )

    # Handle single contributor case
    if len(files_per_contributor_vector) == 1:
        files_per_contributor_entropy = np.nan
    else:
        # Convert to probabilities
        files_per_contributor_vector_as_prob = np.array(files_per_contributor_vector) / sum(
            files_per_contributor_vector
        )
        files_per_contributor_entropy = entropy(files_per_contributor_vector_as_prob, base=2)

    # Handle single file case
    if len(contributors_per_file_vector) == 1:
        contributors_per_file_entropy = np.nan
    else:
        # Convert to probabilities
        contributors_per_file_vector_as_prob = np.array(contributors_per_file_vector) / sum(
            contributors_per_file_vector
        )
        contributors_per_file_entropy = entropy(contributors_per_file_vector_as_prob, base=2)

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
        files_arr = np.array(files_per_contributor_vector)
        twenty_fifth_percentile_files_per_contributor = np.percentile(files_arr, 25)
        median_files_per_contributor = np.median(files_arr)

        simple_threshold_specialist_count = int((files_arr <= 3).sum())
        simple_threshold_generalist_count = int((files_arr > 3).sum())
        median_threshold_specialist_count = int(
            (files_arr <= median_files_per_contributor).sum()
        )
        median_threshold_generalist_count = int(
            (files_arr > median_files_per_contributor).sum()
        )
        twenty_fifth_percentile_threshold_specialist_count = int(
            (files_arr <= twenty_fifth_percentile_files_per_contributor).sum()
        )
        twenty_fifth_percentile_threshold_generalist_count = int(
            (files_arr > twenty_fifth_percentile_files_per_contributor).sum()
        )

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
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> ContributorDistributionMetrics:

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
        file_subset_metrics[file_subset] = _compute_single_file_subset_contributor_distribution(
            filetype_filtered_df=filetype_filtered_df,
            contributor_name_col=contributor_name_col,
        )

    # Compile all file subset metrics into one dataclass
    # Use Any for value type since fields have mixed int/float types
    kwargs: dict[str, Any] = {}
    for file_subset, metrics in file_subset_metrics.items():
        kwargs[f"{file_subset}_contributors_per_file_entropy"] = (
            metrics.contributors_per_file_entropy
        )
        kwargs[f"{file_subset}_contributors_per_file_gini"] = metrics.contributors_per_file_gini
        kwargs[f"{file_subset}_files_per_contributor_entropy"] = (
            metrics.files_per_contributor_entropy
        )
        kwargs[f"{file_subset}_files_per_contributor_gini"] = metrics.files_per_contributor_gini
        kwargs[f"{file_subset}_simple_threshold_generalist_count"] = (
            metrics.simple_threshold_generalist_count
        )
        kwargs[f"{file_subset}_simple_threshold_specialist_count"] = (
            metrics.simple_threshold_specialist_count
        )
        kwargs[f"{file_subset}_median_threshold_generalist_count"] = (
            metrics.median_threshold_generalist_count
        )
        kwargs[f"{file_subset}_median_threshold_specialist_count"] = (
            metrics.median_threshold_specialist_count
        )
        kwargs[f"{file_subset}_twenty_fifth_percentile_threshold_generalist_count"] = (
            metrics.twenty_fifth_percentile_threshold_generalist_count
        )
        kwargs[f"{file_subset}_twenty_fifth_percentile_threshold_specialist_count"] = (
            metrics.twenty_fifth_percentile_threshold_specialist_count
        )
    return ContributorDistributionMetrics(**kwargs)


@dataclass
class ContributorChangeMetrics(DataClassJsonMixin):
    diff_contributor_count: int
    same_contributor_count: int


def compute_contributor_change_metrics(
    commits_df: pl.DataFrame,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
) -> ContributorChangeMetrics:

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
        diff_contributor_count=len(initial_contributors.difference(most_recent_contributors)),
        same_contributor_count=len(initial_contributors.intersection(most_recent_contributors)),
    )
