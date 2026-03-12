#!/usr/bin/env python

from dataclasses import dataclass
from datetime import date, datetime
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

    # Get total number of commits for progress tracking
    total_commit_count = int(repo.git.rev_list("--count", "HEAD"))

    # Init storage
    per_file_commit_deltas: list[PerFileCommitDelta] = []
    per_commit_summaries: list[CommitSummary] = []

    # Iter over commits and collect data
    for commit in tqdm(
        repo.iter_commits(),
        total=total_commit_count,
        desc="Parsing commits",
        unit="commit",
        leave=False,
    ):
        authored_datetime = datetime.fromtimestamp(commit.authored_date)
        committed_datetime = datetime.fromtimestamp(commit.committed_date)
        commit_hash = commit.hexsha
        commit_message = commit.message.strip()
        committer_name = commit.committer.name if commit.committer else None
        committer_email = commit.committer.email if commit.committer else None
        author_name = commit.author.name if commit.author else None
        author_email = commit.author.email if commit.author else None

        # Init per-commit counters
        # Total
        total_files_changed = 0
        total_additions = 0
        total_deletions = 0
        total_lines_changed = 0

        # By type
        programming_files_changed = 0
        programming_additions = 0
        programming_deletions = 0
        programming_lines_changed = 0

        markup_files_changed = 0
        markup_additions = 0
        markup_deletions = 0
        markup_lines_changed = 0

        prose_files_changed = 0
        prose_additions = 0
        prose_deletions = 0
        prose_lines_changed = 0

        data_files_changed = 0
        data_additions = 0
        data_deletions = 0
        data_lines_changed = 0

        unknown_files_changed = 0
        unknown_additions = 0
        unknown_deletions = 0
        unknown_lines_changed = 0

        # Process diffs
        for filename, file_stats in commit.stats.files.items():
            # Get the file type
            filetype = get_linguist_file_type(Path(filename).name)

            # file_stats contains "insertions", "deletions", and "lines"
            additions = file_stats["insertions"]
            deletions = file_stats["deletions"]
            lines_changed = file_stats["lines"]

            # Update counts
            total_additions += additions
            total_deletions += deletions
            total_lines_changed += lines_changed
            total_files_changed += 1

            # Update type-specific counts
            if filetype == "programming":
                programming_files_changed += 1
                programming_additions += additions
                programming_deletions += deletions
                programming_lines_changed += lines_changed
            elif filetype == "markup":
                markup_files_changed += 1
                markup_additions += additions
                markup_deletions += deletions
                markup_lines_changed += lines_changed
            elif filetype == "prose":
                prose_files_changed += 1
                prose_additions += additions
                prose_deletions += deletions
                prose_lines_changed += lines_changed
            elif filetype == "data":
                data_files_changed += 1
                data_additions += additions
                data_deletions += deletions
                data_lines_changed += lines_changed
            else:
                unknown_files_changed += 1
                unknown_additions += additions
                unknown_deletions += deletions
                unknown_lines_changed += lines_changed

            # Store per-file commit delta
            per_file_commit_deltas.append(
                PerFileCommitDelta(
                    authored_datetime=authored_datetime,
                    committed_datetime=committed_datetime,
                    commit_hash=commit_hash,
                    commit_message=commit_message,
                    committer_name=committer_name,
                    committer_email=committer_email,
                    author_name=author_name,
                    author_email=author_email,
                    filename=filename,
                    filetype=filetype,
                    additions=additions,
                    deletions=deletions,
                    lines_changed=lines_changed,
                )
            )

        # Store per-commit summary
        per_commit_summaries.append(
            CommitSummary(
                authored_datetime=authored_datetime,
                committed_datetime=committed_datetime,
                commit_hash=commit_hash,
                commit_message=commit_message,
                committer_name=committer_name,
                committer_email=committer_email,
                author_name=author_name,
                author_email=author_email,
                total_files_changed=total_files_changed,
                total_additions=total_additions,
                total_deletions=total_deletions,
                total_lines_changed=total_lines_changed,
                programming_files_changed=programming_files_changed,
                programming_additions=programming_additions,
                programming_deletions=programming_deletions,
                programming_lines_changed=programming_lines_changed,
                markup_files_changed=markup_files_changed,
                markup_additions=markup_additions,
                markup_deletions=markup_deletions,
                markup_lines_changed=markup_lines_changed,
                prose_files_changed=prose_files_changed,
                prose_additions=prose_additions,
                prose_deletions=prose_deletions,
                prose_lines_changed=prose_lines_changed,
                data_files_changed=data_files_changed,
                data_additions=data_additions,
                data_deletions=data_deletions,
                data_lines_changed=data_lines_changed,
                unknown_files_changed=unknown_files_changed,
                unknown_additions=unknown_additions,
                unknown_deletions=unknown_deletions,
                unknown_lines_changed=unknown_lines_changed,
            )
        )

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
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
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
    start_datetime: str | date | datetime | None = None,
    end_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> CommitCountsResults:
    # Parse datetimes and filter commits to range
    # commits_df, _, _ = filter_changes_to_dt_range(
    #     changes_df=commits_df,
    #     start_datetime=start_datetime,
    #     end_datetime=end_datetime,
    #     datetime_col=datetime_col,
    # )

    results = {}
    for file_subset in ["total", *[ft.value for ft in FileTypes]]:
        results[f"{file_subset}_commit_count"] = len(
            commits_df.filter(pl.col(f"{file_subset}_lines_changed") > 0)
        )

    return CommitCountsResults(**results)
