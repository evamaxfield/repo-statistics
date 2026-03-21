#!/usr/bin/env python

import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .utils import get_commit_hash_for_target_datetime, get_linguist_file_type

###############################################################################

log = logging.getLogger(__name__)

###############################################################################


@dataclass
class ComplexityResults(DataClassJsonMixin):
    complexity_mean: float | None
    complexity_median: float | None
    complexity_max: float | None
    complexity_sum: float | None
    complexity_file_count: int


def compute_complexity_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> ComplexityResults:
    # Check if complexity CLI is available
    if shutil.which("complexity") is None:
        log.warning(
            "complexity CLI not found. Install via: "
            "brew tap thoughtbot/formulae && brew install complexity. "
            "Returning empty results."
        )
        return ComplexityResults(
            complexity_mean=None,
            complexity_median=None,
            complexity_max=None,
            complexity_sum=None,
            complexity_file_count=0,
        )

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

    # Save the original HEAD ref to restore later
    try:
        original_ref = repo.active_branch.name
    except TypeError:
        original_ref = repo.head.commit.hexsha

    try:
        repo.git.checkout(target_hex)
        repo_dir = repo.working_dir

        # Run complexity CLI
        result = subprocess.run(
            ["complexity", repo_dir],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            log.warning(
                f"complexity CLI failed with return code {result.returncode}. "
                f"stderr: {result.stderr.strip()}"
            )
            return ComplexityResults(
                complexity_mean=None,
                complexity_median=None,
                complexity_max=None,
                complexity_sum=None,
                complexity_file_count=0,
            )

        # Parse output: each line is "score filepath"
        scores: list[float] = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(None, 1)
            if len(parts) != 2:
                continue

            try:
                score = float(parts[0])
            except ValueError:
                continue

            filepath = parts[1]
            # Only include programming files
            if get_linguist_file_type(filepath) == "programming":
                scores.append(score)

        if len(scores) == 0:
            return ComplexityResults(
                complexity_mean=None,
                complexity_median=None,
                complexity_max=None,
                complexity_sum=None,
                complexity_file_count=0,
            )

        arr = np.array(scores)
        return ComplexityResults(
            complexity_mean=float(np.mean(arr)),
            complexity_median=float(np.median(arr)),
            complexity_max=float(np.max(arr)),
            complexity_sum=float(np.sum(arr)),
            complexity_file_count=len(scores),
        )

    finally:
        repo.git.checkout(original_ref)
