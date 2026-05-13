# Scientific Software Sustainability Metrics

## Metric Family Summary

Many metrics are scoped by **file type** (`{filetype}` = `total`, `programming`, `markup`, `prose`, `data`, `unknown`) and/or by **period span** (`{period}` = e.g., `1_week`, `4_weeks`).

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

---

## 1. Development Activity Pattern Metrics

Metrics measuring regularity and consistency of development effort over time. All metrics are computed per period span (e.g., `1_week`, `4_weeks`) and per file type (`total`, `programming`, `markup`, `prose`, `data`, `unknown`), producing keys like `1_week_total_changed_binary_entropy`.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `{period}_{filetype}_changed_binary_entropy` | Entropy of commit presence (binary) across time periods | Regular patterns indicate sustained engagement; bursty patterns may align with academic calendars | Higher = more predictable | CHAOSS Burstiness; EPJ Data Science; [17], [18], [19], [20] |
| `{period}_{filetype}_changed_binary_variation` | Coefficient of variation (σ/μ) of commit presence | Lower variation suggests consistent development effort | Lower = more consistent | Similar to CHAOSS Burstiness; [17], [18], [19] |
| `{period}_{filetype}_changed_binary_frac` | Fraction of time periods containing ≥1 commit | Indicates sustained development throughout project lifecycle | Higher = more active periods | Adapted from MSR 2024 "consistency" |
| `{period}_{filetype}_changed_binary_gini` | Gini coefficient of commit presence across time periods | Inequality of development activity distribution (0=equal, 1=max inequality) | Lower = more equal | [51], [52] |
| `{period}_{filetype}_lines_changed_count_entropy` | Entropy of lines changed per time period | Regular code changes suggest ongoing maintenance | Higher = more regular intensity | Extension of commit entropy; [17], [18] |
| `{period}_{filetype}_lines_changed_count_variation` | Coefficient of variation of lines changed | Predictable development intensity patterns | Lower = more consistent | Extension of commit variation |
| `{period}_{filetype}_lines_changed_count_gini` | Gini coefficient of lines changed across time periods | Inequality of development intensity distribution | Lower = more equal | [51], [52] |

## 2. Development Episode Characteristics

Metrics describing the temporal structure of active and inactive development periods. All metrics are computed per period span and per file type, producing keys like `1_week_total_did_change_median_span`.

| Metric | Description | Sustainability Relationship | Directionality |
|--------|-------------|---------------------------|----------------|
| `{period}_{filetype}_did_change_median_span` | Median consecutive time periods with commits | Longer spans indicate sustained development episodes | Higher = longer work periods |
| `{period}_{filetype}_did_change_mean_span` | Mean consecutive time periods with commits | Typical sustained development duration | Higher = longer work periods |
| `{period}_{filetype}_did_change_std_span` | Standard deviation of commit span lengths | Variability in sustained development patterns | Context-dependent |
| `{period}_{filetype}_did_not_change_median_span` | Median consecutive time periods without commits | Shorter gaps indicate continuous engagement | Lower = shorter gaps |
| `{period}_{filetype}_did_not_change_mean_span` | Mean consecutive time periods without commits | Typical dormancy between development activities | Lower = shorter gaps |
| `{period}_{filetype}_did_not_change_std_span` | Standard deviation of no-commit span lengths | Variability in dormancy patterns | Context-dependent |

## 3. Contributor Engagement Patterns

