# Repo Statistics

Calculate collaboration, code, and social metrics and statistics for a source-code repository.

## Metrics Available 

See [full table for additional information](/metrics.md)

Many metrics are scoped by **file type** (`{filetype}` = `total`, `programming`, `markup`, `prose`, `data`, `unknown`) and/or **period span** (`{period}` = e.g., `1_week`, `4_weeks`).

| Metric Family | Representative Metrics | Description |
|--------------|---------|-------------|
| [Development Activity Pattern Metrics](#1-development-activity-pattern-metrics) | `{period}_{filetype}_changed_binary_entropy`, `{period}_{filetype}_changed_binary_variation`, `{period}_{filetype}_changed_binary_frac`, `{period}_{filetype}_changed_binary_gini`, `{period}_{filetype}_lines_changed_count_entropy`, `{period}_{filetype}_lines_changed_count_variation`, `{period}_{filetype}_lines_changed_count_gini` | Metrics measuring regularity and consistency of development effort over time, calculated per period span and file type to identify sustained engagement patterns versus bursty development |
| [Development Episode Characteristics](#2-development-episode-characteristics) | `{period}_{filetype}_did_change_median_span`, `{period}_{filetype}_did_change_mean_span`, `{period}_{filetype}_did_change_std_span`, `{period}_{filetype}_did_not_change_median_span`, `{period}_{filetype}_did_not_change_mean_span`, `{period}_{filetype}_did_not_change_std_span` | Metrics describing the temporal structure of active and inactive development periods, characterizing sustained work episodes and dormancy gaps |
| [Contributor Engagement Patterns](#3-contributor-engagement-patterns) | `{period}_stable_contributors_count`, `{period}_transient_contributors_count`, `{period}_median_contribution_span_days`, `{period}_mean_contribution_span_days`, `{period}_normalized_median_contribution_span`, `{period}_normalized_mean_contribution_span` | Metrics characterizing contributor stability and engagement duration, distinguishing between sustained community members and episodic contributors |
| [Contributor Distribution Metrics](#4-contributor-distribution-metrics) | `{filetype}_contributor_count`, `{filetype}_contributor_absence_factor`, `{filetype}_contributors_per_file_entropy`, `{filetype}_contributors_per_file_gini`, `{filetype}_files_per_contributor_entropy`, `{filetype}_files_per_contributor_gini`, `{filetype}_simple_threshold_specialist_count`, `{filetype}_simple_threshold_generalist_count`, `diff_contributor_count`, `same_contributor_count` | Metrics examining how development effort and knowledge are distributed among contributors, including bus factor analysis and specialist/generalist patterns |
| [Repository Timeline Metrics](#5-repository-timeline-metrics) | `{filetype}_initial_change_datetime`, `{filetype}_most_recent_change_datetime`, `{filetype}_most_recent_substantial_change_datetime`, `{filetype}_change_duration_days`, `{filetype}_change_duration_to_most_recent_substantial_days`, `{filetype}_change_duration_from_substantial_to_most_recent_days` | Basic temporal metadata for development history analysis, tracking project age, activity status, and lifetime of meaningful development |
| [Development Activity Volume](#6-development-activity-volume) | `{filetype}_commit_count`, `bot_changes_count`, `{filetype}_lines_of_code`, `{filetype}_lines_of_comments`, `{filetype}_code_to_comment_ratio` | Metrics quantifying overall development activity and effort, distinguishing between human and automated contributions and measuring codebase size |
| [Community Engagement Metrics](#7-community-engagement-metrics) | `stargazers_count`, `forks_count`, `watchers_count`, `open_issues_count`, `primary_programming_language` | Metrics reflecting community interest and participation through GitHub features, indicating broader impact and active engagement |
| [Release Management Metrics](#8-release-management-metrics) | `semver_tags_count`, `non_semver_tags_count`, `total_tags_count` | Metrics related to versioning and release practices, measuring adoption of formal release management conventions |
| [Repository Classification Metadata](#9-repository-classification-metadata) | `project_type_heuristic_classification` | Descriptive metadata for filtering and comparative analysis, characterizing project type |
| [Documentation and Best Practices](#10-documentation-and-best-practices) | `documentation_checks_passed_count`, `license_file_exists`, `readme_file_exists`, `readme_references_license`, `changelog_file_exists`, `contributing_file_exists`, `code_of_conduct_file_exists`, `code_of_conduct_file_contains_email`, `security_file_exists`, `support_file_exists`, `test_directory_exists`, `integrates_with_ci`, `github_issue_template_exists`, `github_pull_request_template_exists`, `binaries_not_present` | Binary indicators of documentation files and development practices supporting sustainability, including core documentation, community guidelines, and development infrastructure |
| [Code Churn Metrics](#11-code-churn-metrics) | `{period}_{filetype}_churn_lines`, `{period}_{filetype}_churn_normalized` | Metrics quantifying code volatility by measuring files with multiple changes within a period, computed per period span and file type |
| [Code Complexity Metrics](#12-code-complexity-metrics) | `complexity_mean`, `complexity_median`, `complexity_max`, `complexity_sum`, `complexity_file_count` | Cyclomatic complexity of Python source files at the analysis end datetime |
| [Static Analysis Metrics](#13-static-analysis-metrics) | `halstead_volume_mean`, `halstead_difficulty_mean`, `halstead_effort_mean`, `halstead_timerequired_mean`, `halstead_bugprop_mean`, `maintainability_index_mean`, `operators_sum_mean`, `operands_sum_mean`, `static_analysis_file_count` | Halstead software science metrics and maintainability index computed across Python source files at the analysis end datetime |
| [AI Commit Author Metrics](#14-ai-commit-author-metrics) | `ai_commit_author_{agent}_commit_count`, `ai_commit_coauthored_{agent}_commit_count`, `ai_commit_total_ai_associated_count`, `ai_commit_ai_associated_proportion`, `ai_commit_any_detected` | Metrics detecting AI agent involvement in commits via author identity and co-authored-by trailers, across agents: devin, sweep, copilot, codeium, claude, cursor |
| [AI Agent Configuration Metrics](#15-ai-agent-configuration-metrics) | `ai_agent_config_claude_md_exists`, `ai_agent_config_cursor_rules_exists`, `ai_agent_config_copilot_instructions_exists`, `ai_agent_config_aider_exists`, `ai_agent_config_cline_rules_exists`, `ai_agent_config_windsurf_rules_exists`, `ai_agent_config_agents_md_exists`, `ai_agent_config_any_exists` | Binary indicators of AI coding agent configuration files present in the repository at the analysis end datetime |
| [AI Code Detection Metrics](#16-ai-code-detection-metrics) | `ai_detection_unique_files_checked`, `ai_detection_p25_ai_function_proportion`, `ai_detection_p50_ai_function_proportion`, `ai_detection_p75_ai_function_proportion`, `ai_detection_{percentile}_ai_confidence_mean`, `ai_detection_{percentile}_human_confidence_mean` | Per-function AI authorship classification scores at three complexity percentile thresholds (p25/p50/p75), measured at the analysis end datetime |



## Datetime Scoping

When `start_datetime` and `end_datetime` are provided to `analyze_repository`, both the commit summary DataFrame and the per-file delta DataFrame are filtered to that range **before** any metric is computed. This means all metrics implicitly reflect the specified window. How individual metrics use datetimes then falls into three groups:

**Implicitly range-scoped (no extra datetime logic)**
These metrics receive the pre-filtered DataFrames and operate on all rows within the window:
- Commit counts, contributor counts, contributor absence factor, contributor distribution, contributor change metrics, important change dates

**Explicitly range-scoped (period bucketing)**
These metrics also receive `start_datetime` and `end_datetime` to define period bucket boundaries within the window:
- `compute_timeseries_metrics` — iterates from `start_datetime` to `end_datetime` in `period_span` increments, filtering commits into each bucket
- `compute_contributor_stability_metrics` — uses `(end_datetime - start_datetime).days` as the project duration divisor for normalizing contribution spans
- `compute_code_churn` — uses `start_datetime` as the epoch anchor for computing period indices (commits are bucketed by elapsed time since `start_datetime`)

**Point-in-time snapshot (git checkout)**
These metrics use `end_datetime` as a `target_datetime` to find the latest commit at or before that moment, then `git checkout` to that state before measuring the repository:
- Documentation checks (`process_with_repo_linter`)
- Source lines of code (`compute_sloc_metrics`)
- Tag metrics (`compute_tag_metrics`)
- Complexity metrics (`compute_complexity_metrics`)
- Static analysis (`compute_static_analysis_metrics`)
- AI file detection (`compute_ai_detection_metrics`, `compute_ai_agent_config_metrics`)

**No datetime involvement**
- Platform metrics (`stars_count`, `forks_count`, etc.) — live GitHub API call, always reflects current state
- Repository classification — pure heuristic on contributor/star counts

## Usage

### Single Repository Processing

```python
import json

from repo_statistics import analyze_repository

# Repo Path can be a local path or remote
repo_metrics = analyze_repository(
    repo_path="https://github.com/bioio-devs/bioio",
)

with open("example-repo-metrics.json", "w") as f:
    json.dump(repo_metrics, f, indent=4)

# It is recommended to provide a GitHub API token
# unless you disable "platform" metrics
repo_metrics = analyze_repository(
    repo_path="https://github.com/bioio-devs/bioio",
    # Provide a token
    # github_token="ABC",
    # Or disable platform metrics gathering
    compute_platform_metrics=False,
)

# Nearly every portion of metrics can be disable independent from one another
repo_metrics = analyze_repository(
    repo_path="https://github.com/bioio-devs/bioio",
    compute_timeseries_metrics=True,
    compute_contributor_stability_metrics=False,
    compute_contributor_absence_factor=True,
    compute_contributor_distribution_metrics=False,
    compute_repo_linter_metrics=False,
    compute_tag_metrics=True,
    compute_platform_metrics=False,
)

# By default, all time-periods are considered
# However, you can provide also provide a "start_datetime" and/or "end_datetime"
# TODO: Temporarily disabled
# repo_metrics = analyze_repository(
#     repo_path="https://github.com/bioio-devs/bioio",
#     start_datetime="2025-01-01",
#     end_datetime="2026-01-01",
#     compute_platform_metrics=False,
# )

# We also ignore bot changes by default by looking for
# "[bot]" account naming in commit information
# This can be disabled, or, changed as well
repo_metrics = analyze_repository(
    repo_path="https://github.com/bioio-devs/bioio",
    # Keep all bots by ignoring name checks
    bot_name_indicates=None,
    # Keep all bots by ignoring email checks
    bot_email_indicators=None,
    compute_platform_metrics=False,
)
```

### Multiple Repository Processing

```python
from repo_statistics import analyze_repositories, DEFAULT_COILED_KWARGS

analyze_repos_results = analyze_repositories(
    repo_paths=[
        "https://github.com/bioio-devs/bioio",
        "https://github.com/bioio-devs/bioio-ome-zarr",
        "https://github.com/evamaxfield/aws-grobid",
        "https://github.com/evamaxfield/rs-graph",
        "https://github.com/evamaxfield/repo-statistics",
    ],

    # Has built in batching and caching to avoid re-processing repositories
    cache_results_path="repo-metrics-results.parquet",
    cache_errors_path="repo-metrics-errors.parquet",
    batch_size=4,
    # Or as a proportion of the total number of repositories
    # batch_size=0.1,
    # By default, we will use cached results before re-processing
    # This will drop repositories already in the cache and only process new ones
    # To re-process all repositories
    # ignore_cached_results=True,

    # Provide multiple tokens as strings in a list
    # github_tokens=["ghp_exampletoken1", "ghp_exampletoken2"],
    # Or can provide a gh-tokens file path
    # github_tokens=".github-tokens.yml",

    # By default, will process repositories one at a time
    # Can enable multithreading with the following options
    use_multithreading=True,
    n_threads=4,
    # Or, can use Coiled for distributed processing
    # use_coiled=True,
    # coiled_kwargs=DEFAULT_COILED_KWARGS,
    
    # All other keyword arguments are passed to analyze_repository
    # For example, to skip computing repo linter metrics
    # compute_repo_linter_metrics=False,
)

# Provides back an object with results and errors DataFrames
analyze_repos_results.metrics_df
analyze_repos_results.errors_df
```
