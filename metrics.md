# Scientific Software Sustainability Metrics

## Metric Family Summary

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

---

## 1. Development Activity Pattern Metrics

Metrics measuring regularity and consistency of development effort over time. All metrics are calculated at both weekly and monthly intervals.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `commit_entropy` | Entropy of commit presence probabilities across time periods | Regular patterns indicate sustained engagement; bursty patterns may align with academic calendars | Higher = more predictable | CHAOSS Burstiness; EPJ Data Science; [17], [18], [19], [20] |
| `commit_variation` | Coefficient of variation (σ/μ) of commit presence | Lower variation suggests consistent development effort | Lower = more consistent | Similar to CHAOSS Burstiness; [17], [18], [19] |
| `commit_frac` | Fraction of time periods containing ≥1 commit | Indicates sustained development throughout project lifecycle | Higher = more active periods | Adapted from MSR 2024 "consistency" |
| `lines_changed_entropy` | Entropy of lines changed per time period | Regular code changes suggest ongoing maintenance | Higher = more regular intensity | Extension of commit entropy; [17], [18] |
| `lines_changed_variation` | Coefficient of variation of lines changed | Predictable development intensity patterns | Lower = more consistent | Extension of commit variation |

## 2. Development Episode Characteristics

Metrics describing the temporal structure of active and inactive development periods.

| Metric | Description | Sustainability Relationship | Directionality |
|--------|-------------|---------------------------|----------------|
| `median_commit_span` | Median consecutive time periods with commits | Longer spans indicate sustained development episodes | Higher = longer work periods |
| `mean_commit_span` | Mean consecutive time periods with commits | Typical sustained development duration | Higher = longer work periods |
| `std_commit_span` | Standard deviation of commit span lengths | Variability in sustained development patterns | Context-dependent |
| `median_no_commit_span` | Median consecutive time periods without commits | Shorter gaps indicate continuous engagement | Lower = shorter gaps |
| `mean_no_commit_span` | Mean consecutive time periods without commits | Typical dormancy between development activities | Lower = shorter gaps |
| `std_no_commit_span` | Standard deviation of no-commit span lengths | Variability in dormancy patterns | Context-dependent |

## 3. Contributor Engagement Patterns

Metrics characterizing contributor stability and engagement duration.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `stable_contributors_count` | Contributors active across multiple time periods | Sustained community engagement and knowledge retention | Higher = more retention | CHAOSS Occasional Contributors (inverse); [1], [2], [3], [4] |
| `transient_contributors_count` | Contributors active within single time period only | May indicate good onboarding or poor retention depending on stable contributor presence | Context-dependent | CHAOSS Occasional Contributors; [1], [2], [3] |
| `median_contribution_span_days` | Median individual contributor engagement duration | Better contributor retention | Higher = longer engagement | [5], [6], [7] |
| `mean_contribution_span_days` | Mean individual contributor engagement duration | Typical contributor involvement | Higher = longer engagement | [5], [6], [7] |
| `normalized_median_span` | Median contribution span / total project duration | Accounts for project age in assessing engagement | Higher = longer relative engagement | [5], [6] |
| `normalized_mean_span` | Mean contribution span / total project duration | Project-adjusted engagement duration | Higher = longer relative engagement | [5], [6] |

## 4. Contributor Distribution Metrics

Metrics examining how development effort and knowledge are distributed among contributors.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `unique_contributors_count` | Total distinct contributors | Broader engagement reduces bus factor | Higher = more contributors | [4] and numerous MSR studies |
| `contributor_absence_factor_code` | Contributors needed for 50% of code changes (bus factor) | Concentration risk for code development | Higher = less risk | [8], [9], [10], [11] |
| `contributor_absence_factor_all` | Contributors needed for 50% of all changes | Overall concentration risk including documentation | Higher = less risk | [8], [9], [10], [11] |
| `contributor_specialization` | Entropy of contributor-file overlap patterns | Balance between expertise and knowledge silos | Context-dependent | [12], [13], [14] |
| `specialists_contributor_count` | Contributors touching ≤3 files | Deep expertise in specific areas | Context-dependent | [12], [13], [14] |
| `generalists_contributor_count` | Contributors touching >3 files | Broader coverage reduces specialization risks | Higher = more coverage | [12], [13] |
| `contributor_change_count` | Contributors changed between first/last 20% of commits | Turnover may indicate challenges or natural evolution | Context-dependent | [15], [16], [17], [18] |
| `contributor_same_count` | Contributors present in first and last 20% of commits | Sustained engagement and knowledge retention | Higher = more continuity | [15], [16] |

