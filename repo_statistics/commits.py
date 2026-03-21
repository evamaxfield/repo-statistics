#!/usr/bin/env python

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo
from tqdm import tqdm

from .constants import FileTypes
from .utils import get_linguist_file_type

###############################################################################


@dataclass(slots=True)
class PerFileCommitDelta(DataClassJsonMixin):
    authored_datetime: datetime
    committed_datetime: datetime
    commit_hash: str
    commit_message: str
    committer_name: str | None
    committer_email: str | None
    author_name: str | None
    author_email: str | None
    filename: str
    filetype: str
    additions: int
    deletions: int
    lines_changed: int


@dataclass(slots=True)
class CommitSummary(DataClassJsonMixin):
    authored_datetime: datetime
    committed_datetime: datetime
    commit_hash: str
    commit_message: str
    committer_name: str | None
    committer_email: str | None
    author_name: str | None
    author_email: str | None
    total_files_changed: int
    total_additions: int
    total_deletions: int
    total_lines_changed: int
    programming_files_changed: int
    programming_additions: int
    programming_deletions: int
    programming_lines_changed: int
    markup_files_changed: int
    markup_additions: int
    markup_deletions: int
    markup_lines_changed: int
    prose_files_changed: int
    prose_additions: int
    prose_deletions: int
    prose_lines_changed: int
    data_files_changed: int
    data_additions: int
    data_deletions: int
    data_lines_changed: int
    unknown_files_changed: int
    unknown_additions: int
    unknown_deletions: int
    unknown_lines_changed: int


@dataclass
class ParsedCommitsResult:
    per_file_commit_deltas: pl.DataFrame
    commit_summaries: pl.DataFrame


def _make_counters() -> dict[str, int]:
    """Return a zeroed dict of all per-commit accumulator counters."""
    return {
        f"{prefix}_{suffix}": 0
        for prefix in ("total", *[ft.value for ft in FileTypes])
        for suffix in ("files_changed", "additions", "deletions", "lines_changed")
    }


def _accumulate_file_stat(
    counters: dict[str, int],
    filetype: str,
    additions: int,
    deletions: int,
    lines_changed: int,
) -> None:
    """Update per-commit counters for one file stat line (mutates counters)."""
    counters["total_files_changed"] += 1
    counters["total_additions"] += additions
    counters["total_deletions"] += deletions
    counters["total_lines_changed"] += lines_changed
    prefix = filetype if filetype in FileTypes else FileTypes.unknown.value
    counters[f"{prefix}_files_changed"] += 1
    counters[f"{prefix}_additions"] += additions
    counters[f"{prefix}_deletions"] += deletions
    counters[f"{prefix}_lines_changed"] += lines_changed


