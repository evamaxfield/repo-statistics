#!/usr/bin/env python

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import polars as pl
from dataclasses_json import DataClassJsonMixin

from .constants import FileTypes
from .utils import parse_timedelta

###############################################################################


@dataclass
class CodeChurnResults(DataClassJsonMixin):
    total_churn_lines: int
    total_churn_normalized: float | None
    programming_churn_lines: int
    programming_churn_normalized: float | None
    markup_churn_lines: int
    markup_churn_normalized: float | None
    prose_churn_lines: int
    prose_churn_normalized: float | None
    data_churn_lines: int
    data_churn_normalized: float | None
    unknown_churn_lines: int
    unknown_churn_normalized: float | None


def _compute_churn_for_subset(
    df: pl.DataFrame,
    td_seconds: float,
    start_dt: datetime,
    datetime_col: str,
) -> tuple[int, float | None]:
    if len(df) == 0:
        return 0, None

    # Add period index
    df = df.with_columns(
        ((pl.col(datetime_col) - start_dt).dt.total_seconds() / td_seconds)
        .floor()
        .cast(pl.Int64)
        .alias("period_index")
    )

    # Group by (period_index, filename), aggregate lines_changed and commit count
    grouped = df.group_by(["period_index", "filename"]).agg(
        pl.col("lines_changed").sum().alias("total_lines"),
        pl.len().alias("commit_count"),
    )

    total_lines = grouped["total_lines"].sum()
    churn_lines = int(grouped.filter(pl.col("commit_count") > 1)["total_lines"].sum())
    churn_normalized = churn_lines / total_lines if total_lines > 0 else None

    return churn_lines, churn_normalized


def compute_code_churn(
    per_file_commit_deltas_df: pl.DataFrame,
    period_span: str | float | timedelta,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> CodeChurnResults:
    td = parse_timedelta(period_span)
    td_seconds = td.total_seconds()

    # Determine start/end datetimes
    if start_datetime is not None:
        if isinstance(start_datetime, str):
            start_dt = datetime.fromisoformat(start_datetime)
        elif isinstance(start_datetime, date) and not isinstance(start_datetime, datetime):
            start_dt = datetime(start_datetime.year, start_datetime.month, start_datetime.day)
        else:
            start_dt = start_datetime
    else:
        start_dt = per_file_commit_deltas_df[datetime_col].min()

    if end_datetime is not None:
        if isinstance(end_datetime, str):
            end_dt = datetime.fromisoformat(end_datetime)
        elif isinstance(end_datetime, date) and not isinstance(end_datetime, datetime):
            end_dt = datetime(end_datetime.year, end_datetime.month, end_datetime.day)
        else:
            end_dt = end_datetime
    else:
        end_dt = per_file_commit_deltas_df[datetime_col].max()

    # Filter to datetime range
    df = per_file_commit_deltas_df.filter(
        (pl.col(datetime_col) >= start_dt) & (pl.col(datetime_col) <= end_dt)
    )

    # Compute total churn
    total_churn_lines, total_churn_normalized = _compute_churn_for_subset(
        df, td_seconds, start_dt, datetime_col
    )

    # Compute per file type
    results: dict[str, tuple[int, float | None]] = {}
    for file_type in FileTypes:
        subset = df.filter(pl.col("filetype") == file_type.value)
        results[file_type.value] = _compute_churn_for_subset(
            subset, td_seconds, start_dt, datetime_col
        )

    return CodeChurnResults(
        total_churn_lines=total_churn_lines,
        total_churn_normalized=total_churn_normalized,
        programming_churn_lines=results["programming"][0],
        programming_churn_normalized=results["programming"][1],
        markup_churn_lines=results["markup"][0],
        markup_churn_normalized=results["markup"][1],
        prose_churn_lines=results["prose"][0],
        prose_churn_normalized=results["prose"][1],
        data_churn_lines=results["data"][0],
        data_churn_normalized=results["data"][1],
        unknown_churn_lines=results["unknown"][0],
        unknown_churn_normalized=results["unknown"][1],
    )