## 5. Repository Timeline Metrics

Basic temporal metadata for development history analysis.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `initial_commit_datetime` | First commit timestamp | Project age calculation; temporal studies | Metadata | [19], [20], [21] |
| `most_recent_commit_datetime` | Latest commit timestamp | Activity status determination | Metadata | [19], [20], [21] |
| `most_recent_substantial_commit_datetime` | Latest commit >10th percentile lines changed | Recent substantial development (excludes trivial changes) | Context-dependent | [22], [23] |
| `to_most_recent_commit_duration_days` | Days from first to latest commit | Sustained development over time | Higher = longer active | [19], [20], [21] |
| `to_most_recent_substantial_commit_duration_days` | Days from first to latest substantial commit | Sustained meaningful development | Higher = longer active | [22], [23] |

## 6. Development Activity Volume

Metrics quantifying overall development activity and effort.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `commits_count` | Total commits | Activity indicator; quality matters more than quantity | Context-dependent | [24], [26] |
| `non_bot_commits_count` | Commits excluding automated/bot activity | Human development effort | Context-dependent | [25], [26] |
| `coding_commits_count` | Commits modifying code files | Active feature development vs. documentation | Context-dependent | [24] |
| `source_lines_of_code` | Total source code lines | Size indicator for sustainability needs | Context-dependent | [27], [28] |
| `source_lines_of_comments` | Total comment lines | Better maintainability and documentation | Higher = more documented | [27], [28] |

## 7. Community Engagement Metrics

Metrics reflecting community interest and participation through GitHub features.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `stars_count` | GitHub stars | Community interest and broader impact | Higher = more interest | [29], [30], [31] |
| `forks_count` | Repository forks | Community engagement and distributed development potential | Higher = more engagement | [32], [33] |
| `watchers_count` | Active watchers | Community monitoring project | Higher = more active interest | [34], [35] |
| `open_issues_count` | Current open issues | Active engagement or maintenance challenges | Context-dependent | [36] |

## 8. Release Management Metrics

Metrics related to versioning and release practices.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `semver_tags_count` | Semantic version tags | Formal release management practices | Higher = better management | [37], [38], [39] |
| `non_semver_tags_count` | Non-semantic version tags (e.g., CalVer) | Alternative versioning schemes | Context-dependent | [38] |
| `total_tags_count` | All version tags | Some versioning better than none | Higher = better control | [37], [38], [39] |

## 9. Repository Classification Metadata

Descriptive metadata for filtering and comparative analysis.

