#!/usr/bin/env python

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np
import polars as pl
from dataclasses_json import DataClassJsonMixin

from . import constants
from .utils import parse_datetime, parse_timedelta

###############################################################################


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
    if start_datetime is None:
        start_datetime_dt = commits_df[datetime_col].min()
    else:
        start_datetime_dt = parse_datetime(start_datetime)
    if end_datetime is None:
        end_datetime_dt = commits_df[datetime_col].max()
    else:
        end_datetime_dt = parse_datetime(end_datetime)

    # Reduce commits to the specified time range
    commits_df = commits_df.filter(
        (commits_df[datetime_col] >= start_datetime_dt)
        & (commits_df[datetime_col] <= end_datetime_dt)
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
) -> int:
    if start_datetime is None:
        start_datetime_dt = commits_df[datetime_col].min()
    else:
        start_datetime_dt = parse_datetime(start_datetime)
    if end_datetime is None:
        end_datetime_dt = commits_df[datetime_col].max()
    else:
        end_datetime_dt = parse_datetime(end_datetime)

    # Reduce commits to the specified time range
    commits_df = commits_df.filter(
        (commits_df[datetime_col] >= start_datetime_dt)
        & (commits_df[datetime_col] <= end_datetime_dt)
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
