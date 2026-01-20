#!/usr/bin/env python

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, cast

import numpy as np
import polars as pl
from dataclasses_json import DataClassJsonMixin
from scipy.stats import entropy, variation
from tqdm import tqdm

from . import constants
from .gini import _compute_gini
from .utils import parse_timedelta

###############################################################################


@dataclass
class ChangePeriodResults(DataClassJsonMixin):
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
        "authored_datetime",
        "committed_datetime",
    ] = "authored_datetime",
) -> ChangePeriodResults:
    # Parse period span and datetimes
    td = parse_timedelta(period_span)

    # Handle case where commits_df is empty
    if len(commits_df) == 0:
        return ChangePeriodResults(
            total_changed_binary=[],
            total_lines_changed_count=[],
            programming_changed_binary=[],
            programming_lines_changed_count=[],
            markup_changed_binary=[],
            markup_lines_changed_count=[],
            prose_changed_binary=[],
            prose_lines_changed_count=[],
            data_changed_binary=[],
            data_lines_changed_count=[],
            unknown_changed_binary=[],
            unknown_lines_changed_count=[],
        )

    # Parse datetimes and filter commits to range
    # commits_df, start_datetime_dt, end_datetime_dt = filter_changes_to_dt_range(
    #     changes_df=commits_df,
    #     start_datetime=start_datetime,
    #     end_datetime=end_datetime,
    #     datetime_col=datetime_col,
    # )

    start_datetime_dt = cast(datetime, commits_df[datetime_col].min())
    end_datetime_dt = cast(datetime, commits_df[datetime_col].max())

    # Calculate total periods
    change_duration = end_datetime_dt - start_datetime_dt

    # Always have at least one period
    n_tds = max(math.ceil(change_duration / td), 1)

    # Pre-compute file subsets and initialize results dict
    file_subsets = ["total", *[ft.value for ft in constants.FileTypes]]
    results: dict[str, list[int]] = {}
    for file_subset in file_subsets:
        results[f"{file_subset}_changed_binary"] = []
        results[f"{file_subset}_lines_changed_count"] = []

    # Helper function defined once outside the loop
    def _get_binary_and_count(commit_subset: pl.DataFrame, lines_col: str) -> tuple[int, int]:
        if len(commit_subset) == 0:
            return (0, 0)
        return (
            int(len(commit_subset.filter(pl.col(lines_col) > 0)) > 0),
            int(commit_subset[lines_col].sum()),
        )

    # Iterate over periods and record binary or lines changed count
    current_start_dt: datetime = start_datetime_dt
    for _ in tqdm(range(n_tds), desc="Processing change periods", leave=False):
        # Get the subset of commits in this period
        commit_subset = commits_df.filter(
            pl.col(datetime_col).is_between(
                current_start_dt,
                current_start_dt + td,
                closed="left",
            )
        )

        # Process each file subset
        for file_subset in file_subsets:
            lines_changed_col = f"{file_subset}_lines_changed"
            binary, count = _get_binary_and_count(commit_subset, lines_changed_col)
            results[f"{file_subset}_changed_binary"].append(binary)
            results[f"{file_subset}_lines_changed_count"].append(count)

        # Increment
        current_start_dt += td

    return ChangePeriodResults(**results)


@dataclass
class ChangeSpanResults(DataClassJsonMixin):
    did_change_spans: list[int]
    did_not_change_spans: list[int]


