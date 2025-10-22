#!/usr/bin/env python

import json
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


def compute_sloc(
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
    latest_commit_hexsha = get_commit_hash_for_target_datetime(
        commits_df=commits_df,
        target_datetime=target_datetime,
        datetime_col=datetime_col,
    )

    # Try to checkout the repo to that commit
    try:
        # Checkout the repo to the latest commit datetime
        repo.git.checkout(latest_commit_hexsha)

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
