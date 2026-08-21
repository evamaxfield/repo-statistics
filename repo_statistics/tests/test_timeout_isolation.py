#!/usr/bin/env python

"""Regression tests for the shared-working-tree race and the analysis deadline.

Before per-call worktree isolation, every `analyze_repository()` call checked its
target commit out in the *shared* clone and restored the original ref in a `finally`.
An analysis that outlived its timeout kept running in a daemon thread and mutated that
shared tree while the next call was measuring it, silently producing metrics for the
wrong commit. These tests pin the invariants that make that impossible.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from git import Repo

from repo_statistics import documentation, main, source
from repo_statistics.main import TrackedErrorResult

###############################################################################

YEARS = [2021, 2022, 2023, 2024]
# Four commits per year so every timepoint window clears the >=3-commit minimum.
COMMITS = [(year, month) for year in YEARS for month in (3, 6, 9, 12)]
TIMEPOINTS = [datetime(year, 12, 31) for year in YEARS[1:]]
EXPECTED_MARKER = {datetime(year, 12, 31): f"version-{year}-12" for year in YEARS[1:]}


@dataclass
class _StubResults:
    documentation_checks_passed_count: int

    def to_dict(self) -> dict:
        return {"documentation_checks_passed_count": self.documentation_checks_passed_count}


@pytest.fixture
def shared_clone(tmp_path: Path) -> Repo:
    """A repo with one commit per year, each carrying a distinct marker file."""
    repo_dir = tmp_path / "shared-clone"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir, initial_branch="main")
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test User")
        cw.set_value("user", "email", "test@example.com")

    for year, month in COMMITS:
        (repo_dir / "marker.txt").write_text(f"version-{year}-{month:02d}")
        repo.index.add(["marker.txt"])
        stamp = datetime(year, month, 1, 12, 0, 0).isoformat()
        repo.index.commit(f"commit {year}-{month}", author_date=stamp, commit_date=stamp)

    repo.create_remote("origin", "git@github.com:test-owner/test-repo.git")
    return repo


def _analyze(repo: Repo, end_datetime: datetime, **kwargs: Any) -> dict | TrackedErrorResult:
    return main.analyze_repository(
        repo_path=str(repo.working_dir),
        end_datetime=end_datetime,
        compute_platform_metrics=False,
        compute_sloc_metrics=False,
        compute_static_analysis_metrics=False,
        compute_complexity_metrics=False,
        install_complexity_if_missing=False,
        **kwargs,
    )


###############################################################################


def test_orphaned_analysis_cannot_corrupt_a_concurrent_call(
    shared_clone: Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stuck analysis holding its tree must not change what a later call measures."""
    orphan_started = threading.Event()
    orphan_may_finish = threading.Event()
    seen: dict[str, str] = {}

    def fake_linter(repo_path: Repo) -> _StubResults:
        marker = (Path(repo_path.working_dir) / "marker.txt").read_text()
        if not orphan_started.is_set():
            # First caller: pretend to hang well past its deadline.
            seen["orphan"] = marker
            orphan_started.set()
            orphan_may_finish.wait(timeout=30)
            seen["orphan_after_wait"] = (Path(repo_path.working_dir) / "marker.txt").read_text()
        else:
            seen["second"] = marker
        return _StubResults(documentation_checks_passed_count=0)

    monkeypatch.setattr(documentation, "process_with_repo_linter", fake_linter)

    orphan_result: list[object] = []
    orphan = threading.Thread(
        target=lambda: orphan_result.append(_analyze(shared_clone, TIMEPOINTS[0]))
    )
    orphan.start()
    assert orphan_started.wait(timeout=30)

    # Second call runs to completion while the first is still holding its tree.
    second = _analyze(shared_clone, TIMEPOINTS[2])
    assert isinstance(second, dict)
    assert seen["second"] == EXPECTED_MARKER[TIMEPOINTS[2]]

    orphan_may_finish.set()
    orphan.join(timeout=30)

    # The orphan's own tree was never disturbed by the second call either.
    assert seen["orphan"] == EXPECTED_MARKER[TIMEPOINTS[0]]
    assert seen["orphan_after_wait"] == EXPECTED_MARKER[TIMEPOINTS[0]]