def get_change_spans(
    periods_changed: list[int],
) -> ChangeSpanResults:
    """Count consecutive spans of change (1) and no-change (0) periods.

    For example, [0, 0, 1, 1, 1, 0, 0] would produce:
    - did_change_spans: [3] (one span of 3 consecutive changes)
    - did_not_change_spans: [2, 2] (two spans of 2 consecutive no-changes)
    """
    if len(periods_changed) == 0:
        return ChangeSpanResults(did_change_spans=[], did_not_change_spans=[])

    did_change_spans: list[int] = []
    did_not_change_spans: list[int] = []
    current_span_length = 1
    current_is_change = periods_changed[0] == 1

    for period in periods_changed[1:]:
        is_change = period == 1
        if is_change == current_is_change:
            # Continue current span
            current_span_length += 1
        else:
            # End current span and start new one
            if current_is_change:
                did_change_spans.append(current_span_length)
            else:
                did_not_change_spans.append(current_span_length)
            current_span_length = 1
            current_is_change = is_change

    # Append the final span
    if current_is_change:
        did_change_spans.append(current_span_length)
    else:
        did_not_change_spans.append(current_span_length)

    return ChangeSpanResults(
        did_change_spans=did_change_spans,
        did_not_change_spans=did_not_change_spans,
    )


@dataclass
class TimeseriesMetrics(DataClassJsonMixin):
    # Change existance metrics
    total_changed_binary_entropy: float
    total_changed_binary_gini: float
    total_changed_binary_variation: float
    total_changed_binary_frac: float
    programming_changed_binary_entropy: float
    programming_changed_binary_gini: float
    programming_changed_binary_variation: float
    programming_changed_binary_frac: float
    markup_changed_binary_entropy: float
    markup_changed_binary_gini: float
    markup_changed_binary_variation: float
    markup_changed_binary_frac: float
    prose_changed_binary_entropy: float
    prose_changed_binary_gini: float
    prose_changed_binary_variation: float
    prose_changed_binary_frac: float
    data_changed_binary_entropy: float
    data_changed_binary_gini: float
    data_changed_binary_variation: float
    data_changed_binary_frac: float
    unknown_changed_binary_entropy: float
    unknown_changed_binary_gini: float
    unknown_changed_binary_variation: float
    unknown_changed_binary_frac: float
    # Lines changed count metrics
    total_lines_changed_count_entropy: float
    total_lines_changed_count_gini: float
    total_lines_changed_count_variation: float
    programming_lines_changed_count_entropy: float
    programming_lines_changed_count_gini: float
    programming_lines_changed_count_variation: float
    markup_lines_changed_count_entropy: float
    markup_lines_changed_count_gini: float
    markup_lines_changed_count_variation: float
    prose_lines_changed_count_entropy: float
    prose_lines_changed_count_gini: float
    prose_lines_changed_count_variation: float
    data_lines_changed_count_entropy: float
    data_lines_changed_count_gini: float
    data_lines_changed_count_variation: float
    unknown_lines_changed_count_entropy: float
    unknown_lines_changed_count_gini: float
    unknown_lines_changed_count_variation: float
    # Change span metrics (all floats since median can be float and NaN is float)
    total_did_change_median_span: float
    total_did_change_mean_span: float
    total_did_change_std_span: float
    total_did_not_change_median_span: float
    total_did_not_change_mean_span: float
    total_did_not_change_std_span: float
    programming_did_change_median_span: float
    programming_did_change_mean_span: float
    programming_did_change_std_span: float
    programming_did_not_change_median_span: float
    programming_did_not_change_mean_span: float
    programming_did_not_change_std_span: float
    markup_did_change_median_span: float
    markup_did_change_mean_span: float
    markup_did_change_std_span: float
    markup_did_not_change_median_span: float
    markup_did_not_change_mean_span: float
    markup_did_not_change_std_span: float
    prose_did_change_median_span: float
    prose_did_change_mean_span: float
    prose_did_change_std_span: float
    prose_did_not_change_median_span: float
    prose_did_not_change_mean_span: float
    prose_did_not_change_std_span: float
    data_did_change_median_span: float
    data_did_change_mean_span: float
    data_did_change_std_span: float
    data_did_not_change_median_span: float
    data_did_not_change_mean_span: float
    data_did_not_change_std_span: float
    unknown_did_change_median_span: float
    unknown_did_change_mean_span: float
    unknown_did_change_std_span: float
    unknown_did_not_change_median_span: float
    unknown_did_not_change_mean_span: float
    unknown_did_not_change_std_span: float


