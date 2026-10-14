# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The surface of the `now` command outside `now run`

What the process returns before any provenance is read or collected: the
version flag, the help of the program, of each command and of each export
format, the report of a missing store (its stream and its wording), the
treatment of unknown commands and options, the report of a trial that does
not exist, the three ways of naming a trial (id, tag, sequence key) and that
a prefix of an id names none.

The help texts are checked structurally, never as goldens: argparse wraps
them at ``COLUMNS`` and changes their wording between Python versions, and
``kernel -h`` embeds ``sys.prefix``. The tests that need trials only read
them, from the shared ``two_trial_project``.

Several assertions characterize defects: the test of the current behavior
and a ``_desired`` twin, marked ``xfail(strict=True)``, that turns green when
the issue in its reason is fixed.
"""
import ast
import os
import re
from pathlib import Path

import pytest

import noworkflow
from noworkflow.tests.e2e.harness import runs_this_interpreter

PACKAGE_DIR = Path(noworkflow.__file__).resolve().parent
CMD_DIR = PACKAGE_DIR / "now" / "cmd"
VERSION_FILE = PACKAGE_DIR / "resources" / "version.txt"

# The commands that `main()` in now/cmd/__init__.py registers, in its order,
# and the formats of `now export`; test_command_lists_match_the_source keeps
# both lists in step with the source.
COMMANDS = (
    "run", "debug", "list", "show", "diff", "export", "import", "push",
    "pull", "restore", "vis", "demo", "history", "schema", "kernel", "gc",
    "evaluation", "clean",
)
EXPORT_FORMATS = ("prolog", "prov", "dataflow", "ast", "ipynb", "prospective")

# The two wordings of PersistenceConfig.connect_existing().
NO_STORE_HERE = "there is no provenance store in the current directory"
NO_STORE_THERE = "there is no provenance store in the informed directory"
# The report of a missing store, in either wording.
NO_STORE_LINE = re.compile(
    r"\[now\] there is no provenance store in the (current|informed) "
    r"directory\n")

# Every command that opens an existing store, with the arguments it needs to
# get that far. `import` opens the store of --source; without it, it crashes
# before opening anything.
STORE_READERS = (
    ("list",), ("show",), ("history",), ("diff", "1", "2"), ("restore",),
    ("gc",), ("evaluation",), ("clean",), ("vis",),
    ("import", "--source", "."),
) + tuple(("export", name) for name in EXPORT_FORMATS)

# A command of the top-level help: four spaces, then the name. Option lines
# are indented by two spaces and the continuation of a long help by more
# than four.
HELP_COMMAND = re.compile(r"^ {4}(\S+)", re.MULTILINE)


def command_classes(path, function):
    """Class names in the ``commands = [...]`` list of ``function``

    Every element must be a call without arguments, so that instantiating the
    class gives the same command name as the source does.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == function):
            continue
        for statement in ast.walk(node):
            if not isinstance(statement, ast.Assign):
                continue
            if [ast.unparse(target) for target in statement.targets] != [
                    "commands"]:
                continue
            classes = []
            for element in statement.value.elts:
                assert isinstance(element, ast.Call), ast.unparse(element)
                assert not element.args and not element.keywords, (
                    ast.unparse(element))
                classes.append(element.func.id)
            return classes
    raise AssertionError("no `commands = [...]` in {}() of {}".format(
        function, path))


def listed_commands(help_text):
    """Command names that the top-level help lists, in its order"""
    return HELP_COMMAND.findall(help_text)


def assert_untouched(project):
    """The command created nothing in the project directory"""
    assert not project.store.exists(), "a .noworkflow was created"
    names = sorted(path.name for path in project.path.iterdir())
    assert names == [], "the command created {}".format(names)


# ---------------------------------------------------------------------------
# The command lists this module relies on


def test_command_lists_match_the_source():
    """COMMANDS and EXPORT_FORMATS are the commands the source registers

    Read from the ``commands`` lists of ``main()`` and of
    ``Export.add_arguments()``, so a command added there without being
    added here fails this test instead of going untested.
    """
    from noworkflow.now import cmd
    from noworkflow.now.cmd import cmd_export

    main_classes = command_classes(CMD_DIR / "__init__.py", "main")
    assert [getattr(cmd, name)().cmd for name in main_classes] == list(
        COMMANDS)

    export_classes = command_classes(
        CMD_DIR / "cmd_export" / "__init__.py", "add_arguments")
    assert [getattr(cmd_export, name)().cmd
            for name in export_classes] == list(EXPORT_FORMATS)


# ---------------------------------------------------------------------------
# Version and help


@pytest.mark.parametrize("flag", ["-v", "--version"])
def test_version_flag_prints_the_version_of_version_txt(project, flag):
    """``-v`` and ``--version`` print ``noWorkflow <version.txt>`` and exit 0

    When ``NOW_E2E_CMD`` runs another installation, whose version is unknown
    here, only the format is checked.
    """
    result = project.run(flag)
    if runs_this_interpreter(project.command):
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        assert result.stdout == "noWorkflow {}\n".format(version)
    else:
        assert re.fullmatch(r"noWorkflow \S+\n", result.stdout), str(result)
    assert_untouched(project)


