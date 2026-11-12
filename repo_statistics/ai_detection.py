#!/usr/bin/env python

import ast
import hashlib
import logging
import os
import random
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field, make_dataclass
from difflib import SequenceMatcher
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .contribution_types import AGENT_PATTERNS, COMMIT_MARKERS, CommitTrailerInfo
from .utils import AnalysisTimeoutError, Deadline, checked_subprocess_timeout

if TYPE_CHECKING:
    from datetime import datetime

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

# Fixed-budget stratified-random AI-detection sampling. Two-stage funnel for
# function-granularity combos: sample _AI_DETECTION_CANDIDATE_FILE_COUNT files
# first (or all, if fewer), AST-parse only those to pool functions, then
# sample N functions from that pool. File-granularity combos sample N files
# directly, single-stage, no parsing needed. K (the candidate-file pool for the
# function funnel) is a fixed internal constant; N is a caller-supplied
# parameter on compute_ai_detection_metrics (default 100).
_AI_DETECTION_CANDIDATE_FILE_COUNT = 100  # K
# Caps per-forward-pass GPU memory when a batch of cache-miss texts is inferred at once.
_AI_DETECTION_INFERENCE_BATCH_SIZE = 16
# Minimum line counts before a function/file is eligible for the sampling pool at all --
# below these, there isn't enough signal to classify with confidence (a one-line getter
# or a near-empty file is noise). Applied before random sampling, not after. Set to the
# 5th percentile of line counts across the training datasets (paigsf/codet-m4 for
# functions, codemirage for files) so the inference-time floor matches training reality.
_AI_DETECTION_MIN_FUNCTION_LINE_COUNT = 3
_AI_DETECTION_MIN_FILE_LINE_COUNT = 50

# Default combo set for compute_ai_detection_metrics / analyze_repository /
# analyze_repositories -- a tuple, not a list, so it's safe to reference directly as a
# default value (ruff B006 flags mutable list/dict defaults since they're shared across
# calls); each call site converts it to a real list before use, since downstream
# resolve_ai_detection_model_combos() requires isinstance(combos, list).
DEFAULT_AI_DETECTION_MODEL_COMBOS: tuple[str, ...] = (
    "modern-bert-combined",
    "modern-bert-aidev-pop",
)

###############################################################################


# AI-detection combo registry. Pulled live from sci_soft_models.ai_detection_clf.constants
# (the source of truth) when that optional dependency (`repo-statistics[ai]`) is installed,
# so a new dataset/model added there needs no hand-sync here. Falls back to a hardcoded
# mirror when the extra isn't installed, since this module's dataclass generation runs at
# import time and repo_statistics.main imports ai_detection unconditionally -- `import
# repo_statistics` must keep working without the extra. A combo added on the sci-soft-models
# side won't resolve via the fallback until it's copied down, but an environment lacking the
# extra can't load or run the model anyway, so that's a soft staleness, not a correctness gap.
_Granularity = Literal["function", "file"]
try:
    from sci_soft_models.ai_detection_clf.constants import (  # type: ignore[import-untyped]
        AI_DETECTION_BASE_MODELS as _AI_DETECTION_BASE_MODELS,
    )
    from sci_soft_models.ai_detection_clf.constants import (  # type: ignore[import-untyped]
        DATASET_CONFIGS as _SCI_SOFT_MODELS_DATASET_CONFIGS,
    )

    _AI_DETECTION_DATASET_GRANULARITY: dict[str, _Granularity] = {
        # "script" (aigcodeset) is stats-shape-equivalent to "function": one result per item.
        dataset: cast(
            "_Granularity",
            "function" if config.granularity in ("function", "script") else "file",
        )
        for dataset, config in _SCI_SOFT_MODELS_DATASET_CONFIGS.items()
        if not config.eval_only
    }