def test_shared_clone_working_tree_is_never_mutated(
    shared_clone: Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No analysis may check out, detach, or otherwise move the shared clone's HEAD."""
    monkeypatch.setattr(
        documentation,
        "process_with_repo_linter",
        lambda repo_path: _StubResults(documentation_checks_passed_count=0),
    )

    original_branch = shared_clone.active_branch.name
    original_head = shared_clone.head.commit.hexsha
    original_marker = (Path(shared_clone.working_dir) / "marker.txt").read_text()

    for timepoint in TIMEPOINTS:
        assert isinstance(_analyze(shared_clone, timepoint), dict)

    assert shared_clone.active_branch.name == original_branch
    assert shared_clone.head.commit.hexsha == original_head
    assert (Path(shared_clone.working_dir) / "marker.txt").read_text() == original_marker


def test_concurrent_analyses_each_measure_their_own_commit(
    shared_clone: Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N threads on one clone: N correct results, no index.lock contention."""
    observed: list[tuple[datetime, str, str]] = []
    lock = threading.Lock()
    current_timepoint = threading.local()

    def fake_linter(repo_path: Repo) -> _StubResults:
        time.sleep(0.05)
        marker = (Path(repo_path.working_dir) / "marker.txt").read_text()
        with lock:
            observed.append((current_timepoint.value, marker, str(repo_path.working_dir)))
        return _StubResults(documentation_checks_passed_count=0)

    monkeypatch.setattr(documentation, "process_with_repo_linter", fake_linter)

    schedule = TIMEPOINTS * 2
    results: list[object | None] = [None] * len(schedule)

    def run(idx: int, timepoint: datetime) -> None:
        current_timepoint.value = timepoint
        results[idx] = _analyze(shared_clone, timepoint)

    threads = [threading.Thread(target=run, args=(idx, tp)) for idx, tp in enumerate(schedule)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    for result in results:
        assert isinstance(result, dict), result
    for timepoint, marker, _ in observed:
        assert marker == EXPECTED_MARKER[timepoint]
    # Every call got its own private working directory.
    assert len({working_dir for _, _, working_dir in observed}) == len(schedule)
    assert shared_clone.active_branch.name == "main"


def test_no_worktrees_are_leaked(
    shared_clone: Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        documentation,
        "process_with_repo_linter",
        lambda repo_path: _StubResults(documentation_checks_passed_count=0),
    )

    for timepoint in TIMEPOINTS:
        _analyze(shared_clone, timepoint)

    listed = shared_clone.git.worktree("list", "--porcelain")
    assert listed.count("worktree ") == 1


###############################################################################


def test_deadline_stops_the_analysis_and_leaves_no_orphan(
    shared_clone: Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An over-budget analysis must abort synchronously, not keep running in a thread."""
    later_stages_ran: list[str] = []

    def slow_linter(repo_path: Repo) -> _StubResults:
        time.sleep(2)
        return _StubResults(documentation_checks_passed_count=0)

    def should_not_run(*args: Any, **kwargs: Any) -> Any:
        later_stages_ran.append("tag_metrics")
        raise AssertionError("metric family ran after the deadline expired")

    monkeypatch.setattr(documentation, "process_with_repo_linter", slow_linter)
    monkeypatch.setattr(source, "compute_tag_metrics", should_not_run)

    threads_before = set(threading.enumerate())
    start = time.monotonic()
    result = _analyze(shared_clone, TIMEPOINTS[1], analyze_timeout_seconds=1)
    elapsed = time.monotonic() - start

    assert isinstance(result, TrackedErrorResult)
    assert "exceeded 1s timeout" in result.err
    assert later_stages_ran == []
    # Cut off shortly after the one slow step returns, not after the full pipeline.
    assert elapsed < 5

    # No daemon analysis thread survived the raise.
    time.sleep(0.2)
    assert set(threading.enumerate()) - threads_before == set()


def test_deadline_error_is_a_timeout_error(shared_clone: Repo) -> None:
    from repo_statistics.utils import AnalysisTimeoutError, Deadline

    deadline = Deadline(0)
    with pytest.raises(TimeoutError, match="exceeded 0s timeout"):
        deadline.check()
    assert issubclass(AnalysisTimeoutError, TimeoutError)
