#!/usr/bin/env python

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Literal

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .complexity import _check_and_install_complexity_cli
from .utils import get_commit_hash_for_target_datetime

if TYPE_CHECKING:
    from sci_soft_models.ai_detection_clf import (  # type: ignore[import-untyped]
        AIDetectionError,
        AIDetectionResult,
        MultiModelAIDetectionResults,  # type: ignore[misc]
    )

###############################################################################

log = logging.getLogger(__name__)

###############################################################################

_EXCLUDE_DIR_NAMES = frozenset(
    {
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
    }
)

_EXCLUDE_PACKAGING_FILENAMES = frozenset(
    {
        "setup.py",
        "setup.cfg",
        "conftest.py",
        "_version.py",
        "pyproject.toml",
        "MANIFEST.in",
        "__init__.py",
        "__version__.py",
    }
)

_EXCLUDE_TEST_FILENAME_PATTERNS = ("test_*", "*_test", "test-*")

###############################################################################


@dataclass
class AIDetectionResults(DataClassJsonMixin):
    ai_detection_unique_files_checked: int
    # Shared per-percentile filepaths (same file selected for all models)
    ai_detection_p25_filepath: str | None
    ai_detection_p50_filepath: str | None
    ai_detection_p75_filepath: str | None
    # paigsf (function-level) — p25
    ai_detection_paigsf_p25_total_function_count: int | None
    ai_detection_paigsf_p25_ai_function_count: int | None
    ai_detection_paigsf_p25_human_function_count: int | None
    ai_detection_paigsf_p25_ai_function_proportion: float | None
    ai_detection_paigsf_p25_ai_confidence_mean: float | None
    ai_detection_paigsf_p25_ai_confidence_std: float | None
    ai_detection_paigsf_p25_ai_confidence_median: float | None
    ai_detection_paigsf_p25_human_confidence_mean: float | None
    ai_detection_paigsf_p25_human_confidence_std: float | None
    ai_detection_paigsf_p25_human_confidence_median: float | None
    # paigsf — p50
    ai_detection_paigsf_p50_total_function_count: int | None
    ai_detection_paigsf_p50_ai_function_count: int | None
    ai_detection_paigsf_p50_human_function_count: int | None
    ai_detection_paigsf_p50_ai_function_proportion: float | None
    ai_detection_paigsf_p50_ai_confidence_mean: float | None
    ai_detection_paigsf_p50_ai_confidence_std: float | None
    ai_detection_paigsf_p50_ai_confidence_median: float | None
    ai_detection_paigsf_p50_human_confidence_mean: float | None
    ai_detection_paigsf_p50_human_confidence_std: float | None
    ai_detection_paigsf_p50_human_confidence_median: float | None
    # paigsf — p75
    ai_detection_paigsf_p75_total_function_count: int | None
    ai_detection_paigsf_p75_ai_function_count: int | None
    ai_detection_paigsf_p75_human_function_count: int | None
    ai_detection_paigsf_p75_ai_function_proportion: float | None
    ai_detection_paigsf_p75_ai_confidence_mean: float | None
    ai_detection_paigsf_p75_ai_confidence_std: float | None
    ai_detection_paigsf_p75_ai_confidence_median: float | None
    ai_detection_paigsf_p75_human_confidence_mean: float | None
    ai_detection_paigsf_p75_human_confidence_std: float | None
    ai_detection_paigsf_p75_human_confidence_median: float | None
    # aigcodeset (function-level) — p25
    ai_detection_aigcodeset_p25_total_function_count: int | None
    ai_detection_aigcodeset_p25_ai_function_count: int | None
    ai_detection_aigcodeset_p25_human_function_count: int | None
    ai_detection_aigcodeset_p25_ai_function_proportion: float | None
    ai_detection_aigcodeset_p25_ai_confidence_mean: float | None
    ai_detection_aigcodeset_p25_ai_confidence_std: float | None
    ai_detection_aigcodeset_p25_ai_confidence_median: float | None
    ai_detection_aigcodeset_p25_human_confidence_mean: float | None
    ai_detection_aigcodeset_p25_human_confidence_std: float | None
    ai_detection_aigcodeset_p25_human_confidence_median: float | None
    # aigcodeset — p50
    ai_detection_aigcodeset_p50_total_function_count: int | None
    ai_detection_aigcodeset_p50_ai_function_count: int | None
    ai_detection_aigcodeset_p50_human_function_count: int | None
    ai_detection_aigcodeset_p50_ai_function_proportion: float | None
    ai_detection_aigcodeset_p50_ai_confidence_mean: float | None
    ai_detection_aigcodeset_p50_ai_confidence_std: float | None
    ai_detection_aigcodeset_p50_ai_confidence_median: float | None
    ai_detection_aigcodeset_p50_human_confidence_mean: float | None
    ai_detection_aigcodeset_p50_human_confidence_std: float | None
    ai_detection_aigcodeset_p50_human_confidence_median: float | None
    # aigcodeset — p75
    ai_detection_aigcodeset_p75_total_function_count: int | None
    ai_detection_aigcodeset_p75_ai_function_count: int | None
    ai_detection_aigcodeset_p75_human_function_count: int | None
    ai_detection_aigcodeset_p75_ai_function_proportion: float | None
    ai_detection_aigcodeset_p75_ai_confidence_mean: float | None
    ai_detection_aigcodeset_p75_ai_confidence_std: float | None
    ai_detection_aigcodeset_p75_ai_confidence_median: float | None
    ai_detection_aigcodeset_p75_human_confidence_mean: float | None
    ai_detection_aigcodeset_p75_human_confidence_std: float | None
    ai_detection_aigcodeset_p75_human_confidence_median: float | None
    # codet_m4 (function-level) — p25
    ai_detection_codet_m4_p25_total_function_count: int | None
    ai_detection_codet_m4_p25_ai_function_count: int | None
    ai_detection_codet_m4_p25_human_function_count: int | None
    ai_detection_codet_m4_p25_ai_function_proportion: float | None
    ai_detection_codet_m4_p25_ai_confidence_mean: float | None
    ai_detection_codet_m4_p25_ai_confidence_std: float | None
    ai_detection_codet_m4_p25_ai_confidence_median: float | None
    ai_detection_codet_m4_p25_human_confidence_mean: float | None
    ai_detection_codet_m4_p25_human_confidence_std: float | None
    ai_detection_codet_m4_p25_human_confidence_median: float | None
    # codet_m4 — p50
    ai_detection_codet_m4_p50_total_function_count: int | None
    ai_detection_codet_m4_p50_ai_function_count: int | None
    ai_detection_codet_m4_p50_human_function_count: int | None
    ai_detection_codet_m4_p50_ai_function_proportion: float | None
    ai_detection_codet_m4_p50_ai_confidence_mean: float | None
    ai_detection_codet_m4_p50_ai_confidence_std: float | None
    ai_detection_codet_m4_p50_ai_confidence_median: float | None
    ai_detection_codet_m4_p50_human_confidence_mean: float | None
    ai_detection_codet_m4_p50_human_confidence_std: float | None
    ai_detection_codet_m4_p50_human_confidence_median: float | None
    # codet_m4 — p75
    ai_detection_codet_m4_p75_total_function_count: int | None
    ai_detection_codet_m4_p75_ai_function_count: int | None
    ai_detection_codet_m4_p75_human_function_count: int | None
    ai_detection_codet_m4_p75_ai_function_proportion: float | None
    ai_detection_codet_m4_p75_ai_confidence_mean: float | None
    ai_detection_codet_m4_p75_ai_confidence_std: float | None
    ai_detection_codet_m4_p75_ai_confidence_median: float | None
    ai_detection_codet_m4_p75_human_confidence_mean: float | None
    ai_detection_codet_m4_p75_human_confidence_std: float | None
    ai_detection_codet_m4_p75_human_confidence_median: float | None
    # codemirage (file-level) — p25 / p50 / p75
    ai_detection_codemirage_p25_ai_classification: str | None
    ai_detection_codemirage_p25_ai_confidence: float | None
    ai_detection_codemirage_p50_ai_classification: str | None
    ai_detection_codemirage_p50_ai_confidence: float | None
    ai_detection_codemirage_p75_ai_classification: str | None
    ai_detection_codemirage_p75_ai_confidence: float | None
    # combined (file-level) — p25 / p50 / p75
    ai_detection_combined_p25_ai_classification: str | None
    ai_detection_combined_p25_ai_confidence: float | None
    ai_detection_combined_p50_ai_classification: str | None
    ai_detection_combined_p50_ai_confidence: float | None
    ai_detection_combined_p75_ai_classification: str | None
    ai_detection_combined_p75_ai_confidence: float | None