except ImportError:
    _AI_DETECTION_BASE_MODELS = ["modern-bert", "codebert", "graphcodebert"]
    _AI_DETECTION_DATASET_GRANULARITY = {
        "paigsf": "function",
        "aigcodeset": "function",
        "codemirage": "file",
        "codet-m4": "function",
        "combined": "file",
        "swe-chat": "function",
        "aidev-pop": "function",
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


def _ai_detection_combo_fields(prefix: str) -> list[tuple[str, type, Any]]:
    """One field per combo x stat, named `{prefix}{dataset}_{model}_{stat}`."""
    fields: list[tuple[str, type, Any]] = []
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
            field_name = f"{prefix}{dataset_col}_{model_col}_{stat_name}"
            fields.append((field_name, stat_type, field(default=None)))
    return fields


def _make_ai_detection_results_dataclass() -> type:
    """Build the AIDetectionResults dataclass with one field per combo x stat.

    Generated rather than hand-written: 15 combos x (10 or 2 stats, depending on the
    dataset's granularity) is ~90 fields, which isn't practical to maintain by hand
    and would only grow as more base models/datasets are added. The percentile
    dimension that used to triple every field (`p25`/`p50`/`p75`) is gone — the new
    sampling design computes one set of stats per repo-year per combo over the
    N-sample, not three percentile-conditioned sets. The new-code (`ai_detection_new_`)
    set repeats the same per-combo fields for the code added since the previous
    year-end commit.
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
    fields.extend(_ai_detection_combo_fields("ai_detection_"))

    fields.append(("ai_detection_new_status", str | None, field(default=None)))
    fields.append(("ai_detection_new_base_commit_hash", str | None, field(default=None)))
    for new_count_name in (
        "added_files_count",
        "modified_files_count",
        "added_lines_count",
        "file_units_pooled_count",
        "whole_file_units_scored_count",
        "snippet_units_scored_count",
        "candidate_files_sampled_count",
        "functions_pooled_count",
        "functions_sampled_count",
    ):
        fields.append((f"ai_detection_new_{new_count_name}", int | None, field(default=None)))
    fields.append(("ai_detection_new_elapsed_seconds", float | None, field(default=None)))
    fields.extend(_ai_detection_combo_fields("ai_detection_new_"))

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
    ai_agent_config_gemini_md_exists: bool
    ai_agent_config_claude_dir_exists: bool
    ai_agent_config_cursor_dir_exists: bool
    ai_agent_config_copilot_path_instructions_exists: bool
    ai_agent_config_windsurf_dir_exists: bool
    ai_agent_config_any_exists: bool
    # ISO datetime of the earliest commit adding the path; None if never added in history
    ai_agent_config_claude_md_first_added_datetime: str | None
    ai_agent_config_cursor_rules_first_added_datetime: str | None
    ai_agent_config_copilot_instructions_first_added_datetime: str | None
    ai_agent_config_aider_first_added_datetime: str | None
    ai_agent_config_cline_rules_first_added_datetime: str | None
    ai_agent_config_windsurf_rules_first_added_datetime: str | None
    ai_agent_config_agents_md_first_added_datetime: str | None
    ai_agent_config_gemini_md_first_added_datetime: str | None
    ai_agent_config_claude_dir_first_added_datetime: str | None
    ai_agent_config_cursor_dir_first_added_datetime: str | None
    ai_agent_config_copilot_path_instructions_first_added_datetime: str | None
    ai_agent_config_windsurf_dir_first_added_datetime: str | None
    ai_agent_config_any_first_added_datetime: str | None


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
            part.lower() in _EXCLUDE_DIR_NAMES for part in f.relative_to(repo_path).parts[:-1]
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


# New-code scoring helpers: the code a repo gained between a base commit (the previous
# year-end) and the target commit, split into file-level and function-level units.


class _ChangedFile(NamedTuple):
    """One `git diff --name-status` entry; dicts of these are keyed by the new path."""

    status: str  # first letter of git's status: "A" added, "M" modified, "R" renamed
    old_path: str

    @property
    def is_added(self) -> bool:
        return self.status == "A"


class _ModifiedNotebook(NamedTuple):
    old_path: str
    new_script_text: str  # the target-commit notebook, already converted to .py


def _is_notebook(rel: str) -> bool:
    return rel.endswith(".ipynb")


def _as_script_relpath(rel: str) -> str:
    """Map a notebook path to its converted script (`a/b.ipynb` -> `a/b.py`)."""
    return rel[: -len(".ipynb")] + ".py" if _is_notebook(rel) else rel


def _split_lines(text: str) -> list[str]:
    """Split on newlines only, so line numbers match git's."""
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return lines


def _unit_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _make_unit(
    text: str,
    scope: str,
    unit_type: str,
    file_path: str,
    from_notebook: bool,
    function_name: str | None = None,
    line_count: int | None = None,
    changed_line_fraction: float | None = None,
) -> dict:
    """One classification unit plus the metadata written to its per-unit score rows."""
    return {
        "text": text,
        "scope": scope,
        "unit_type": unit_type,
        "file_path": file_path,
        "from_notebook": from_notebook,
        "function_name": function_name,
        "unit_hash": _unit_hash(text),
        "line_count": len(text.splitlines()) if line_count is None else line_count,
        "changed_line_fraction": changed_line_fraction,
    }


def _unit_score_rows(
    combo_key: str,
    units: list[dict],
    scored: list[dict],
    base_commit_hash: str | None,
    target_commit_hash: str | None,
) -> list[dict]:
    """One row per scored unit for one combo (the per-unit side output)."""
    return [
        {
            "model": combo_key,
            "scope": unit["scope"],
            "unit_type": unit["unit_type"],
            "file_path": unit["file_path"],
            "from_notebook": unit["from_notebook"],
            "function_name": unit["function_name"],
            "unit_hash": unit["unit_hash"],
            "line_count": unit["line_count"],
            "changed_line_fraction": unit["changed_line_fraction"],
            # The classifier reports its confidence in the predicted label; store P(ai).
            "ai_probability": (
                result["score"] if result["label"] == "ai" else 1 - result["score"]
            ),
            "label": result["label"],
            "base_commit_hash": base_commit_hash,
            "target_commit_hash": target_commit_hash,
        }
        for unit, result in zip(units, scored, strict=True)
    ]


def _is_core_python_relpath(rel: PurePosixPath) -> bool:
    """Repo-relative twin of `_get_core_python_file_set`'s filters."""
    if any(part.lower() in _EXCLUDE_DIR_NAMES for part in rel.parts[:-1]):
        return False
    if rel.name in _EXCLUDE_PACKAGING_FILENAMES:
        return False
    return not any(
        fnmatch(rel.name.lower(), pattern) for pattern in _EXCLUDE_TEST_FILENAME_PATTERNS
    )


def _run_git(args: list[str], cwd: Path, deadline: Deadline) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        check=True,
        timeout=checked_subprocess_timeout(deadline, 60),
    )
    return result.stdout


def _parse_name_status(output: str) -> dict[str, _ChangedFile]:
    """Parse `git diff --name-status -z` into {new_path: _ChangedFile}."""
    tokens = output.split("\0")
    parsed: dict[str, _ChangedFile] = {}
    i = 0
    while i < len(tokens) and tokens[i]:
        status = tokens[i]
        # Renames and copies carry two paths (old, then new); everything else carries one.
        if status[0] in "RC":
            parsed[tokens[i + 2]] = _ChangedFile(status[0], tokens[i + 1])
            i += 3
        else:
            parsed[tokens[i + 1]] = _ChangedFile(status[0], tokens[i + 1])
            i += 2
    return parsed


def _parse_numstat(output: str) -> dict[str, int]:
    """Parse `git diff --numstat -z` into {new_path: added line count}."""
    tokens = output.split("\0")
    parsed: dict[str, int] = {}
    i = 0
    while i < len(tokens) and tokens[i]:
        added, _, path = tokens[i].split("\t", 2)
        # A rename leaves the path empty and puts the old and new paths in the next tokens.
        if path:
            i += 1
        else:
            path = tokens[i + 2]
            i += 3
        # Binary files report "-" instead of a count.
        parsed[path] = int(added) if added.isdigit() else 0
    return parsed


