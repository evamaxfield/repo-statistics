#!/usr/bin/env python

from datetime import date, datetime, timedelta
from functools import lru_cache
from numbers import Number
from pathlib import Path
from typing import Literal

import polars as pl

from . import constants
from .data import FILE_FORMATS_TO_DTYPE_DF

###############################################################################


@lru_cache(2**14)
def get_linguist_file_type(fp: str | Path) -> str:
    """Determine the file type based on its extension using the Linguist data."""
    # Extract the filename from the path
    filename = Path(fp).name.lower()

    # Check if there is an exact filename match in the data
    filename_match = FILE_FORMATS_TO_DTYPE_DF.filter(pl.col("filename") == filename)
    if not filename_match.is_empty():
        matched_types = filename_match["type"].unique()
        if len(matched_types) == 1:
            return matched_types[0]

    # Check for extension match in the data
    extension = Path(fp).suffix.lower()
    matched = FILE_FORMATS_TO_DTYPE_DF.filter(pl.col("extension") == extension)
    if matched.is_empty():
        return constants.FileTypes.unknown.value

    matched_types = matched["type"].unique()

    # Handle single type match
    if len(matched_types) == 1:
        return matched_types[0]

    # Check if multiple types matched;
    # default to priority order: "prose", "data", "markup", "programming", "unknown"
    if len(matched_types) > 1:
        for dtype in constants.FileTypes:
            if dtype.value in matched_types:
                return dtype.value

    return constants.FileTypes.unknown.value


###############################################################################

TIMEDELTA_SIZES_SECONDS = {
    "s": 1,
    "ms": 1e-3,
    "us": 1e-6,
    "ns": 1e-9,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    "w": 7 * 60 * 60 * 24,
    "y": 365 * 60 * 60 * 24,
}

TIMEDELTA_SIZES_SECONDS_2 = {
    "second": 1,
    "millisecond": 1e-3,
    "microsecond": 1e-6,
    "nanosecond": 1e-9,
    "minute": 60,
    "hour": 60 * 60,
    "day": 60 * 60 * 24,
    "week": 7 * 60 * 60 * 24,
    "year": 365 * 60 * 60 * 24,
}
TIMEDELTA_SIZES_SECONDS_2.update(
    {k + "s": v for k, v in TIMEDELTA_SIZES_SECONDS_2.items()}
)
TIMEDELTA_SIZES_SECONDS.update(TIMEDELTA_SIZES_SECONDS_2)
TIMEDELTA_SIZES_SECONDS.update(
    {k.upper(): v for k, v in TIMEDELTA_SIZES_SECONDS.items()}
)

# Create the inversions of these as well
TIMEDELTA_SIZES_SECONDS_INV = {v: k for k, v in TIMEDELTA_SIZES_SECONDS_2.items()}

###############################################################################


def parse_timedelta(  # noqa: C901
    s: str | float | timedelta,
    default: str | Literal[False] = "seconds",
) -> timedelta:
    """Parse timedelta string to number of seconds.

    Parameters
    ----------
    s : str, float, timedelta
        String to parse, or a float representing seconds, or a timedelta object.
    default: str or False, optional
        Unit of measure if s  does not specify one. Defaults to seconds.
        Set to False to require s to explicitly specify its own unit.

    Examples
    --------
    >>> from datetime import timedelta
    >>> from dask.utils import parse_timedelta
    >>> parse_timedelta('3s')
    3
    >>> parse_timedelta('3.5 seconds')
    3.5
    >>> parse_timedelta('300ms')
    0.3
    >>> parse_timedelta(timedelta(seconds=3))  # also supports timedeltas
    3

    Notes
    -----
    This function was copied from dask.utils.parse_timedelta.
    It was modified to add support for years and linted, formatted, and typed.
    """
    if isinstance(s, timedelta):
        return s
    if isinstance(s, Number):
        s_str = str(s)
    if isinstance(s, str):
        s_str = s

    # Should be a string now, parse
    s_str = s_str.replace(" ", "")
    if not s_str[0].isdigit():
        s_str = "1" + s_str

    for i in range(len(s_str) - 1, -1, -1):
        if not s_str[i].isalpha():
            break
    index = i + 1

    prefix = s_str[:index]
    suffix = s_str[index:] or default
    if suffix is False:
        raise ValueError(f"Missing time unit: {s_str}")
    if not isinstance(suffix, str):
        raise TypeError(f"default must be str or False, got {default!r}")

    n = float(prefix)

    try:
        multiplier = TIMEDELTA_SIZES_SECONDS[suffix.lower()]
    except KeyError:
        valid_units = ", ".join(TIMEDELTA_SIZES_SECONDS.keys())
        raise KeyError(
            f"Invalid time unit: {suffix}. Valid units are: {valid_units}"
        ) from None

    result = n * multiplier
    if int(result) == result:
        result = int(result)
    return timedelta(seconds=result)