def parse_commits(repo_path: str | Path | Repo) -> ParsedCommitsResult:
    """
    Parse the commits in a Git repository to extract per-file commit deltas
    and per-commit summaries.

    Args:
        repo_path: A string or Path to a repository,
            or a GitPython Repo object representing the repository.

    Returns:
        A ParsedCommitsResult object containing two Polars DataFrames:
            - per_file_commit_deltas: Detailed changes per file per commit.
            - commit_summaries: Summary of changes per commit.
    """
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    # Single subprocess: emit all commits with per-file numstat in one call.
    # Each commit starts with a COMMIT| header line, followed by tab-separated
    # file stat lines, separated by blank lines.
    result = subprocess.run(
        [
            "git",
            "log",
            "--format=COMMIT|%H|%an|%ae|%cn|%ce|%ai|%ci|%s",
            "--numstat",
            "--no-renames",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        cwd=repo.working_dir,
        check=True,
    )
    output = result.stdout

    # Init storage
    per_file_commit_deltas: list[PerFileCommitDelta] = []
    per_commit_summaries: list[CommitSummary] = []

    # Per-commit state (set on each COMMIT| line)
    current_authored_datetime: datetime | None = None
    current_committed_datetime: datetime | None = None
    current_commit_hash: str | None = None
    current_commit_message: str | None = None
    current_committer_name: str | None = None
    current_committer_email: str | None = None
    current_author_name: str | None = None
    current_author_email: str | None = None

    # Per-commit counters (reset on each COMMIT| line)
    counters = _make_counters()

    def _flush_commit() -> None:
        per_commit_summaries.append(
            CommitSummary(
                authored_datetime=current_authored_datetime,  # type: ignore[arg-type]
                committed_datetime=current_committed_datetime,  # type: ignore[arg-type]
                commit_hash=current_commit_hash,  # type: ignore[arg-type]
                commit_message=current_commit_message,  # type: ignore[arg-type]
                committer_name=current_committer_name,
                committer_email=current_committer_email,
                author_name=current_author_name,
                author_email=current_author_email,
                **counters,
            )
        )

    in_commit = False
    for line in tqdm(output.splitlines(), desc="Parsing commits", leave=False):
        if line.startswith("COMMIT|"):
            if in_commit:
                _flush_commit()
            # maxsplit=8 so commit messages containing "|" are preserved intact
            parts = line.split("|", 8)
            current_commit_hash = parts[1]
            current_author_name = parts[2] or None
            current_author_email = parts[3] or None
            current_committer_name = parts[4] or None
            current_committer_email = parts[5] or None
            current_authored_datetime = datetime.fromisoformat(parts[6]).replace(tzinfo=None)
            current_committed_datetime = datetime.fromisoformat(parts[7]).replace(tzinfo=None)
            current_commit_message = parts[8] if len(parts) > 8 else ""
            # Reset counters
            counters = _make_counters()
            in_commit = True
        elif "\t" in line and in_commit:
            additions_str, deletions_str, filename = line.split("\t", 2)
            # Binary files use "-" for both counts; treat as 0
            additions = 0 if additions_str == "-" else int(additions_str)
            deletions = 0 if deletions_str == "-" else int(deletions_str)
            lines_changed = additions + deletions
            filetype = get_linguist_file_type(Path(filename).name)

            _accumulate_file_stat(counters, filetype, additions, deletions, lines_changed)

            per_file_commit_deltas.append(
                PerFileCommitDelta(
                    authored_datetime=current_authored_datetime,  # type: ignore[arg-type]
                    committed_datetime=current_committed_datetime,  # type: ignore[arg-type]
                    commit_hash=current_commit_hash,  # type: ignore[arg-type]
                    commit_message=current_commit_message,  # type: ignore[arg-type]
                    committer_name=current_committer_name,
                    committer_email=current_committer_email,
                    author_name=current_author_name,
                    author_email=current_author_email,
                    filename=filename,
                    filetype=filetype,
                    additions=additions,
                    deletions=deletions,
                    lines_changed=lines_changed,
                )
            )
        # blank lines are skipped implicitly

    # Flush the final commit
    if in_commit:
        _flush_commit()

    return ParsedCommitsResult(
        per_file_commit_deltas=pl.DataFrame(per_file_commit_deltas),
        commit_summaries=pl.DataFrame(per_commit_summaries),
    )


def normalize_changes_df_and_remove_bot_changes(
    changes_df: pl.DataFrame,
    contributor_name_col: Literal["author_name", "committer_name"] = "author_name",
    contributor_email_col: Literal["author_email", "committer_email"] = "author_email",
    contributor_name_cols: tuple[str, ...] = ("committer_name", "author_name"),
    contributor_email_cols: tuple[str, ...] = ("committer_email", "author_email"),
    bot_name_indicators: tuple[str, ...] | None = ("[bot]",),
    bot_email_indicators: tuple[str, ...] | None = ("[bot]",),
) -> tuple[pl.DataFrame, int]:
    # Lower case and strip all author and committer names and emails
    for c_name_col in contributor_name_cols:
        changes_df = changes_df.with_columns(
            pl.col(c_name_col).str.to_lowercase().str.strip_chars().alias(c_name_col)
        )
    for c_email_col in contributor_email_cols:
        changes_df = changes_df.with_columns(
            pl.col(c_email_col).str.to_lowercase().str.strip_chars().alias(c_email_col)
        )

    # Remove bot changes
    before_drop_count = len(changes_df)
    if bot_name_indicators is not None:
        for bot_name_indicator in bot_name_indicators:
            changes_df = changes_df.filter(
                pl.col(contributor_name_col)
                .str.contains(bot_name_indicator, literal=True)
                .not_()
            )
    if bot_email_indicators is not None:
        for bot_email_indicator in bot_email_indicators:
            changes_df = changes_df.filter(
                pl.col(contributor_email_col)
                .str.contains(bot_email_indicator, literal=True)
                .not_()
            )

    after_drop_count = len(changes_df)
    dropped_count = before_drop_count - after_drop_count

    return changes_df, dropped_count


@dataclass
class ImportantChangeDatesResults(DataClassJsonMixin):
    total_initial_change_datetime: str | None
    total_most_recent_change_datetime: str | None
    total_most_recent_substantial_change_datetime: str | None
    total_change_duration_days: int | None
    total_change_duration_to_most_recent_substantial_days: int | None
    total_change_duration_from_substantial_to_most_recent_days: int | None
    programming_initial_change_datetime: str | None
    programming_most_recent_change_datetime: str | None
    programming_most_recent_substantial_change_datetime: str | None
    programming_change_duration_to_most_recent_substantial_days: int | None
    programming_change_duration_from_substantial_to_most_recent_days: int | None
    programming_change_duration_days: int | None
    markup_initial_change_datetime: str | None
    markup_most_recent_change_datetime: str | None
    markup_most_recent_substantial_change_datetime: str | None
    markup_change_duration_days: int | None
    markup_change_duration_to_most_recent_substantial_days: int | None
    markup_change_duration_from_substantial_to_most_recent_days: int | None
    prose_initial_change_datetime: str | None
    prose_most_recent_change_datetime: str | None
    prose_most_recent_substantial_change_datetime: str | None
    prose_change_duration_days: int | None
    prose_change_duration_to_most_recent_substantial_days: int | None
    prose_change_duration_from_substantial_to_most_recent_days: int | None
    data_initial_change_datetime: str | None
    data_most_recent_change_datetime: str | None
    data_most_recent_substantial_change_datetime: str | None
    data_change_duration_days: int | None
    data_change_duration_to_most_recent_substantial_days: int | None
    data_change_duration_from_substantial_to_most_recent_days: int | None
    unknown_initial_change_datetime: str | None
    unknown_most_recent_change_datetime: str | None
    unknown_most_recent_substantial_change_datetime: str | None
    unknown_change_duration_days: int | None
    unknown_change_duration_to_most_recent_substantial_days: int | None
    unknown_change_duration_from_substantial_to_most_recent_days: int | None


@dataclass
class _FileSubsetChangeDates:
    """Intermediate storage for file subset change date metrics."""

    initial_change_datetime: str | None
    most_recent_change_datetime: str | None
    most_recent_substantial_change_datetime: str | None
    change_duration_days: int | None
    change_duration_to_most_recent_substantial_days: int | None
    change_duration_from_substantial_to_most_recent_days: int | None


def _compute_file_subset_change_dates(
    subset_df: pl.DataFrame,
    datetime_col: str,
    lines_changed_col: str,
    substantial_change_threshold_quantile: float,
) -> _FileSubsetChangeDates:
    """Compute change date metrics for a single file subset."""
    if len(subset_df) == 0:
        return _FileSubsetChangeDates(
            initial_change_datetime=None,
            most_recent_change_datetime=None,
            most_recent_substantial_change_datetime=None,
            change_duration_days=None,
            change_duration_to_most_recent_substantial_days=None,
            change_duration_from_substantial_to_most_recent_days=None,
        )

    # Find initial and most recent change datetimes
    # Polars min/max on datetime columns returns datetime
    initial_change_dt = cast(datetime, subset_df[datetime_col].min())
    most_recent_change_dt = cast(datetime, subset_df[datetime_col].max())

    # Find threshold of lines changed
    lines_change_target = subset_df[lines_changed_col].quantile(
        substantial_change_threshold_quantile,
        interpolation="nearest",
    )

    # Filter subset to changes with at least that many lines changed
    substantial_changes_df = subset_df.filter(pl.col(lines_changed_col) >= lines_change_target)
    # Sort substantial changes by datetime descending and get most recent
    # Fall back to most_recent_change_dt if no substantial changes found
    if len(substantial_changes_df) == 0:
        most_recent_substantial_dt = most_recent_change_dt
    else:
        most_recent_substantial_dt = cast(
            datetime,
            substantial_changes_df.sort(by=datetime_col, descending=True)[datetime_col][0],
        )

    return _FileSubsetChangeDates(
        initial_change_datetime=initial_change_dt.isoformat(),
        most_recent_change_datetime=most_recent_change_dt.isoformat(),
        most_recent_substantial_change_datetime=most_recent_substantial_dt.isoformat(),
        change_duration_days=(most_recent_change_dt - initial_change_dt).days,
        change_duration_to_most_recent_substantial_days=(
            most_recent_substantial_dt - initial_change_dt
        ).days,
        change_duration_from_substantial_to_most_recent_days=(
            most_recent_change_dt - most_recent_substantial_dt
        ).days,
    )


def compute_important_change_dates(
    commits_df: pl.DataFrame,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
    substantial_change_threshold_quantile: float = 0.1,
) -> ImportantChangeDatesResults:
    """Compute important change date metrics for each file type subset."""
    results: dict[str, _FileSubsetChangeDates] = {}

    for file_subset in ["total", *[ft.value for ft in FileTypes]]:
        # Get subset of changes that are relevant to this file type
        lines_changed_col = f"{file_subset}_lines_changed"
        subset_df = commits_df.filter(pl.col(lines_changed_col) > 0)

        results[file_subset] = _compute_file_subset_change_dates(
            subset_df=subset_df,
            datetime_col=datetime_col,
            lines_changed_col=lines_changed_col,
            substantial_change_threshold_quantile=substantial_change_threshold_quantile,
        )

    return ImportantChangeDatesResults(
        total_initial_change_datetime=results["total"].initial_change_datetime,
        total_most_recent_change_datetime=results["total"].most_recent_change_datetime,
        total_most_recent_substantial_change_datetime=results[
            "total"
        ].most_recent_substantial_change_datetime,
        total_change_duration_days=results["total"].change_duration_days,
        total_change_duration_to_most_recent_substantial_days=results[
            "total"
        ].change_duration_to_most_recent_substantial_days,
        total_change_duration_from_substantial_to_most_recent_days=results[
            "total"
        ].change_duration_from_substantial_to_most_recent_days,
        programming_initial_change_datetime=results["programming"].initial_change_datetime,
        programming_most_recent_change_datetime=results[
            "programming"
        ].most_recent_change_datetime,
        programming_most_recent_substantial_change_datetime=results[
            "programming"
        ].most_recent_substantial_change_datetime,
        programming_change_duration_days=results["programming"].change_duration_days,
        programming_change_duration_to_most_recent_substantial_days=results[
            "programming"
        ].change_duration_to_most_recent_substantial_days,
        programming_change_duration_from_substantial_to_most_recent_days=results[
            "programming"
        ].change_duration_from_substantial_to_most_recent_days,
        markup_initial_change_datetime=results["markup"].initial_change_datetime,
        markup_most_recent_change_datetime=results["markup"].most_recent_change_datetime,
        markup_most_recent_substantial_change_datetime=results[
            "markup"
        ].most_recent_substantial_change_datetime,
        markup_change_duration_days=results["markup"].change_duration_days,
        markup_change_duration_to_most_recent_substantial_days=results[
            "markup"
        ].change_duration_to_most_recent_substantial_days,
        markup_change_duration_from_substantial_to_most_recent_days=results[
            "markup"
        ].change_duration_from_substantial_to_most_recent_days,
        prose_initial_change_datetime=results["prose"].initial_change_datetime,
        prose_most_recent_change_datetime=results["prose"].most_recent_change_datetime,
        prose_most_recent_substantial_change_datetime=results[
            "prose"
        ].most_recent_substantial_change_datetime,
        prose_change_duration_days=results["prose"].change_duration_days,
        prose_change_duration_to_most_recent_substantial_days=results[
            "prose"
        ].change_duration_to_most_recent_substantial_days,
        prose_change_duration_from_substantial_to_most_recent_days=results[
            "prose"
        ].change_duration_from_substantial_to_most_recent_days,
        data_initial_change_datetime=results["data"].initial_change_datetime,
        data_most_recent_change_datetime=results["data"].most_recent_change_datetime,
        data_most_recent_substantial_change_datetime=results[
            "data"
        ].most_recent_substantial_change_datetime,
        data_change_duration_days=results["data"].change_duration_days,
        data_change_duration_to_most_recent_substantial_days=results[
            "data"
        ].change_duration_to_most_recent_substantial_days,
        data_change_duration_from_substantial_to_most_recent_days=results[
            "data"
        ].change_duration_from_substantial_to_most_recent_days,
        unknown_initial_change_datetime=results["unknown"].initial_change_datetime,
        unknown_most_recent_change_datetime=results["unknown"].most_recent_change_datetime,
        unknown_most_recent_substantial_change_datetime=results[
            "unknown"
        ].most_recent_substantial_change_datetime,
        unknown_change_duration_days=results["unknown"].change_duration_days,
        unknown_change_duration_to_most_recent_substantial_days=results[
            "unknown"
        ].change_duration_to_most_recent_substantial_days,
        unknown_change_duration_from_substantial_to_most_recent_days=results[
            "unknown"
        ].change_duration_from_substantial_to_most_recent_days,
    )


@dataclass
class CommitCountsResults(DataClassJsonMixin):
    total_commit_count: int
    programming_commit_count: int
    markup_commit_count: int
    prose_commit_count: int
    data_commit_count: int
    unknown_commit_count: int


def compute_commit_counts(
    commits_df: pl.DataFrame,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> CommitCountsResults:

    results = {}
    for file_subset in ["total", *[ft.value for ft in FileTypes]]:
        results[f"{file_subset}_commit_count"] = len(
            commits_df.filter(pl.col(f"{file_subset}_lines_changed") > 0)
        )

    return CommitCountsResults(**results)