_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _added_lines_by_file(diff_output: str) -> dict[str, set[int]]:
    """Collect added line numbers (in the new file) per path from a `git diff -U0` patch."""
    added_by_file: dict[str, set[int]] = {}
    # Added-line set of the file being read; None while skipping a file.
    current: set[int] | None = None
    # Lines still to read in the current hunk, and the new-file number of the next added line.
    old_left = new_left = next_new = 0
    for line in diff_output.split("\n"):
        if old_left > 0 and line.startswith("-"):
            old_left -= 1
        elif new_left > 0 and line.startswith("+"):
            if current is not None:
                current.add(next_new)
            next_new += 1
            new_left -= 1
        elif line.startswith("\\"):
            # "\ No newline at end of file"
            continue
        elif line.startswith("+++ "):
            # Git tab-terminates header names that contain spaces.
            name = line[4:].rstrip("\t")
            # Quoted paths (tabs, quotes, newlines in the name) are skipped.
            current = (
                added_by_file.setdefault(name[2:], set()) if name.startswith("b/") else None
            )
        elif match := _HUNK_HEADER_RE.match(line):
            # "@@ -a[,b] +c[,d] @@": b lines removed, d lines added from line c; counts
            # default to 1.
            old_left = int(match[1]) if match[1] is not None else 1
            next_new = int(match[2])
            new_left = int(match[3]) if match[3] is not None else 1
    return added_by_file


def _strip_whitespace(lines: list[str]) -> list[str]:
    return ["".join(line.split()) for line in lines]


def _whitespace_insensitive_added_lines(old_text: str, new_text: str) -> set[int]:
    """Line numbers of `new_text` inserted or replaced relative to `old_text`, ignoring
    whitespace like `git diff -w`.
    """
    matcher = SequenceMatcher(
        None,
        _strip_whitespace(_split_lines(old_text)),
        _strip_whitespace(_split_lines(new_text)),
        autojunk=False,
    )
    added: set[int] = set()
    for tag, _, _, new_start, new_end in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            added.update(range(new_start + 1, new_end + 1))
    return added


