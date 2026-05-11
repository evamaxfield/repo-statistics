#!/usr/bin/env python

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Literal

try:
    import numpy as np
    import polars as pl
    from dataclasses_json import DataClassJsonMixin
    from git import Repo
    from nb_to_src import convert_directory
    from sci_soft_models.ai_detection_clf import (
        AIDetectionError,
        AIDetectionResult,
        detect_ai_in_python_file,
        load_ai_detection_clf_model,
    )
except ImportError as e:
    raise ImportError(
        f"Missing required dependency for AI detection: {e.name}. "
        "Please install with 'pip install repo-statistics[ai]' to use this feature."
    ) from e

from .complexity import _check_and_install_complexity_cli
from .utils import get_commit_hash_for_target_datetime

if TYPE_CHECKING:
    from transformers import Pipeline

###############################################################################

log = logging.getLogger(__name__)

###############################################################################

_EXCLUDE_DIR_NAMES = frozenset({
    "tests",
    "test",
    "tutorial",
    "tutorials",
    "example",
    "examples",
    "docs",
    "doc",
    "vignettes",
    "data",
})

_EXCLUDE_PACKAGING_FILENAMES = frozenset({
    "setup.py",
    "setup.cfg",
    "conftest.py",
    "_version.py",
    "pyproject.toml",
    "MANIFEST.in",
    "__init__.py",
    "__version__.py",
})

_EXCLUDE_TEST_FILENAME_PATTERNS = ("test_*", "*_test", "test-*")

###############################################################################


@dataclass
class AIDetectionResults(DataClassJsonMixin):  # noqa: D101
    ai_detection_unique_files_checked: int
    # p25
    ai_detection_p25_filepath: str | None
    ai_detection_p25_total_function_count: int | None
    ai_detection_p25_ai_function_count: int | None
    ai_detection_p25_human_function_count: int | None
    ai_detection_p25_ai_function_proportion: float | None
    ai_detection_p25_ai_confidence_mean: float | None
    ai_detection_p25_ai_confidence_std: float | None
    ai_detection_p25_ai_confidence_median: float | None
    ai_detection_p25_human_confidence_mean: float | None
    ai_detection_p25_human_confidence_std: float | None
    ai_detection_p25_human_confidence_median: float | None
    # p50
    ai_detection_p50_filepath: str | None
    ai_detection_p50_total_function_count: int | None
    ai_detection_p50_ai_function_count: int | None
    ai_detection_p50_human_function_count: int | None
    ai_detection_p50_ai_function_proportion: float | None
    ai_detection_p50_ai_confidence_mean: float | None
    ai_detection_p50_ai_confidence_std: float | None
    ai_detection_p50_ai_confidence_median: float | None
    ai_detection_p50_human_confidence_mean: float | None
    ai_detection_p50_human_confidence_std: float | None
    ai_detection_p50_human_confidence_median: float | None
    # p75
    ai_detection_p75_filepath: str | None
    ai_detection_p75_total_function_count: int | None
    ai_detection_p75_ai_function_count: int | None
    ai_detection_p75_human_function_count: int | None
    ai_detection_p75_ai_function_proportion: float | None
    ai_detection_p75_ai_confidence_mean: float | None
    ai_detection_p75_ai_confidence_std: float | None
    ai_detection_p75_ai_confidence_median: float | None
    ai_detection_p75_human_confidence_mean: float | None
    ai_detection_p75_human_confidence_std: float | None
    ai_detection_p75_human_confidence_median: float | None


def _empty_results() -> AIDetectionResults:
    return AIDetectionResults(
        ai_detection_unique_files_checked=0,
        ai_detection_p25_filepath=None,
        ai_detection_p25_total_function_count=None,
        ai_detection_p25_ai_function_count=None,
        ai_detection_p25_human_function_count=None,
        ai_detection_p25_ai_function_proportion=None,
        ai_detection_p25_ai_confidence_mean=None,
        ai_detection_p25_ai_confidence_std=None,
        ai_detection_p25_ai_confidence_median=None,
        ai_detection_p25_human_confidence_mean=None,
        ai_detection_p25_human_confidence_std=None,
        ai_detection_p25_human_confidence_median=None,
        ai_detection_p50_filepath=None,
        ai_detection_p50_total_function_count=None,
        ai_detection_p50_ai_function_count=None,
        ai_detection_p50_human_function_count=None,
        ai_detection_p50_ai_function_proportion=None,
        ai_detection_p50_ai_confidence_mean=None,
        ai_detection_p50_ai_confidence_std=None,
        ai_detection_p50_ai_confidence_median=None,
        ai_detection_p50_human_confidence_mean=None,
        ai_detection_p50_human_confidence_std=None,
        ai_detection_p50_human_confidence_median=None,
        ai_detection_p75_filepath=None,
        ai_detection_p75_total_function_count=None,
        ai_detection_p75_ai_function_count=None,
        ai_detection_p75_human_function_count=None,
        ai_detection_p75_ai_function_proportion=None,
        ai_detection_p75_ai_confidence_mean=None,
        ai_detection_p75_ai_confidence_std=None,
        ai_detection_p75_ai_confidence_median=None,
        ai_detection_p75_human_confidence_mean=None,
        ai_detection_p75_human_confidence_std=None,
        ai_detection_p75_human_confidence_median=None,
    )


