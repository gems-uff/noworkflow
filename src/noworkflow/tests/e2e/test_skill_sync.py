# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The user skill, ``skills/noworkflow/SKILL.md``, against the commands

The skill is what a user copies into their AI agent so that it can drive
``now``. These tests keep it in step with the command line: every command
and every export format appears in it as ``now <command>`` (or
``now export <format>``), and every ``now <word>`` it shows names a command
that exists. Only code is read, the fenced blocks and the inline code
spans, so prose may use the word "now" freely.

The command lists are the ones of test_cli.py, which
test_command_lists_match_the_source keeps in step with the source.

The skill lives at the root of the repository, outside the package, so a
wheel does not carry it: there the tests skip instead of failing.
"""
import re
from pathlib import Path

import pytest

from noworkflow.tests.e2e.test_cli import COMMANDS, EXPORT_FORMATS

# src/noworkflow/tests/e2e/ -> the root of the checkout
SKILL = Path(__file__).resolve().parents[4] / "skills" / "noworkflow" / "SKILL.md"

FENCED_BLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
# `now` as a program, followed by a word: not `noworkflow`, `%now_run` or
# `now -h`, but also `.venv/bin/now run` and the `!now export` of a notebook.
NOW_WORD = re.compile(r"(?<![\w%-])now[ \t]+([A-Za-z][\w-]*)")
EXPORT_WORD = re.compile(r"(?<![\w%-])now[ \t]+export[ \t]+([A-Za-z][\w-]*)")


@pytest.fixture(scope="module")
def skill_code():
    """The code of the skill: fenced blocks and inline spans, one string"""
    if not SKILL.is_file():
        pytest.skip("{} is not in this installation: the skill ships with "
                    "the repository, not with the package".format(SKILL))
    text = SKILL.read_text(encoding="utf-8")
    blocks = FENCED_BLOCK.findall(text)
    prose = FENCED_BLOCK.sub("", text)
    return "\n".join(blocks + INLINE_CODE.findall(prose))


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_appears_in_the_skill(skill_code, command):
    """The skill shows ``now <command>`` for each command of ``main()``"""
    assert command in NOW_WORD.findall(skill_code), (
        "skills/noworkflow/SKILL.md never shows `now {}`".format(command))


@pytest.mark.parametrize("name", EXPORT_FORMATS)
def test_every_export_format_appears_in_the_skill(skill_code, name):
    """The skill shows ``now export <format>`` for each export format"""
    assert name in EXPORT_WORD.findall(skill_code), (
        "skills/noworkflow/SKILL.md never shows `now export {}`".format(name))


def test_every_command_the_skill_shows_exists(skill_code):
    """Each ``now <word>`` in the skill's code is a command of ``main()``"""
    unknown = sorted(set(NOW_WORD.findall(skill_code)) - set(COMMANDS))
    assert unknown == [], (
        "skills/noworkflow/SKILL.md shows commands that do not exist: "
        "{}".format(unknown))


def test_every_export_format_the_skill_shows_exists(skill_code):
    """Each ``now export <word>`` in the skill's code is an export format"""
    unknown = sorted(
        set(EXPORT_WORD.findall(skill_code)) - set(EXPORT_FORMATS))
    assert unknown == [], (
        "skills/noworkflow/SKILL.md shows export formats that do not "
        "exist: {}".format(unknown))