def _notebook_added_lines(
    notebooks: dict[str, _ModifiedNotebook],
    base_commit: str,
    repo_dir: Path,
    deadline: Deadline,
) -> dict[str, set[int]]:
    """Find added lines of modified notebooks by converting each base-commit notebook and
    diffing the old and new scripts. Git's own diff is over notebook JSON, so unusable here.
    """
    added_by_file: dict[str, set[int]] = {}
    with TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        out_dir = tmp_dir / "out"

        # Write each notebook's base-commit JSON under a unique temp name.
        old_notebook_files: dict[str, Path] = {}
        for i, (rel, notebook) in enumerate(notebooks.items()):
            old_file = tmp_dir / f"nb{i}.ipynb"
            old_file.write_text(
                _run_git(["show", f"{base_commit}:{notebook.old_path}"], repo_dir, deadline),
                encoding="utf-8",
            )
            old_notebook_files[rel] = old_file

        # One nbconvert call for all of them; same exporter as nb_to_src, so the old and
        # new scripts are formatted alike.
        subprocess.run(
            [
                "jupyter",
                "nbconvert",
                "--to",
                "script",
                "--output-dir",
                str(out_dir),
                *map(str, old_notebook_files.values()),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=checked_subprocess_timeout(deadline, 120),
        )

        for rel, old_file in old_notebook_files.items():
            old_script = out_dir / f"{old_file.stem}.py"
            # No .py output: the old version failed to convert or isn't a Python notebook.
            if not old_script.exists():
                continue
            added_by_file[rel] = _whitespace_insensitive_added_lines(
                old_script.read_text(), notebooks[rel].new_script_text
            )
    return added_by_file


def _added_lines_text(lines: list[str], added: set[int]) -> tuple[str, int]:
    """Join the added lines in file order, with one blank line between separate hunks.

    Returns the snippet and its added-line count (separators not counted).
    """
    added_in_file = sorted(n for n in added if 1 <= n <= len(lines))
    out: list[str] = []
    previous: int | None = None
    for number in added_in_file:
        if previous is not None and number != previous + 1:
            out.append("")
        out.append(lines[number - 1])
        previous = number
    return "\n".join(out) + "\n", len(added_in_file)


def _function_line_spans(text: str, name_prefix: str) -> dict[str, tuple[int, int]]:
    """Line span per function key, mirroring sci_soft_models' function traversal."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    spans: dict[str, tuple[int, int]] = {}

    # Recurse into classes (which extend the key) and other blocks, never into function
    # bodies, so keys match `parse_python_source_file` one-to-one.
    def _walk(nodes: list[ast.AST], path_prefix: list[str]) -> None:
        for node in nodes:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                key = f"{name_prefix}.{'.'.join([*path_prefix, node.name])}"
                spans[key] = (node.lineno, node.end_lineno or node.lineno)
            elif isinstance(node, ast.ClassDef):
                _walk(list(ast.iter_child_nodes(node)), [*path_prefix, node.name])
            else:
                _walk(list(ast.iter_child_nodes(node)), path_prefix)

    _walk(list(ast.iter_child_nodes(tree)), [])
    return spans


def _changed_line_fraction(lines: list[str], added: set[int], start: int, end: int) -> float:
    """Share of a span's non-blank lines that were added."""
    nonblank = [n for n in range(start, min(end, len(lines)) + 1) if lines[n - 1].strip()]
    if not nonblank:
        return 0.0
    return sum(1 for n in nonblank if n in added) / len(nonblank)


def _find_new_code_candidates(
    base_commit: str,
    target_commit: str,
    repo_dir: Path,
    deadline: Deadline,
) -> tuple[dict[str, _ChangedFile], dict[str, int]]:
    """Core .py/.ipynb files that gained code since the base commit, plus the numstat
    added-line count of every changed file.
    """
    pathspec = ["--", "*.py", "*.ipynb"]
    # Added, modified and renamed files, with each one's path at the base commit.
    name_status = _parse_name_status(
        _run_git(
            [
                *["diff", "--name-status", "-z", "-M", "--diff-filter=AMR"],
                *[base_commit, target_commit, *pathspec],
            ],
            repo_dir,
            deadline,
        )
    )
    # Added-line counts that ignore whitespace; whitespace-only edits are left out entirely.
    added_line_counts = _parse_numstat(
        _run_git(
            ["diff", "--numstat", "-z", "-M", "-w", base_commit, target_commit, *pathspec],
            repo_dir,
            deadline,
        )
    )

    candidates: dict[str, _ChangedFile] = {}
    for rel, changed in name_status.items():
        added = added_line_counts.get(rel)
        # Whitespace-only edits (no numstat entry) and pure renames (0 added) drop out.
        if added is None or (not changed.is_added and added == 0):
            continue
        # Same test/packaging/excluded-dir filters as the snapshot, on the script path.
        if _is_core_python_relpath(PurePosixPath(_as_script_relpath(rel))):
            candidates[rel] = changed
    return candidates, added_line_counts


def _read_new_code_texts(
    rels: list[str],
    temp_dir: Path,
    notebook_scripts: dict[str, Path],
    deadline: Deadline,
) -> tuple[dict[str, str], dict[str, Path]]:
    """Read each file's target-commit text from the temp copy (a notebook's converted
    script). Returns {rel: text} and {rel: script path}, skipping unreadable files.
    """
    texts: dict[str, str] = {}
    script_paths: dict[str, Path] = {}
    for rel in rels:
        deadline.check()
        script = notebook_scripts.get(rel) if _is_notebook(rel) else temp_dir / rel
        # Notebooks that failed to convert or aren't Python have no .py script.
        if script is None or script.suffix != ".py":
            continue
        try:
            texts[rel] = script.read_text()
        except (OSError, UnicodeDecodeError) as e:
            print(f"Failed to read {script} for new-code AI detection: {e}")
            continue
        script_paths[rel] = script
    return texts, script_paths


def _find_added_lines(
    texts: dict[str, str],
    candidates: dict[str, _ChangedFile],
    base_commit: str,
    target_commit: str,
    repo_dir: Path,
    deadline: Deadline,
) -> dict[str, set[int]]:
    """Find the added line numbers (in the target text) of each read file. Files whose
    added lines can't be recovered are left out.
    """
    modified_py = [
        rel for rel in texts if not candidates[rel].is_added and not _is_notebook(rel)
    ]
    modified_notebooks = {
        rel: _ModifiedNotebook(candidates[rel].old_path, texts[rel])
        for rel in texts
        if not candidates[rel].is_added and _is_notebook(rel)
    }

    modified_added: dict[str, set[int]] = {}
    # Modified .py files: one zero-context, whitespace-insensitive diff covering all of
    # them; old paths are included so renames still pair up.
    if modified_py:
        diff_paths = sorted({*modified_py, *(candidates[rel].old_path for rel in modified_py)})
        modified_added = _added_lines_by_file(
            _run_git(
                [
                    *["--literal-pathspecs", "-c", "core.quotePath=false", "diff"],
                    *["-M", "-w", "-U0", "--no-color", "--no-ext-diff"],
                    *["--src-prefix=a/", "--dst-prefix=b/", base_commit, target_commit],
                    *["--", *diff_paths],
                ],
                repo_dir,
                deadline,
            )
        )
    # Modified notebooks: diff the converted old and new scripts instead.
    if modified_notebooks:
        modified_added.update(
            _notebook_added_lines(modified_notebooks, base_commit, repo_dir, deadline)
        )

    added_by_rel: dict[str, set[int]] = {}
    for rel, text in texts.items():
        # Every line of a new file is an added line.
        if candidates[rel].is_added:
            added_by_rel[rel] = set(range(1, len(_split_lines(text)) + 1))
        elif rel in modified_added:
            added_by_rel[rel] = modified_added[rel]
    return added_by_rel


def _build_file_units(
    file_sample: list[str],
    texts: dict[str, str],
    candidates: dict[str, _ChangedFile],
    added_by_rel: dict[str, set[int]],
) -> list[dict]:
    """File-level units: a new file's whole text, or a modified file's added lines as one
    snippet. Units under the file-level line floor are dropped.
    """
    file_units: list[dict] = []
    for rel in file_sample:
        if rel not in added_by_rel:
            continue
        text = texts[rel]
        if candidates[rel].is_added:
            unit_text, line_count = text, len(text.splitlines())
            scope, unit_type = "new_file", "file"
        else:
            unit_text, line_count = _added_lines_text(_split_lines(text), added_by_rel[rel])
            scope, unit_type = "added_lines", "snippet"
        if line_count < _AI_DETECTION_MIN_FILE_LINE_COUNT:
            continue
        file_units.append(
            _make_unit(
                unit_text,
                scope,
                unit_type,
                _as_script_relpath(rel),
                _is_notebook(rel),
                line_count=line_count,
            )
        )
    return file_units


def _pool_changed_functions(
    funnel_sample: list[str],
    texts: dict[str, str],
    script_paths: dict[str, Path],
    added_by_rel: dict[str, set[int]],
    parse_functions: Callable[[Path], dict[str, str]],
    deadline: Deadline,
) -> list[dict]:
    """Function-level units: every function in the funnel files that has at least one
    added non-blank line, tagged with its changed-line fraction.
    """
    pooled_functions: list[dict] = []
    for rel in funnel_sample:
        deadline.check()
        if rel not in added_by_rel:
            continue
        script = script_paths[rel]
        try:
            parsed_functions = parse_functions(script)
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as e:
            print(f"Failed to parse {script} for new-code function-level AI detection: {e}")
            continue
        lines = _split_lines(texts[rel])
        # The parser returns function texts only, so line spans are looked up by key.
        spans = _function_line_spans(texts[rel], script.stem)
        for name, function_text in parsed_functions.items():
            span = spans.get(name)
            if (
                span is None
                or len(function_text.splitlines()) < _AI_DETECTION_MIN_FUNCTION_LINE_COUNT
            ):
                continue
            # Untouched functions (fraction 0) stay out; the fraction itself is stored,
            # not thresholded.
            fraction = _changed_line_fraction(lines, added_by_rel[rel], *span)
            if fraction > 0:
                pooled_functions.append(
                    _make_unit(
                        function_text,
                        "changed_function",
                        "function",
                        _as_script_relpath(rel),
                        _is_notebook(rel),
                        name,
                        changed_line_fraction=fraction,
                    )
                )
    return pooled_functions


###############################################################################


def compute_ai_detection_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    ai_detection_model_combos: "str | list[str] | None" = None,
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
    # code already distinguishes the two granularities and may want different
    # budgets. Not to be confused with compute_ai_detection_metrics' unrelated
    # "sample size" param, which controls the number of repos to process.
    ai_detection_function_sample_size: int = 50,
    ai_detection_file_sample_size: int = 20,
    deadline: Deadline | None = None,
    compute_new_code_ai_detection: bool = True,
    ai_detection_new_code_timeout_seconds: float = 60.0,
    # Sink for one row per scored unit and model; the caller passes a fresh list per call.
    ai_detection_unit_scores: list[dict] | None = None,
    new_code_base_commit: str | None = None,
    new_code_target_commit: str | None = None,
) -> DataClassJsonMixin:
    if ai_detection_model_combos is None:
        ai_detection_model_combos = list(DEFAULT_AI_DETECTION_MODEL_COMBOS)

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

    def _classify_batch_cached(
        combo_key: str,
        texts: list[str],
        clf: "Pipeline",
        batch_deadline: Deadline | None = None,
    ) -> list[dict]:
        nonlocal cache_hits, cache_misses
        active_deadline = batch_deadline if batch_deadline is not None else deadline
        combo_cache = cache.setdefault(combo_key, {})
        results: list[dict | None] = [None] * len(texts)
        miss_indices: list[int] = []
        miss_texts: list[str] = []
        for i, text in enumerate(texts):
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            cached = combo_cache.get(text_hash)
            if cached is not None:
                cache_hits += 1
                results[i] = cached
            else:
                cache_misses += 1
                miss_indices.append(i)
                miss_texts.append(text)

        # Sorting by length cuts padding; predictions don't depend on batch composition.
        order = sorted(range(len(miss_texts)), key=lambda j: len(miss_texts[j]))
        miss_indices = [miss_indices[j] for j in order]
        miss_texts = [miss_texts[j] for j in order]

        # Chunk inference so the deadline is checked between batches rather than only
        # before an unbounded whole-sample run.
        for start in range(0, len(miss_texts), _AI_DETECTION_INFERENCE_BATCH_SIZE):
            if active_deadline is not None:
                active_deadline.check()
            batch_indices = miss_indices[start : start + _AI_DETECTION_INFERENCE_BATCH_SIZE]
            batch_texts = miss_texts[start : start + _AI_DETECTION_INFERENCE_BATCH_SIZE]
            outputs = clf(batch_texts, batch_size=_AI_DETECTION_INFERENCE_BATCH_SIZE)
            for i, text, output in zip(batch_indices, batch_texts, outputs, strict=True):
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                scored = {"label": output["label"], "score": output["score"]}
                combo_cache[text_hash] = scored
                results[i] = scored

        return cast("list[dict]", results)

    def _compute_new_code_fields(
        new_code_deadline: Deadline,
        repo_dir: Path,
        temp_dir: Path,
        notebook_scripts: dict[str, Path],
        clf_models: dict,
        combo_registry: dict[str, tuple[str, str]],
        func_combo_keys: list[str],
        file_combo_keys: list[str],
    ) -> tuple[dict, list[dict]]:
        """Score the code added between `new_code_base_commit` and the target commit."""
        base_commit = cast("str", new_code_base_commit)
        target_commit = new_code_target_commit or "HEAD"

        # 1. Candidate files: core .py/.ipynb files that gained code since the base.
        candidates, added_line_counts = _find_new_code_candidates(
            base_commit, target_commit, repo_dir, new_code_deadline
        )
        candidate_rels = sorted(candidates)
        added_files_count = sum(1 for changed in candidates.values() if changed.is_added)
        # Notebook numstat counts JSON lines, so notebooks are left out of the line total.
        added_lines_count = sum(
            added_line_counts[rel] for rel in candidate_rels if not _is_notebook(rel)
        )

        # 2. Two samples from the candidates, drawn in this order so a seed reproduces them.
        # File sample: .py files whose numstat already clears the line floor, plus every
        # notebook (its JSON numstat can't be compared; the floor is applied to its unit).
        file_pool = [
            rel
            for rel in candidate_rels
            if _is_notebook(rel) or added_line_counts[rel] >= _AI_DETECTION_MIN_FILE_LINE_COUNT
        ]
        file_sample: list[str] = []
        if file_combo_keys:
            file_sample = rng.sample(
                file_pool, min(ai_detection_file_sample_size, len(file_pool))
            )
        # Funnel sample: up to K candidate files to parse for changed functions, the same
        # two-stage funnel as the snapshot.
        funnel_sample: list[str] = []
        if func_combo_keys:
            funnel_sample = rng.sample(
                candidate_rels, min(_AI_DETECTION_CANDIDATE_FILE_COUNT, len(candidate_rels))
            )

        # 3. Read each sampled file once, even if it is in both samples.
        texts, script_paths = _read_new_code_texts(
            list(dict.fromkeys([*file_sample, *funnel_sample])),
            temp_dir,
            notebook_scripts,
            new_code_deadline,
        )

        # 4. Which lines of each read file are new since the base commit.
        added_by_rel = _find_added_lines(
            texts, candidates, base_commit, target_commit, repo_dir, new_code_deadline
        )

        # 5. Build the units: whole-file/snippet units, then sampled changed functions.
        file_units = _build_file_units(file_sample, texts, candidates, added_by_rel)
        pooled_functions = _pool_changed_functions(
            funnel_sample,
            texts,
            script_paths,
            added_by_rel,
            parse_python_source_file,
            new_code_deadline,
        )
        sampled_function_units = rng.sample(
            pooled_functions, min(ai_detection_function_sample_size, len(pooled_functions))
        )

        fields: dict[str, Any] = {
            "ai_detection_new_added_files_count": added_files_count,
            "ai_detection_new_modified_files_count": len(candidates) - added_files_count,
            "ai_detection_new_added_lines_count": added_lines_count,
            "ai_detection_new_file_units_pooled_count": len(file_pool),
            "ai_detection_new_whole_file_units_scored_count": sum(
                1 for u in file_units if u["scope"] == "new_file"
            ),
            "ai_detection_new_snippet_units_scored_count": sum(
                1 for u in file_units if u["scope"] == "added_lines"
            ),
            "ai_detection_new_candidate_files_sampled_count": len(funnel_sample),
            "ai_detection_new_functions_pooled_count": len(pooled_functions),
            "ai_detection_new_functions_sampled_count": len(sampled_function_units),
        }

        # 6. Score: each combo classifies the units of its own granularity. Rows are
        # returned rather than written to the sink, so a failure drops them all.
        rows: list[dict] = []
        for combo_key in clf_models:
            base_model, dataset = combo_registry[combo_key]
            dataset_col = _ai_detection_column_safe(dataset)
            model_col = _ai_detection_column_safe(base_model)
            granularity = _AI_DETECTION_DATASET_GRANULARITY[dataset]
            units = sampled_function_units if granularity == "function" else file_units
            scored = _classify_batch_cached(
                combo_key,
                [unit["text"] for unit in units],
                clf_models[combo_key],
                batch_deadline=new_code_deadline,
            )
            for stat_name, value in _compute_aggregate_stats(granularity, scored).items():
                fields[f"ai_detection_new_{dataset_col}_{model_col}_{stat_name}"] = value
            if ai_detection_unit_scores is not None:
                rows.extend(
                    _unit_score_rows(
                        combo_key, units, scored, new_code_base_commit, new_code_target_commit
                    )
                )
        return fields, rows

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

    try:
        repo_dir = Path(repo.working_dir)

        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir) / "repo"
            shutil.copytree(repo_dir, temp_dir, ignore=shutil.ignore_patterns(".git"))
            print("Repository copied to temporary directory for AI detection.")  # Debug print

            conversion = convert_directory(temp_dir, recursive=True, show_progress=False)
            # Repo-relative notebook path -> its converted script, and the set of those
            # script paths, so units can be traced back to notebooks.
            temp_dir_resolved = temp_dir.resolve()
            notebook_scripts = {
                src.relative_to(temp_dir_resolved).as_posix(): script
                for src, script in conversion.converted.items()
                if src.suffix == ".ipynb"
            }
            notebook_script_paths = {
                script.relative_to(temp_dir_resolved).as_posix()
                for script in notebook_scripts.values()
            }
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
            file_text_paths: list[str] = []
            if file_combo_keys:
                file_sample_size = min(ai_detection_file_sample_size, len(core_files))
                sampled_files = rng.sample(core_files, file_sample_size)
                for f in sampled_files:
                    try:
                        text = f.read_text()
                    except (OSError, UnicodeDecodeError) as e:
                        print(f"Failed to read {f} for file-level AI detection: {e}")
                        continue
                    if len(text.splitlines()) < _AI_DETECTION_MIN_FILE_LINE_COUNT:
                        continue
                    file_texts.append(text)
                    file_text_paths.append(f.relative_to(temp_dir).as_posix())
            files_sampled_count = len(file_texts)

            # Function-granularity sampling: bounded two-stage funnel. Sample K
            # candidate files first (cheap — plain file listing), AST-parse only
            # those to pool functions, then sample N functions from the pool. This
            # bounds both files-read and files-parsed to K regardless of repo size.
            # (repo-relative path, function key, function text) per sampled function.
            function_units: list[tuple[str, str, str]] = []
            candidate_files_sampled_count = 0
            functions_pooled_count = 0
            if func_combo_keys:
                candidate_file_count = min(_AI_DETECTION_CANDIDATE_FILE_COUNT, len(core_files))
                candidate_files = rng.sample(core_files, candidate_file_count)
                candidate_files_sampled_count = len(candidate_files)

                pooled_functions: list[tuple[str, str, str]] = []
                for f in candidate_files:
                    if deadline is not None:
                        deadline.check()
                    try:
                        parsed_functions = parse_python_source_file(f).items()
                    except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as e:
                        print(f"Failed to parse {f} for function-level AI detection: {e}")
                        continue
                    rel_path = f.relative_to(temp_dir).as_posix()
                    pooled_functions.extend(
                        (rel_path, name, text)
                        for name, text in parsed_functions
                        if len(text.splitlines()) >= _AI_DETECTION_MIN_FUNCTION_LINE_COUNT
                    )
                functions_pooled_count = len(pooled_functions)

                function_sample_size = min(
                    ai_detection_function_sample_size, len(pooled_functions)
                )
                function_units = rng.sample(pooled_functions, function_sample_size)
            function_texts = [text for _, _, text in function_units]
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

            # Snapshot units for the per-unit score rows, built only when a sink is given.
            snapshot_function_unit_rows: list[dict] = []
            snapshot_file_unit_rows: list[dict] = []
            if ai_detection_unit_scores is not None:
                snapshot_function_unit_rows = [
                    _make_unit(
                        text,
                        "snapshot",
                        "function",
                        rel_path,
                        rel_path in notebook_script_paths,
                        name,
                    )
                    for rel_path, name, text in function_units
                ]
                snapshot_file_unit_rows = [
                    _make_unit(
                        text, "snapshot", "file", rel_path, rel_path in notebook_script_paths
                    )
                    for text, rel_path in zip(file_texts, file_text_paths, strict=True)
                ]

            for combo_key in clf_models:
                base_model, dataset = combo_registry[combo_key]
                dataset_col = _ai_detection_column_safe(dataset)
                model_col = _ai_detection_column_safe(base_model)
                granularity = _AI_DETECTION_DATASET_GRANULARITY[dataset]
                clf = clf_models[combo_key]

                if granularity == "function":
                    scored = _classify_batch_cached(combo_key, function_texts, clf)
                    stats = _compute_aggregate_stats("function", scored)
                    unit_rows = snapshot_function_unit_rows
                else:
                    scored = _classify_batch_cached(combo_key, file_texts, clf)
                    stats = _compute_aggregate_stats("file", scored)
                    unit_rows = snapshot_file_unit_rows

                for stat_name, value in stats.items():
                    all_fields[f"ai_detection_{dataset_col}_{model_col}_{stat_name}"] = value

                if ai_detection_unit_scores is not None:
                    ai_detection_unit_scores.extend(
                        _unit_score_rows(
                            combo_key, unit_rows, scored, None, new_code_target_commit
                        )
                    )

            all_fields["ai_detection_cache_hits"] = cache_hits
            all_fields["ai_detection_cache_misses"] = cache_misses

            # New-code scoring runs after the baseline is assembled, so a failure here
            # can only null the new-code fields.
            if not compute_new_code_ai_detection:
                all_fields["ai_detection_new_status"] = "disabled"
                all_fields["ai_detection_new_elapsed_seconds"] = 0.0
            elif new_code_base_commit is None:
                # No earlier year-end: all code is new, so the snapshot columns cover it.
                all_fields["ai_detection_new_status"] = "first_year"
                all_fields["ai_detection_new_elapsed_seconds"] = 0.0
            else:
                new_code_started = time.monotonic()
                new_code_budget = ai_detection_new_code_timeout_seconds
                if deadline is not None:
                    # Stop before the outer deadline can fire on a finished baseline.
                    new_code_budget = min(new_code_budget, deadline.remaining() - 5)
                new_code_deadline = Deadline(max(new_code_budget, 0))
                # Fields and unit rows are only merged in once the whole pass succeeds.
                try:
                    new_code_fields, new_code_rows = _compute_new_code_fields(
                        new_code_deadline,
                        repo_dir,
                        temp_dir,
                        notebook_scripts,
                        clf_models,
                        combo_registry,
                        func_combo_keys,
                        file_combo_keys,
                    )
                    all_fields.update(new_code_fields)
                    all_fields["ai_detection_new_status"] = "ok"
                    all_fields["ai_detection_new_base_commit_hash"] = new_code_base_commit
                    if ai_detection_unit_scores is not None:
                        ai_detection_unit_scores.extend(new_code_rows)
                except (AnalysisTimeoutError, subprocess.TimeoutExpired):
                    all_fields["ai_detection_new_status"] = "timeout"
                except Exception as e:
                    print(f"Error during new-code AI detection: {e}")
                    import traceback

                    print(traceback.format_exc())
                    all_fields["ai_detection_new_status"] = "error"
                all_fields["ai_detection_new_elapsed_seconds"] = (
                    time.monotonic() - new_code_started
                )

            print("Computed AI detection statistics for sampled functions/files.")  # Debug
            return AIDetectionResults(**all_fields)

    except AnalysisTimeoutError:
        raise

    except Exception as e:
        print(f"Error during AI detection metrics computation: {e}")
        import traceback

        print(traceback.format_exc())

        return _empty_results()


