#!/usr/bin/env python

"""Merge the different names and emails one person commits under into a single identity."""

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

import polars as pl
from rapidfuzz import fuzz

###############################################################################

_GITHUB_NOREPLY_DOMAIN = "users.noreply.github.com"
_MAX_FUZZY_IDENTITIES = 500
_MIN_HANDLE_LENGTH = 3
_MIN_KEY_LETTERS = 4
_MIN_HANDLE_PREFIX_LETTERS = 6
_MIN_NAME_PREFIX_LETTERS = 8
_MIN_OTHER_SURNAME_LETTERS = 3
_MAX_LOGIN_INITIALS = 3
# Letter-only keys that never merge on name alone
_PLACEHOLDER_KEYS = frozenset(
    {
        "unknown",
        "yourname",
        "yourusername",
        "user",
        "root",
        "admin",
        "git",
        "ubuntu",
        "anonymous",
        "none",
    }
)
# Email domains shared by many people, so never evidence for one person
_COMMON_EMAIL_PROVIDERS = frozenset(
    {"gmail", "outlook", "hotmail", "yahoo", "protonmail", "icloud", "qq", "github", "users"}
)

# Matches how contributors.py normalizes names before counting
_NORMALIZED_NAME = pl.col("name").str.to_lowercase().str.strip_chars()
_NORMALIZED_EMAIL = pl.col("email").fill_null("").str.to_lowercase().str.strip_chars()

###############################################################################


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[Hashable, Hashable] = {}

    def find(self, item: Hashable) -> Hashable:
        root = self._parent.setdefault(item, item)
        while root != self._parent[root]:
            self._parent[root] = self._parent[self._parent[root]]
            root = self._parent[root]
        return root

    def union(self, a: Hashable, b: Hashable) -> bool:
        root_a, root_b = self.find(a), self.find(b)
        if root_a == root_b:
            return False
        self._parent[root_b] = root_a
        return True


def _is_generic_email(email: str) -> bool:
    local, at, domain = email.partition("@")
    if not at or email == "(none)":
        return True
    if domain == _GITHUB_NOREPLY_DOMAIN:
        return False
    return (
        local in {"noreply", "no-reply"}
        or domain.startswith("localhost")
        or domain == "local"
        or domain.endswith(".local")
    )


def _github_login(email: str) -> str | None:
    local, _, domain = email.partition("@")
    if domain != _GITHUB_NOREPLY_DOMAIN:
        return None
    return local.split("+")[-1] or None


def _github_account_id(email: str) -> str | None:
    # The numeric account id in `123+login@users.noreply.github.com`; it survives a rename
    local, _, domain = email.partition("@")
    account_id, plus, _ = local.partition("+")
    if domain != _GITHUB_NOREPLY_DOMAIN or not plus or not account_id.isdigit():
        return None
    return account_id


def _letters(text: str) -> str:
    # Lowercase, accent-stripped, letters only: the comparison key for names and handles
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if char.isascii() and char.isalpha())


def _name_tokens(raw_name: str) -> list[str]:
    # Split on camelCase and any non-letter, then keep the letters of each piece
    decomposed = unicodedata.normalize("NFKD", raw_name)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", unaccented)
    return [token for token in map(_letters, re.split(r"[^A-Za-z]+", spaced)) if token]


@dataclass(frozen=True)
class _Node:
    """A normalized name, split by GitHub login when one name is used with several logins."""

    name: str
    login: str


def _node_for(name: str, email: str, name_logins: set[str]) -> _Node:
    # A name used with several GitHub logins is several people; otherwise one node per name
    if len(name_logins) > 1:
        return _Node(name, _github_login(email) or "")
    return _Node(name, next(iter(name_logins), ""))


def _group_by_root(uf: _UnionFind, nodes: Iterable[_Node]) -> dict[Hashable, list[_Node]]:
    groups: dict[Hashable, list[_Node]] = defaultdict(list)
    for node in nodes:
        groups[uf.find(node)].append(node)
    return groups