###############################################################################


def _get_core_python_file_set(repo_path: Path) -> list[Path]:
    file_list = [f for f in repo_path.rglob("*.py") if f.is_file()]

    file_list = [
        f
        for f in file_list
        if not any(
            f.parents[i].name.lower() in _EXCLUDE_DIR_NAMES
            for i in range(len(f.parents))
        )
    ]

    file_list = [f for f in file_list if f.name not in _EXCLUDE_PACKAGING_FILENAMES]

    file_list = [
        f
        for f in file_list
        if not any(
            f.match(pattern, case_sensitive=False) for pattern in _EXCLUDE_TEST_FILENAME_PATTERNS
        )
    ]

    return file_list


def _compute_file_stats(
    file_path: Path,
    results: list[AIDetectionResult | AIDetectionError],
    temp_dir: Path,
) -> dict:
    successes = [r for r in results if isinstance(r, AIDetectionResult)]
    total_function_count = len(successes)

    filepath = str(file_path.relative_to(temp_dir))

    if total_function_count == 0:
        return {
            "filepath": filepath,
            "total_function_count": 0,
            "ai_function_count": None,
            "human_function_count": None,
            "ai_function_proportion": None,
            "ai_confidence_mean": None,
            "ai_confidence_std": None,
            "ai_confidence_median": None,
            "human_confidence_mean": None,
            "human_confidence_std": None,
            "human_confidence_median": None,
        }

    ai_results = [r for r in successes if r.ai_classification == "ai"]
    human_results = [r for r in successes if r.ai_classification != "ai"]

    ai_function_count = len(ai_results)
    human_function_count = len(human_results)
    ai_function_proportion = ai_function_count / total_function_count

    def _stats(
        items: list[AIDetectionResult],
    ) -> tuple[float | None, float | None, float | None]:
        if not items:
            return None, None, None
        scores = np.array([r.ai_confidence for r in items])
        return float(np.mean(scores)), float(np.std(scores)), float(np.median(scores))

    ai_mean, ai_std, ai_median = _stats(ai_results)
    human_mean, human_std, human_median = _stats(human_results)

    return {
        "filepath": filepath,
        "total_function_count": total_function_count,
        "ai_function_count": ai_function_count,
        "human_function_count": human_function_count,
        "ai_function_proportion": ai_function_proportion,
        "ai_confidence_mean": ai_mean,
        "ai_confidence_std": ai_std,
        "ai_confidence_median": ai_median,
        "human_confidence_mean": human_mean,
        "human_confidence_std": human_std,
        "human_confidence_median": human_median,
    }


###############################################################################


