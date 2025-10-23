# Repo Statistics

Calculate collaboration, code, and social metrics and statistics for a source-code repository.

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
repo_metrics = analyze_repository(
    repo_path="https://github.com/bioio-devs/bioio",
    start_datetime="2025-01-01",
    end_datetime="2026-01-01",
    compute_platform_metrics=False,
)

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