@dataclass
class _Identity:
    """One merged cluster: the names it commits under and the handles in its emails."""

    names: list[list[str]]  # letter-only tokens per name
    handles: set[str]  # letter-only email local parts and GitHub logins
    logins: set[str]  # letter-only GitHub logins from noreply emails
    email_locals: set[str]  # letter-only local parts of all non-noreply emails
    email_domains: set[str]  # letter-only registrable labels of all non-noreply emails

    @property
    def name_keys(self) -> set[str]:
        # Whole names as one string, minus keys too short or generic to match on
        keys = {"".join(tokens) for tokens in self.names}
        return {
            key for key in keys if len(key) >= _MIN_KEY_LETTERS and key not in _PLACEHOLDER_KEYS
        }

    @property
    def full_names(self) -> list[list[str]]:
        return [tokens for tokens in self.names if len(tokens) >= 2]

    @property
    def first_names(self) -> set[str]:
        return {tokens[0] for tokens in self.full_names}

    @property
    def single_names(self) -> set[str]:
        return {tokens[0] for tokens in self.names if len(tokens) == 1} & self.name_keys


def _keys_link(keys_a: set[str], keys_b: set[str]) -> bool:
    for key_a in keys_a:
        for key_b in keys_b:
            short, long = sorted((key_a, key_b), key=len)
            # Equal keys, or a long enough key that starts the other
            if len(short) >= _MIN_KEY_LETTERS and short == long:
                return True
            if len(short) >= _MIN_NAME_PREFIX_LETTERS and long.startswith(short):
                return True
    return False


def _login_is_email_local(a: _Identity, b: _Identity) -> bool:
    # One side's GitHub login is the other side's email local part (e.g. etal@laptop.example)
    shared = (a.logins & b.email_locals) | (b.logins & a.email_locals)
    return any(len(key) >= _MIN_KEY_LETTERS and key not in _PLACEHOLDER_KEYS for key in shared)


def _domain_label(email: str) -> str:
    # The label before the TLD, e.g. "puer-robustus" in alex@puer-robustus.eu
    labels = email.partition("@")[2].split(".")
    return _letters(labels[-2]) if len(labels) >= 2 else ""


def _domain_is_login(a: _Identity, b: _Identity) -> bool:
    # One side's email domain is the other side's GitHub login (a personal domain)
    shared = (a.email_domains & b.logins) | (b.email_domains & a.logins)
    return any(
        len(key) >= _MIN_KEY_LETTERS
        and key not in _PLACEHOLDER_KEYS
        and key not in _COMMON_EMAIL_PROVIDERS
        for key in shared
    )


def _login_is_first_name_and_initials(logins: set[str], full_names: list[list[str]]) -> bool:
    for login in logins:
        for tokens in full_names:
            first_name, initials = tokens[0], login[len(tokens[0]) :]
            # "Yulia Kremlyakova" -> "yuliajk": first name plus initials ending in the surname's
            if (
                len(first_name) >= _MIN_KEY_LETTERS
                and login.startswith(first_name)
                and 1 <= len(initials) <= _MAX_LOGIN_INITIALS
                and initials[-1] == tokens[-1][0]
            ):
                return True
    return False


def _handle_matches_initial_surname(keys: set[str], full_names: list[list[str]]) -> bool:
    for key in keys:
        for tokens in full_names:
            # "Cassandra Goldberg" -> "cgoldberg"; a handle may be a truncated prefix of it
            target = tokens[0][0] + tokens[-1]
            if key == target and len(key) >= _MIN_KEY_LETTERS:
                return True
            if len(key) >= _MIN_HANDLE_PREFIX_LETTERS and target.startswith(key):
                return True
    return False


def _names_match(tokens_a: list[str], tokens_b: list[str], threshold: float) -> bool:
    if fuzz.token_sort_ratio(" ".join(tokens_a), " ".join(tokens_b)) >= threshold:
        return True
    smaller, larger = sorted((set(tokens_a), set(tokens_b)), key=len)
    return len(smaller) >= 2 and smaller <= larger


def _handle_supports_name(handle: str, tokens: list[str], threshold: float) -> bool:
    if len(handle) < _MIN_HANDLE_LENGTH:
        return False
    if fuzz.ratio(handle, "".join(tokens)) >= threshold:
        return True
    return len(tokens) >= 2 and handle == tokens[0][0] + tokens[-1]


