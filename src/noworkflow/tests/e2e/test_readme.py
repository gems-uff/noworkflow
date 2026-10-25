# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The README, against the tool it describes

``README.md`` is the page users read first, on GitHub and on PyPI, and it
shows commands, their options and what they print. These tests hold it to
the tool:

- every ``$ now ...`` line of its code blocks parses with the real command
  line, and every option its prose names exists;
- the lists of values it gives for an option are the option's choices;
- what it says about installing (the oldest Python, the tested versions,
  the extras and what they bring) matches ``pyproject.toml`` and the CI
  matrix;
- the output it shows for ``now run -v`` and ``now list`` is what ``now``
  prints for the same steps, once ids, hashes and clock readings are
  masked;
- its links work on PyPI, which resolves no relative link, and point to
  files and headings that exist; the relative links of the other Markdown
  files of the repository point to files that exist.

When one of them turns red, the maintainer decides whether the tool
regressed or the README must follow it; the expectation is never edited
only to make the test pass. The README lives at the root of the
repository, outside the package, so these tests skip outside a checkout.
"""

import argparse
import contextlib
import io
import re
import shlex
import tomllib
from pathlib import Path
from urllib.parse import unquote

import pytest

from noworkflow.now.cmd import build_parser

# src/noworkflow/tests/e2e/ -> the root of the checkout
ROOT = Path(__file__).resolve().parents[4]
README = ROOT / "README.md"
# The Markdown files whose relative links are checked, besides the README.
OTHER_MARKDOWN = (
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "skills/noworkflow/SKILL.md",
    "Examples/glue_pipeline/README.md",
    "Examples/usecase_credit_fraud/README.md",
)

FENCED_BLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
# A Markdown link or image target: ``](target)``.
LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(.+)\n(?:=+|-+)[ \t]*$|^#{1,6}[ \t]+(.+)$", re.MULTILINE)
# An option named in prose, in italics: ``*-d*``, ``*--dir*``, ``*-f path*``.
PROSE_OPTION = re.compile(r"(?<![*\w])\*(--?[A-Za-z][\w-]*)(?: [^*\n]*)?\*(?![*\w])")
REPOSITORY_URL = re.compile(
    r"^https://(?:github\.com/gems-uff/noworkflow/(?:blob|tree|raw)/main/"
    r"|raw\.githubusercontent\.com/gems-uff/noworkflow/main/)(?P<path>[^?#]*)"
)
# What stands for a trial in the README's command lines.
PLACEHOLDERS = {"[trial]": "1.1.1", "[trial1]": "1.1.1", "[trial2]": "1.1.2"}
HEX = re.compile(r"\b[0-9a-f]{40}\b")

# The lists of values the README gives, as (command path, option, values).
# Each list is an option's choices, and each value appears in the README in
# italics. A ``*`` choice that the README does not mention is left out.
CHOICES = (
    (("run",), "-e", {"all", "relevant", "none"}),
    (("run",), "-c", {"main", "package", "all"}),
    (("run",), "-r", {"repr", "jsonpickle", "jsonpickle_content", "simple"}),
    (("run",), "--external-tracer", {"none", "argv", "strace"}),
    (
        ("export", "dataflow"),
        "-m",
        {"activation", "coarseGrain", "looplessCoarseGrain", "fineGrain", "all"},
    ),
    (("history",), "-e", {"finished", "unfinished", "backup"}),
)


@pytest.fixture(scope="module")
def readme():
    if not README.is_file():
        pytest.skip(
            "{} is not in this installation: the README ships with the "
            "repository, not with the package".format(README)
        )
    return README.read_text(encoding="utf-8")


def code_blocks(text):
    return FENCED_BLOCK.findall(text)


def prose(text):
    return FENCED_BLOCK.sub("", text)


def command_lines(text):
    """The ``now`` command lines of the code blocks, without the prompt,
    the trailing comment or what a pipe feeds"""
    lines = []
    for block in code_blocks(text):
        for line in block.splitlines():
            if line.startswith("$ now "):
                command = re.split(r"\s+#\s|\s\|\s", line[2:])[0].strip()
                lines.append(command)
    return lines


def subparsers(parser, prefix=()):
    """``(command path, parser)`` of every subcommand, nested ones included"""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                yield prefix + (name,), sub
                yield from subparsers(sub, prefix + (name,))


def parser_of(path):
    return dict(subparsers(build_parser()))[path]


def output_after(text, first_line):
    """The output the README shows under ``first_line``: the rest of the
    first code block that starts with that line and has more lines"""
    for block in code_blocks(text):
        lines = block.splitlines()
        if len(lines) > 1 and lines[0] == first_line:
            return lines[1:]
    raise AssertionError("README.md shows no output under {!r}".format(first_line))


def magic_options():
    """The options of the ``%now_run`` magic, which the README's IPython
    section names besides those of ``now run``"""
    from noworkflow.now.ipython.magics.now_run import NowRun

    magic = NowRun("now_run", "")
    magic.add_arguments()
    return {
        option
        for argument in magic.args
        for option in argument.args
        if option.startswith("-")
    }


def slug(heading):
    """The anchor GitHub gives a heading"""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def test_every_now_command_line_parses(readme, tmp_path, monkeypatch):
    """Every ``$ now ...`` line of the README is accepted by the command
    line of this version, with a trial standing for each placeholder"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "script.py").write_text("x = 1\n", encoding="utf-8")
    lines = command_lines(readme)
    assert len(lines) > 20, "README.md shows fewer command lines than expected"
    failures = {}
    for line in lines:
        for placeholder, value in PLACEHOLDERS.items():
            line = line.replace(placeholder, value)
        stderr = io.StringIO()
        try:
            with (
                contextlib.redirect_stderr(stderr),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                build_parser().parse_args(shlex.split(line)[1:])
        except SystemExit as exit:
            if exit.code:
                failures[line] = stderr.getvalue().strip().splitlines()[-1]
    assert failures == {}


def test_every_option_the_prose_names_exists(readme):
    """Every option the README names in italics is an option of some
    command, or of the ``%now_run`` magic"""
    options = magic_options()
    for _, sub in subparsers(build_parser()):
        for action in sub._actions:
            options.update(action.option_strings)
    named = set(PROSE_OPTION.findall(prose(readme)))
    assert len(named) > 20, "README.md names fewer options than expected"
    assert sorted(named - options) == []


@pytest.mark.parametrize(
    "path, option, values", CHOICES, ids=[" ".join(c[0]) + " " + c[1] for c in CHOICES]
)
def test_the_values_the_readme_lists_are_the_choices(readme, path, option, values):
    """The README lists every choice of the option, and only them: each
    value in italics, or after the option on a command line"""
    action = next(
        action for action in parser_of(path)._actions if option in action.option_strings
    )
    assert set(action.choices) - {"*"} == values
    text = prose(readme)
    lines = command_lines(readme)
    absent = [
        value
        for value in sorted(values)
        if "*{}*".format(value) not in text
        and not any("{} {}".format(option, value) in line for line in lines)
    ]
    assert absent == []


def test_the_installation_section_matches_the_project(readme):
    """The oldest Python, the tested versions and the extras the README
    gives are the ones of ``pyproject.toml`` and of the CI matrix"""
    with open(ROOT / "pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)["project"]
    floor = re.fullmatch(r">=\s*(\d+\.\d+)", project["requires-python"]).group(1)
    assert "With Python {} or later".format(floor) in readme

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    versions = sorted(
        set(re.findall(r'os: ubuntu-latest, python: "(\d+\.\d+)"', ci)),
        key=lambda version: tuple(map(int, version.split("."))),
    )
    assert versions[0] == floor
    assert "tested with Python {} to {}".format(versions[0], versions[-1]) in readme

    names = {re.split(r"[<>=!~\[ ]", dep)[0].lower() for dep in project["dependencies"]}
    assert "flask" in names  # "pip install noworkflow already installs" Flask
    extras = project["optional-dependencies"]
    assert "matplotlib" in extras["demo"]  # the `demo` extra of `now demo 1`
    lowered = readme.lower()
    missing = [
        name
        for name in extras["all"]
        if name.lower() not in names and name.lower() not in lowered
    ]
    assert missing == []  # every package the `all` extra adds is named


def test_the_readme_links_work_on_pypi_and_point_to_what_exists(readme):
    """No relative link (PyPI resolves none), every link into this
    repository names a file that exists, and every anchor a heading"""
    targets = LINK_TARGET.findall(readme)
    assert len(targets) > 20
    relative = [
        target for target in targets if not re.match(r"(https?:|mailto:|#)", target)
    ]
    assert relative == []
    missing = []
    for target in targets:
        match = REPOSITORY_URL.match(target)
        if match and not (ROOT / unquote(match.group("path"))).exists():
            missing.append(target)
    assert missing == []
    headings = {slug(a or b) for a, b in HEADING.findall(prose(readme))}
    anchors = {target[1:] for target in targets if target.startswith("#")}
    assert sorted(anchors - headings) == []


@pytest.mark.parametrize("name", OTHER_MARKDOWN)
def test_the_relative_links_of_the_markdown_files_exist(name):
    """The relative links of the other Markdown files point to files of the
    repository (GitHub resolves them; PyPI never shows these files)"""
    path = ROOT / name
    if not path.is_file():
        pytest.skip("{} is not in this installation".format(name))
    text = prose(path.read_text(encoding="utf-8"))
    missing = []
    for target in LINK_TARGET.findall(text):
        if re.match(r"(https?:|mailto:|#)", target):
            continue
        target = unquote(target.split("#")[0])
        if not (path.parent / target).exists():
            missing.append(target)
    assert missing == []


def mask(project, lines):
    """The lines as the normalizer leaves them, hashes numbered"""
    text = project.normalize("\n".join(lines))
    seen = {}
    text = HEX.sub(
        lambda m: seen.setdefault(m.group(0), "<HASH{}>".format(len(seen) + 1)), text
    )
    return text.splitlines()


def test_run_v_prints_what_the_readme_shows(readme, project):
    """``now run -v script.py`` prints, in the first run of a project, the
    lines the README shows (the trial id masked)"""
    shown = output_after(readme, "$ now run -v script.py")
    project.write("script.py", "x = 1\n")
    result = project.run("run", "-v", "script.py")
    assert mask(project, result.stdout.splitlines()) == mask(project, shown)


def test_list_prints_what_the_readme_shows(readme, project):
    """Two runs, an edit and ``now restore 1.1.1`` give the ``now list``
    the README shows: two finished trials and a backup, with their tags"""
    shown = output_after(readme, "$ now list")
    assert shown[0].startswith("[now] trials available"), shown[:1]
    project.write("script.py", "total = sum(range(10))\n")
    project.run("run", "script.py")
    project.run("run", "script.py")
    project.write("script.py", "total = sum(range(20))\n")
    project.run("restore", "1.1.1")
    result = project.run("list")
    assert mask(project, result.stdout.splitlines()) == mask(project, shown)
