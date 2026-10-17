# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Keep this machine's hostname out of what pytest reports

A model's repr is its Prolog fact, and a trial's ends with ``user_id``,
``<hostname>\\<login>``. When a test fails, pytest prints the reprs of the
arguments of every frame, of the locals under ``--showlocals`` and of the
operands of a failed assertion, the messages of chained exceptions and the
output the test captured. A failure log is something people paste into an
issue or a PR, which ``AGENTS.md`` ("Sensitive data") forbids for the
hostname.

The root ``conftest.py`` passes every report, of a test or of a
collection, through ``mask_report`` before any reporter reads it, and the
traceback of an internal error through ``mask``: the hostname becomes
``<HOSTNAME>`` wherever the rules of the goldens (``normalize.host_rules``)
find it, and so do the pieces of it that pytest leaves where it cut a long
repr (``cut_host_rules``). The rest of the report stays as pytest built
it, the frame arguments included.

Out of its reach: node ids (a parametrize id built from a value), the
description of a subtest, the warnings summary, the LEAKS section, what a
test prints or logs live (``-s``, ``--log-cli-level``), a
``KeyboardInterrupt`` under ``--full-trace``, pieces shorter than four
characters, and a hostname that ``usable_hostname`` refuses (shorter than
four characters, or ``localhost``), which names no machine. A test still
never puts a store's environment or user id in an assertion message or a
test id.
"""
import dataclasses
import re
import socket

from ..e2e.normalize import host_rules, usable_hostname

PLACEHOLDER = "<HOSTNAME>"
# The shortest piece of a cut hostname that is masked.
SHORTEST_PIECE = 4


def cut_host_rules(hostname):
    """Patterns of what is left of the hostname where pytest cut a repr

    ``saferepr`` keeps the head and the tail of a long repr around
    ``...``, so it may cut a long hostname: its first characters end the
    head, and its last characters start the tail. Each such piece, of
    ``SHORTEST_PIECE`` characters or more and with the boundaries of
    ``host_rules`` on its other side, is masked.
    """
    names = {hostname, hostname.split(".")[0]} if hostname else set()
    rules = []
    for name in sorted(names, key=len, reverse=True):
        if not usable_hostname(name):
            continue
        sizes = range(len(name) - 1, SHORTEST_PIECE - 1, -1)
        heads = "|".join(re.escape(name[:size]) for size in sizes)
        tails = "|".join(re.escape(name[-size:]) for size in sizes)
        if not heads:
            continue
        rules.append(re.compile(
            r"(?<![A-Za-z0-9.-])(?:{})(?=\.\.\.)".format(heads),
            re.IGNORECASE))
        rules.append(re.compile(
            r"(?<=\.\.\.)(?:{})(?![A-Za-z0-9-])".format(tails),
            re.IGNORECASE))
    return rules


def hostname_rules(hostname):
    """Every pattern the reports mask for ``hostname``"""
    return host_rules(hostname) + cut_host_rules(hostname)


# Read once, when the root conftest.py imports this module at configure
# time, before any test could patch ``socket``.
HOSTNAME_RULES = hostname_rules(socket.gethostname())


def mask_report(report, rules=None):
    """Mask the hostname in a report's failure, in its captured output and
    in the reason of an xfail

    ``rules`` defaults to this machine's hostname; without rules the report
    is left as it is.
    """
    rules = HOSTNAME_RULES if rules is None else rules
    if not rules:
        return
    seen = set()
    report.longrepr = mask(report.longrepr, rules, seen)
    report.sections = mask(list(report.sections), rules, seen)
    if isinstance(getattr(report, "wasxfail", None), str):
        report.wasxfail = mask(report.wasxfail, rules, seen)


def mask(value, rules, seen=None):
    """``value`` with the text that ``rules`` match replaced everywhere

    Strings are replaced, lists in place, tuples rebuilt with their type,
    and an object that renders itself to the terminal (pytest's
    ``TerminalRepr`` classes: the exception chain, its tracebacks and
    entries, the frame arguments, the locals, the crash location, the
    lines of a doctest) has each of its attributes masked in place, so
    nothing depends on their names. Anything else is returned as it is.
    """
    seen = set() if seen is None else seen
    if isinstance(value, str):
        for rule in rules:
            value = rule.sub(PLACEHOLDER, value)
        return value
    if isinstance(value, tuple):
        items = [mask(item, rules, seen) for item in value]
        if hasattr(value, "_fields"):
            return type(value)(*items)
        return type(value)(items)
    if id(value) in seen:
        return value
    if isinstance(value, list):
        seen.add(id(value))
        value[:] = [mask(item, rules, seen) for item in value]
    elif hasattr(value, "toterminal"):
        seen.add(id(value))
        if hasattr(value, "__dict__"):
            names = list(vars(value))
        else:
            names = [field.name for field in dataclasses.fields(value)]
        for name in names:
            # Also for frozen dataclasses.
            object.__setattr__(value, name,
                               mask(getattr(value, name), rules, seen))
    return value
