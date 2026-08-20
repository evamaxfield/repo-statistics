#!/usr/bin/env python

import hashlib
import logging
import os
import random
import shutil
import subprocess
from dataclasses import dataclass, field, make_dataclass
from datetime import date, datetime
from fnmatch import fnmatch
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Literal

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .utils import get_commit_hash_for_target_datetime

if TYPE_CHECKING:
    from transformers import Pipeline

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

# Sampling budgets for the fixed-budget stratified-random AI-detection sampling
# design. See `[[2026-08-20-ai-detection-at-scale-classification-plan]]` (Eva's
# original locked-in numbers, 2026-08-20) for why this shape was chosen. Two-stage
# funnel for function-granularity combos: sample _AI_DETECTION_CANDIDATE_FILE_COUNT
# files first (or all, if fewer), AST-parse only those to pool functions, then
# sample N functions from that pool. File-granularity combos sample N files
# directly, single-stage, no parsing needed. K (the candidate-file pool for the
# function funnel) stays a fixed internal implementation constant -- Eva asked for
# "the sample size" (N) to be configurable, not K. N itself is now a caller-supplied
# parameter on compute_ai_detection_metrics (default 100 per Eva's 2026-08-20
# instruction, superseding the original N=50/N=20 defaults from the plan above).
_AI_DETECTION_CANDIDATE_FILE_COUNT = 100  # K

###############################################################################


# AI-detection combo registry, mirroring sci_soft_models.ai_detection_clf.constants.
# Duplicated (not imported) deliberately: sci-soft-models is an optional dependency
# (`repo-statistics[ai]`) loaded lazily inside compute_ai_detection_metrics, so this
# module's dataclass generation at import time can't depend on it being installed.
_AI_DETECTION_BASE_MODELS = ["modern-bert", "codebert", "graphcodebert"]
_AI_DETECTION_DATASET_GRANULARITY: dict[str, Literal["function", "file"]] = {
    # "script" (aigcodeset) is stats-shape-equivalent to "function": one result per item.
    "paigsf": "function",
    "aigcodeset": "function",
    "codemirage": "file",
    "codet-m4": "function",
    "combined": "file",
}


def _ai_detection_stat_names(unit: Literal["function", "file"]) -> tuple[str, ...]:
    """Stat-field-name suffixes for one combo's aggregated N-sample results.

    Same shape for both granularities now that both are N-sample aggregates
    (previously file-granularity combos classified a single file per percentile
    and so only needed a single classification/confidence pair — now that they
    classify a sample of N files just like function-granularity combos classify a
    sample of N functions, both need the same aggregate stat set).
    """
    return (
        f"total_{unit}_count",
        f"ai_{unit}_count",
        f"human_{unit}_count",
        f"ai_{unit}_proportion",
        "ai_confidence_mean",
        "ai_confidence_std",
        "ai_confidence_median",
        "human_confidence_mean",
        "human_confidence_std",
        "human_confidence_median",
    )


_AI_DETECTION_FUNC_STAT_NAMES = _ai_detection_stat_names("function")
_AI_DETECTION_FILE_STAT_NAMES = _ai_detection_stat_names("file")


def _ai_detection_column_safe(name: str) -> str:
    """Turn a hyphenated combo/dataset/model key into a valid Python identifier."""
    return name.replace("-", "_")


def _all_ai_detection_combo_keys() -> dict[str, tuple[str, str]]:
    """Every valid combo key, mapped to its (base_model, dataset) pair.

    Mirrors sci_soft_models.ai_detection_clf.constants.all_ai_detection_combo_keys() —
    kept in sync by hand since this module can't import that (optional dependency).
    """
    return {
        f"{base_model}-{dataset}": (base_model, dataset)
        for base_model in _AI_DETECTION_BASE_MODELS
        for dataset in _AI_DETECTION_DATASET_GRANULARITY
    }