Metrics characterizing contributor stability and engagement duration. All metrics are computed per period span (e.g., `1_week`, `4_weeks`), producing keys like `1_week_stable_contributors_count`. The period span defines the threshold for classifying a contributor as stable vs. transient.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `{period}_stable_contributors_count` | Contributors whose activity spans ≥1 period span | Sustained community engagement and knowledge retention | Higher = more retention | CHAOSS Occasional Contributors (inverse); [1], [2], [3], [4] |
| `{period}_transient_contributors_count` | Contributors whose activity spans <1 period span | May indicate good onboarding or poor retention depending on stable contributor presence | Context-dependent | CHAOSS Occasional Contributors; [1], [2], [3] |
| `{period}_median_contribution_span_days` | Median individual contributor engagement duration in days | Better contributor retention | Higher = longer engagement | [5], [6], [7] |
| `{period}_mean_contribution_span_days` | Mean individual contributor engagement duration in days | Typical contributor involvement | Higher = longer engagement | [5], [6], [7] |
| `{period}_normalized_median_contribution_span` | Median contribution span / total analysis window duration | Accounts for project age in assessing engagement | Higher = longer relative engagement | [5], [6] |
| `{period}_normalized_mean_contribution_span` | Mean contribution span / total analysis window duration | Project-adjusted engagement duration | Higher = longer relative engagement | [5], [6] |

## 4. Contributor Distribution Metrics

Metrics examining how development effort and knowledge are distributed among contributors. Most metrics are scoped per file type (`total`, `programming`, `markup`, `prose`, `data`, `unknown`). Generalist/specialist counts are computed at three thresholds: `simple` (fixed 3-file cutoff), `median`, and `twenty_fifth_percentile`.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `{filetype}_contributor_count` | Total distinct contributors touching this file type | Broader engagement reduces bus factor | Higher = more contributors | [4] and numerous MSR studies |
| `{filetype}_contributor_absence_factor` | Contributors needed for 50% of changes to this file type (bus factor) | Concentration risk | Higher = less risk | [8], [9], [10], [11] |
| `{filetype}_contributors_per_file_entropy` | Entropy of contributor count distribution across files | Balance between deep expertise and knowledge coverage | Higher = more even distribution | [12], [13], [14] |
| `{filetype}_contributors_per_file_gini` | Gini coefficient of contributor count distribution across files | Inequality in how contributors are spread across files | Lower = more equal | [51], [52], [53] |
| `{filetype}_files_per_contributor_entropy` | Entropy of file count distribution across contributors | Generalism vs. specialism balance | Higher = more even distribution | [12], [13], [14] |
| `{filetype}_files_per_contributor_gini` | Gini coefficient of file count distribution across contributors | Inequality in how much of the codebase each contributor touches | Lower = more equal | [51], [52] |
| `{filetype}_simple_threshold_specialist_count` | Contributors touching ≤3 files of this type | Deep expertise in specific areas | Context-dependent | [12], [13], [14] |
| `{filetype}_simple_threshold_generalist_count` | Contributors touching >3 files of this type | Broader coverage reduces specialization risks | Higher = more coverage | [12], [13] |
| `{filetype}_median_threshold_specialist_count` | Contributors below median files-touched threshold | Relative specialist count | Context-dependent | [12], [13], [14] |
| `{filetype}_median_threshold_generalist_count` | Contributors above median files-touched threshold | Relative generalist count | Context-dependent | [12], [13] |
| `{filetype}_twenty_fifth_percentile_threshold_specialist_count` | Contributors below 25th percentile files-touched threshold | Narrow specialist count | Context-dependent | [12], [13], [14] |
| `{filetype}_twenty_fifth_percentile_threshold_generalist_count` | Contributors above 25th percentile files-touched threshold | Broad generalist count | Context-dependent | [12], [13] |
| `diff_contributor_count` | Contributors in the first 20% of commits but not the last 20% | Turnover may indicate challenges or natural evolution | Context-dependent | [15], [16], [17], [18] |
| `same_contributor_count` | Contributors present in both the first and last 20% of commits | Sustained engagement and knowledge retention | Higher = more continuity | [15], [16] |

## 5. Repository Timeline Metrics

