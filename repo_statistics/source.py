#!/usr/bin/env python

import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

from dataclasses_json import DataClassJsonMixin
from git import Repo

from .constants import FileTypes
from .utils import (
    AnalysisTimeoutError,
    Deadline,
    checked_subprocess_timeout,
    get_linguist_file_type,
)

###############################################################################

# The IPython plugin lexer also claims *.py and wins at random, which drops docstring comments.
_PYGOUNT_WRAPPER = """
import pygount.analysis, pygount.command
from pygments.lexers import PythonLexer

_guess_lexer = pygount.analysis.guess_lexer


def guess_lexer(source_path, text):
    lexer = _guess_lexer(source_path, text)
    return PythonLexer() if getattr(lexer, "name", None) == "IPython" else lexer


pygount.analysis.guess_lexer = guess_lexer
pygount.command.main()
"""


@dataclass
class SLOCResults(DataClassJsonMixin):
    total_lines_of_code: int | None
    total_lines_of_comments: int | None
    programming_lines_of_code: int | None
    programming_lines_of_comments: int | None
    markup_lines_of_code: int | None
    markup_lines_of_comments: int | None
    prose_lines_of_code: int | None
    prose_lines_of_comments: int | None
    data_lines_of_code: int | None
    data_lines_of_comments: int | None
    unknown_lines_of_code: int | None
    unknown_lines_of_comments: int | None
    total_code_to_comment_ratio: float | None
    programming_code_to_comment_ratio: float | None
    markup_code_to_comment_ratio: float | None
    prose_code_to_comment_ratio: float | None
    data_code_to_comment_ratio: float | None
    unknown_code_to_comment_ratio: float | None


def compute_sloc_metrics(  # noqa: C901
    repo_path: str | Path | Repo,
    deadline: Deadline | None = None,
) -> SLOCResults:
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    try:
        # Get repo_dir from repo
        repo_dir = repo.working_dir

        # Run cloc on the repo.
        # pygount can be pathologically slow (observed: indefinite hang) on very
        # large plain-text/data files, so bound it -- otherwise a single stuck
        # subprocess silently consumes the whole outer analyze deadline.
        pygount_timeout_seconds = checked_subprocess_timeout(deadline, 60)
        try:
            pygount_output = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _PYGOUNT_WRAPPER,
                    "--format=json",
                    repo_dir,
                ],
                capture_output=True,
                text=True,
                timeout=pygount_timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"pygount SLOC counting exceeded {pygount_timeout_seconds}s timeout "
                f"for repo at {repo_dir}."
            ) from e

        if pygount_output.returncode != 0:
            raise RuntimeError(
                f"pygount failed with return code {pygount_output.returncode}. "
                f"stderr: {pygount_output.stderr.strip()}"
            )

        # Read JSON
        try:
            sloc_results = json.loads(pygount_output.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse pygount JSON output: {e}. "
                f"stdout: {pygount_output.stdout[:200]!r}"
            ) from e

        # Iter over "files"
        total_lines_of_code = 0
        total_lines_of_comments = 0
        programming_lines_of_code = 0
        programming_lines_of_comments = 0
        markup_lines_of_code = 0
        markup_lines_of_comments = 0
        prose_lines_of_code = 0
        prose_lines_of_comments = 0
        data_lines_of_code = 0
        data_lines_of_comments = 0
        unknown_lines_of_code = 0
        unknown_lines_of_comments = 0
        for file in sloc_results["files"]:
            # Always add to total
            total_lines_of_code += file["codeCount"]
            total_lines_of_comments += file["documentationCount"]

            # Get file type
            file_type = get_linguist_file_type(file["path"])

            if file_type == FileTypes.programming.value:
                programming_lines_of_code += file["codeCount"]
                programming_lines_of_comments += file["documentationCount"]
            elif file_type == FileTypes.markup.value:
                markup_lines_of_code += file["codeCount"]
                markup_lines_of_comments += file["documentationCount"]
            elif file_type == FileTypes.prose.value:
                prose_lines_of_code += file["codeCount"]
                prose_lines_of_comments += file["documentationCount"]
            elif file_type == FileTypes.data.value:
                data_lines_of_code += file["codeCount"]
                data_lines_of_comments += file["documentationCount"]
            else:
                unknown_lines_of_code += file["codeCount"]
                unknown_lines_of_comments += file["documentationCount"]

        def _ratio(code: int, comments: int) -> float | None:
            return code / comments if comments > 0 else None

        return SLOCResults(
            total_lines_of_code=total_lines_of_code,
            total_lines_of_comments=total_lines_of_comments,
            programming_lines_of_code=programming_lines_of_code,
            programming_lines_of_comments=programming_lines_of_comments,
            markup_lines_of_code=markup_lines_of_code,
            markup_lines_of_comments=markup_lines_of_comments,
            prose_lines_of_code=prose_lines_of_code,
            prose_lines_of_comments=prose_lines_of_comments,
            data_lines_of_code=data_lines_of_code,
            data_lines_of_comments=data_lines_of_comments,
            unknown_lines_of_code=unknown_lines_of_code,
            unknown_lines_of_comments=unknown_lines_of_comments,
            total_code_to_comment_ratio=_ratio(total_lines_of_code, total_lines_of_comments),
            programming_code_to_comment_ratio=_ratio(
                programming_lines_of_code, programming_lines_of_comments
            ),
            markup_code_to_comment_ratio=_ratio(markup_lines_of_code, markup_lines_of_comments),
            prose_code_to_comment_ratio=_ratio(prose_lines_of_code, prose_lines_of_comments),
            data_code_to_comment_ratio=_ratio(data_lines_of_code, data_lines_of_comments),
            unknown_code_to_comment_ratio=_ratio(
                unknown_lines_of_code, unknown_lines_of_comments
            ),
        )

    except AnalysisTimeoutError:
        raise

    except Exception:
        return SLOCResults(
            total_lines_of_code=None,
            total_lines_of_comments=None,
            programming_lines_of_code=None,
            programming_lines_of_comments=None,
            markup_lines_of_code=None,
            markup_lines_of_comments=None,
            prose_lines_of_code=None,
            prose_lines_of_comments=None,
            data_lines_of_code=None,
            data_lines_of_comments=None,
            unknown_lines_of_code=None,
            unknown_lines_of_comments=None,
            total_code_to_comment_ratio=None,
            programming_code_to_comment_ratio=None,
            markup_code_to_comment_ratio=None,
            prose_code_to_comment_ratio=None,
            data_code_to_comment_ratio=None,
            unknown_code_to_comment_ratio=None,
        )