###############################################################################

_AI_AGENT_CONFIG_GLOBS: list[tuple[str, list[str]]] = [
    ("ai_agent_config_claude_md_exists", ["CLAUDE.md", "CLAUDE.MD"]),
    ("ai_agent_config_cursor_rules_exists", [".cursorrules", ".cursor/rules"]),
    ("ai_agent_config_copilot_instructions_exists", [".github/copilot-instructions.md"]),
    ("ai_agent_config_aider_exists", [".aider*", "aider.conf.yml"]),
    ("ai_agent_config_cline_rules_exists", [".clinerules"]),
    ("ai_agent_config_windsurf_rules_exists", [".windsurfrules"]),
    ("ai_agent_config_agents_md_exists", ["AGENTS.md", "AGENTS.MD"]),
    ("ai_agent_config_gemini_md_exists", ["GEMINI.md"]),
    ("ai_agent_config_claude_dir_exists", [".claude"]),
    ("ai_agent_config_cursor_dir_exists", [".cursor"]),
    ("ai_agent_config_copilot_path_instructions_exists", [".github/instructions"]),
    ("ai_agent_config_windsurf_dir_exists", [".windsurf"]),
]


def _first_added_datetime(
    per_file_commit_deltas_df: pl.DataFrame,
    patterns: list[str],
    end_datetime: "datetime | None",
    datetime_col: str,
) -> str | None:
    """Earliest commit adding a path equal to, under, or matching one of `patterns`."""
    deltas = per_file_commit_deltas_df
    if deltas.is_empty():
        return None
    if end_datetime is not None:
        deltas = deltas.filter(pl.col(datetime_col) <= end_datetime)
    # Cheap literal-prefix prefilter so fnmatch only runs on plausible paths.
    prefix_expr = pl.lit(False)
    for pattern in patterns:
        prefix_expr = prefix_expr | pl.col("filename").str.starts_with(pattern.split("*")[0])
    matched = [
        added_at
        for filename, added_at in deltas.filter(prefix_expr)
        .select("filename", datetime_col)
        .iter_rows()
        if any(
            filename == p or filename.startswith(p + "/") or fnmatch(filename, p)
            for p in patterns
        )
    ]
    return min(matched).isoformat() if matched else None


