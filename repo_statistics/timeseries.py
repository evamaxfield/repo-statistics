#!/usr/bin/env python

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np
import polars as pl
from dataclasses_json import DataClassJsonMixin
from scipy.stats import entropy, variation
from tqdm import tqdm

from . import constants
from .utils import parse_datetime, parse_timedelta, timedelta_to_string

###############################################################################


@dataclass
class CommitPeriodResults(DataClassJsonMixin):
    period_span: str
    start_datetime: str
    end_datetime: str
    datetime_column: str
    total_changed_binary: list[int]
    total_lines_changed_count: list[int]
    programming_changed_binary: list[int]
    programming_lines_changed_count: list[int]
    markup_changed_binary: list[int]
    markup_lines_changed_count: list[int]
    prose_changed_binary: list[int]
    prose_lines_changed_count: list[int]
    data_changed_binary: list[int]
    data_lines_changed_count: list[int]
    unknown_changed_binary: list[int]
    unknown_lines_changed_count: list[int]


def get_periods_changed(
    commits_df: pl.DataFrame,
    period_span: str | float | timedelta,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "committed_datetime",
) -> CommitPeriodResults:
    # Parse period span and datetimes
    td = parse_timedelta(period_span)
    if start_datetime is None:
        start_datetime_dt: datetime = commits_df[datetime_col].min()
    else:
        start_datetime_dt = parse_datetime(start_datetime)
    if end_datetime is None:
        end_datetime_dt: datetime = commits_df[datetime_col].max()
    else:
        end_datetime_dt = parse_datetime(end_datetime)

    # Calculate total periods
    change_duration = end_datetime_dt - start_datetime_dt
    n_tds = math.ceil(change_duration / td)

    # Iterate over periods and record binary or lines changed count
    current_start_dt = start_datetime_dt
    results: dict[str, list[int]] = {}
    for _ in tqdm(range(n_tds), desc="Processing change periods"):
        # Get the subset of commits in this period
        commit_subset = commits_df.filter(
            pl.col(datetime_col).is_between(
                current_start_dt,
                current_start_dt + td,
                closed="left",
            )
        )

        # Update changes (binary and lines) for this period
        def _get_binary_and_count_from_file_subset(
            commit_subset: pl.DataFrame, file_subset: str
        ) -> tuple[int, int]:
            lines_changed_col = f"{file_subset}_lines_changed"
            return (
                int(len(commit_subset.filter(pl.col(lines_changed_col) > 0)) > 0),
                commit_subset[lines_changed_col].sum(),
            )

        # Iter over each file subset
        for file_subset in ["total", *[ft.value for ft in constants.FileTypes]]:
            # Process period
            binary, count = _get_binary_and_count_from_file_subset(
                commit_subset,
                file_subset,
            )

            # Check if list already exists at key
            changed_binary_key = f"{file_subset}_changed_binary"
            lines_changed_count_key = f"{file_subset}_lines_changed_count"
            if changed_binary_key not in results:
                results[changed_binary_key] = []
            if lines_changed_count_key not in results:
                results[lines_changed_count_key] = []

            # Append to the lists
            results[changed_binary_key].append(binary)
            results[lines_changed_count_key].append(count)

        # Increment
        current_start_dt += td

    return CommitPeriodResults(
        period_span=timedelta_to_string(td),
        start_datetime=start_datetime_dt.isoformat(),
        end_datetime=end_datetime_dt.isoformat(),
        datetime_column=datetime_col,
        **results,
    )


@dataclass
class TimeseriesMetrics(DataClassJsonMixin):
    # Metadata
    period_span: str
    start_datetime: str
    end_datetime: str
    datetime_column: str
    # Change existance metrics
    total_changed_binary_entropy: float
    total_changed_binary_variation: float
    total_changed_binary_frac: float
    programming_changed_binary_entropy: float
    programming_changed_binary_variation: float
    programming_changed_binary_frac: float
    markup_changed_binary_entropy: float
    markup_changed_binary_variation: float
    markup_changed_binary_frac: float
    prose_changed_binary_entropy: float
    prose_changed_binary_variation: float
    prose_changed_binary_frac: float
    data_changed_binary_entropy: float
    data_changed_binary_variation: float
    data_changed_binary_frac: float
    unknown_changed_binary_entropy: float
    unknown_changed_binary_variation: float
    unknown_changed_binary_frac: float
    # Lines changed metrics
    total_lines_changed_count_entropy: float
    total_lines_changed_count_variation: float
    programming_lines_changed_count_entropy: float
    programming_lines_changed_count_variation: float
    markup_lines_changed_count_entropy: float
    markup_lines_changed_count_variation: float
    prose_lines_changed_count_entropy: float
    prose_lines_changed_count_variation: float
    data_lines_changed_count_entropy: float
    data_lines_changed_count_variation: float
    unknown_lines_changed_count_entropy: float
    unknown_lines_changed_count_variation: float
    # # Commit span metrics
    # median_commit_span: int
    # mean_commit_span: float
    # std_commit_span: float
    # median_no_commit_span: int
    # mean_no_commit_span: float
    # std_no_commit_span: float
    # # Contributor metrics
    # stable_contributors_count: int
    # transient_contributors_count: int
    # median_contribution_span_days: float
    # mean_contribution_span_days: float
    # normalized_median_span: float
    # normalized_mean_span: float


def compute_timeseries_metrics(
    commits_df: pl.DataFrame,
    period_span: str | float | timedelta,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "committed_datetime",
) -> TimeseriesMetrics:
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

    # Get periods changed
    periods_changed_results = get_periods_changed(
        commits_df=commits_df,
        period_span=td,
        start_datetime=start_datetime_dt,
        end_datetime=end_datetime_dt,
        datetime_col=datetime_col,
    )

    def _compute_entropy(arr: list[int]) -> float:
        return entropy(
            arr / np.sum(arr),
            base=2,
        )

    def _compute_frac(arr: list[int]) -> float:
        return np.sum(arr) / len(arr)

    # Iter over all non-metadata items returned in periods_changed_results
    # Compute single metrics in-place of arrays
    period_metrics = {}
    for key, metadata_or_arr in periods_changed_results.to_dict().items():
        # Ignore metadata fields
        if key in (
            "period_span",
            "start_datetime",
            "end_datetime",
            "datetime_column",
        ):
            continue

        # All metadata should not be filtered out
        arr = metadata_or_arr
        assert isinstance(arr, list)

        # Compute
        period_metrics[f"{key}_entropy"] = _compute_entropy(arr)
        period_metrics[f"{key}_variation"] = variation(arr)
        if "binary" in key:
            period_metrics[f"{key}_frac"] = _compute_frac(arr)

    return TimeseriesMetrics(
        period_span=timedelta_to_string(td),
        start_datetime=start_datetime_dt.isoformat(),
        end_datetime=end_datetime_dt.isoformat(),
        datetime_column=datetime_col,
        **period_metrics,
    )
