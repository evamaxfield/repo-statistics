# Repo Statistics

Calculate collaboration, code, and social metrics and statistics for a source-code repository.

## Metrics Available 

See [full table for additional information](/metrics.md) 

| Metric Family | Metrics | Description |
|--------------|---------|-------------|
| [Development Activity Pattern Metrics](#1-development-activity-pattern-metrics) | `commit_entropy`, `commit_variation`, `commit_frac`, `lines_changed_entropy`, `lines_changed_variation` | Metrics measuring regularity and consistency of development effort over time, calculated at both weekly and monthly intervals to identify sustained engagement patterns versus bursty development |
| [Development Episode Characteristics](#2-development-episode-characteristics) | `median_commit_span`, `mean_commit_span`, `std_commit_span`, `median_no_commit_span`, `mean_no_commit_span`, `std_no_commit_span` | Metrics describing the temporal structure of active and inactive development periods, characterizing sustained work episodes and dormancy gaps |
| [Contributor Engagement Patterns](#3-contributor-engagement-patterns) | `stable_contributors_count`, `transient_contributors_count`, `median_contribution_span_days`, `mean_contribution_span_days`, `normalized_median_span`, `normalized_mean_span` | Metrics characterizing contributor stability and engagement duration, distinguishing between sustained community members and episodic contributors |
| [Contributor Distribution Metrics](#4-contributor-distribution-metrics) | `unique_contributors_count`, `contributor_absence_factor_code`, `contributor_absence_factor_all`, `contributor_specialization`, `specialists_contributor_count`, `generalists_contributor_count`, `contributor_change_count`, `contributor_same_count` | Metrics examining how development effort and knowledge are distributed among contributors, including bus factor analysis and specialist/generalist patterns |
| [Repository Timeline Metrics](#5-repository-timeline-metrics) | `initial_commit_datetime`, `most_recent_commit_datetime`, `most_recent_substantial_commit_datetime`, `to_most_recent_commit_duration_days`, `to_most_recent_substantial_commit_duration_days` | Basic temporal metadata for development history analysis, tracking project age, activity status, and lifetime of meaningful development |
| [Development Activity Volume](#6-development-activity-volume) | `commits_count`, `non_bot_commits_count`, `coding_commits_count`, `source_lines_of_code`, `source_lines_of_comments` | Metrics quantifying overall development activity and effort, distinguishing between human and automated contributions and measuring codebase size |
| [Community Engagement Metrics](#7-community-engagement-metrics) | `stars_count`, `forks_count`, `watchers_count`, `open_issues_count` | Metrics reflecting community interest and participation through GitHub features, indicating broader impact and active engagement |
| [Release Management Metrics](#8-release-management-metrics) | `semver_tags_count`, `non_semver_tags_count`, `total_tags_count` | Metrics related to versioning and release practices, measuring adoption of formal release management conventions |
| [Repository Classification Metadata](#9-repository-classification-metadata) | `repo_primary_language`, `repo_classification`, `file_extensions_set` | Descriptive metadata for filtering and comparative analysis, characterizing project type and technical composition |
| [Documentation and Best Practices](#10-documentation-and-best-practices) | `repo_linter_license_file_exists`, `repo_linter_readme_file_exists`, `repo_linter_readme_references_license`, `repo_linter_changelog_file_exists`, `repo_linter_contributing_file_exists`, `repo_linter_code_of_conduct_file_exists`, `repo_linter_code_of_conduct_file_contains_email`, `repo_linter_security_file_exists`, `repo_linter_support_file_exists`, `repo_linter_test_directory_exists`, `repo_linter_integrates_with_ci`, `repo_linter_github_issue_template_exists`, `repo_linter_github_pull_request_template_exists`, `repo_linter_binaries_not_present` | Binary indicators of documentation files and development practices supporting sustainability, including core documentation, community guidelines, and development infrastructure |
| [Gini Coefficients (experimental)](#11-gini-coefficients-experimental) | `commit_gini_coefficient`, `lines_changed_gini_coefficient`, `contributor_commit_gini`, `contributor_lines_gini`, `commit_size_gini`, `time_between_commits_gini` | Alternative inequality measures using Gini coefficients to complement existing sustainability indicators, measuring distribution equality across temporal and contributor dimensions |
| [Commit Pattern Metrics](#12-commit-pattern-metrics) | `commit_size_entropy`, `commit_size_variation`, `time_between_commits_entropy`, `time_between_commits_variation` | Metrics analyzing commit sizing and timing patterns using entropy and variation measures to characterize development rhythm and consistency |
| [Advanced Sustainability Indicators](#13-advanced-sustainability-indicators) | `documentation_to_code_ratio`, `contributor_retention_rate`, `releases_per_year`, `knowledge_concentration_risk`, `simple_code_churn_rate` | Higher-level metrics for comprehensive sustainability assessment combining multiple dimensions including documentation quality, contributor retention, release cadence, knowledge distribution, and code volatility |



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