def test_no_arguments_prints_the_help_and_creates_no_store(project):
    """``now`` alone prints the help on stdout, exits 0 and writes nothing"""
    result = project.run()
    assert result.stdout.startswith("usage:"), str(result)
    assert "Commands and argument parsers for 'now'" in result.stdout
    assert_untouched(project)


def test_commands_in_the_top_level_help(project):
    """The top-level help lists every command except ``import``

    ``import`` has an empty docstring, so its subparser gets no ``help`` and
    argparse leaves it out of the list. #253 changes this.
    """
    result = project.run()
    assert listed_commands(result.stdout) == [
        name for name in COMMANDS if name != "import"]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#253: `import` has no help line, so `now -h` omits it"))
def test_commands_in_the_top_level_help_desired(project):
    """The top-level help lists all 18 commands, in the order of main()"""
    result = project.run()
    assert listed_commands(result.stdout) == list(COMMANDS)


@pytest.mark.parametrize(
    "args",
    [(name, "-h") for name in COMMANDS]
    + [("export", name, "-h") for name in EXPORT_FORMATS],
    ids=lambda args: "-".join(args[:-1]),
)
def test_command_help_exits_0_on_stdout_without_a_store(project, args):
    """``now <command> -h`` prints its usage on stdout and touches nothing"""
    result = project.run(*args)
    assert result.stdout.startswith("usage:"), str(result)
    assert_untouched(project)


# ---------------------------------------------------------------------------
# A directory without a store


@pytest.mark.parametrize("args", STORE_READERS, ids=" ".join)
def test_store_reader_without_a_store(project, args):
    """A store-reading command in an empty directory exits 1 with a message

    The message goes to stdout, through ``print_msg``; #226 moves it to
    stderr. test_missing_store_wording pins the wording. Nothing is created
    in the directory.
    """
    result = project.run(*args, expect=1)
    assert NO_STORE_LINE.fullmatch(result.stdout), str(result)
    assert_untouched(project)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#226: print_msg writes errors to stdout"))
def test_store_reader_without_a_store_desired(project):
    """The missing-store error goes to stderr, rc 1, and stdout stays empty"""
    result = project.run("list", expect=1, allow_stderr=True)
    assert result.stdout == "", str(result)
    assert "no provenance store" in result.stderr, str(result)
    assert_untouched(project)


def test_missing_store_wording(project):
    """The missing-store report says "informed directory", ``--dir`` or not

    Every reader calls ``connect_existing(args.dir or os.getcwd())``, so the
    wording for the current directory (persistence/config.py) is never used.
    #253 changes this.
    """
    result = project.run("list", expect=1)
    assert result.stdout == "[now] {}\n".format(NO_STORE_THERE)

    (project.root / "other").mkdir()
    result = project.run("list", "--dir", os.path.join("..", "other"),
                         expect=1)
    assert result.stdout == "[now] {}\n".format(NO_STORE_THERE)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#253: the readers always pass a directory to "
    "connect_existing, so without --dir the message says 'informed "
    "directory'"))
def test_missing_store_wording_desired(project):
    """Without ``--dir`` the report names the current directory; with it, not

    Read from stdout and stderr together, so that #226 moving the message to
    stderr does not change this test.
    """
    result = project.run("list", expect=1, allow_stderr=True)
    output = result.stdout + result.stderr
    assert NO_STORE_HERE in output, str(result)

    other = project.root / "other"
    other.mkdir()
    result = project.run("list", "--dir", os.path.join("..", "other"),
                         expect=1, allow_stderr=True)
    output = result.stdout + result.stderr
    assert "no provenance store" in output, str(result)
    assert "current directory" not in output, str(result)
    assert list(other.iterdir()) == [], "a file was created in --dir"
    assert_untouched(project)


def test_schema_sql_creates_a_store_in_an_empty_directory(project):
    """``now schema sql`` exits 0 and creates ``.noworkflow`` in the cwd

    Unlike the commands that read a store, ``schema`` connects with
    ``create``, so printing the schema leaves a new, empty store behind.
    """
    result = project.run("schema", "sql")
    assert "CREATE TABLE trial (" in result.stdout
    assert (project.store / "db.sqlite").is_file()
    assert project.query("SELECT COUNT(*) AS n FROM trial") == [{"n": 0}]


# ---------------------------------------------------------------------------
# Unknown commands and options


def test_unknown_command_exits_2_listing_every_command(project):
    """An unknown command is an argparse error, rc 2, on stderr

    The choices in the message are the commands argparse registered, all 18,
    ``import`` included.
    """
    result = project.run("bogus-command", expect=2, allow_stderr=True)
    assert result.stdout == ""
    assert "invalid choice: 'bogus-command'" in result.stderr, str(result)
    choices = re.search(r"\(choose from (.*)\)", result.stderr).group(1)
    assert [choice.strip("'\"") for choice in choices.split(", ")] == list(
        COMMANDS)
    assert_untouched(project)


