#!/usr/bin/env python

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dataclasses_json import DataClassJsonMixin
from git import Repo

from .constants import FileTypes
from .utils import (
    AnalysisTimeoutError,
    Deadline,
    checked_subprocess_timeout,
    get_linguist_file_type,
)

###############################################################################


@dataclass
class SLOCResults(DataClassJsonMixin):
    total_lines_of_code: int | None
    total_lines_of_comments: int | None
    programming_lines_of_code: int | None
    programming_lines_of_comments: int | None
    markup_lines_of_code: int | None
    markup_lines_of_comments: int | None
    prose_lines_of_code: int | None
    prose_lines_of_comments: int | None
    data_lines_of_code: int | None
    data_lines_of_comments: int | None
    unknown_lines_of_code: int | None
    unknown_lines_of_comments: int | None
    total_code_to_comment_ratio: float | None
    programming_code_to_comment_ratio: float | None
    markup_code_to_comment_ratio: float | None
    prose_code_to_comment_ratio: float | None
    data_code_to_comment_ratio: float | None
    unknown_code_to_comment_ratio: float | None


def compute_sloc_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    deadline: Deadline | None = None,
) -> SLOCResults:
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    try:
        # Get repo_dir from repo
        repo_dir = repo.working_dir

        # Run cloc on the repo.
        # pygount can be pathologically slow (observed: indefinite hang) on very
        # large plain-text/data files, so bound it -- otherwise a single stuck
        # subprocess silently consumes the whole outer analyze deadline.
        pygount_timeout_seconds = checked_subprocess_timeout(deadline, 60)
        try:
            pygount_output = subprocess.run(
                [
                    "pygount",
                    "--format=json",
                    repo_dir,
                ],
                capture_output=True,
                text=True,
                timeout=pygount_timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"pygount SLOC counting exceeded {pygount_timeout_seconds}s timeout "
                f"for repo at {repo_dir}."
            ) from e

        if pygount_output.returncode != 0:
            raise RuntimeError(
                f"pygount failed with return code {pygount_output.returncode}. "
                f"stderr: {pygount_output.stderr.strip()}"
            )

        # Read JSON
        try:
            sloc_results = json.loads(pygount_output.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse pygount JSON output: {e}. "
                f"stdout: {pygount_output.stdout[:200]!r}"
            ) from e

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

        def _ratio(code: int, comments: int) -> float | None:
            return code / comments if comments > 0 else None

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
            total_code_to_comment_ratio=_ratio(total_lines_of_code, total_lines_of_comments),
            programming_code_to_comment_ratio=_ratio(
                programming_lines_of_code, programming_lines_of_comments
            ),
            markup_code_to_comment_ratio=_ratio(markup_lines_of_code, markup_lines_of_comments),
            prose_code_to_comment_ratio=_ratio(prose_lines_of_code, prose_lines_of_comments),
            data_code_to_comment_ratio=_ratio(data_lines_of_code, data_lines_of_comments),
            unknown_code_to_comment_ratio=_ratio(
                unknown_lines_of_code, unknown_lines_of_comments
            ),
        )

    except AnalysisTimeoutError:
        raise

    except Exception:
        return SLOCResults(
            total_lines_of_code=None,
            total_lines_of_comments=None,
            programming_lines_of_code=None,
            programming_lines_of_comments=None,
            markup_lines_of_code=None,
            markup_lines_of_comments=None,
            prose_lines_of_code=None,
            prose_lines_of_comments=None,
            data_lines_of_code=None,
            data_lines_of_comments=None,
            unknown_lines_of_code=None,
            unknown_lines_of_comments=None,
            total_code_to_comment_ratio=None,
            programming_code_to_comment_ratio=None,
            markup_code_to_comment_ratio=None,
            prose_code_to_comment_ratio=None,
            data_code_to_comment_ratio=None,
            unknown_code_to_comment_ratio=None,
        )


@dataclass
class RepoTagMetrics(DataClassJsonMixin):
    semver_tags_count: int
    non_semver_tags_count: int
    total_tags_count: int


def compute_tag_metrics(
    repo_path: str | Path | Repo,
) -> RepoTagMetrics:
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

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