def _make_ai_detection_results_dataclass() -> type:
    """Build the AIDetectionResults dataclass with one field per combo x stat.

    Generated rather than hand-written: 15 combos x (10 or 2 stats, depending on the
    dataset's granularity) is ~90 fields, which isn't practical to maintain by hand
    and would only grow as more base models/datasets are added. The percentile
    dimension that used to triple every field (`p25`/`p50`/`p75`) is gone — the new
    sampling design computes one set of stats per repo-year per combo over the
    N-sample, not three percentile-conditioned sets.
    """
    fields: list[tuple[str, type, Any]] = [
        # Sample-auditing metadata, so downstream consumers can confirm the sampler
        # actually hit its target budgets rather than silently under-sampling
        # small repos. See the staged-rollout checks in the plan doc.
        ("ai_detection_unique_files_checked", int, field(default=0)),
        ("ai_detection_core_files_available_count", int, field(default=0)),
        ("ai_detection_files_sampled_count", int, field(default=0)),
        ("ai_detection_candidate_files_sampled_count", int, field(default=0)),
        ("ai_detection_functions_pooled_count", int, field(default=0)),
        ("ai_detection_functions_sampled_count", int, field(default=0)),
        ("ai_detection_cache_hits", int, field(default=0)),
        ("ai_detection_cache_misses", int, field(default=0)),
    ]
    for base_model, dataset in _all_ai_detection_combo_keys().values():
        dataset_col = _ai_detection_column_safe(dataset)
        model_col = _ai_detection_column_safe(base_model)
        granularity = _AI_DETECTION_DATASET_GRANULARITY[dataset]
        stat_names = (
            _AI_DETECTION_FUNC_STAT_NAMES
            if granularity == "function"
            else _AI_DETECTION_FILE_STAT_NAMES
        )
        stat_type = int | float | None
        for stat_name in stat_names:
            field_name = f"ai_detection_{dataset_col}_{model_col}_{stat_name}"
            fields.append((field_name, stat_type, field(default=None)))

    return make_dataclass(
        "AIDetectionResults",
        fields,
        bases=(DataClassJsonMixin,),
    )


AIDetectionResults = _make_ai_detection_results_dataclass()


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


def _empty_results() -> DataClassJsonMixin:
    # Every generated field defaults to 0 (unique_files_checked) or None (everything
    # else), so an "empty" result is just the dataclass's own defaults.
    return AIDetectionResults()


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
            fnmatch(f.name.lower(), pattern) for pattern in _EXCLUDE_TEST_FILENAME_PATTERNS
        )
    ]

    # Sorted deterministically (by path relative to repo_path) so that, given the same
    # seed, `random.Random(seed).sample(...)` over this list reproduces the same sample
    # across calls. `rglob` order is filesystem-dependent and not guaranteed stable
    # across separate checkouts/copies of the same commit, so without this sort the same
    # seed could still yield different samples purely from directory-iteration order.
    file_list = sorted(file_list, key=lambda f: str(f.relative_to(repo_path)))

    return file_list


###############################################################################