def _compute_entropy(arr: list[int]) -> float:
    arr_sum = np.sum(arr)
    if arr_sum == 0:
        return np.nan

    return entropy(
        np.array(arr) / arr_sum,
        base=2,
    )


def _compute_frac(arr: list[int]) -> float:
    if len(arr) == 0:
        return float("nan")

    return np.sum(arr) / len(arr)


def _compute_metrics_from_periods_change_results(
    periods_changed_results: ChangePeriodResults,
) -> dict[str, int | float]:
    # Iter over all non-metadata items returned in periods_changed_results
    # Compute single metrics in-place of arrays
    period_and_span_metrics: dict[str, int | float] = {}
    for period_key, metadata_or_arr in periods_changed_results.to_dict().items():
        # Ignore metadata fields
        if period_key in (
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
        period_and_span_metrics[f"{period_key}_entropy"] = _compute_entropy(arr)
        period_and_span_metrics[f"{period_key}_gini"] = _compute_gini(arr)
        period_and_span_metrics[f"{period_key}_variation"] = (
            variation(arr) if len(arr) > 1 else np.nan
        )
        if "binary" in period_key:
            period_and_span_metrics[f"{period_key}_frac"] = _compute_frac(arr)

            # All "binary" keys follow pattern of
            # <file_subset>_changed_binary
            file_subset = period_key.replace("_changed_binary", "")

            # Get spans
            span_results = get_change_spans(arr)
            for span_reduction_func in [
                np.median,
                np.mean,
                np.std,
            ]:
                # Did change spans
                did_change_span_key = (
                    f"{file_subset}_did_change_{span_reduction_func.__name__}_span"
                )
                if len(span_results.did_change_spans) > 0:
                    period_and_span_metrics[did_change_span_key] = float(
                        span_reduction_func(span_results.did_change_spans)
                    )
                else:
                    period_and_span_metrics[did_change_span_key] = float("nan")

                # Did not change spans
                did_not_change_span_key = (
                    f"{file_subset}_did_not_change_{span_reduction_func.__name__}_span"
                )
                if len(span_results.did_not_change_spans) > 0:
                    period_and_span_metrics[did_not_change_span_key] = float(
                        span_reduction_func(span_results.did_not_change_spans)
                    )
                else:
                    period_and_span_metrics[did_not_change_span_key] = float("nan")

    return period_and_span_metrics


def compute_timeseries_metrics(
    commits_df: pl.DataFrame,
    period_span: str | float | timedelta,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> TimeseriesMetrics:
    # Parse period span and datetimes
    td = parse_timedelta(period_span)

    # Parse datetimes and filter commits to range
    # commits_df, start_datetime_dt, end_datetime_dt = filter_changes_to_dt_range(
    #     changes_df=commits_df,
    #     start_datetime=start_datetime,
    #     end_datetime=end_datetime,
    #     datetime_col=datetime_col,
    # )

    start_datetime_dt = cast(datetime, commits_df[datetime_col].min())
    end_datetime_dt = cast(datetime, commits_df[datetime_col].max())

    # Get periods changed
    periods_changed_results = get_periods_changed(
        commits_df=commits_df,
        period_span=td,
        start_datetime=start_datetime_dt,
        end_datetime=end_datetime_dt,
        datetime_col=datetime_col,
    )

    # Compute metrics from periods changed results
    # 1. Entropy, gini, and variation of binary and lines changed count
    # 2. Fraction of periods with changes (for binary only)
    # 3. Change spans (for binary only)
    #    - Median, mean, std of spans with changes
    #    - Median, mean, std of spans without changes
    period_and_span_metrics = _compute_metrics_from_periods_change_results(
        periods_changed_results,
    )

    return TimeseriesMetrics(**period_and_span_metrics)