def compute_ai_agent_config_metrics(
    repo_path: str | Path | Repo,
    per_file_commit_deltas_df: pl.DataFrame | None = None,
    end_datetime: "datetime | None" = None,
    datetime_col: str = "authored_datetime",
) -> AIAgentConfigResults:
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    repo_dir = Path(repo.working_dir)

    field_values: dict[str, Any] = {}
    first_added_datetimes: list[str] = []
    for field_name, patterns in _AI_AGENT_CONFIG_GLOBS:
        found = any(list(repo_dir.glob(pattern)) for pattern in patterns)
        field_values[field_name] = found
        first_added = (
            _first_added_datetime(
                per_file_commit_deltas_df, patterns, end_datetime, datetime_col
            )
            if per_file_commit_deltas_df is not None
            else None
        )
        field_values[field_name.replace("_exists", "_first_added_datetime")] = first_added
        if first_added is not None:
            first_added_datetimes.append(first_added)

    return AIAgentConfigResults(
        **field_values,
        ai_agent_config_any_exists=any(
            value for key, value in field_values.items() if key.endswith("_exists")
        ),
        ai_agent_config_any_first_added_datetime=(
            min(first_added_datetimes) if first_added_datetimes else None
        ),
    )


###############################################################################

_NAME_COLS = ("author_name", "committer_name")
_EMAIL_COLS = ("author_email", "committer_email")


