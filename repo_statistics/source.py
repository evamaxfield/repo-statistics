#!/usr/bin/env python

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .constants import FileTypes
from .utils import get_commit_hash_for_target_datetime, get_linguist_file_type

###############################################################################


@dataclass
class SLOCResults(DataClassJsonMixin):
    total_lines_of_code: int
    total_lines_of_comments: int
    programming_lines_of_code: int
    programming_lines_of_comments: int
    markup_lines_of_code: int
    markup_lines_of_comments: int
    prose_lines_of_code: int
    prose_lines_of_comments: int
    data_lines_of_code: int
    data_lines_of_comments: int
    unknown_lines_of_code: int
    unknown_lines_of_comments: int


def compute_sloc_metrics(
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> SLOCResults:
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    # Get the latest commit hexsha for the target datetime
    target_hex = get_commit_hash_for_target_datetime(
        commits_df=commits_df,
        target_datetime=target_datetime,
        datetime_col=datetime_col,
    )

    # Try to checkout the repo to that commit
    try:
        # Checkout the repo to the latest commit datetime
        repo.git.checkout(target_hex)

        # Get repo_dir from repo
        repo_dir = repo.working_dir

        # Run cloc on the repo
        pygount_output = subprocess.run(
            [
                "pygount",
                "--format=json",
                repo_dir,
            ],
            capture_output=True,
            text=True,
        )

        # Read JSON
        sloc_results = json.loads(pygount_output.stdout)

        # Iter over "files"
        total_lines_of_code = 0
        total_lines_of_comments = 0
        programming_lines_of_code = 0
        programming_lines_of_comments = 0
        markup_lines_of_code = 0
        markup_lines_of_comments = 0
        prose_lines_of_code = 0
        prose_lines_of_comments = 0
        data_lines_of_code = 0
        data_lines_of_comments = 0
        unknown_lines_of_code = 0
        unknown_lines_of_comments = 0
        for file in sloc_results["files"]:
            # Always add to total
            total_lines_of_code += file["codeCount"]
            total_lines_of_comments += file["documentationCount"]

            # Get file type
            file_type = get_linguist_file_type(file["path"])

            if file_type == FileTypes.programming.value:
                programming_lines_of_code += file["codeCount"]
                programming_lines_of_comments += file["documentationCount"]
            elif file_type == FileTypes.markup.value:
                markup_lines_of_code += file["codeCount"]
                markup_lines_of_comments += file["documentationCount"]
            elif file_type == FileTypes.prose.value:
                prose_lines_of_code += file["codeCount"]
                prose_lines_of_comments += file["documentationCount"]
            elif file_type == FileTypes.data.value:
                data_lines_of_code += file["codeCount"]
                data_lines_of_comments += file["documentationCount"]
            else:
                unknown_lines_of_code += file["codeCount"]
                unknown_lines_of_comments += file["documentationCount"]

        return SLOCResults(
            total_lines_of_code=total_lines_of_code,
            total_lines_of_comments=total_lines_of_comments,
            programming_lines_of_code=programming_lines_of_code,
            programming_lines_of_comments=programming_lines_of_comments,
            markup_lines_of_code=markup_lines_of_code,
            markup_lines_of_comments=markup_lines_of_comments,
            prose_lines_of_code=prose_lines_of_code,
            prose_lines_of_comments=prose_lines_of_comments,
            data_lines_of_code=data_lines_of_code,
            data_lines_of_comments=data_lines_of_comments,
            unknown_lines_of_code=unknown_lines_of_code,
            unknown_lines_of_comments=unknown_lines_of_comments,
        )

    finally:
        # Checkout back to HEAD
        repo.git.checkout("HEAD")


@dataclass
class RepoTagMetrics(DataClassJsonMixin):
    semver_tags_count: int
    non_semver_tags_count: int
    total_tags_count: int


def compute_tag_metrics(
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> RepoTagMetrics:
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    # Get the latest commit hexsha for the target datetime
    target_hex = get_commit_hash_for_target_datetime(
        commits_df=commits_df,
        target_datetime=target_datetime,
        datetime_col=datetime_col,
    )

    # Try to checkout the repo to that commit
    try:
        # Checkout the repo to the latest commit datetime
        repo.git.checkout(target_hex)

        # Get all tags
        tags = repo.tags

        # Construct semver regex
        # Direct from https://semver.org/
        # Only addition was "(v)?" to allow for "v" prefix
        semver_regex = re.compile(
            r"^(v)?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        )

        # Count tags
        semver_tags_count = 0
        non_semver_tags_count = 0
        for tag in tags:
            if semver_regex.match(tag.name):
                semver_tags_count += 1
            else:
                non_semver_tags_count += 1

        return RepoTagMetrics(
            semver_tags_count=semver_tags_count,
            non_semver_tags_count=non_semver_tags_count,
            total_tags_count=len(tags),
        )

    finally:
        # Checkout back to HEAD
        repo.git.checkout("HEAD")