def compute_ai_detection_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal["authored_datetime", "committed_datetime"] = "authored_datetime",
    ai_detection_model_combos: "str | list[str]" = "ModernBERT",
    loaded_ai_detection_clf_models: "dict | None" = None,
    hf_token: str | None = None,
    ai_detection_result_cache: dict[str, dict[str, dict]] | None = None,
    # Controls reproducibility of the stratified-random sampling, not persistence of RNG
    # state across calls: same seed + same candidate file/function population at call
    # time -> same sample. A different population (files added/removed/changed between
    # timepoints) can still yield a different sample with the same seed -- expected, not
    # a bug, since the sample is drawn from a different population. Default None keeps
    # today's nondeterministic (fresh-entropy-per-call) behavior unchanged.
    ai_detection_sampling_seed: int | None = None,
    # N -- how many functions/files, respectively, to sample per repo-year for
    # function-granularity vs file-granularity combos. Two separate params since the
    # code already distinguishes the two granularities and they may legitimately want
    # different budgets later. Defaults match the original 2026-08-20 sampling-redesign
    # values (Eva's later "sample size, default 100" instruction referred to the number
    # of repos to process, not this per-repo function/file budget).
    ai_detection_function_sample_size: int = 50,
    ai_detection_file_sample_size: int = 20,
) -> DataClassJsonMixin:
    try:
        import numpy as np
        from nb_to_src import convert_directory
        from sci_soft_models.ai_detection_clf import (  # type: ignore[import-untyped]
            load_ai_detection_clf_models,  # type: ignore[misc]
            parse_python_source_file,
        )
    except ImportError as e:
        raise ImportError(
            f"Missing required dependency for AI detection: {e.name}. "
            "Please install with 'pip install repo-statistics[ai]' to use this feature."
        ) from e

    def _compute_aggregate_stats(unit: str, scored: "list[dict]") -> dict:
        """Aggregate stats over a combo's N-sample of classified functions/files.

        `scored` is a list of `{"label": "ai" | "human", "score": float}` dicts —
        one per sampled function (function-granularity combos) or per sampled file
        (file-granularity combos). Same shape either way, so one implementation
        covers both.
        """
        total = len(scored)
        if total == 0:
            return {
                f"total_{unit}_count": 0,
                f"ai_{unit}_count": None,
                f"human_{unit}_count": None,
                f"ai_{unit}_proportion": None,
                "ai_confidence_mean": None,
                "ai_confidence_std": None,
                "ai_confidence_median": None,
                "human_confidence_mean": None,
                "human_confidence_std": None,
                "human_confidence_median": None,
            }
        ai_items = [s for s in scored if s["label"] == "ai"]
        human_items = [s for s in scored if s["label"] != "ai"]
        ai_count = len(ai_items)
        human_count = len(human_items)
        ai_proportion = ai_count / total

        def _stats(
            items: "list[dict]",
        ) -> "tuple[float | None, float | None, float | None]":
            if not items:
                return None, None, None
            scores = np.array([i["score"] for i in items])
            return float(np.mean(scores)), float(np.std(scores)), float(np.median(scores))

        ai_mean, ai_std, ai_median = _stats(ai_items)
        human_mean, human_std, human_median = _stats(human_items)
        return {
            f"total_{unit}_count": total,
            f"ai_{unit}_count": ai_count,
            f"human_{unit}_count": human_count,
            f"ai_{unit}_proportion": ai_proportion,
            "ai_confidence_mean": ai_mean,
            "ai_confidence_std": ai_std,
            "ai_confidence_median": ai_median,
            "human_confidence_mean": human_mean,
            "human_confidence_std": human_std,
            "human_confidence_median": human_median,
        }

    # Exact-text cache, keyed cache[combo_key][sha256_hex(text)] = {"label", "score"}.
    # A caller looping over a repo's annual timepoints can pass the same dict back in
    # on each call to skip reclassifying functions/files whose text hasn't changed
    # since a prior timepoint. Default to a fresh dict when the caller doesn't opt in,
    # so behavior is unchanged for every existing caller today.
    cache: dict[str, dict[str, dict]] = (
        ai_detection_result_cache if ai_detection_result_cache is not None else {}
    )
    cache_hits = 0
    cache_misses = 0

    # Local RNG instance, not the module-level `random` functions: this function may run
    # concurrently across threads/Coiled workers, and mutating global RNG state would be
    # thread-unsafe and would pollute other unrelated code paths' randomness.
    # `random.Random(None)` seeds from system entropy identically to the module-level
    # default, so this is a behavior-neutral drop-in when no seed is passed.
    rng = random.Random(ai_detection_sampling_seed)

    def _classify_cached(combo_key: str, text: str, clf: "Pipeline") -> dict:
        nonlocal cache_hits, cache_misses
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        combo_cache = cache.setdefault(combo_key, {})
        cached = combo_cache.get(text_hash)
        if cached is not None:
            cache_hits += 1
            return cached
        cache_misses += 1
        output = clf([text])[0]
        scored = {"label": output["label"], "score": output["score"]}
        combo_cache[text_hash] = scored
        return scored

    print(
        "Within compute_ai_detection_metrics..."
    )  # Debug print to confirm function is being called

    # Resolve HF token: explicit param takes priority over environment variable.
    # Set in environment so HuggingFace Hub picks it up when loading the model.
    resolved_token = hf_token or os.environ.get("HF_TOKEN")
    if resolved_token is not None:
        os.environ["HF_TOKEN"] = resolved_token

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
            core_files_available_count = len(core_files)
            if not core_files:
                return _empty_results()
            print(
                f"Found {len(core_files)} core Python files to analyze for AI detection."
            )  # Debug print

            if loaded_ai_detection_clf_models is None:
                print(
                    "No pre-loaded AI detection models provided; loading now (may be slow)..."
                )
                clf_models = load_ai_detection_clf_models(combos=ai_detection_model_combos)
            else:
                clf_models = loaded_ai_detection_clf_models

            combo_registry = _all_ai_detection_combo_keys()
            func_combo_keys = [
                k
                for k in clf_models
                if _AI_DETECTION_DATASET_GRANULARITY[combo_registry[k][1]] == "function"
            ]
            file_combo_keys = [
                k
                for k in clf_models
                if _AI_DETECTION_DATASET_GRANULARITY[combo_registry[k][1]] == "file"
            ]

            # File-granularity sampling: single-stage, sample N files directly (no
            # parsing needed — the whole file's text is the classification unit).
            file_texts: list[str] = []
            if file_combo_keys:
                file_sample_size = min(ai_detection_file_sample_size, len(core_files))
                sampled_files = rng.sample(core_files, file_sample_size)
                for f in sampled_files:
                    try:
                        file_texts.append(f.read_text())
                    except (OSError, UnicodeDecodeError) as e:
                        print(f"Failed to read {f} for file-level AI detection: {e}")
            files_sampled_count = len(file_texts)

            # Function-granularity sampling: bounded two-stage funnel. Sample K
            # candidate files first (cheap — plain file listing), AST-parse only
            # those to pool functions, then sample N functions from the pool. This
            # bounds both files-read and files-parsed to K regardless of repo size.
            function_texts: list[str] = []
            candidate_files_sampled_count = 0
            functions_pooled_count = 0
            if func_combo_keys:
                candidate_file_count = min(_AI_DETECTION_CANDIDATE_FILE_COUNT, len(core_files))
                candidate_files = rng.sample(core_files, candidate_file_count)
                candidate_files_sampled_count = len(candidate_files)

                pooled_functions: list[str] = []
                for f in candidate_files:
                    try:
                        pooled_functions.extend(parse_python_source_file(f).values())
                    except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as e:
                        print(f"Failed to parse {f} for function-level AI detection: {e}")
                functions_pooled_count = len(pooled_functions)

                function_sample_size = min(
                    ai_detection_function_sample_size, len(pooled_functions)
                )
                function_texts = rng.sample(pooled_functions, function_sample_size)
            functions_sampled_count = len(function_texts)

            print(
                f"Sampled {files_sampled_count} files and {functions_sampled_count} "
                f"functions (from {candidate_files_sampled_count} candidate files, "
                f"{functions_pooled_count} functions pooled) for AI detection."
            )  # Debug print

            all_fields: dict = {
                "ai_detection_unique_files_checked": (
                    files_sampled_count + candidate_files_sampled_count
                ),
                "ai_detection_core_files_available_count": core_files_available_count,
                "ai_detection_files_sampled_count": files_sampled_count,
                "ai_detection_candidate_files_sampled_count": candidate_files_sampled_count,
                "ai_detection_functions_pooled_count": functions_pooled_count,
                "ai_detection_functions_sampled_count": functions_sampled_count,
            }

            for combo_key in clf_models:
                base_model, dataset = combo_registry[combo_key]
                dataset_col = _ai_detection_column_safe(dataset)
                model_col = _ai_detection_column_safe(base_model)
                granularity = _AI_DETECTION_DATASET_GRANULARITY[dataset]
                clf = clf_models[combo_key]

                if granularity == "function":
                    scored = [_classify_cached(combo_key, text, clf) for text in function_texts]
                    stats = _compute_aggregate_stats("function", scored)
                else:
                    scored = [_classify_cached(combo_key, text, clf) for text in file_texts]
                    stats = _compute_aggregate_stats("file", scored)

                for stat_name, value in stats.items():
                    all_fields[f"ai_detection_{dataset_col}_{model_col}_{stat_name}"] = value

            all_fields["ai_detection_cache_hits"] = cache_hits
            all_fields["ai_detection_cache_misses"] = cache_misses

            print("Computed AI detection statistics for sampled functions/files.")  # Debug
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