@dataclass
class AIAgentConfigResults(DataClassJsonMixin):
    ai_agent_config_claude_md_exists: bool
    ai_agent_config_cursor_rules_exists: bool
    ai_agent_config_copilot_instructions_exists: bool
    ai_agent_config_aider_exists: bool
    ai_agent_config_cline_rules_exists: bool
    ai_agent_config_windsurf_rules_exists: bool
    ai_agent_config_agents_md_exists: bool
    ai_agent_config_any_exists: bool


def _empty_results() -> AIDetectionResults:
    none_func_stats: dict = {
        "total_function_count": None,
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
    none_file_stats: dict = {"ai_classification": None, "ai_confidence": None}

    def _func_fields(model: str) -> dict:
        result = {}
        for p in ("p25", "p50", "p75"):
            for k, v in none_func_stats.items():
                result[f"ai_detection_{model}_{p}_{k}"] = v
        return result

    def _file_fields(model: str) -> dict:
        result = {}
        for p in ("p25", "p50", "p75"):
            for k, v in none_file_stats.items():
                result[f"ai_detection_{model}_{p}_{k}"] = v
        return result

    return AIDetectionResults(
        ai_detection_unique_files_checked=0,
        ai_detection_p25_filepath=None,
        ai_detection_p50_filepath=None,
        ai_detection_p75_filepath=None,
        **_func_fields("paigsf"),
        **_func_fields("aigcodeset"),
        **_func_fields("codet_m4"),
        **_file_fields("codemirage"),
        **_file_fields("combined"),
    )


###############################################################################


def _get_core_python_file_set(repo_path: Path) -> list[Path]:
    file_list = [f for f in repo_path.rglob("*.py") if f.is_file()]

    file_list = [
        f
        for f in file_list
        if not any(
            f.parents[i].name.lower() in _EXCLUDE_DIR_NAMES for i in range(len(f.parents))
        )
    ]

    file_list = [f for f in file_list if f.name not in _EXCLUDE_PACKAGING_FILENAMES]

    file_list = [
        f
        for f in file_list
        if not any(
            f.match(pattern, case_sensitive=False)
            for pattern in _EXCLUDE_TEST_FILENAME_PATTERNS
        )
    ]

    return file_list


###############################################################################


def compute_ai_detection_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
    loaded_ai_detection_clf_models: "dict | None" = None,
    hf_token: str | None = None,
    install_complexity_if_missing: bool = False,
) -> AIDetectionResults:
    try:
        import numpy as np
        from nb_to_src import convert_directory
        from sci_soft_models.ai_detection_clf import (  # type: ignore[import-untyped]
            AIDetectionError,
            AIDetectionResult,
            detect_ai_in_python_file,
            load_all_ai_detection_clf_models,  # type: ignore[misc]
        )
    except ImportError as e:
        raise ImportError(
            f"Missing required dependency for AI detection: {e.name}. "
            "Please install with 'pip install repo-statistics[ai]' to use this feature."
        ) from e

    def _compute_file_stats(
        results: "list[AIDetectionResult | AIDetectionError]",
    ) -> dict:
        successes = [r for r in results if isinstance(r, AIDetectionResult)]
        total_function_count = len(successes)
        if total_function_count == 0:
            return {
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
            items: "list[AIDetectionResult]",
        ) -> "tuple[float | None, float | None, float | None]":
            if not items:
                return None, None, None
            scores = np.array([r.ai_confidence for r in items])
            return float(np.mean(scores)), float(np.std(scores)), float(np.median(scores))

        ai_mean, ai_std, ai_median = _stats(ai_results)
        human_mean, human_std, human_median = _stats(human_results)
        return {
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

    def _compute_file_level_stats(
        result: "AIDetectionResult | AIDetectionError | None",
    ) -> dict:
        if result is None or isinstance(result, AIDetectionError):
            return {"ai_classification": None, "ai_confidence": None}
        return {
            "ai_classification": result.ai_classification,
            "ai_confidence": result.ai_confidence,
        }

    print(
        "Within compute_ai_detection_metrics..."
    )  # Debug print to confirm function is being called

    # Resolve HF token: explicit param takes priority over environment variable.
    # Set in environment so HuggingFace Hub picks it up when loading the model.
    resolved_token = hf_token or os.environ.get("HF_TOKEN")
    if resolved_token is not None:
        os.environ["HF_TOKEN"] = resolved_token

    if not _check_and_install_complexity_cli(install_complexity_if_missing):
        print(
            "complexity CLI is not available and could not be installed. "
            "Skipping AI detection metrics."
        )  # Debug print
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
    print(f"Target commit hash for AI detection: {target_hex}")  # Debug print

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
            print("Repository copied to temporary directory for AI detection.")  # Debug print

            convert_directory(temp_dir, recursive=True, show_progress=False)
            print(
                "Jupyter notebooks converted to Python files for AI detection."
            )  # Debug print

            core_files = _get_core_python_file_set(temp_dir)
            if not core_files:
                return _empty_results()
            print(
                f"Found {len(core_files)} core Python files to analyze for AI detection."
            )  # Debug print

            core_files_set = set(core_files)

            result = subprocess.run(
                ["complexity", "--format", "json"],
                cwd=str(temp_dir),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(
                    f"complexity CLI failed with return code {result.returncode}. "
                    f"stderr: {result.stderr.strip()}"
                )
                return _empty_results()

            try:
                complexity_data: dict[str, float] = json.loads(result.stdout)
            except json.JSONDecodeError:
                print("complexity CLI returned invalid JSON for AI detection.")
                return _empty_results()

            print(
                f"complexity CLI returned complexity scores for {len(complexity_data)} files."
            )  # Debug print

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

            def _select_file(target_val: float | None) -> Path:
                if target_val is None:
                    return paths_list[0]
                for path, score in zip(paths_list, scores_series.to_list(), strict=False):
                    if score == target_val:
                        return path
                return paths_list[0]

            p25_file = _select_file(p25_val)
            p50_file = _select_file(p50_val)
            p75_file = _select_file(p75_val)

            unique_files_checked = len({p25_file, p50_file, p75_file})
            print(
                f"Selected files for AI detection: {p25_file}, {p50_file}, {p75_file}"
            )  # Debug print

            if loaded_ai_detection_clf_models is None:
                print(
                    "No pre-loaded AI detection models provided; loading now (may be slow)..."
                )
                clf_models = load_all_ai_detection_clf_models()
            else:
                clf_models = loaded_ai_detection_clf_models

            # Cache MultiModelAIDetectionResults per unique file
            _cache: dict[Path, MultiModelAIDetectionResults | None] = {}
            for f in {p25_file, p50_file, p75_file}:
                try:
                    _cache[f] = detect_ai_in_python_file(f, loaded_models=clf_models)  # type: ignore[call-arg]
                except Exception as e:
                    print(f"detect_ai_in_python_file failed for {f}: {e}")
                    _cache[f] = None

            def _func_stats_for(
                file_path: Path,
                attr: str,
            ) -> dict:
                multi = _cache[file_path]
                if multi is None:
                    return {
                        "total_function_count": None,
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
                return _compute_file_stats(getattr(multi, attr))

            def _file_stats_for(file_path: Path, attr: str) -> dict:
                multi = _cache[file_path]
                if multi is None:
                    return {"ai_classification": None, "ai_confidence": None}
                return _compute_file_level_stats(getattr(multi, attr))

            def _prefixed(model: str, percentile: str, stats: dict) -> dict:
                return {f"ai_detection_{model}_{percentile}_{k}": v for k, v in stats.items()}

            all_fields: dict = {
                "ai_detection_unique_files_checked": unique_files_checked,
                "ai_detection_p25_filepath": str(p25_file.relative_to(temp_dir)),
                "ai_detection_p50_filepath": str(p50_file.relative_to(temp_dir)),
                "ai_detection_p75_filepath": str(p75_file.relative_to(temp_dir)),
            }

            for model, attr, is_func in [
                ("paigsf", "paigsf_results", True),
                ("aigcodeset", "aigcodeset_results", True),
                ("codet_m4", "codet_m4_results", True),
                ("codemirage", "codemirage_results", False),
                ("combined", "combined_results", False),
            ]:
                for percentile, file_path in [
                    ("p25", p25_file),
                    ("p50", p50_file),
                    ("p75", p75_file),
                ]:
                    if is_func:
                        stats = _func_stats_for(file_path, attr)
                    else:
                        stats = _file_stats_for(file_path, attr)
                    all_fields.update(_prefixed(model, percentile, stats))

            print("Computed AI detection statistics for selected files.")  # Debug print
            return AIDetectionResults(**all_fields)

    except Exception as e:
        print(f"Error during AI detection metrics computation: {e}")
        import traceback

        print(traceback.format_exc())

        return _empty_results()

    finally:
        repo.git.checkout(original_ref)


###############################################################################

_AI_AGENT_CONFIG_GLOBS: list[tuple[str, list[str]]] = [
    ("ai_agent_config_claude_md_exists", ["CLAUDE.md", "CLAUDE.MD"]),
    ("ai_agent_config_cursor_rules_exists", [".cursorrules", ".cursor/rules"]),
    ("ai_agent_config_copilot_instructions_exists", [".github/copilot-instructions.md"]),
    ("ai_agent_config_aider_exists", [".aider.conf.yml", "aider.conf.yml", ".aider.conf"]),
    ("ai_agent_config_cline_rules_exists", [".clinerules"]),
    ("ai_agent_config_windsurf_rules_exists", [".windsurfrules"]),
    ("ai_agent_config_agents_md_exists", ["AGENTS.md", "AGENTS.MD"]),
]


def compute_ai_agent_config_metrics(
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
) -> AIAgentConfigResults:
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

        field_values: dict[str, bool] = {}
        for field_name, patterns in _AI_AGENT_CONFIG_GLOBS:
            found = any(list(repo_dir.glob(pattern)) for pattern in patterns)
            field_values[field_name] = found

        return AIAgentConfigResults(
            **field_values,
            ai_agent_config_any_exists=any(field_values.values()),
        )

    finally:
        repo.git.checkout(original_ref)


###############################################################################

_NAME_COLS = ("author_name", "committer_name")
_EMAIL_COLS = ("author_email", "committer_email")

# Each entry: (name_substrings, email_substrings)
_AGENT_PATTERNS: dict[str, tuple[list[str], list[str]]] = {
    "devin": (["devin"], ["devin", "cognition"]),
    "sweep": (["sweep"], ["sweep"]),
    "copilot": (["copilot"], ["copilot"]),
    "codeium": (["codeium"], ["codeium"]),
    "claude": (["claude"], ["anthropic"]),
    "cursor": (["cursor"], ["cursor"]),
}


@dataclass
class AICommitAuthorResults(DataClassJsonMixin):
    # Direct author/committer identity
    ai_commit_author_devin_commit_count: int
    ai_commit_author_sweep_commit_count: int
    ai_commit_author_copilot_commit_count: int
    ai_commit_author_codeium_commit_count: int
    ai_commit_author_claude_commit_count: int
    ai_commit_author_cursor_commit_count: int
    # Co-authored-by trailer
    ai_commit_coauthored_devin_commit_count: int
    ai_commit_coauthored_sweep_commit_count: int
    ai_commit_coauthored_copilot_commit_count: int
    ai_commit_coauthored_codeium_commit_count: int
    ai_commit_coauthored_claude_commit_count: int
    ai_commit_coauthored_cursor_commit_count: int
    # Aggregates (union of both signals)
    ai_commit_total_ai_associated_count: int
    ai_commit_ai_associated_proportion: float | None
    ai_commit_any_detected: bool


def _count_agent_commits(
    df: pl.DataFrame,
    name_substrings: list[str],
    email_substrings: list[str],
) -> int:
    expr = pl.lit(False)
    for col in _NAME_COLS:
        for s in name_substrings:
            expr = expr | pl.col(col).str.to_lowercase().str.contains(s)
    for col in _EMAIL_COLS:
        for s in email_substrings:
            expr = expr | pl.col(col).str.to_lowercase().str.contains(s)
    return df.filter(expr).height


def _get_coauthor_counts_and_hashes(
    git_log_output: str,
    valid_hashes: set[str],
) -> tuple[dict[str, int], set[str]]:
    coauthor_counts: dict[str, int] = dict.fromkeys(_AGENT_PATTERNS, 0)
    coauthor_hashes: set[str] = set()
    chunks = git_log_output.split("\x00")
    for i in range(0, len(chunks) - 1, 2):
        commit_hash = chunks[i].strip()
        body = chunks[i + 1].lower()
        if commit_hash not in valid_hashes:
            continue
        for line in body.splitlines():
            if not line.startswith("co-authored-by:"):
                continue
            for agent, (name_subs, email_subs) in _AGENT_PATTERNS.items():
                if any(s in line for s in name_subs + email_subs):
                    coauthor_counts[agent] += 1
                    coauthor_hashes.add(commit_hash)
    return coauthor_counts, coauthor_hashes


def compute_ai_commit_author_metrics(
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
) -> AICommitAuthorResults:
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    # Part A: direct author/committer identity (DataFrame scan)
    author_counts: dict[str, int] = {}
    ai_associated_hashes: set[str] = set()
    for agent, (name_subs, email_subs) in _AGENT_PATTERNS.items():
        expr = pl.lit(False)
        for col in _NAME_COLS:
            for s in name_subs:
                expr = expr | pl.col(col).str.to_lowercase().str.contains(s)
        for col in _EMAIL_COLS:
            for s in email_subs:
                expr = expr | pl.col(col).str.to_lowercase().str.contains(s)
        matched_hashes = commits_df.filter(expr)["commit_hash"].to_list()
        author_counts[agent] = len(matched_hashes)
        ai_associated_hashes.update(matched_hashes)

    # Part B: Co-authored-by trailer (second git log pass)
    valid_hashes: set[str] = set(commits_df["commit_hash"].to_list())
    coauthor_counts: dict[str, int] = dict.fromkeys(_AGENT_PATTERNS, 0)

    result = subprocess.run(
        ["git", "log", "--format=%H%x00%b%x00", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo.working_dir,
    )
    if result.returncode == 0:
        coauthor_counts, coauthor_hashes = _get_coauthor_counts_and_hashes(
            result.stdout, valid_hashes
        )
        ai_associated_hashes.update(coauthor_hashes)

    total_commits = len(commits_df)
    total_ai = len(ai_associated_hashes)
    proportion = total_ai / total_commits if total_commits > 0 else None

    return AICommitAuthorResults(
        ai_commit_author_devin_commit_count=author_counts["devin"],
        ai_commit_author_sweep_commit_count=author_counts["sweep"],
        ai_commit_author_copilot_commit_count=author_counts["copilot"],
        ai_commit_author_codeium_commit_count=author_counts["codeium"],
        ai_commit_author_claude_commit_count=author_counts["claude"],
        ai_commit_author_cursor_commit_count=author_counts["cursor"],
        ai_commit_coauthored_devin_commit_count=coauthor_counts["devin"],
        ai_commit_coauthored_sweep_commit_count=coauthor_counts["sweep"],
        ai_commit_coauthored_copilot_commit_count=coauthor_counts["copilot"],
        ai_commit_coauthored_codeium_commit_count=coauthor_counts["codeium"],
        ai_commit_coauthored_claude_commit_count=coauthor_counts["claude"],
        ai_commit_coauthored_cursor_commit_count=coauthor_counts["cursor"],
        ai_commit_total_ai_associated_count=total_ai,
        ai_commit_ai_associated_proportion=proportion,
        ai_commit_any_detected=total_ai > 0,
    )
