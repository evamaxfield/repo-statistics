#!/usr/bin/env python

import json
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

from .constants import FileTypes
from .utils import get_commit_hash_for_target_datetime, get_linguist_file_type

###############################################################################

log = logging.getLogger(__name__)

###############################################################################

# Metrics we extract from multimetric output per file
_HALSTEAD_KEYS = [
    "halstead_volume",
    "halstead_difficulty",
    "halstead_effort",
    "halstead_timerequired",
    "halstead_bugprop",
]
_OPERATOR_OPERAND_KEYS = [
    "operators_sum",
    "operators_uniq",
    "operands_sum",
    "operands_uniq",
]
_OTHER_KEYS = [
    "pylint",
    "maintainability_index",
]

_ALL_METRIC_KEYS = _HALSTEAD_KEYS + _OPERATOR_OPERAND_KEYS + _OTHER_KEYS

_AGGREGATIONS = ["mean", "median", "std", "sum"]


def _empty_results() -> "StaticAnalysisResults":
    kwargs: dict = {}
    for key in _ALL_METRIC_KEYS:
        for agg in _AGGREGATIONS:
            kwargs[f"{key}_{agg}"] = None
    kwargs["static_analysis_file_count"] = 0
    return StaticAnalysisResults(**kwargs)


def _aggregate_metrics(
    file_metrics: list[dict],
) -> dict:
    if len(file_metrics) == 0:
        result: dict = {}
        for key in _ALL_METRIC_KEYS:
            for agg in _AGGREGATIONS:
                result[f"{key}_{agg}"] = None
        result["static_analysis_file_count"] = 0
        return result

    def _safe_vals(key: str) -> list:
        return [f[key] for f in file_metrics if key in f and f[key] is not None]

    result: dict = {}
    for key in _ALL_METRIC_KEYS:
        vals = _safe_vals(key)
        result[f"{key}_mean"] = float(np.mean(vals)) if vals else None
        result[f"{key}_median"] = float(np.median(vals)) if vals else None
        result[f"{key}_std"] = float(np.std(vals)) if vals else None
        result[f"{key}_sum"] = float(np.sum(vals)) if vals else None
    result["static_analysis_file_count"] = len(file_metrics)
    return result


@dataclass
class StaticAnalysisResults(DataClassJsonMixin):
    # Halstead metrics (programming files only)
    halstead_volume_mean: float | None
    halstead_volume_median: float | None
    halstead_volume_std: float | None
    halstead_volume_sum: float | None
    halstead_difficulty_mean: float | None
    halstead_difficulty_median: float | None
    halstead_difficulty_std: float | None
    halstead_difficulty_sum: float | None
    halstead_effort_mean: float | None
    halstead_effort_median: float | None
    halstead_effort_std: float | None
    halstead_effort_sum: float | None
    halstead_timerequired_mean: float | None
    halstead_timerequired_median: float | None
    halstead_timerequired_std: float | None
    halstead_timerequired_sum: float | None
    halstead_bugprop_mean: float | None
    halstead_bugprop_median: float | None
    halstead_bugprop_std: float | None
    halstead_bugprop_sum: float | None
    # Operator/operand metrics
    operators_sum_mean: float | None
    operators_sum_median: float | None
    operators_sum_std: float | None
    operators_sum_sum: float | None
    operators_uniq_mean: float | None
    operators_uniq_median: float | None
    operators_uniq_std: float | None
    operators_uniq_sum: float | None
    operands_sum_mean: float | None
    operands_sum_median: float | None
    operands_sum_std: float | None
    operands_sum_sum: float | None
    operands_uniq_mean: float | None
    operands_uniq_median: float | None
    operands_uniq_std: float | None
    operands_uniq_sum: float | None
    # Pylint and maintainability
    pylint_mean: float | None
    pylint_median: float | None
    pylint_std: float | None
    pylint_sum: float | None
    maintainability_index_mean: float | None
    maintainability_index_median: float | None
    maintainability_index_std: float | None
    maintainability_index_sum: float | None
    # File count
    static_analysis_file_count: int


def _extract_file_metrics(file_data: dict) -> dict:
    return {
        "halstead_volume": file_data.get("halstead_volume"),
        "halstead_difficulty": file_data.get("halstead_difficulty"),
        "halstead_effort": file_data.get("halstead_effort"),
        "halstead_timerequired": file_data.get("halstead_timerequired"),
        "halstead_bugprop": file_data.get("halstead_bugprop"),
        "operators_sum": file_data.get("operators_sum"),
        "operators_uniq": file_data.get("operators_uniq"),
        "operands_sum": file_data.get("operands_sum"),
        "operands_uniq": file_data.get("operands_uniq"),
        "pylint": file_data.get("pylint"),
        "maintainability_index": file_data.get("maintainability_index"),
    }


def compute_static_analysis_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> StaticAnalysisResults:
    # Check if multimetric CLI is available
    if shutil.which("multimetric") is None:
        log.warning(
            "multimetric CLI not found. Install via: pip install multimetric. "
            "Returning empty results."
        )
        return _empty_results()

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
        repo_dir = Path(repo.working_dir)

        # Collect all non-binary files
        files: list[str] = []
        for fp in repo_dir.rglob("*"):
            if fp.is_file() and ".git" not in fp.parts:
                try:
                    fp.read_text(encoding="utf-8")
                    files.append(str(fp))
                except (UnicodeDecodeError, PermissionError):
                    continue

        if not files:
            return _empty_results()

        # Run multimetric on all files
        result = subprocess.run(
            ["multimetric", *files],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            log.warning(
                f"multimetric failed with return code {result.returncode}. "
                f"stderr: {result.stderr.strip()}"
            )
            return _empty_results()

        try:
            mm_output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse multimetric JSON output: {e}")
            return _empty_results()

        # Collect metrics for programming files only
        programming_file_metrics: list[dict] = []

        files_data = mm_output.get("files", {})
        for filepath, file_data in files_data.items():
            if get_linguist_file_type(filepath) == FileTypes.programming.value:
                programming_file_metrics.append(_extract_file_metrics(file_data))

        return StaticAnalysisResults(**_aggregate_metrics(programming_file_metrics))

    finally:
        repo.git.checkout(original_ref)
