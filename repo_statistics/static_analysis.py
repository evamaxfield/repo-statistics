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

# File type prefixes
_FILE_TYPE_PREFIXES = ["total", "programming", "markup", "prose", "data", "unknown"]


def _empty_results() -> "StaticAnalysisResults":
    kwargs: dict = {}
    for prefix in _FILE_TYPE_PREFIXES:
        # Halstead: mean/median/sum for volume, mean for others
        kwargs[f"{prefix}_halstead_volume_mean"] = None
        kwargs[f"{prefix}_halstead_volume_median"] = None
        kwargs[f"{prefix}_halstead_volume_sum"] = None
        kwargs[f"{prefix}_halstead_difficulty_mean"] = None
        kwargs[f"{prefix}_halstead_effort_mean"] = None
        kwargs[f"{prefix}_halstead_timerequired_mean"] = None
        kwargs[f"{prefix}_halstead_bugprop_mean"] = None
        # Operator/operand sums
        kwargs[f"{prefix}_operators_sum"] = None
        kwargs[f"{prefix}_operators_uniq"] = None
        kwargs[f"{prefix}_operands_sum"] = None
        kwargs[f"{prefix}_operands_uniq"] = None
        # Pylint and maintainability
        kwargs[f"{prefix}_pylint_mean"] = None
        kwargs[f"{prefix}_maintainability_index_mean"] = None
        # File count
        kwargs[f"{prefix}_static_analysis_file_count"] = 0
    return StaticAnalysisResults(**kwargs)


def _aggregate_metrics(
    file_metrics: list[dict],
) -> dict:
    if len(file_metrics) == 0:
        return {
            "halstead_volume_mean": None,
            "halstead_volume_median": None,
            "halstead_volume_sum": None,
            "halstead_difficulty_mean": None,
            "halstead_effort_mean": None,
            "halstead_timerequired_mean": None,
            "halstead_bugprop_mean": None,
            "operators_sum": None,
            "operators_uniq": None,
            "operands_sum": None,
            "operands_uniq": None,
            "pylint_mean": None,
            "maintainability_index_mean": None,
            "static_analysis_file_count": 0,
        }

    def _safe_mean(key: str) -> float | None:
        vals = [f[key] for f in file_metrics if key in f and f[key] is not None]
        return float(np.mean(vals)) if vals else None

    def _safe_median(key: str) -> float | None:
        vals = [f[key] for f in file_metrics if key in f and f[key] is not None]
        return float(np.median(vals)) if vals else None

    def _safe_sum(key: str) -> int | None:
        vals = [f[key] for f in file_metrics if key in f and f[key] is not None]
        return int(np.sum(vals)) if vals else None

    volumes = [
        f["halstead_volume"]
        for f in file_metrics
        if "halstead_volume" in f and f["halstead_volume"] is not None
    ]

    return {
        "halstead_volume_mean": float(np.mean(volumes)) if volumes else None,
        "halstead_volume_median": float(np.median(volumes)) if volumes else None,
        "halstead_volume_sum": float(np.sum(volumes)) if volumes else None,
        "halstead_difficulty_mean": _safe_mean("halstead_difficulty"),
        "halstead_effort_mean": _safe_mean("halstead_effort"),
        "halstead_timerequired_mean": _safe_mean("halstead_timerequired"),
        "halstead_bugprop_mean": _safe_mean("halstead_bugprop"),
        "operators_sum": _safe_sum("operators_sum"),
        "operators_uniq": _safe_sum("operators_uniq"),
        "operands_sum": _safe_sum("operands_sum"),
        "operands_uniq": _safe_sum("operands_uniq"),
        "pylint_mean": _safe_mean("pylint"),
        "maintainability_index_mean": _safe_mean("maintainability_index"),
        "static_analysis_file_count": len(file_metrics),
    }