def compute_ai_detection_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
    loaded_ai_detection_clf_model: "Pipeline | None" = None,
    install_complexity_if_missing: bool = False,
) -> AIDetectionResults:
    if not _check_and_install_complexity_cli(install_complexity_if_missing):
        return _empty_results()

    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    target_hex = get_commit_hash_for_target_datetime(
        commits_df=commits_df,
        target_datetime=target_datetime,
        datetime_col=datetime_col,
    )

    try:
        original_ref = repo.active_branch.name
    except TypeError:
        original_ref = repo.head.commit.hexsha

    try:
        repo.git.checkout(target_hex)
        repo_dir = Path(repo.working_dir)

        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir) / "repo"
            shutil.copytree(repo_dir, temp_dir, ignore=shutil.ignore_patterns(".git"))

            convert_directory(temp_dir, recursive=True, show_progress=False)

            core_files = _get_core_python_file_set(temp_dir)
            if not core_files:
                return _empty_results()

            core_files_set = set(core_files)

            result = subprocess.run(
                ["complexity", "--format", "json"],
                cwd=str(temp_dir),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                log.warning(
                    f"complexity CLI failed with return code {result.returncode}. "
                    f"stderr: {result.stderr.strip()}"
                )
                return _empty_results()

            try:
                complexity_data: dict[str, float] = json.loads(result.stdout)
            except json.JSONDecodeError:
                log.warning("complexity CLI returned invalid JSON for AI detection.")
                return _empty_results()

            # Normalize paths from "./relative/path.py" to absolute, filter to core set
            filtered_scores: dict[Path, float] = {}
            for rel_path_str, score in complexity_data.items():
                normalized = rel_path_str.lstrip("./")
                abs_path = temp_dir / normalized
                if abs_path in core_files_set:
                    filtered_scores[abs_path] = score

            if not filtered_scores:
                return _empty_results()

            scores_series = pl.Series("score", list(filtered_scores.values()))
            paths_list = list(filtered_scores.keys())

            p25_val = scores_series.quantile(0.25, interpolation="nearest")
            p50_val = scores_series.quantile(0.50, interpolation="nearest")
            p75_val = scores_series.quantile(0.75, interpolation="nearest")

            def _select_file(target_val: float) -> Path:
                for path, score in zip(paths_list, scores_series.to_list()):
                    if score == target_val:
                        return path
                # Fallback: return first file (should never reach here)
                return paths_list[0]

            p25_file = _select_file(p25_val)
            p50_file = _select_file(p50_val)
            p75_file = _select_file(p75_val)

            unique_files_checked = len({p25_file, p50_file, p75_file})

            if loaded_ai_detection_clf_model is None:
                log.info(
                    "No pre-loaded AI detection model provided; loading now (may be slow)..."
                )
                clf = load_ai_detection_clf_model()
            else:
                clf = loaded_ai_detection_clf_model

            # Cache classifications per unique file to avoid redundant model calls
            _cache: dict[Path, list[AIDetectionResult | AIDetectionError]] = {}
            for f in {p25_file, p50_file, p75_file}:
                try:
                    _cache[f] = detect_ai_in_python_file(f, clf)
                except Exception as e:
                    log.warning(f"detect_ai_in_python_file failed for {f}: {e}")
                    _cache[f] = []

            p25_stats = _compute_file_stats(p25_file, _cache[p25_file], temp_dir)
            p50_stats = _compute_file_stats(p50_file, _cache[p50_file], temp_dir)
            p75_stats = _compute_file_stats(p75_file, _cache[p75_file], temp_dir)

            return AIDetectionResults(
                ai_detection_unique_files_checked=unique_files_checked,
                ai_detection_p25_filepath=p25_stats["filepath"],
                ai_detection_p25_total_function_count=p25_stats["total_function_count"],
                ai_detection_p25_ai_function_count=p25_stats["ai_function_count"],
                ai_detection_p25_human_function_count=p25_stats["human_function_count"],
                ai_detection_p25_ai_function_proportion=p25_stats["ai_function_proportion"],
                ai_detection_p25_ai_confidence_mean=p25_stats["ai_confidence_mean"],
                ai_detection_p25_ai_confidence_std=p25_stats["ai_confidence_std"],
                ai_detection_p25_ai_confidence_median=p25_stats["ai_confidence_median"],
                ai_detection_p25_human_confidence_mean=p25_stats["human_confidence_mean"],
                ai_detection_p25_human_confidence_std=p25_stats["human_confidence_std"],
                ai_detection_p25_human_confidence_median=p25_stats["human_confidence_median"],
                ai_detection_p50_filepath=p50_stats["filepath"],
                ai_detection_p50_total_function_count=p50_stats["total_function_count"],
                ai_detection_p50_ai_function_count=p50_stats["ai_function_count"],
                ai_detection_p50_human_function_count=p50_stats["human_function_count"],
                ai_detection_p50_ai_function_proportion=p50_stats["ai_function_proportion"],
                ai_detection_p50_ai_confidence_mean=p50_stats["ai_confidence_mean"],
                ai_detection_p50_ai_confidence_std=p50_stats["ai_confidence_std"],
                ai_detection_p50_ai_confidence_median=p50_stats["ai_confidence_median"],
                ai_detection_p50_human_confidence_mean=p50_stats["human_confidence_mean"],
                ai_detection_p50_human_confidence_std=p50_stats["human_confidence_std"],
                ai_detection_p50_human_confidence_median=p50_stats["human_confidence_median"],
                ai_detection_p75_filepath=p75_stats["filepath"],
                ai_detection_p75_total_function_count=p75_stats["total_function_count"],
                ai_detection_p75_ai_function_count=p75_stats["ai_function_count"],
                ai_detection_p75_human_function_count=p75_stats["human_function_count"],
                ai_detection_p75_ai_function_proportion=p75_stats["ai_function_proportion"],
                ai_detection_p75_ai_confidence_mean=p75_stats["ai_confidence_mean"],
                ai_detection_p75_ai_confidence_std=p75_stats["ai_confidence_std"],
                ai_detection_p75_ai_confidence_median=p75_stats["ai_confidence_median"],
                ai_detection_p75_human_confidence_mean=p75_stats["human_confidence_mean"],
                ai_detection_p75_human_confidence_std=p75_stats["human_confidence_std"],
                ai_detection_p75_human_confidence_median=p75_stats["human_confidence_median"],
            )

    except Exception as e:
        log.warning(f"AI detection metrics failed: {e}")
        return _empty_results()

    finally:
        repo.git.checkout(original_ref)