| Metric | Description | Sustainability Relationship | Directionality |
|--------|-------------|---------------------------|----------------|
| `repo_primary_language` | Primary programming language | Affects community size, tooling, long-term support | Metadata |
| `repo_classification` | Project type (single-experiment, lab-tool, specialized-instrument, field-tool) | Different types have different sustainability patterns (adapted from Eghbal's "Working in Public") | Type-specific |
| `file_extensions_set` | File extensions present | Diversity indicates complexity; homogeneity indicates focus | Context-dependent |

## 10. Documentation and Best Practices

Binary indicators of documentation files and development practices supporting sustainability.

### Core Documentation

| Metric | Description | Importance | Related Work |
|--------|-------------|------------|--------------|
| `repo_linter_license_file_exists` | LICENSE file present | Legal clarity for reuse | [43] |
| `repo_linter_readme_file_exists` | README file present | Basic project understanding | [44], [45], [46] |
| `repo_linter_readme_references_license` | README mentions license | Improves legal clarity | [44], [45] |
| `repo_linter_changelog_file_exists` | CHANGELOG present | Tracks changes and updates | |

### Community Guidelines

| Metric | Description | Importance | Related Work |
|--------|-------------|------------|--------------|
| `repo_linter_contributing_file_exists` | CONTRIBUTING guidelines present | Facilitates participation | [47], [48] |
| `repo_linter_code_of_conduct_file_exists` | Code of conduct present | Promotes inclusive environment | [47], [48] |
| `repo_linter_code_of_conduct_file_contains_email` | Code of conduct includes contact | Reporting mechanism | |
| `repo_linter_security_file_exists` | SECURITY policy present | Responsible security handling | [49] |
| `repo_linter_support_file_exists` | SUPPORT info present | Reduces maintainer burden | [47], [48] |

### Development Infrastructure

| Metric | Description | Importance | Related Work |
|--------|-------------|------------|--------------|
| `repo_linter_test_directory_exists` | Test directory present | Testing infrastructure | [50] |
| `repo_linter_integrates_with_ci` | CI integration | Automated testing/deployment | [50] |
| `repo_linter_github_issue_template_exists` | Issue templates present | Improves issue quality | |
| `repo_linter_github_pull_request_template_exists` | PR templates present | Facilitates code review | |
| `repo_linter_binaries_not_present` | No binaries in repo | Version control best practices | |

## 11. Gini Coefficients (experimental)

Alternative inequality measures complementing existing sustainability indicators.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `commit_gini_coefficient` | Gini coefficient of commits across time periods | Alternative inequality measure to entropy (0=equal, 1=maximum inequality) | Lower = more equal | [51], [52] |
| `lines_changed_gini_coefficient` | Gini coefficient of lines changed across time periods | Development intensity inequality | Lower = more equal | [51], [52] |
| `contributor_commit_gini` | Gini coefficient of commits per contributor | Measures commit distribution democracy | Context-dependent | [53], [52] |
| `contributor_lines_gini` | Gini coefficient of lines changed per contributor | Code contribution effort concentration | Context-dependent | [51], [52] |
| `commit_size_gini` | Gini coefficient of individual commit sizes | Few massive commits vs. many small commits | Context-dependent | [54] |
| `time_between_commits_gini` | Gini coefficient of inter-commit intervals | Long gaps punctuated by bursts | Context-dependent | [55], [56] |

## 12. Commit Pattern Metrics

Metrics analyzing commit sizing and timing patterns.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `commit_size_entropy` | Entropy of commit sizes (lines changed) | Mix of small fixes and large features vs. consistent sizing | Context-dependent | [54] |
| `commit_size_variation` | Coefficient of variation of commit sizes | Consistent commit practices | Lower = more consistent | [54] |
| `time_between_commits_entropy` | Entropy of inter-commit time intervals | Regularity of development timing | Higher = more regular | [55], [56] |
| `time_between_commits_variation` | Coefficient of variation of inter-commit intervals | Consistent development rhythm | Lower = more consistent | [55], [56] |

## 13. Advanced Sustainability Indicators

Higher-level metrics for comprehensive sustainability assessment.

| Metric | Description | Sustainability Relationship | Directionality | Related Work |
|--------|-------------|---------------------------|----------------|--------------|
| `documentation_to_code_ratio` | Documentation lines / source code lines | Maintainability and user onboarding | Higher = more documented | No direct validation found |
| `contributor_retention_rate` | % contributors returning within 6 months of first commit | Welcoming community and sustainable practices | Higher = better retention | [5], [6], [7], [18] |
| `releases_per_year` | Tagged releases per year | Active maintenance and user focus | Higher = more regular | [40], [41], [42] |
| `knowledge_concentration_risk` | % files modified by only one contributor | Knowledge silos from contributor departure | Lower = less concentration | [57], [58], [59] |
| `simple_code_churn_rate` | (Lines added + deleted) / current total lines | Code volatility or active development | Context-dependent | [24], [60], [61], [62] |

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

[57] Bird, C., et al. 2011. *Don’t Touch My Code!* ESEC/FSE. [DOI](https://doi.org/10.1145/2025113.2025119)

[58] Greiler, M., Herzig, K., & Czerwonka, J. 2015. *Code Ownership and Software Quality.* MSR. [DOI](https://doi.org/10.1109/MSR.2015.9)

[59] Rahman, F., & Devanbu, P. 2011. *Ownership, Experience and Defects.* ICSE. [DOI](https://doi.org/10.1145/1985793.1985859)

[60] Munson, J.C., & Elbaum, S. 1998. *Code Churn.* ICSM. [DOI](https://doi.org/10.1109/ICSM.1998.738505)

[61] Shin, Y., Meneely, A., Williams, L., & Osborne, J.A. 2011. *Evaluating Complexity, Code Churn, and Developer Activity Metrics.* TSE. [DOI](https://doi.org/10.1109/TSE.2010.68)

[62] Faragó, D., Hegedűs, P., Ferenc, R., & Gyimóthy, T. 2015. *Cumulative Code Churn.* SCAM. [DOI](https://doi.org/10.1109/SCAM.2015.7335404)

