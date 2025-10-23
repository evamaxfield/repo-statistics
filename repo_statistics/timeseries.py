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
from .gini import _compute_gini
from .utils import filter_changes_to_dt_range, parse_timedelta

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

    # Parse datetimes and filter commits to range
    commits_df, start_datetime_dt, end_datetime_dt = filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

    # Calculate total periods
    change_duration = end_datetime_dt - start_datetime_dt
    n_tds = math.ceil(change_duration / td)

    # Iterate over periods and record binary or lines changed count
    current_start_dt = start_datetime_dt
    results: dict[str, list[int]] = {}
    for _ in tqdm(range(n_tds), desc="Processing change periods", leave=False):
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

    try:
        return ChangePeriodResults(**results)
    except Exception as e:
        print(e)
        print("results", results)
        print("commit_subset", commit_subset)


@dataclass
class ChangeSpanResults(DataClassJsonMixin):
    did_change_spans: list[int]
    did_not_change_spans: list[int]


def get_change_spans(
    periods_changed: list[int],
) -> ChangeSpanResults:
    # Iter over list of periods changed and count periods between changes
    did_change_spans = []
    did_not_change_spans = []
    in_change_span = False
    did_change_current_periods = 0
    did_not_change_current_periods = 0
    for period in periods_changed:
        if not in_change_span and period == 0:
            did_not_change_current_periods += 1
        if not in_change_span and period == 1:
            did_not_change_spans.append(did_not_change_current_periods)
            did_not_change_current_periods = 0
            in_change_span = True
            did_change_current_periods += 1
        if in_change_span and period == 0:
            did_change_spans.append(did_change_current_periods)
            did_change_current_periods = 0
            in_change_span = False
            did_not_change_current_periods += 1
        if in_change_span and period == 1:
            did_change_current_periods += 1

    # Remove extra zero in either of the lists
    did_change_spans = [span for span in did_change_spans if span != 0]
    did_not_change_spans = [span for span in did_not_change_spans if span != 0]

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
    # Change span metrics
    total_did_change_median_span: int
    total_did_change_mean_span: float
    total_did_change_std_span: float
    total_did_not_change_median_span: int
    total_did_not_change_mean_span: float
    total_did_not_change_std_span: float
    programming_did_change_median_span: int
    programming_did_change_mean_span: float
    programming_did_change_std_span: float
    programming_did_not_change_median_span: int
    programming_did_not_change_mean_span: float
    programming_did_not_change_std_span: float
    markup_did_change_median_span: int
    markup_did_change_mean_span: float
    markup_did_change_std_span: float
    markup_did_not_change_median_span: int
    markup_did_not_change_mean_span: float
    markup_did_not_change_std_span: float
    prose_did_change_median_span: int
    prose_did_change_mean_span: float
    prose_did_change_std_span: float
    prose_did_not_change_median_span: int
    prose_did_not_change_mean_span: float
    prose_did_not_change_std_span: float
    data_did_change_median_span: int
    data_did_change_mean_span: float
    data_did_change_std_span: float
    data_did_not_change_median_span: int
    data_did_not_change_mean_span: float
    data_did_not_change_std_span: float
    unknown_did_change_median_span: int
    unknown_did_change_mean_span: float
    unknown_did_change_std_span: float
    unknown_did_not_change_median_span: int
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
        period_and_span_metrics[f"{period_key}_variation"] = variation(arr)
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
                    f"{file_subset}_did_change_" f"{span_reduction_func.__name__}_span"
                )
                if len(span_results.did_change_spans) > 0:
                    period_and_span_metrics[did_change_span_key] = span_reduction_func(
                        span_results.did_change_spans
                    )
                else:
                    period_and_span_metrics[did_change_span_key] = float("nan")

                # Did not change spans
                did_not_change_span_key = (
                    f"{file_subset}_did_not_change_"
                    f"{span_reduction_func.__name__}_span"
                )
                if len(span_results.did_not_change_spans) > 0:
                    period_and_span_metrics[did_not_change_span_key] = (
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
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> TimeseriesMetrics:
    # Parse period span and datetimes
    td = parse_timedelta(period_span)

    # Parse datetimes and filter commits to range
    commits_df, start_datetime_dt, end_datetime_dt = filter_changes_to_dt_range(
        changes_df=commits_df,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        datetime_col=datetime_col,
    )

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

    return TimeseriesMetrics(
        **period_and_span_metrics,  # type: ignore
    )