@dataclass
class RepoTagMetrics(DataClassJsonMixin):
    semver_tags_count: int
    non_semver_tags_count: int
    total_tags_count: int


def compute_tag_metrics(
    repo_path: str | Path | Repo,
) -> RepoTagMetrics:
    # Get Repo object from path if necessary
    if isinstance(repo_path, Repo):
        repo = repo_path
    else:
        repo = Repo(repo_path)

    # Get all tags
    tags = repo.tags

    # Construct semver regex
    # Direct from https://semver.org/
    # Only addition was "(v)?" to allow for "v" prefix
    semver_regex = re.compile(
        r"^(v)?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    # Count tags
    semver_tags_count = 0
    non_semver_tags_count = 0
    for tag in tags:
        if semver_regex.match(tag.name):
            semver_tags_count += 1
        else:
            non_semver_tags_count += 1

    return RepoTagMetrics(
        semver_tags_count=semver_tags_count,
        non_semver_tags_count=non_semver_tags_count,
        total_tags_count=len(tags),
    )


@dataclass
class PythonDocAndNotebookResults(DataClassJsonMixin):
    python_lines_of_docstrings: int | None
    python_lines_of_comments: int | None
    notebook_file_count: int | None
    notebook_lines_of_code: int | None


# Tokens that can sit between a header's colon and the first statement of its body.
_BODY_PREFIX_TOKEN_TYPES = {
    tokenize.NEWLINE,
    tokenize.NL,
    tokenize.INDENT,
    tokenize.COMMENT,
    tokenize.ENCODING,
}


def _ast_docstring_lines(text: str) -> int:
    docstring_lines = 0
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstring_lines += (first.end_lineno or first.lineno) - first.lineno + 1
    return docstring_lines


def _string_statement_lines(tokens: list[tokenize.TokenInfo], start: int) -> tuple[int, int]:
    """Lines of a str-literal statement starting at `start` (0 if none) and the next index."""
    first = tokens[start]
    if first.type != tokenize.STRING or first.string.lstrip("rRuU")[:1] in "bB":
        return 0, start + 1
    end = start + 1
    while tokens[end].type == tokenize.STRING:
        end += 1
    # The string must be the whole statement, not the start of an expression.
    after = tokens[end]
    if (
        after.type in (tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.COMMENT)
        or after.string == ";"
    ):
        return tokens[end - 1].end[0] - first.start[0] + 1, end
    return 0, end


def _tokenize_docstring_lines(tokens: list[tokenize.TokenInfo]) -> int:
    """Docstring lines for source ast rejects, such as Python 2."""
    docstring_lines = 0
    expect_docstring = True  # the module's first statement
    in_header = False
    depth = 0
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token.type in _BODY_PREFIX_TOKEN_TYPES:
            continue
        if expect_docstring:
            expect_docstring = False
            lines, end = _string_statement_lines(tokens, i - 1)
            if lines:
                docstring_lines += lines
                i = end
                continue
        if token.type == tokenize.NAME and token.string in ("def", "class"):
            in_header, depth = True, 0
        elif in_header and token.type == tokenize.OP:
            if token.string in ("(", "[", "{"):
                depth += 1
            elif token.string in (")", "]", "}"):
                depth -= 1
            elif token.string == ":" and depth == 0:
                in_header = False
                expect_docstring = True
    return docstring_lines


def _python_docstring_and_comment_lines(text: str) -> tuple[int, int]:
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    # Comments come from tokenize alone, so files ast rejects still count them.
    comment_lines = {
        token.start[0]
        for token in tokens
        if token.type == tokenize.COMMENT and not token.line[: token.start[1]].strip()
    }
    try:
        docstring_lines = _ast_docstring_lines(text)
    except (SyntaxError, ValueError, RecursionError):
        docstring_lines = _tokenize_docstring_lines(tokens)
    return docstring_lines, len(comment_lines)


def _notebook_code_line_count(path: Path) -> int:
    notebook = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    code_lines = 0
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        code_lines += sum(1 for line in source.splitlines() if line.strip())
    return code_lines


def compute_python_doc_and_notebook_metrics(
    repo_path: str | Path | Repo,
    deadline: Deadline | None = None,
) -> PythonDocAndNotebookResults:
    """Best-effort: all None (never partial counts) on any failure or when time runs short."""
    empty = PythonDocAndNotebookResults(
        python_lines_of_docstrings=None,
        python_lines_of_comments=None,
        notebook_file_count=None,
        notebook_lines_of_code=None,
    )
    try:
        repo = repo_path if isinstance(repo_path, Repo) else Repo(repo_path)
        repo_dir = Path(repo.working_dir)

        docstring_lines = 0
        comment_lines = 0
        for py_file in repo_dir.rglob("*.py"):
            if deadline is not None and deadline.remaining() < 5:
                return empty
            if not py_file.is_file():
                continue
            try:
                file_docstrings, file_comments = _python_docstring_and_comment_lines(
                    py_file.read_text(encoding="utf-8", errors="replace")
                )
            except (SyntaxError, ValueError, RecursionError, tokenize.TokenError):
                continue
            docstring_lines += file_docstrings
            comment_lines += file_comments

        notebook_count = 0
        notebook_code_lines = 0
        for notebook_file in repo_dir.rglob("*.ipynb"):
            if deadline is not None and deadline.remaining() < 5:
                return empty
            if (
                not notebook_file.is_file()
                or ".ipynb_checkpoints" in notebook_file.relative_to(repo_dir).parts
            ):
                continue
            notebook_count += 1
            try:
                notebook_code_lines += _notebook_code_line_count(notebook_file)
            except (ValueError, AttributeError, TypeError):
                continue

        return PythonDocAndNotebookResults(
            python_lines_of_docstrings=docstring_lines,
            python_lines_of_comments=comment_lines,
            notebook_file_count=notebook_count,
            notebook_lines_of_code=notebook_code_lines,
        )
    except Exception:
        return empty