def _fuzzy_names_match(a: _Identity, b: _Identity, threshold: float) -> bool:
    for name_a in a.names:
        for name_b in b.names:
            if "".join(name_a) in _PLACEHOLDER_KEYS or "".join(name_b) in _PLACEHOLDER_KEYS:
                continue
            if not _names_match(name_a, name_b, threshold):
                continue
            # Similar names also need a handle that backs one of them
            if any(_handle_supports_name(h, name_b, threshold) for h in a.handles) or any(
                _handle_supports_name(h, name_a, threshold) for h in b.handles
            ):
                return True
    return False


def _identities_match(a: _Identity, b: _Identity, threshold: float) -> bool:
    # A lone first name whose own handles spell another surname is not this full name
    if _contradicts_lone_first_name(a, b) or _contradicts_lone_first_name(b, a):
        return False
    keys_a, keys_b = a.name_keys, b.name_keys
    # Equal or long-prefix keys across names and handles
    if _keys_link(keys_a, keys_b | b.handles) or _keys_link(a.handles, keys_b):
        return True
    # A name or handle that spells the other side's initial + surname
    if _handle_matches_initial_surname(keys_a | a.handles, b.full_names):
        return True
    if _handle_matches_initial_surname(keys_b | b.handles, a.full_names):
        return True
    # A GitHub login that is the other side's email local part
    if _login_is_email_local(a, b):
        return True
    # A GitHub login that is the other side's email domain
    if _domain_is_login(a, b):
        return True
    # A GitHub login that is the other side's first name plus initials
    if _login_is_first_name_and_initials(
        a.logins, b.full_names
    ) or _login_is_first_name_and_initials(b.logins, a.full_names):
        return True
    return _fuzzy_names_match(a, b, threshold)


def _build_identities(
    clusters: dict[Hashable, list[_Node]],
    emails_by_node: dict[_Node, set[str]],
    raw_names: dict[_Node, str],
) -> dict[Hashable, _Identity]:
    identities: dict[Hashable, _Identity] = {}
    for root, nodes in clusters.items():
        # Handles: GitHub login or email local part, from real emails only
        handles = {
            _letters(_github_login(email) or email.partition("@")[0])
            for node in nodes
            for email in emails_by_node[node]
            if not _is_generic_email(email)
        }
        # Logins come from noreply emails; local parts and domains from any other email
        emails = {email for node in nodes for email in emails_by_node[node]}
        logins = {_letters(login) for email in emails if (login := _github_login(email))}
        other_emails = [
            email for email in emails if "@" in email and _github_login(email) is None
        ]
        identities[root] = _Identity(
            names=[tokens for node in nodes if (tokens := _name_tokens(raw_names[node]))],
            handles=handles - _PLACEHOLDER_KEYS,
            logins=logins,
            email_locals={_letters(email.partition("@")[0]) for email in other_emails},
            email_domains={_domain_label(email) for email in other_emails},
        )
    return identities


def _handle_names_another_surname(handles: set[str], first_name: str, surname: str) -> bool:
    for handle in handles:
        _, found, tail = handle.partition(first_name)
        # "benjaminkreis" has "kreis" after the first name, which does not start "ramhorst"
        if found and len(tail) >= _MIN_OTHER_SURNAME_LETTERS and not surname.startswith(tail):
            return True
    return False


def _contradicts_lone_first_name(lone: _Identity, other: _Identity) -> bool:
    handles = lone.email_locals | lone.logins
    for first_name in lone.single_names:
        surnames = [tokens[-1] for tokens in other.full_names if tokens[0] == first_name]
        # Every full name starting with this first name has a surname the handles contradict
        if surnames and all(
            _handle_names_another_surname(handles, first_name, s) for s in surnames
        ):
            return True
    return False


def _lone_first_name_links(
    identities: dict[Hashable, _Identity],
) -> list[tuple[Hashable, Hashable]]:
    # Index each first name by the identities that have a full name starting with it
    first_name_owners: dict[str, list[Hashable]] = defaultdict(list)
    for root, identity in identities.items():
        for first_name in identity.first_names:
            first_name_owners[first_name].append(root)

    # A lone first name links to the full name that starts with it, but only if exactly one does
    links: list[tuple[Hashable, Hashable]] = []
    for root, identity in identities.items():
        for single_name in identity.single_names:
            # Skip owners whose surname the lone identity's own handles contradict
            owners = [
                owner
                for owner in first_name_owners.get(single_name, [])
                if owner != root
                and not _contradicts_lone_first_name(identity, identities[owner])
            ]
            if len(owners) == 1:
                links.append((owners[0], root))
    return links


