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

from .utils import parse_datetime, parse_timedelta, timedelta_to_string

###############################################################################


@dataclass
class CommitPeriodResults(DataClassJsonMixin):
    period_span: str
    start_datetime: str
    end_datetime: str
    datetime_column: str
    periods_changed_binary: np.ndarray
    periods_total_lines_changed_count: np.ndarray
    periods_programming_files_changed_binary: np.ndarray
    periods_programming_lines_changed_count: np.ndarray
    periods_markup_files_changed_binary: np.ndarray
    periods_markup_lines_changed_count: np.ndarray
    periods_prose_files_changed_binary: np.ndarray
    periods_prose_lines_changed_count: np.ndarray
    periods_data_files_changed_binary: np.ndarray
    periods_data_lines_changed_count: np.ndarray
    periods_unknown_files_changed_binary: np.ndarray
    periods_unknown_lines_changed_count: np.ndarray


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
    periods_changed_binary: list[int] = []
    periods_total_lines_changed_count: list[int] = []
    periods_programming_files_changed_binary: list[int] = []
    periods_programming_lines_changed_count: list[int] = []
    periods_markup_files_changed_binary: list[int] = []
    periods_markup_lines_changed_count: list[int] = []
    periods_prose_files_changed_binary: list[int] = []
    periods_prose_lines_changed_count: list[int] = []
    periods_data_files_changed_binary: list[int] = []
    periods_data_lines_changed_count: list[int] = []
    periods_unknown_files_changed_binary: list[int] = []
    periods_unknown_lines_changed_count: list[int] = []
    current_process_date = start_datetime_dt
    for _ in tqdm(range(n_tds), desc="Processing change periods"):
        # Get the subset of commits in this period
        commit_subset = commits_df.filter(
            pl.col(datetime_col).is_between(
                current_process_date,
                current_process_date + td,
                closed="left",
            )
        )

        # Update changes (binary and lines) for this period
        if len(commit_subset) > 0:
            periods_changed_binary.append(1)
            periods_total_lines_changed_count.append(
                commit_subset["total_lines_changed"].sum(),
            )

        else:
            periods_changed_binary.append(0)
            periods_total_lines_changed_count.append(0)

        def _get_binary_and_count_from_file_subset(
            commit_subset: pl.DataFrame,
            file_subset: str,
        ) -> tuple[int, int]:
            return (
                len(commit_subset.filter(pl.col(f"{file_subset}_files_changed") > 0)),
                commit_subset[f"{file_subset}_lines_changed"].sum(),
            )

        # Handle "programming files"
        (
            programming_files_changed_binary,
            programming_lines_changed_count,
        ) = _get_binary_and_count_from_file_subset(
            commit_subset,
            "programming",
        )
        periods_programming_files_changed_binary.append(
            programming_files_changed_binary
        )
        periods_programming_lines_changed_count.append(programming_lines_changed_count)

        # Handle "markup files"
        (
            markup_files_changed_binary,
            markup_lines_changed_count,
        ) = _get_binary_and_count_from_file_subset(
            commit_subset,
            "markup",
        )
        periods_markup_files_changed_binary.append(markup_files_changed_binary)
        periods_markup_lines_changed_count.append(markup_lines_changed_count)

        # Handle "prose files"
        (
            prose_files_changed_binary,
            prose_lines_changed_count,
        ) = _get_binary_and_count_from_file_subset(
            commit_subset,
            "prose",
        )
        periods_prose_files_changed_binary.append(prose_files_changed_binary)
        periods_prose_lines_changed_count.append(prose_lines_changed_count)

        # Handle "data files"
        (
            data_files_changed_binary,
            data_lines_changed_count,
        ) = _get_binary_and_count_from_file_subset(
            commit_subset,
            "data",
        )
        periods_data_files_changed_binary.append(data_files_changed_binary)
        periods_data_lines_changed_count.append(data_lines_changed_count)

        # Handle "unknown files"
        (
            unknown_files_changed_binary,
            unknown_lines_changed_count,
        ) = _get_binary_and_count_from_file_subset(
            commit_subset,
            "unknown",
        )
        periods_unknown_files_changed_binary.append(unknown_files_changed_binary)
        periods_unknown_lines_changed_count.append(unknown_lines_changed_count)

        # Increment process date
        current_process_date += td

    return CommitPeriodResults(
        period_span=timedelta_to_string(td),
        start_datetime=start_datetime_dt.isoformat(),
        end_datetime=end_datetime_dt.isoformat(),
        datetime_column=datetime_col,
        periods_changed_binary=np.array(periods_changed_binary),
        periods_total_lines_changed_count=np.array(periods_total_lines_changed_count),
        periods_programming_files_changed_binary=np.array(
            periods_programming_files_changed_binary
        ),
        periods_programming_lines_changed_count=np.array(
            periods_programming_lines_changed_count
        ),
        periods_markup_files_changed_binary=np.array(
            periods_markup_files_changed_binary
        ),
        periods_markup_lines_changed_count=np.array(periods_markup_lines_changed_count),
        periods_prose_files_changed_binary=np.array(periods_prose_files_changed_binary),
        periods_prose_lines_changed_count=np.array(periods_prose_lines_changed_count),
        periods_data_files_changed_binary=np.array(periods_data_files_changed_binary),
        periods_data_lines_changed_count=np.array(periods_data_lines_changed_count),
        periods_unknown_files_changed_binary=np.array(
            periods_unknown_files_changed_binary
        ),
        periods_unknown_lines_changed_count=np.array(
            periods_unknown_lines_changed_count
        ),
    )