Basic temporal metadata for development history analysis. All metrics are scoped per file type (`total`, `programming`, `markup`, `prose`, `data`, `unknown`), producing keys like `total_initial_change_datetime`.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `{filetype}_initial_change_datetime` | First commit timestamp for this file type | Project age calculation; temporal studies | Metadata | [19], [20], [21] |
| `{filetype}_most_recent_change_datetime` | Latest commit timestamp for this file type | Activity status determination | Metadata | [19], [20], [21] |
| `{filetype}_most_recent_substantial_change_datetime` | Latest commit >10th percentile lines changed for this file type | Recent substantial development (excludes trivial changes) | Context-dependent | [22], [23] |
| `{filetype}_change_duration_days` | Days from first to latest commit for this file type | Sustained development over time | Higher = longer active | [19], [20], [21] |
| `{filetype}_change_duration_to_most_recent_substantial_days` | Days from first to latest substantial commit for this file type | Sustained meaningful development | Higher = longer active | [22], [23] |
| `{filetype}_change_duration_from_substantial_to_most_recent_days` | Days from last substantial commit to last commit | Gap between meaningful work and minor activity | Lower = more recent meaningful work | [22], [23] |

## 6. Development Activity Volume

Metrics quantifying overall development activity and effort. Commit counts are scoped per file type; SLOC metrics include per-file-type breakdowns.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `{filetype}_commit_count` | Commits touching at least one file of this type | Activity indicator; quality matters more than quantity | Context-dependent | [24], [26] |
| `bot_changes_count` | Commits excluded as automated/bot activity | Proportion of non-human development effort | Context-dependent | [25], [26] |
| `{filetype}_lines_of_code` | Source lines of code for this file type at analysis end datetime | Size indicator for sustainability needs | Context-dependent | [27], [28] |
| `{filetype}_lines_of_comments` | Comment lines for this file type at analysis end datetime | Maintainability and documentation | Higher = more documented | [27], [28] |
| `{filetype}_code_to_comment_ratio` | Code lines / comment lines for this file type | Code documentation density | Higher = more comments per line of code | [27], [28] |

## 7. Community Engagement Metrics

Metrics reflecting community interest and participation through GitHub features. These are live API values at time of analysis, not scoped to the analysis datetime window.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `stargazers_count` | GitHub stars | Community interest and broader impact | Higher = more interest | [29], [30], [31] |
| `forks_count` | Repository forks | Community engagement and distributed development potential | Higher = more engagement | [32], [33] |
| `watchers_count` | Active watchers | Community monitoring project | Higher = more active interest | [34], [35] |
| `open_issues_count` | Current open issues | Active engagement or maintenance challenges | Context-dependent | [36] |
| `primary_programming_language` | Primary programming language as reported by GitHub | Affects community size, tooling, long-term support | Metadata | |

## 8. Release Management Metrics

Metrics related to versioning and release practices. Measured at the analysis end datetime.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `semver_tags_count` | Semantic version tags (e.g., v1.2.3) | Formal release management practices | Higher = better management | [37], [38], [39] |
| `non_semver_tags_count` | Non-semantic version tags (e.g., CalVer) | Alternative versioning schemes | Context-dependent | [38] |
| `total_tags_count` | All version tags | Some versioning better than none | Higher = better control | [37], [38], [39] |

## 9. Repository Classification Metadata