def _drop_ambiguous_links(
    links: list[tuple[Hashable, Hashable]], identities: dict[Hashable, _Identity]
) -> list[tuple[Hashable, Hashable]]:
    # Which logins each login-less identity is linked to
    linked_logins: dict[Hashable, set[Hashable]] = defaultdict(set)
    for a, b in links:
        for loose, other in ((a, b), (b, a)):
            if not identities[loose].logins and identities[other].logins:
                linked_logins[loose].add(other)

    # A login-less identity linked to clusters with different logins joins none of them
    ambiguous = {root for root, others in linked_logins.items() if len(others) > 1}
    return [
        (a, b)
        for a, b in links
        if not (a in ambiguous and identities[b].logins)
        and not (b in ambiguous and identities[a].logins)
    ]


def _union_unless_logins_differ(
    uf: _UnionFind, logins: dict[Hashable, set[str]], a: Hashable, b: Hashable
) -> bool:
    root_a, root_b = uf.find(a), uf.find(b)
    # Clusters that each carry a GitHub login are different people
    if root_a == root_b or (logins[root_a] and logins[root_b]):
        return False
    uf.union(root_a, root_b)
    logins[root_a] |= logins.pop(root_b)
    return True


def _merge_by_names(
    uf: _UnionFind,
    emails_by_node: dict[_Node, set[str]],
    raw_names: dict[_Node, str],
    threshold: float | None,
) -> int:
    # No threshold turns off every name-based rule; too many identities is too slow to compare
    if threshold is None:
        return 0
    clusters = _group_by_root(uf, emails_by_node)
    if len(clusters) > _MAX_FUZZY_IDENTITIES:
        return 0

    identities = _build_identities(clusters, emails_by_node, raw_names)

    # Compare every pair of clusters left by the email and login merges
    roots = list(clusters)
    links = [
        (root_a, root_b)
        for i, root_a in enumerate(roots)
        for root_b in roots[i + 1 :]
        if _identities_match(identities[root_a], identities[root_b], threshold)
    ]
    links += _lone_first_name_links(identities)

    # Name-based links never join clusters that carry different GitHub logins
    logins = {root: set(identity.logins) for root, identity in identities.items()}
    return sum(
        _union_unless_logins_differ(uf, logins, a, b)
        for a, b in _drop_ambiguous_links(links, identities)
    )


def _merge_by_emails_and_logins(uf: _UnionFind, emails_by_node: dict[_Node, set[str]]) -> None:
    for node, emails in emails_by_node.items():
        # A name equal to a login joins it, unless the name already carries a different login
        if len(node.name) >= 3 and not node.login:
            uf.union(node, ("login", node.name))
        for email in emails:
            if not _is_generic_email(email):
                uf.union(node, ("email", email))
            login = _github_login(email)
            if login is not None:
                uf.union(node, ("login", login))
            # Renamed accounts keep their id, so logins sharing an id are one account
            account_id = _github_account_id(email)
            if account_id is not None:
                uf.union(node, ("github_id", account_id))


def _canonical_names(
    clusters: dict[Hashable, list[_Node]], commit_counts: dict[str, int]
) -> dict[_Node, str]:
    # Most frequent name in each cluster, ties broken alphabetically
    names = {
        root: min(nodes, key=lambda n: (-commit_counts.get(n.name, 0), n.name)).name
        for root, nodes in clusters.items()
    }
    shared = {name for name, count in Counter(names.values()).items() if count > 1}

    mapping: dict[_Node, str] = {}
    for root, nodes in clusters.items():
        logins = sorted({node.login for node in nodes if node.login})
        # People who share a name keep distinct keys by adding their GitHub login
        name = (
            f"{names[root]} ({logins[0]})" if names[root] in shared and logins else names[root]
        )
        mapping.update(dict.fromkeys(nodes, name))
    return mapping


###############################################################################