@dataclass
class StaticAnalysisResults(DataClassJsonMixin):
    # Total
    total_halstead_volume_mean: float | None
    total_halstead_volume_median: float | None
    total_halstead_volume_sum: float | None
    total_halstead_difficulty_mean: float | None
    total_halstead_effort_mean: float | None
    total_halstead_timerequired_mean: float | None
    total_halstead_bugprop_mean: float | None
    total_operators_sum: int | None
    total_operators_uniq: int | None
    total_operands_sum: int | None
    total_operands_uniq: int | None
    total_pylint_mean: float | None
    total_maintainability_index_mean: float | None
    total_static_analysis_file_count: int
    # Programming
    programming_halstead_volume_mean: float | None
    programming_halstead_volume_median: float | None
    programming_halstead_volume_sum: float | None
    programming_halstead_difficulty_mean: float | None
    programming_halstead_effort_mean: float | None
    programming_halstead_timerequired_mean: float | None
    programming_halstead_bugprop_mean: float | None
    programming_operators_sum: int | None
    programming_operators_uniq: int | None
    programming_operands_sum: int | None
    programming_operands_uniq: int | None
    programming_pylint_mean: float | None
    programming_maintainability_index_mean: float | None
    programming_static_analysis_file_count: int
    # Markup
    markup_halstead_volume_mean: float | None
    markup_halstead_volume_median: float | None
    markup_halstead_volume_sum: float | None
    markup_halstead_difficulty_mean: float | None
    markup_halstead_effort_mean: float | None
    markup_halstead_timerequired_mean: float | None
    markup_halstead_bugprop_mean: float | None
    markup_operators_sum: int | None
    markup_operators_uniq: int | None
    markup_operands_sum: int | None
    markup_operands_uniq: int | None
    markup_pylint_mean: float | None
    markup_maintainability_index_mean: float | None
    markup_static_analysis_file_count: int
    # Prose
    prose_halstead_volume_mean: float | None
    prose_halstead_volume_median: float | None
    prose_halstead_volume_sum: float | None
    prose_halstead_difficulty_mean: float | None
    prose_halstead_effort_mean: float | None
    prose_halstead_timerequired_mean: float | None
    prose_halstead_bugprop_mean: float | None
    prose_operators_sum: int | None
    prose_operators_uniq: int | None
    prose_operands_sum: int | None
    prose_operands_uniq: int | None
    prose_pylint_mean: float | None
    prose_maintainability_index_mean: float | None
    prose_static_analysis_file_count: int
    # Data
    data_halstead_volume_mean: float | None
    data_halstead_volume_median: float | None
    data_halstead_volume_sum: float | None
    data_halstead_difficulty_mean: float | None
    data_halstead_effort_mean: float | None
    data_halstead_timerequired_mean: float | None
    data_halstead_bugprop_mean: float | None
    data_operators_sum: int | None
    data_operators_uniq: int | None
    data_operands_sum: int | None
    data_operands_uniq: int | None
    data_pylint_mean: float | None
    data_maintainability_index_mean: float | None
    data_static_analysis_file_count: int
    # Unknown
    unknown_halstead_volume_mean: float | None
    unknown_halstead_volume_median: float | None
    unknown_halstead_volume_sum: float | None
    unknown_halstead_difficulty_mean: float | None
    unknown_halstead_effort_mean: float | None
    unknown_halstead_timerequired_mean: float | None
    unknown_halstead_bugprop_mean: float | None
    unknown_operators_sum: int | None
    unknown_operators_uniq: int | None
    unknown_operands_sum: int | None
    unknown_operands_uniq: int | None
    unknown_pylint_mean: float | None
    unknown_maintainability_index_mean: float | None
    unknown_static_analysis_file_count: int


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

        # Classify files and collect per-type metrics
        all_file_metrics: list[dict] = []
        by_type: dict[str, list[dict]] = {ft.value: [] for ft in FileTypes}

        files_data = mm_output.get("files", {})
        for filepath, file_data in files_data.items():
            metrics = _extract_file_metrics(file_data)
            all_file_metrics.append(metrics)
            file_type = get_linguist_file_type(filepath)
            if file_type in by_type:
                by_type[file_type].append(metrics)

        # Aggregate per type
        kwargs: dict = {}
        total_agg = _aggregate_metrics(all_file_metrics)
        for key, value in total_agg.items():
            kwargs[f"total_{key}"] = value

        for file_type in FileTypes:
            type_agg = _aggregate_metrics(by_type[file_type.value])
            for key, value in type_agg.items():
                kwargs[f"{file_type.value}_{key}"] = value

        return StaticAnalysisResults(**kwargs)

    finally:
        repo.git.checkout(original_ref)
