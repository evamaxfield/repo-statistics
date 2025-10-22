#!/usr/bin/env python

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import polars as pl
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .data import DATA_FILES_DIR
from .utils import get_commit_hash_for_target_datetime

###############################################################################

REPO_LINTER_RULESET_PATH = DATA_FILES_DIR / "repo-linter-ruleset.json"

###############################################################################


def _process_repo_linter_file_existence_rule(
    repo: Repo,
    rule_details: dict,
    check_dir: bool = False,
) -> bool:
    # Get repo_dir from repo
    repo_dir = repo.working_dir

    # Check for certain parameters
    allow_directories = rule_details.get("dirs", False)
    ignore_case = rule_details.get("nocase", False)

    # Get all of the glob patterns to check for
    glob_patterns = rule_details["globsAny"]

    # Iterate over all of the glob patterns and store the boolean values in a list
    glob_results = []
    for glob_pattern in glob_patterns:
        # Run the glob pattern
        if ignore_case:
            glob_result = list(Path(repo_dir).glob(glob_pattern, case_sensitive=False))
        else:
            glob_result = list(Path(repo_dir).glob(glob_pattern))

        # If we are not allowing directories, filter out directories
        if not allow_directories:
            glob_result = [fp for fp in glob_result if not fp.is_dir()]

        # Check dir if we are checking for directories
        if check_dir:
            glob_result = [fp for fp in glob_result if fp.is_dir()]

        # Check if there are any files present
        glob_results.append(len(glob_result) > 0)

    # Check if any of the glob results are True
    return len(glob_results) >= 1 and any(glob_results)


def _process_repo_linter_file_contents_rule(
    repo: Repo,
    rule_details: dict,
) -> bool:
    # Get repo_dir from repo
    repo_dir = repo.working_dir

    # Check for certain parameters
    regex_content = rule_details["content"]
    ignore_case = rule_details.get("nocase", False)
    regex_flags = rule_details.get("flags", "")

    # The only flag that is possible present is "ignore case" so just check for that
    if "i" in regex_flags:
        ignore_case = True

    # Globs to parse
    glob_patterns = rule_details["globsAll"]

    # Iterate over all of the glob patterns and store the boolean values in a list
    glob_results = []
    for glob_pattern in glob_patterns:
        # Run the glob pattern
        glob_result = list(Path(repo_dir).glob(glob_pattern))

        # Check if there are any files present
        for fp in glob_result:
            with open(fp) as open_f:
                file_contents = open_f.read()

                # Check if we should ignore case
                if ignore_case:
                    if re.search(regex_content, file_contents, flags=re.IGNORECASE):
                        glob_results.append(True)
                    else:
                        glob_results.append(False)
                else:
                    if re.search(regex_content, file_contents):
                        glob_results.append(True)
                    else:
                        glob_results.append(False)

    # Check if all of the glob results are True
    return len(glob_results) >= 1 and all(glob_results)


def _process_repo_linter_file_type_exclusion_rule(
    repo: Repo,
    rule_details: dict,
) -> bool:
    # Get repo_dir from repo
    repo_dir = repo.working_dir

    # Iter over all "type" globs
    glob_results = []
    for glob_pattern in rule_details["type"]:
        # Run the glob pattern
        glob_result = list(Path(repo_dir).glob(glob_pattern))

        # Check if there are any files present
        glob_results.append(len(glob_result) > 0)

    # Check if any of the glob results are True
    return len(glob_results) == 0 or not any(glob_results)


def _process_repo_linter_rule(
    repo: Repo,
    rule_type: str,
    rule_details: dict,
) -> bool:
    # Process based on rule type
    if rule_type == "file-existence":
        return _process_repo_linter_file_existence_rule(
            repo=repo,
            rule_details=rule_details,
        )

    if rule_type == "directory-existence":
        return _process_repo_linter_file_existence_rule(
            repo=repo,
            rule_details=rule_details,
            check_dir=True,
        )

    if rule_type == "file-contents":
        return _process_repo_linter_file_contents_rule(
            repo=repo,
            rule_details=rule_details,
        )

    if rule_type == "file-type-exclusion":
        return _process_repo_linter_file_type_exclusion_rule(
            repo=repo,
            rule_details=rule_details,
        )

    raise ValueError(f"Unknown rule type: {rule_type}")


@dataclass
class RepoLinterResults(DataClassJsonMixin):
    license_file_exists: bool
    readme_file_exists: bool
    contributing_file_exists: bool
    code_of_conduct_file_exists: bool
    changelog_file_exists: bool
    security_file_exists: bool
    support_file_exists: bool
    readme_references_license: bool
    binaries_not_present: bool
    test_directory_exists: bool
    integrates_with_ci: bool
    code_of_conduct_file_contains_email: bool
    github_issue_template_exists: bool
    github_pull_request_template_exists: bool


def process_with_repo_linter(
    repo_path: str | Path | Repo,
    commits_df: pl.DataFrame,
    target_datetime: str | date | datetime | None = None,
    datetime_col: Literal[
        "authored_datetime", "committed_datetime"
    ] = "authored_datetime",
) -> RepoLinterResults:
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

        # Load the ruleset
        with open(REPO_LINTER_RULESET_PATH) as open_file:
            repo_linter_full_ruleset_data = json.load(open_file)

        # Get the rules
        repo_linter_rules = repo_linter_full_ruleset_data["rules"]

        # Process each rule
        rule_results = {}
        for rule_name, rule_full_details in repo_linter_rules.items():
            # Unpack full details to get rule type and rule details
            rule_type = rule_full_details["rule"]["type"]
            rule_details = rule_full_details["rule"]["options"]

            # Process rule
            rule_result = _process_repo_linter_rule(
                repo=repo,
                rule_type=rule_type,
                rule_details=rule_details,
            )

            # Add to rule results
            rule_results[rule_name] = rule_result

        return RepoLinterResults(
            **{
                rule_name.replace("-", "_"): rule_result
                for rule_name, rule_result in rule_results.items()
            }
        )

    finally:
        # Checkout back to HEAD
        repo.git.checkout("HEAD")