def resolve_contributor_identities(
    commits_df: pl.DataFrame,
    deltas_df: pl.DataFrame,
    name_col: str,
    email_col: str,
    fuzzy_identity_threshold: float | None = 90,
) -> tuple[pl.DataFrame, pl.DataFrame, int]:
    """
    Merge human contributor identities and overwrite `name_col` with a canonical key.

    Merges run in order over the union of both frames: shared non-generic email, GitHub
    noreply login (logins sharing a numeric account id are one account), then name-based
    rules on letter-only keys (equal or long-prefix names and handles, handle vs initial +
    surname, a GitHub login equal to the other side's email local part or email domain, a
    login that is a first name plus initials, a lone first name vs the one full name that
    starts with it, and rapidfuzz names backed by email or login evidence). Name-based rules
    never merge identities that carry different GitHub logins, and a name used with several
    logins stays split into one identity per login. Only `contribution_type == "human"` rows
    are touched.

    Returns the two frames and the number of name-based merges.
    """
    # Human rows from both frames, so identities agree across them
    both_df = pl.concat(
        [
            commits_df.select(
                pl.col(name_col).alias("name"),
                pl.col(email_col).alias("email"),
                pl.col("contribution_type"),
            ),
            deltas_df.select(
                pl.col(name_col).alias("name"),
                pl.col(email_col).alias("email"),
                pl.col("contribution_type"),
            ),
        ]
    ).filter((pl.col("contribution_type") == "human") & pl.col("name").is_not_null())

    # Raw (stripped) name, normalized name, and normalized email per distinct combination
    rows = (
        both_df.select(
            pl.col("name").str.strip_chars().alias("raw_name"),
            _NORMALIZED_NAME.alias("name"),
            _NORMALIZED_EMAIL.alias("email"),
        )
        .unique()
        .sort("name", "raw_name", "email")
        .rows()
    )

    # GitHub logins each normalized name is used with
    name_logins: dict[str, set[str]] = defaultdict(set)
    for _, name, email in rows:
        if login := _github_login(email):
            name_logins[name].add(login)

    # One union-find node per name (per login for names with several); remember a raw spelling
    uf = _UnionFind()
    raw_names: dict[_Node, str] = {}
    emails_by_node: dict[_Node, set[str]] = defaultdict(set)
    row_nodes: list[tuple[str, str, _Node]] = []
    for raw_name, name, email in rows:
        node = _node_for(name, email, name_logins[name])
        raw_names.setdefault(node, raw_name)
        emails_by_node[node].add(email)
        row_nodes.append((name, email, node))
        uf.find(node)

    # Steps 2 and 3: merge names sharing a real email or a GitHub login
    _merge_by_emails_and_logins(uf, emails_by_node)

    # Step 4: name-based merges (equal keys, handles, first names, fuzzy names)
    fuzzy_merge_count = _merge_by_names(uf, emails_by_node, raw_names, fuzzy_identity_threshold)

    # Canonical key per (name, email) row, so a name split by login maps to each of its people
    commit_counts = (
        commits_df.filter(pl.col("contribution_type") == "human")
        .select(pl.col(name_col).alias("name"))
        .select(_NORMALIZED_NAME)
        .drop_nulls()
        .to_series()
        .value_counts()
        .rows()
    )
    canonical = _canonical_names(_group_by_root(uf, emails_by_node), dict(commit_counts))
    canonical_df = pl.DataFrame(
        [(name, email, canonical[node]) for name, email, node in row_nodes],
        schema={"_name": pl.String, "_email": pl.String, "_canonical": pl.String},
        orient="row",
    ).unique()

    # Rewrite human names to their canonical key; other rows keep their name
    def _apply(df: pl.DataFrame) -> pl.DataFrame:
        if canonical_df.is_empty():
            return df
        keyed = df.with_columns(
            pl.col(name_col).str.to_lowercase().str.strip_chars().alias("_name"),
            pl.col(email_col)
            .fill_null("")
            .str.to_lowercase()
            .str.strip_chars()
            .alias("_email"),
        ).join(canonical_df, on=["_name", "_email"], how="left", maintain_order="left")
        return keyed.with_columns(
            pl.when(
                (pl.col("contribution_type") == "human") & pl.col("_canonical").is_not_null()
            )
            .then(pl.col("_canonical"))
            .otherwise(pl.col(name_col))
            .alias(name_col)
        ).drop("_name", "_email", "_canonical")

    return _apply(commits_df), _apply(deltas_df), fuzzy_merge_count
