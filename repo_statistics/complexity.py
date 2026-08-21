#!/usr/bin/env python

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from dataclasses_json import DataClassJsonMixin
from git import Repo

from .utils import (
    Deadline,
    checked_subprocess_timeout,
    get_linguist_file_type,
)

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


def _install_and_setup_complexity_cli() -> bool:
    uname_result = subprocess.run(
        ["uname", "-s"],
        capture_output=True,
        text=True,
        check=True,
    )
    os_name = uname_result.stdout.strip().lower()

    arch_result = subprocess.run(
        ["uname", "-m"],
        capture_output=True,
        text=True,
        check=True,
    )
    arch = arch_result.stdout.strip().lower()
    if arch != "x86_64":
        log.warning(
            f"Unsupported architecture for automatic complexity installation: {arch}. "
            "Only x86_64 binaries are available. "
            "Please install complexity manually. Returning empty results."
        )
        return False

    if os_name == "linux":
        url = "https://github.com/thoughtbot/complexity/releases/download/0.3.0/complexity-0.3.0-x86_64-unknown-linux-musl.tar.gz"
    elif os_name == "darwin":
        url = "https://github.com/thoughtbot/complexity/releases/download/0.3.0/complexity-0.3.0-x86_64-apple-darwin.tar.gz"
    else:
        log.warning(
            f"Unsupported OS for automatic complexity installation: {os_name}. "
            "Please install complexity manually. Returning empty results."
        )
        return False

    # Download and extract the tar.gz
    log.info(f"Downloading complexity CLI from {url}...")
    try:
        download_result = subprocess.run(
            ["curl", "-L", url, "-o", "complexity.tar.gz"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        log.warning(
            "Downloading complexity CLI exceeded 60s timeout. "
            "Please install complexity manually. Returning empty results."
        )
        return False
    if download_result.returncode != 0:
        log.warning(
            f"Failed to download complexity CLI: "
            f"{download_result.stderr.strip()}. "
            "Please install complexity manually. Returning empty results."
        )
        return False

    install_dir = Path.home() / ".local" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)

    extract_result = subprocess.run(
        [
            "tar",
            "-xzf",
            "complexity.tar.gz",
            "-C",
            str(install_dir),
            "--strip-components=1",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if extract_result.returncode != 0:
        log.warning(
            f"Failed to extract complexity CLI: "
            f"{extract_result.stderr.strip()}. "
            "Please install complexity manually. Returning empty results."
        )
        return False

    if str(install_dir) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(install_dir) + ":" + os.environ.get("PATH", "")

    # Clean up the downloaded tar.gz
    Path("complexity.tar.gz").unlink()

    # Verify installation
    if shutil.which("complexity") is None:
        log.warning(
            "complexity CLI installation failed. "
            "Please install complexity manually. Returning empty results."
        )
        return False

    # Run basic setup
    # complexity install-configuration
    setup_result = subprocess.run(
        ["complexity", "install-configuration"],
        capture_output=True,
        text=True,
        check=True,
    )
    if setup_result.returncode != 0:
        log.warning(
            f"Failed to run complexity install-configuration: "
            f"{setup_result.stderr.strip()}. "
            "Please complete complexity setup manually. Returning empty results."
        )
        return False

    return True


def _check_and_install_complexity_cli(install_if_missing: bool) -> bool:
    # Check if complexity CLI is available
    if shutil.which("complexity") is None:
        if install_if_missing:
            # Install from GitHub release:
            # https://github.com/thoughtbot/complexity/releases/tag/0.3.0
            system = shutil.which("uname")
            if system is not None:
                try:
                    return _install_and_setup_complexity_cli()

                except subprocess.CalledProcessError as e:
                    log.warning(
                        f"Failed to determine OS for automatic complexity installation: "
                        f"{e}. "
                        "Please install complexity manually. Returning empty results."
                    )
                    return False

        else:
            log.warning(
                "complexity CLI not found. Install via: "
                "brew tap thoughtbot/formulae && brew install complexity. "
                "Returning empty results."
            )
            return False

    return True


def compute_complexity_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    install_complexity_if_missing: bool = False,
    deadline: Deadline | None = None,
) -> ComplexityResults:
    # Check if complexity CLI is available (and optionally install it)
    if not _check_and_install_complexity_cli(install_complexity_if_missing):
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

    repo_dir = repo.working_dir

    # Run complexity CLI.
    # Like pygount (see source.py), this scans every file in the repo and can
    # be pathologically slow on very large repos -- bound it so a stuck
    # subprocess can't silently consume the whole outer analyze deadline.
    complexity_cli_timeout_seconds = checked_subprocess_timeout(deadline, 90)
    try:
        result = subprocess.run(
            ["complexity"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=complexity_cli_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        log.warning(
            f"complexity CLI exceeded {complexity_cli_timeout_seconds}s timeout "
            f"for repo at {repo_dir}."
        )
        return ComplexityResults(
            complexity_mean=None,
            complexity_median=None,
            complexity_max=None,
            complexity_sum=None,
            complexity_file_count=0,
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