def test_unknown_option_after_a_command(two_trial_project):
    """``now list --bogus`` ignores the option and lists the trials, rc 0

    ``main`` parses with ``parse_known_args`` and drops what it does not
    know. #226 changes this.
    """
    project = two_trial_project
    expected = project.run("list").stdout
    result = project.run("list", "--bogus")
    assert result.stdout == expected


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#226: unknown arguments are dropped by parse_known_args instead of "
    "failing with rc 2"))
def test_unknown_option_after_a_command_desired(two_trial_project):
    """``now list --bogus`` is an argparse error: rc 2, nothing listed"""
    result = two_trial_project.run("list", "--bogus", expect=None,
                                   allow_stderr=True)
    assert result.returncode == 2, str(result)
    assert "unrecognized arguments: --bogus" in result.stderr, str(result)
    assert result.stdout == "", str(result)


def test_unknown_option_without_a_command(project):
    """``now --bogus`` crashes: rc 1 and an AttributeError traceback

    With the option dropped and no command, the namespace has no ``func``.
    #226 changes this.
    """
    result = project.run("--bogus", expect=1, allow_stderr=True)
    assert result.stdout == ""
    assert result.stderr.startswith("Traceback"), str(result)
    assert result.stderr.rstrip().endswith(
        "AttributeError: 'Namespace' object has no attribute 'func'"), (
            str(result))
    assert_untouched(project)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#226: an unknown option without a command crashes with AttributeError "
    "instead of failing with rc 2"))
def test_unknown_option_without_a_command_desired(project):
    """``now --bogus`` is an argparse error: rc 2, no traceback"""
    result = project.run("--bogus", expect=None, allow_stderr=True)
    assert result.returncode == 2, str(result)
    assert "Traceback" not in result.stderr, str(result)
    assert "--bogus" in result.stderr, str(result)
    assert_untouched(project)


def test_export_without_a_format_exits_2(project):
    """``now export`` alone is an argparse error: rc 2, usage on stderr"""
    result = project.run("export", expect=2, allow_stderr=True)
    assert result.stdout == ""
    assert "the following arguments are required" in result.stderr, (
        str(result))
    assert_untouched(project)


# ---------------------------------------------------------------------------
# Trials that do not exist


def test_show_of_a_missing_trial(two_trial_project):
    """``now show 99`` reports the trial as not found, on stdout, with rc 0

    #226 changes the code to 1 and the stream to stderr.
    """
    result = two_trial_project.run("show", "99")
    assert result.stdout == "[now] Trial 99 not found\n"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#226: 'Trial X not found' exits 0 and is printed on stdout"))
def test_show_of_a_missing_trial_desired(two_trial_project):
    """``now show 99`` exits 1 with the message on stderr"""
    result = two_trial_project.run("show", "99", expect=None,
                                   allow_stderr=True)
    assert result.returncode == 1, str(result)
    assert "Trial 99 not found" in result.stderr, str(result)
    assert result.stdout == "", str(result)


def test_diff_with_a_missing_trial(two_trial_project):
    """``now diff 1 99`` reports trial 99 as not found, on stdout, rc 0

    #226 changes the code to 1 and the stream to stderr.
    """
    result = two_trial_project.run("diff", "1", "99")
    assert result.stdout == "[now] Trial 99 not found\n"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "#226: 'Trial X not found' exits 0 and is printed on stdout"))
def test_diff_with_a_missing_trial_desired(two_trial_project):
    """``now diff 1 99`` exits 1 with the message on stderr"""
    result = two_trial_project.run("diff", "1", "99", expect=None,
                                   allow_stderr=True)
    assert result.returncode == 1, str(result)
    assert "Trial 99 not found" in result.stderr, str(result)
    assert result.stdout == "", str(result)


# ---------------------------------------------------------------------------
# Trial references


def test_id_tag_and_sequence_key_name_the_same_trial(two_trial_project):
    """``now show`` prints the same trial for its id, its tag and its key

    The control: the other trial of the store prints something else.
    """
    project = two_trial_project
    first = project.trial("1")
    assert project.trial("1.1.1")["id"] == first["id"]

    outputs = {}
    for ref in (first["id"], "1.1.1", "1"):
        result = project.run("show", ref)
        assert first["id"] in result.stdout, str(result)
        assert "Sequence Key: 1\n" in result.stdout, str(result)
        outputs[ref] = project.normalize(result.stdout)
    assert len(set(outputs.values())) == 1, str(outputs)

    other = project.run("show", project.trial("2")["id"])
    assert project.normalize(other.stdout) != outputs["1"]


def test_unknown_id_prefix_is_not_found(two_trial_project):
    """A prefix of a trial id names no trial: only the whole id does

    Reported on stdout with rc 0, like every missing trial (#226). The
    prefix keeps the dash, so SQLite cannot read it as a sequence key.
    """
    project = two_trial_project
    prefix = project.trial("1")["id"][:13]
    result = project.run("show", prefix)
    assert result.stdout == "[now] Trial {} not found\n".format(prefix)