def timedelta_to_string(
    td: timedelta,
) -> str:
    """Convert a timedelta object to a human-readable string.

    Parameters
    ----------
    td : timedelta
        The timedelta object to convert.

    Returns
    -------
    str
        A human-readable string representation of the timedelta.

    Examples
    --------
    >>> from datetime import timedelta
    >>> td = timedelta(days=2)
    >>> timedelta_to_string(td)
    '2 days'
    >>> td = timedelta(hours=5)
    >>> timedelta_to_string(td)
    '5 hours'
    >>> td = timedelta(minutes=30)
    >>> timedelta_to_string(td)
    '30 minutes'
    >>> td = timedelta(days=21)
    >>> timedelta_to_string(td)
    '3 weeks'

    Notes
    -----
    This function breaks down the timedelta into its components (weeks, days,
    hours, minutes, seconds) and constructs a readable string.
    """
    # Use total seconds and find the largest fitting unit
    # That is cleanly divisble by the total seconds
    total_seconds = int(td.total_seconds())
    if total_seconds == 0:
        return "0 seconds"

    # Get sorted units by size in seconds
    sorted_units = sorted(TIMEDELTA_SIZES_SECONDS_INV.keys(), reverse=True)

    # Find the largest fitting unit
    for unit_size in sorted_units:
        if total_seconds >= unit_size and total_seconds % unit_size == 0:
            unit_name = TIMEDELTA_SIZES_SECONDS_INV[unit_size]
            count = total_seconds // unit_size
            if count == 1:
                unit_name = unit_name.rstrip("s")  # Singular form
            return f"{count} {unit_name}"

    # Fallback to seconds if no larger unit fits
    return f"{total_seconds} seconds"


def parse_datetime(s: str | date | datetime) -> datetime:
    """Parse a datetime string to a datetime object.

    Parameters
    ----------
    s : str or datetime
        String to parse, or a datetime object.

    Returns
    -------
    datetime
        Parsed datetime object.

    Examples
    --------
    >>> parse_datetime("2023-10-05T14:48:00")
    datetime.datetime(2023, 10, 5, 14, 48)
    >>> parse_datetime(datetime(2023, 10, 5, 14, 48))
    datetime.datetime(2023, 10, 5, 14, 48)

    Notes
    -----
    This function uses the built-in datetime.fromisoformat method for parsing.
    """
    if isinstance(s, datetime):
        return s
    if isinstance(s, date):
        return datetime(s.year, s.month, s.day)
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s)
        except ValueError as e:
            raise ValueError(f"Invalid datetime string: {s}") from e
    raise TypeError(f"Input must be a str or datetime, got {type(s)}")


def parse_date(s: str | datetime | date) -> date:
    """Parse a date string to a date object.

    Parameters
    ----------
    s : str, datetime, or date
        String to parse, or a datetime or date object.

    Returns
    -------
    date
        Parsed date object.

    Examples
    --------
    >>> parse_date("2023-10-05")
    datetime.date(2023, 10, 5)
    >>> parse_date(datetime(2023, 10, 5, 14, 48))
    datetime.date(2023, 10, 5)
    >>> parse_date(date(2023, 10, 5))
    datetime.date(2023, 10, 5)

    Notes
    -----
    This function uses the built-in datetime.fromisoformat method for parsing.
    """
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s).date()
        except ValueError as e:
            raise ValueError(f"Invalid date string: {s}") from e
    raise TypeError(f"Input must be a str, datetime, or date, got {type(s)}")


def filter_changes_to_dt_range(
    changes_df: pl.DataFrame,
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> tuple[pl.DataFrame, datetime, datetime]:
    """Filter changes DataFrame to a specified datetime range.

    Parameters
    ----------
    changes_df : pl.DataFrame
        DataFrame containing commit data or per-file-commit-deltas with
        'authored_datetime' and 'committed_datetime' columns.
    start_datetime : str, date, datetime, or None, optional
        Start of the datetime range.
        If None, uses the minimum datetime in the DataFrame.
    end_datetime : str, date, datetime, or None, optional
        End of the datetime range. If None, uses the maximum datetime in the DataFrame.
    datetime_col : str, optional
        Column to use for filtering ('authored_datetime' or 'committed_datetime').

    Returns
    -------
    pl.DataFrame
        Filtered DataFrame containing only changes within the specified datetime range.
    datetime
        The start datetime used for filtering.
    datetime
        The end datetime used for filtering.
    """
    if start_datetime is None:
        start_datetime_dt = changes_df[datetime_col].min()
    else:
        start_datetime_dt = parse_datetime(start_datetime)
    if end_datetime is None:
        end_datetime_dt = changes_df[datetime_col].max()
    else:
        end_datetime_dt = parse_datetime(end_datetime)

    # Filter changes to the specified time range
    filtered_changes_df = changes_df.filter(
        (changes_df[datetime_col] >= start_datetime_dt)
        & (changes_df[datetime_col] <= end_datetime_dt)
    )

    return filtered_changes_df, start_datetime_dt, end_datetime_dt