@dataclass
class AICommitAuthorResults(DataClassJsonMixin):
    # Direct author/committer identity
    ai_commit_author_devin_commit_count: int
    ai_commit_author_sweep_commit_count: int
    ai_commit_author_copilot_commit_count: int
    ai_commit_author_codeium_commit_count: int
    ai_commit_author_claude_commit_count: int
    ai_commit_author_cursor_commit_count: int
    ai_commit_author_jules_commit_count: int
    ai_commit_author_gemini_commit_count: int
    ai_commit_author_aider_commit_count: int
    ai_commit_author_amp_commit_count: int
    # Co-authored-by trailer
    ai_commit_coauthored_devin_commit_count: int
    ai_commit_coauthored_sweep_commit_count: int
    ai_commit_coauthored_copilot_commit_count: int
    ai_commit_coauthored_codeium_commit_count: int
    ai_commit_coauthored_claude_commit_count: int
    ai_commit_coauthored_cursor_commit_count: int
    ai_commit_coauthored_jules_commit_count: int
    ai_commit_coauthored_gemini_commit_count: int
    ai_commit_coauthored_aider_commit_count: int
    ai_commit_coauthored_amp_commit_count: int
    # Commit message markers
    ai_commit_marker_claude_code_commit_count: int
    ai_commit_marker_aider_commit_count: int
    # Aggregates (union of all signals)
    ai_commit_total_ai_associated_count: int
    ai_commit_ai_associated_proportion: float | None
    ai_commit_any_detected: bool