Heuristic classification of project type based on contributor count and star count (adapted from Eghbal's "Working in Public").

| Metric | Description | Sustainability Relationship | Directionality |
|--------|-------------|---------------------------|----------------|
| `project_type_heuristic_classification` | Project type (federation, club, stadium, toy) | Different types have different sustainability patterns | Type-specific |

## 10. Documentation and Best Practices

Binary indicators of documentation files and development practices supporting sustainability. Measured at the analysis end datetime via git checkout.

### Core Documentation

| Metric | Description | Importance | Related Work |
|--------|-------------|------------|--------------|
| `documentation_checks_passed_count` | Total number of documentation checks that passed | Overall documentation completeness score | |
| `license_file_exists` | LICENSE file present | Legal clarity for reuse | [43] |
| `readme_file_exists` | README file present | Basic project understanding | [44], [45], [46] |
| `readme_references_license` | README mentions license | Improves legal clarity | [44], [45] |
| `changelog_file_exists` | CHANGELOG present | Tracks changes and updates | |

### Community Guidelines

| Metric | Description | Importance | Related Work |
|--------|-------------|------------|--------------|
| `contributing_file_exists` | CONTRIBUTING guidelines present | Facilitates participation | [47], [48] |
| `code_of_conduct_file_exists` | Code of conduct present | Promotes inclusive environment | [47], [48] |
| `code_of_conduct_file_contains_email` | Code of conduct includes contact email | Reporting mechanism | |
| `security_file_exists` | SECURITY policy present | Responsible security handling | [49] |
| `support_file_exists` | SUPPORT info present | Reduces maintainer burden | [47], [48] |

### Development Infrastructure

| Metric | Description | Importance | Related Work |
|--------|-------------|------------|--------------|
| `test_directory_exists` | Test directory present | Testing infrastructure | [50] |
| `integrates_with_ci` | CI integration detected | Automated testing/deployment | [50] |
| `github_issue_template_exists` | Issue templates present | Improves issue quality | |
| `github_pull_request_template_exists` | PR templates present | Facilitates code review | |
| `binaries_not_present` | No binaries in repo | Version control best practices | |

## 11. Code Churn Metrics

Metrics quantifying code volatility by measuring files that are modified more than once within a single period (i.e., files that "churn"). Computed per period span and per file type, producing keys like `1_week_total_churn_lines`.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `{period}_{filetype}_churn_lines` | Total lines changed in churning files (modified >1× per period) | High churn may indicate instability or active refactoring | Context-dependent | [24], [60], [61], [62] |
| `{period}_{filetype}_churn_normalized` | Churn lines as fraction of total lines changed | Normalized volatility indicator | Lower = more stable | [24], [60], [61], [62] |

## 12. Code Complexity Metrics

Cyclomatic complexity of Python source files, measured at the analysis end datetime. Requires `radon` or equivalent tool to be installed.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `complexity_mean` | Mean cyclomatic complexity across all functions | Average maintainability burden | Lower = simpler | [28] |
| `complexity_median` | Median cyclomatic complexity across all functions | Typical complexity per function | Lower = simpler | [28] |
| `complexity_max` | Maximum cyclomatic complexity across all functions | Worst-case complexity hotspot | Lower = simpler | [28] |
| `complexity_sum` | Sum of cyclomatic complexity across all functions | Total complexity burden of the codebase | Lower = simpler | [28] |
| `complexity_file_count` | Number of Python files analyzed for complexity | Coverage of complexity analysis | Metadata | |

## 13. Static Analysis Metrics

Halstead software science metrics and maintainability index, computed across Python source files at the analysis end datetime. All aggregate statistics (`mean`, `median`, `std`, `sum`) are computed over per-file values.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `halstead_volume_{mean\|median\|std\|sum}` | Halstead volume (bits to implement the program) | Implementation size and complexity | Lower = simpler | [28] |
| `halstead_difficulty_{mean\|median\|std\|sum}` | Halstead difficulty (effort to understand/write) | Developer comprehension burden | Lower = easier | [28] |
| `halstead_effort_{mean\|median\|std\|sum}` | Halstead effort (volume × difficulty) | Total mental effort to implement | Lower = easier | [28] |
| `halstead_timerequired_{mean\|median\|std\|sum}` | Estimated time to implement (seconds) | Proxy for implementation complexity | Lower = faster | [28] |
| `halstead_bugprop_{mean\|median\|std\|sum}` | Estimated bug proportion (delivered bugs per KLOC) | Predicted defect density | Lower = fewer bugs | [28] |
| `operators_sum_{mean\|median\|std\|sum}` | Total operator tokens per file | Syntactic complexity | Context-dependent | [28] |
| `operators_uniq_{mean\|median\|std\|sum}` | Unique operator tokens per file | Operator vocabulary richness | Context-dependent | [28] |
| `operands_sum_{mean\|median\|std\|sum}` | Total operand tokens per file | Data usage complexity | Context-dependent | [28] |
| `operands_uniq_{mean\|median\|std\|sum}` | Unique operand tokens per file | Operand vocabulary richness | Context-dependent | [28] |
| `maintainability_index_{mean\|median\|std\|sum}` | Maintainability index (0–100 scale) | Overall code maintainability | Higher = more maintainable | [28] |
| `static_analysis_file_count` | Number of Python files analyzed | Coverage of static analysis | Metadata | |

## 14. AI Commit Author Metrics

Metrics detecting AI agent involvement in commits, via both direct author/committer identity matching and `Co-authored-by:` trailer scanning. Covers agents: `devin`, `sweep`, `copilot`, `codeium`, `claude`, `cursor`.

| Metric | Description | Sustainability Relationship | Directionality |
|--------|-------------|---------------------------|----------------|
| `ai_commit_author_{agent}_commit_count` | Commits where the author/committer identity matches an AI agent pattern | Proportion of AI-authored code | Metadata |
| `ai_commit_coauthored_{agent}_commit_count` | Commits with a `Co-authored-by:` trailer matching an AI agent | AI-assisted (human-initiated) commits | Metadata |
| `ai_commit_total_ai_associated_count` | Commits associated with any AI agent (authored or co-authored) | Overall AI involvement in development | Metadata |
| `ai_commit_ai_associated_proportion` | AI-associated commits / total commits | Fraction of commits with AI involvement | Metadata |
| `ai_commit_any_detected` | Whether any AI-associated commit was found | Boolean indicator of AI tool usage | Metadata |

## 15. AI Agent Configuration Metrics

Binary indicators of AI coding agent configuration files present in the repository at the analysis end datetime.

| Metric | Description |
|--------|-------------|
| `ai_agent_config_claude_md_exists` | `CLAUDE.md` (Claude Code) configuration file present |
| `ai_agent_config_cursor_rules_exists` | `.cursorrules` (Cursor) configuration file present |
| `ai_agent_config_copilot_instructions_exists` | `.github/copilot-instructions.md` (GitHub Copilot) present |
| `ai_agent_config_aider_exists` | `.aider*` (Aider) configuration file present |
| `ai_agent_config_cline_rules_exists` | `.clinerules` (Cline) configuration file present |
| `ai_agent_config_windsurf_rules_exists` | `.windsurfrules` (Windsurf) configuration file present |
| `ai_agent_config_agents_md_exists` | `AGENTS.md` (generic agent instructions) present |
| `ai_agent_config_any_exists` | Any AI agent configuration file detected |

## 16. AI Code Detection Metrics

Per-function AI authorship classification scores using a trained classifier, reported at three complexity percentile thresholds (`p25`, `p50`, `p75`) to sample files at varying complexity levels. Measured at the analysis end datetime.

| Metric | Description |
|--------|-------------|
| `ai_detection_unique_files_checked` | Number of unique source files analyzed |
| `ai_detection_{p25\|p50\|p75}_filepath` | Path of the file at the given complexity percentile |
| `ai_detection_{p25\|p50\|p75}_total_function_count` | Total functions analyzed in the sampled file |
| `ai_detection_{p25\|p50\|p75}_ai_function_count` | Functions classified as AI-generated |
| `ai_detection_{p25\|p50\|p75}_human_function_count` | Functions classified as human-written |
| `ai_detection_{p25\|p50\|p75}_ai_function_proportion` | Fraction of functions classified as AI-generated |
| `ai_detection_{p25\|p50\|p75}_ai_confidence_mean` | Mean classifier confidence for AI-classified functions |
| `ai_detection_{p25\|p50\|p75}_ai_confidence_std` | Std dev of classifier confidence for AI-classified functions |
| `ai_detection_{p25\|p50\|p75}_ai_confidence_median` | Median classifier confidence for AI-classified functions |
| `ai_detection_{p25\|p50\|p75}_human_confidence_mean` | Mean classifier confidence for human-classified functions |
| `ai_detection_{p25\|p50\|p75}_human_confidence_std` | Std dev of classifier confidence for human-classified functions |
| `ai_detection_{p25\|p50\|p75}_human_confidence_median` | Median classifier confidence for human-classified functions |

---

## Works Cited 

[1] Barcomb, A., Stol, K.-J., Fitzgerald, B., & Riehle, D. 2016. *Episodic Volunteering in Open Source Communities.* In EASE 2016, 1–10. [PDF](https://barcomb.org/papers/barcomb-2016-episodic.pdf)

[2] Barcomb, A., Stol, K.-J., Riehle, D., & Fitzgerald, B. 2019. *Why Do Episodic Volunteers Stay in FLOSS Communities?* In ICSE 2019, 948–959. [PDF](https://dirkriehle.com/wp-content/uploads/2019/01/Preprint.pdf)

[3] Joblin, M., Apel, S., Hunsen, C., & Mauerer, W. 2017. *Classifying Developers into Core and Peripheral.* In ICSE 2017, 164–174. [DOI](https://doi.org/10.1109/ICSE.2017.23)

[4] Mockus, A., Fielding, R.T., & Herbsleb, J.D. 2002. *Two Case Studies of Open Source Software Development.* TOSEM 11(3), 309–346. [DOI](https://doi.org/10.1145/567793.567795)

[5] Lin, B., Robles, G., & Serebrenik, A. 2017. *Developer Turnover in Global, Industrial Open Source Projects.* ICGSE. [DOI](https://doi.org/10.1109/ICGSE.2017.11)

[6] Constantinou, E., Mens, T., & Goeminne, M. 2017. *Analyzing the Evolution of Developer Retention in Software Ecosystems.* SANER. [arXiv](https://arxiv.org/abs/1708.02618)

[7] Zhou, M., & Mockus, A. 2012. *What Makes Long Term Contributors?* ICSE. [ACM](https://dl.acm.org/doi/10.5555/2337223.2337284)

[8] Avelino, G., Passos, L., Hora, A., & Valente, M.T. 2016. *A Novel Approach for Estimating Truck Factors.* [arXiv](https://arxiv.org/abs/1604.06766)

[9] Ferreira, M., Valente, M.T., & Ferreira, K. 2017. *A Comparison of Three Algorithms for Computing Truck Factors.* ICPC. [IEEE](https://ieeexplore.ieee.org/document/7961518)

[10] Cosentino, V., Izquierdo, J.L.C., & Cabot, J. 2015. *Assessing the Bus Factor of Git Repositories.* SANER. [ResearchGate](https://www.researchgate.net/publication/272794507_Assessing_the_Bus_Factor_of_Git_Repositories)

[11] Jabrayilzade, E., Evtikhiev, M., Kovalenko, V., & Bryksin, T. 2022. *Bus Factor In Practice.* [arXiv](https://arxiv.org/abs/2202.01523)

[12] Fritz, T., Murphy, G.C., Murphy-Hill, E., Ou, J., & Hill, E. 2014. *Degree-of-Knowledge.* TOSEM. [ACM](https://dl.acm.org/doi/10.1145/2786805.2786870)

[13] Von Krogh, G., Spaeth, S., & Lakhani, K.R. 2003. *Community, Joining, and Specialization in Open Source Software Innovation.* Research Policy. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0048733303000860)

[14] Shafiq, S., Mayr-Dorn, C., Mashkoor, A., & Egyed, A. 2024. *Balanced Knowledge Distribution.* JSEP. [Wiley](https://onlinelibrary.wiley.com/doi/full/10.1002/smr.2655)

[15] Foucault, M., Palyart, M., Blanc, X., Murphy, G.C., & Falleri, J.-R. 2015. *Impact of Developer Turnover.* ESEC/FSE. [ACM](https://dl.acm.org/doi/10.1145/2786805.2786870)

[16] Ferreira, F., Silva, L.L., & Valente, M.T. 2020. *Turnover in Open-Source Projects.* SBES. [ACM](https://dl.acm.org/doi/10.1145/3422392.3422433)

[17] Jamieson, H., Frluckaj, H., Dabbish, L., & Herbsleb, J.D. 2024. *Predicting Open Source Contributor Turnover.* ICSE. [DOI](https://doi.org/10.1145/3597503.3623340)

[18] Constantinou, E., & Mens, T. 2017. *An Empirical Comparison of Developer Retention.* Innovations in Systems and Software Engineering. [DOI](https://doi.org/10.1007/s11334-017-0303-4)

[19] Avelino, G., Constantinou, E., Valente, M.T., & Serebrenik, A. 2019. *On the Abandonment and Survival of Open Source Projects.* ESEM. [DOI](https://doi.org/10.1109/ESEM.2019.8870181)

[20] Kalliamvakou, E., et al. 2014. *The Promises and Perils of Mining GitHub.* MSR. [ACM](https://dl.acm.org/doi/10.1145/2597073.2597074)

[21] Spinellis, D., Giannikas, V., & Chatzigeorgiou, A. 2018. *Software Evolution.* EMSE. [PeerJ](https://peerj.com/articles/cs-372/)

[22] Zhou, M., & Mockus, A. 2015. *Why Commit Stops.* MSR. [DOI](https://doi.org/10.1109/MSR.2015.20)

[23] Bird, C., et al. 2009. *The Promises and Perils of Mining Git.* MSR. [IEEE](https://ieeexplore.ieee.org/document/5071336)

[24] Nagappan, N., & Ball, T. 2005. *Use of Relative Code Churn Measures.* ICSE. [DOI](https://doi.org/10.1145/1062455.1062535)

[25] Dey, T., et al. 2020. *Detecting and Characterizing Bots.* MSR. [DOI](https://doi.org/10.1145/3379597.3387474)

[26] Golzadeh, M., et al. 2021. *A Ground-truth Dataset for Bots.* JSS. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S016412122100008X)

[27] Park, R.E. 1992. *Software Size Measurement.* CMU SEI. [PDF](https://resources.sei.cmu.edu/asset_files/TechnicalReport/1992_004_001_55405.pdf)

[28] Landman, D., et al. 2016. *CC and SLOC Relationship.* JSEP. [Wiley](https://onlinelibrary.wiley.com/doi/10.1002/smr.1760)

[29] Borges, H., & Valente, M.T. 2018. *GitHub Star.* JSS. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0164121218301961)

[30] Borges, H., Hora, A., & Valente, M.T. 2016. *Factors Impacting Popularity.* ICSME. [IEEE](https://ieeexplore.ieee.org/document/7886993)

[31] Borges, H., Hora, A., & Valente, M.T. 2016. *Predicting Popularity.* PROMISE. [ACM](https://dl.acm.org/doi/10.1145/2915970.2915984)

[32] Jiang, J., et al. 2017. *Why and How Developers Fork.* EMSE. [Springer](https://link.springer.com/article/10.1007/s10664-016-9449-8)

[33] Pietri, A., Rousseau, G., & Zacchiroli, S. 2020. *Forking Without Clicking.* MSR. [DOI](https://doi.org/10.1145/3379597.3387450)

[34] Sheoran, J., et al. 2014. *Understanding Watchers.* MSR. [IEEE](https://ieeexplore.ieee.org/document/6884278)

[35] Kalliamvakou, E., et al. 2016. *An In-Depth Study of Mining GitHub.* EMSE. [Springer](https://link.springer.com/article/10.1007/s10664-015-9402-4)

[36] Bissyandé, T.F., et al. 2013. *Got Issues?* ISSRE. [PDF](https://ink.library.smu.edu.sg/cgi/viewcontent.cgi?article=3086&context=sis_research)

[37] Pinckney, D., et al. 2023. *Semantic Versioning in NPM.* MSR. [Conference site](https://conf.researchr.org/details/msr-2023/msr-2023-technical-papers/42/A-Large-Scale-Analysis-of-Semantic-Versioning-in-NPM)

[38] Dietrich, J., et al. 2019. *Dependency Versioning in the Wild.* MSR. [ACM](https://dl.acm.org/doi/10.1109/MSR.2019.00039)

[39] Raemaekers, S., van Deursen, A., & Visser, J. 2017. *Semantic Versioning.* JSS. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0164121216300243)

[40] Khomh, F., et al. 2012. *Do Faster Releases Improve Software Quality?* MSR. [DOI](https://doi.org/10.1109/MSR.2012.6224304)

[41] McIlwain, S., Ali, N., & Hassan, A.E. 2016. *Fresh Apps.* EMSE. [DOI](https://doi.org/10.1007/s10664-015-9391-0)

[42] CHAOSS Project. 2017–present. *CHAOSS Metrics for Community Health.* [Linux Foundation](https://chaoss.community/metrics/)

[43] Vendome, C., et al. 2017. *License Usage and Changes.* EMSE. [DOI](https://doi.org/10.1007/s10664-016-9471-y)

[44] Prana, G.A., et al. 2019. *Categorizing GitHub README Files.* EMSE. [DOI](https://doi.org/10.1007/s10664-018-9620-1)

[45] Wang, T., Wang, S., & Chen, T.H.P. 2023. *README and Popularity.* JSS. [DOI](https://doi.org/10.1016/j.jss.2023.111806)

[46] Aghaei Chadegani, A., & Sillito, J. 2022. *How ReadMe files are structured.* IST. [DOI](https://doi.org/10.1016/j.infsof.2022.106922)

[47] Goggins, S., Lumbard, K., & Germonprez, M. 2021. *Open Source Community Health.* ICSE-SEIS. [DOI](https://doi.org/10.1109/ICSE-SEIS52602.2021.00009)

[48] CHAOSS Project. 2017–present. *CHAOSS Metrics for Community Health.* [Linux Foundation](https://chaoss.community/metrics/)

[49] Kanaji, R., et al. 2024. *Security-Policy Related Issues.* arXiv:2510.05604. [arXiv](https://arxiv.org/abs/2510.05604)

[50] Trockman, A., Zhou, S., Kästner, C., & Vasilescu, B. 2018. *Repository Badges in npm.* ICSE. [DOI](https://doi.org/10.1145/3180155.3180208)

[51] Vasa, R., Lumpe, M., Branch, P., & Nierstrasz, O. 2009. *Gini Coefficient.* ICSM. [DOI](https://doi.org/10.1109/ICSM.2009.5306317)

[52] Giger, E., Pinzger, M., & Gall, H. 2011. *Using the Gini Coefficient for Bug Prediction.* IWPSE-EVOL. [DOI](https://doi.org/10.1145/2024445.2024457)

[53] Chełkowski, T., Gloor, P., & Jemielniak, D. 2016. *Inequalities in Open Source Software Development.* PLOS ONE. [DOI](https://doi.org/10.1371/journal.pone.0152976)

[54] Arafat, O., & Riehle, D. 2009. *The Commit Size Distribution of Open Source Software.* HICSS. [DOI](https://doi.org/10.1109/HICSS.2009.116)

[55] Kaur, A., Kaur, K., & Pathak, K. 2020. *Entropy Churn Metrics for Fault Prediction.* Entropy 20(12). [MDPI](https://www.mdpi.com/1099-4300/20/12/955)

[56] Hassan, A.E., & Holt, R.C. 2005. *The Top Ten List: Dynamic Fault Prediction.* ICSM. [DOI](https://doi.org/10.1109/ICSM.2005.68)

[57] Bird, C., et al. 2011. *Don't Touch My Code!* ESEC/FSE. [DOI](https://doi.org/10.1145/2025113.2025119)

[58] Greiler, M., Herzig, K., & Czerwonka, J. 2015. *Code Ownership and Software Quality.* MSR. [DOI](https://doi.org/10.1109/MSR.2015.9)

[59] Rahman, F., & Devanbu, P. 2011. *Ownership, Experience and Defects.* ICSE. [DOI](https://doi.org/10.1145/1985793.1985859)

[60] Munson, J.C., & Elbaum, S. 1998. *Code Churn.* ICSM. [DOI](https://doi.org/10.1109/ICSM.1998.738505)

[61] Shin, Y., Meneely, A., Williams, L., & Osborne, J.A. 2011. *Evaluating Complexity, Code Churn, and Developer Activity Metrics.* TSE. [DOI](https://doi.org/10.1109/TSE.2010.68)

[62] Faragó, D., Hegedűs, P., Ferenc, R., & Gyimóthy, T. 2015. *Cumulative Code Churn.* SCAM. [DOI](https://doi.org/10.1109/SCAM.2015.7335404)
