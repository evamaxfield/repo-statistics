#!/usr/bin/env python

"""Classify every commit as human, bot, or agent work, and credit co-authors."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import polars as pl

###############################################################################

# Copybara's export service account has no "[bot]" suffix
DEFAULT_BOT_NAME_INDICATORS = ("[bot]", "copybara-service")
# Service accounts: GitHub Actions, the Gitter badger (README PRs), Quantified Code, Waffle.io,
# Copybara
DEFAULT_BOT_EMAIL_INDICATORS = (
    "[bot]",
    "action@github.com",
    "badger@gitter.im",
    "@quantifiedcode.com",
    "@waffle.io",
    "copybara-worker@google.com",
)

# Agent -> identity substrings, matched against lowercased name/email fields and
# Co-authored-by lines. Bare name tokens (e.g. "devin", "claude") match real people.
AGENT_PATTERNS: dict[str, list[str]] = {
    "devin": ["devin-ai-integration[bot]"],
    "sweep": ["sweep-ai[bot]"],
    "copilot": ["copilot-swe-agent[bot]"],
    "codeium": [],
    "claude": ["claude[bot]", "noreply@anthropic.com"],
    "cursor": ["cursor[bot]", "cursoragent@cursor.com"],
    "jules": ["google-labs-jules[bot]"],
    "gemini": ["gemini-cli[bot]"],
    "aider": ["(aider)", "aider@aider.chat"],
    "amp": ["amp@ampcode.com"],
    # Placeholder identity some agent tools commit under
    "ai_assistant": ["bot@example.com"],
}

# Marker -> predicate over the lowercased full commit message (subject + body).
COMMIT_MARKERS: dict[str, Callable[[str], bool]] = {
    "claude_code": lambda message: "generated with [claude code]" in message,
    "aider": lambda message: message.startswith("aider: "),
}


@dataclass
class CommitTrailerInfo:
    is_merge: bool
    # Agents named by a Co-authored-by trailer
    coauthor_agents: set[str] = field(default_factory=set)
    # Agents named by a commit message marker
    markers: set[str] = field(default_factory=set)
    # (name, email) of every Co-authored-by trailer that names no agent
    other_trailers: list[tuple[str, str | None]] = field(default_factory=list)

    @property
    def agent_associated(self) -> bool:
        """Whether any agent trailer or marker is present."""
        return bool(self.coauthor_agents or self.markers)


###############################################################################


def add_contribution_type(
    changes_df: pl.DataFrame,
    contributor_name_col: str,
    contributor_email_col: str,
    bot_name_indicators: Iterable[str] | None = DEFAULT_BOT_NAME_INDICATORS,
    bot_email_indicators: Iterable[str] | None = DEFAULT_BOT_EMAIL_INDICATORS,
) -> pl.DataFrame:
    """Add a `contribution_type` column: agent rules first, then bot, then human."""
    name = pl.col(contributor_name_col).str.to_lowercase()
    email = pl.col(contributor_email_col).str.to_lowercase()

    agent_expr = pl.lit(False)
    for identities in AGENT_PATTERNS.values():
        for identity in identities:
            agent_expr = (
                agent_expr
                | name.str.contains(identity, literal=True).fill_null(False)
                | email.str.contains(identity, literal=True).fill_null(False)
            )

    bot_expr = pl.lit(False)
    for indicator in bot_name_indicators or ():
        bot_expr = bot_expr | name.str.contains(indicator, literal=True).fill_null(False)
    for indicator in bot_email_indicators or ():
        bot_expr = bot_expr | email.str.contains(indicator, literal=True).fill_null(False)

    return changes_df.with_columns(
        pl.when(agent_expr)
        .then(pl.lit("agent"))
        .when(bot_expr)
        .then(pl.lit("bot"))
        .otherwise(pl.lit("human"))
        .alias("contribution_type")
    )


def add_human_credit_rows(
    commits_df: pl.DataFrame,
    deltas_df: pl.DataFrame,
    trailer_info: dict[str, CommitTrailerInfo],
    contributor_name_col: str,
    contributor_email_col: str,
    bot_name_indicators: Iterable[str] | None = DEFAULT_BOT_NAME_INDICATORS,
    bot_email_indicators: Iterable[str] | None = DEFAULT_BOT_EMAIL_INDICATORS,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Append one human-typed copy of each agent commit (and its file deltas) per human
    Co-authored-by trailer, and flag them in an `is_credit_row` column.
    """
    commits_df = commits_df.with_columns(pl.lit(False).alias("is_credit_row"))
    deltas_df = deltas_df.with_columns(pl.lit(False).alias("is_credit_row"))

    agent_hashes = set(commits_df.filter(pl.col("contribution_type") == "agent")["commit_hash"])
    trailer_rows = [
        (commit_hash, name, email)
        for commit_hash, info in trailer_info.items()
        if commit_hash in agent_hashes
        for name, email in info.other_trailers
    ]
    if not trailer_rows:
        return commits_df, deltas_df

    trailers_df = (
        pl.DataFrame(
            trailer_rows,
            schema={
                "commit_hash": pl.String,
                "trailer_name": pl.String,
                "trailer_email": pl.String,
            },
            orient="row",
        )
        .pipe(add_contribution_type, "trailer_name", "trailer_email")
        .filter(pl.col("contribution_type") == "human")
        .drop("contribution_type")
        .unique(maintain_order=True)
    )

    def _with_credit_rows(df: pl.DataFrame) -> pl.DataFrame:
        credit_df = (
            df.join(trailers_df, on="commit_hash", how="inner")
            .with_columns(
                pl.col("trailer_name").alias(contributor_name_col),
                pl.col("trailer_email").alias(contributor_email_col),
                pl.lit("human").alias("contribution_type"),
                pl.lit(True).alias("is_credit_row"),
            )
            .drop("trailer_name", "trailer_email")
        )
        return pl.concat([df, credit_df])

    return _with_credit_rows(commits_df), _with_credit_rows(deltas_df)


def add_contribution_set_flags(
    real_commits_df: pl.DataFrame,
    credited_hashes: set[str],
    agent_associated_hashes: set[str],
) -> pl.DataFrame:
    """
    Add `in_human`, `in_agent` and `in_bot` set-membership flags to one-row-per-commit
    data. A commit with a human and an agent party is in both the human and agent sets.
    """
    commit_type = pl.col("contribution_type")
    commit_hash = pl.col("commit_hash")
    return real_commits_df.with_columns(
        (
            (commit_type == "human")
            | ((commit_type == "agent") & commit_hash.is_in(credited_hashes))
        ).alias("in_human"),
        (
            (commit_type == "agent")
            | ((commit_type == "human") & commit_hash.is_in(agent_associated_hashes))
        ).alias("in_agent"),
        (commit_type == "bot").alias("in_bot"),
    )