_CO_AUTHORED_BY_RE = re.compile(
    r"^co-authored-by:\s*(?P<name>[^<]*?)\s*(?:<(?P<email>[^>]*)>)?\s*$"
)


def _parse_commit_trailer_info(git_log_output: str) -> dict[str, CommitTrailerInfo]:
    trailer_info: dict[str, CommitTrailerInfo] = {}
    chunks = git_log_output.split("\x00")
    for i in range(0, len(chunks) - 2, 3):
        commit_hash = chunks[i].strip()
        message = chunks[i + 2].lower()
        info = CommitTrailerInfo(is_merge=len(chunks[i + 1].split()) > 1)
        trailers = [line for line in message.splitlines() if line.startswith("co-authored-by:")]
        for agent, identities in AGENT_PATTERNS.items():
            if any(s in line for line in trailers for s in identities):
                info.coauthor_agents.add(agent)
        for marker, matches in COMMIT_MARKERS.items():
            if matches(message):
                info.markers.add(marker)
        for line in trailers:
            if any(s in line for identities in AGENT_PATTERNS.values() for s in identities):
                continue
            trailer_match = _CO_AUTHORED_BY_RE.match(line.strip())
            if trailer_match is not None and trailer_match.group("name"):
                info.other_trailers.append(
                    (trailer_match.group("name"), trailer_match.group("email") or None)
                )
        trailer_info[commit_hash] = info
    return trailer_info


def get_commit_trailer_info(repo_path: str | Path | Repo) -> dict[str, CommitTrailerInfo]:
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    result = subprocess.run(
        ["git", "log", "--format=%H%x00%P%x00%B%x00", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=repo.working_dir,
    )
    if result.returncode != 0:
        return {}
    return _parse_commit_trailer_info(result.stdout)


def compute_ai_commit_author_metrics(
    commits_df: pl.DataFrame,
    trailer_info: dict[str, CommitTrailerInfo],
) -> AICommitAuthorResults:
    # Part A: direct author/committer identity (DataFrame scan)
    author_counts: dict[str, int] = {}
    ai_associated_hashes: set[str] = set()
    for agent, identities in AGENT_PATTERNS.items():
        expr = pl.lit(False)
        for col in (*_NAME_COLS, *_EMAIL_COLS):
            for s in identities:
                expr = expr | pl.col(col).str.to_lowercase().str.contains(s, literal=True)
        matched_hashes = commits_df.filter(expr)["commit_hash"].to_list()
        author_counts[agent] = len(matched_hashes)
        ai_associated_hashes.update(matched_hashes)

    # Part B: Co-authored-by trailer and message markers
    valid_hashes: set[str] = set(commits_df["commit_hash"].to_list())
    coauthor_counts: dict[str, int] = dict.fromkeys(AGENT_PATTERNS, 0)
    marker_counts: dict[str, int] = dict.fromkeys(COMMIT_MARKERS, 0)
    for commit_hash in valid_hashes:
        info = trailer_info.get(commit_hash)
        if info is None:
            continue
        for agent in info.coauthor_agents:
            coauthor_counts[agent] += 1
        for marker in info.markers:
            marker_counts[marker] += 1
        if info.agent_associated:
            ai_associated_hashes.add(commit_hash)

    total_commits = sum(
        1
        for commit_hash in valid_hashes
        if commit_hash not in trailer_info or not trailer_info[commit_hash].is_merge
    )
    total_ai = len(ai_associated_hashes)
    proportion = total_ai / total_commits if total_commits > 0 else None

    return AICommitAuthorResults(
        ai_commit_author_devin_commit_count=author_counts["devin"],
        ai_commit_author_sweep_commit_count=author_counts["sweep"],
        ai_commit_author_copilot_commit_count=author_counts["copilot"],
        ai_commit_author_codeium_commit_count=author_counts["codeium"],
        ai_commit_author_claude_commit_count=author_counts["claude"],
        ai_commit_author_cursor_commit_count=author_counts["cursor"],
        ai_commit_author_jules_commit_count=author_counts["jules"],
        ai_commit_author_gemini_commit_count=author_counts["gemini"],
        ai_commit_author_aider_commit_count=author_counts["aider"],
        ai_commit_author_amp_commit_count=author_counts["amp"],
        ai_commit_coauthored_devin_commit_count=coauthor_counts["devin"],
        ai_commit_coauthored_sweep_commit_count=coauthor_counts["sweep"],
        ai_commit_coauthored_copilot_commit_count=coauthor_counts["copilot"],
        ai_commit_coauthored_codeium_commit_count=coauthor_counts["codeium"],
        ai_commit_coauthored_claude_commit_count=coauthor_counts["claude"],
        ai_commit_coauthored_cursor_commit_count=coauthor_counts["cursor"],
        ai_commit_coauthored_jules_commit_count=coauthor_counts["jules"],
        ai_commit_coauthored_gemini_commit_count=coauthor_counts["gemini"],
        ai_commit_coauthored_aider_commit_count=coauthor_counts["aider"],
        ai_commit_coauthored_amp_commit_count=coauthor_counts["amp"],
        ai_commit_marker_claude_code_commit_count=marker_counts["claude_code"],
        ai_commit_marker_aider_commit_count=marker_counts["aider"],
        ai_commit_total_ai_associated_count=total_ai,
        ai_commit_ai_associated_proportion=proportion,
        ai_commit_any_detected=total_ai > 0,
    )
