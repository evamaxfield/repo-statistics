#!/usr/bin/env python

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .utils import get_linguist_file_type

###############################################################################


@dataclass
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


@dataclass
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

    # Init storage
    per_file_commit_deltas: list[PerFileCommitDelta] = []
    per_commit_summaries: list[CommitSummary] = []

    # Iter over commits and collect data
    for commit in repo.iter_commits():
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
        per_file_commit_deltas=pl.DataFrame(
            [cd.to_dict() for cd in per_file_commit_deltas]
        ),
        commit_summaries=pl.DataFrame([cs.to_dict() for cs in per_commit_summaries]),
    )
