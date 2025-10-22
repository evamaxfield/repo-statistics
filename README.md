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
# dependabot / github / [bot] account naming in commit information
# This can be disabled, or, changed as well
repo_metrics = analyze_repository(
    repo_path="https://github.com/bioio-devs/bioio",
    # Keep all bots by ignoring name checks
    bot_names=None,
    # Keep all bots by ignoring email checks
    bot_email_indicators=None,
    compute_platform_metrics=False,
)
```