@dataclass
class TimeseriesMetrics(DataClassJsonMixin):
    # Metadata
    period_span: str
    start_datetime: str
    end_datetime: str
    datetime_column: str
    # Change existance metrics
    changed_entropy: float
    changed_variation: float
    changed_frac: float
    programming_files_changed_entropy: float
    programming_files_changed_variation: float
    programming_files_changed_frac: float
    markup_files_changed_entropy: float
    markup_files_changed_variation: float
    markup_files_changed_frac: float
    prose_files_changed_entropy: float
    prose_files_changed_variation: float
    prose_files_changed_frac: float
    data_files_changed_entropy: float
    data_files_changed_variation: float
    data_files_changed_frac: float
    unknown_files_changed_entropy: float
    unknown_files_changed_variation: float
    unknown_files_changed_frac: float
    # Lines changed metrics
    total_lines_changed_entropy: float
    total_lines_changed_variation: float
    programming_lines_changed_entropy: float
    programming_lines_changed_variation: float
    markup_lines_changed_entropy: float
    markup_lines_changed_variation: float
    prose_lines_changed_entropy: float
    prose_lines_changed_variation: float
    data_lines_changed_entropy: float
    data_lines_changed_variation: float
    unknown_lines_changed_entropy: float
    unknown_lines_changed_variation: float
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

    def _compute_entropy(arr: np.ndarray) -> float:
        return entropy(
            arr / np.sum(arr),
            base=2,
        )

    def _compute_frac(arr: np.ndarray) -> float:
        return np.sum(arr) / len(arr)

    return TimeseriesMetrics(
        # Metadata
        period_span=timedelta_to_string(td),
        start_datetime=start_datetime_dt.isoformat(),
        end_datetime=end_datetime_dt.isoformat(),
        datetime_column=datetime_col,
        # Change existance metrics
        changed_entropy=_compute_entropy(
            periods_changed_results.periods_changed_binary
        ),
        changed_variation=variation(periods_changed_results.periods_changed_binary),
        changed_frac=_compute_frac(periods_changed_results.periods_changed_binary),
        programming_files_changed_entropy=_compute_entropy(
            periods_changed_results.periods_programming_files_changed_binary
        ),
        programming_files_changed_variation=variation(
            periods_changed_results.periods_programming_files_changed_binary
        ),
        programming_files_changed_frac=_compute_frac(
            periods_changed_results.periods_programming_files_changed_binary
        ),
        markup_files_changed_entropy=_compute_entropy(
            periods_changed_results.periods_markup_files_changed_binary
        ),
        markup_files_changed_variation=variation(
            periods_changed_results.periods_markup_files_changed_binary
        ),
        markup_files_changed_frac=_compute_frac(
            periods_changed_results.periods_markup_files_changed_binary
        ),
        prose_files_changed_entropy=_compute_entropy(
            periods_changed_results.periods_prose_files_changed_binary
        ),
        prose_files_changed_variation=variation(
            periods_changed_results.periods_prose_files_changed_binary
        ),
        prose_files_changed_frac=_compute_frac(
            periods_changed_results.periods_prose_files_changed_binary
        ),
        data_files_changed_entropy=_compute_entropy(
            periods_changed_results.periods_data_files_changed_binary
        ),
        data_files_changed_variation=variation(
            periods_changed_results.periods_data_files_changed_binary
        ),
        data_files_changed_frac=_compute_frac(
            periods_changed_results.periods_data_files_changed_binary
        ),
        unknown_files_changed_entropy=_compute_entropy(
            periods_changed_results.periods_unknown_files_changed_binary
        ),
        unknown_files_changed_variation=variation(
            periods_changed_results.periods_unknown_files_changed_binary
        ),
        unknown_files_changed_frac=_compute_frac(
            periods_changed_results.periods_unknown_files_changed_binary
        ),
        # Lines changed metrics
        total_lines_changed_entropy=_compute_entropy(
            periods_changed_results.periods_total_lines_changed_count
        ),
        total_lines_changed_variation=variation(
            periods_changed_results.periods_total_lines_changed_count
        ),
        programming_lines_changed_entropy=_compute_entropy(
            periods_changed_results.periods_programming_lines_changed_count
        ),
        programming_lines_changed_variation=variation(
            periods_changed_results.periods_programming_lines_changed_count
        ),
        markup_lines_changed_entropy=_compute_entropy(
            periods_changed_results.periods_markup_lines_changed_count
        ),
        markup_lines_changed_variation=variation(
            periods_changed_results.periods_markup_lines_changed_count
        ),
        prose_lines_changed_entropy=_compute_entropy(
            periods_changed_results.periods_programming_lines_changed_count
        ),
        prose_lines_changed_variation=variation(
            periods_changed_results.periods_programming_lines_changed_count
        ),
        data_lines_changed_entropy=_compute_entropy(
            periods_changed_results.periods_data_lines_changed_count
        ),
        data_lines_changed_variation=variation(
            periods_changed_results.periods_data_lines_changed_count
        ),
        unknown_lines_changed_entropy=_compute_entropy(
            periods_changed_results.periods_unknown_lines_changed_count
        ),
        unknown_lines_changed_variation=variation(
            periods_changed_results.periods_unknown_lines_changed_count
        ),
    )
