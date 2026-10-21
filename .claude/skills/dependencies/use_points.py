#!/usr/bin/env python3
"""Coverage of the use points of each third-party package.

Part of the dependencies skill ("A campaign"). A use point is a line of
product code where a name bound by an import of a third-party package is
loaded: the import line itself, and every line that reads the imported
module or one of the names it exported (``sqlalchemy.Column(...)`` counts its
line once; ``from flask import jsonify`` then ``jsonify(...)`` counts the
line of the call). Line coverage tells which of those lines the suite
executed; a use point the suite never reaches is where an update can break
without a red.

usage, from the repository root, after a coverage run of the suite:

  uv run pytest -n 4 --cov --cov-report=json:<outside>/coverage.json
  uv run --no-sync python .claude/skills/dependencies/use_points.py src/noworkflow
      --exclude src/noworkflow/tests src/noworkflow/resources/demo
      --coverage <outside>/coverage.json [--detail MODULE ...] [--tsv FILE]

ROOT (src/noworkflow) is the package directory. --coverage is a coverage.py
JSON report; without it the table has the static counts only. --detail
prints the unexecuted use points of the named top-level modules (the import
name: ``sqlalchemy``, ``IPython``). --tsv writes every use point with its
status.

Not counted: a name reached through getattr or a string, a plugin a package
loads by entry point, and the modules of the standard library. The Python 2
names that cross_version.py imports on Python 2 only (cStringIO, cPickle,
imp, __builtin__, repr) are not standard modules on Python 3, so they show
up as packages: leave them out of the reading. A transitive has no use point
of its own.
"""

import argparse
import ast
import json
import os
import sys
from collections import defaultdict

STDLIB = set(sys.stdlib_module_names)
LOCAL = {"noworkflow", "__future__", "__main__"}


class Uses(ast.NodeVisitor):
    def __init__(self):
        self.bound = {}  # local name -> top-level module
        self.star = set()  # top-level modules imported with *
        self.points = defaultdict(set)  # top-level module -> {line}

    def top(self, name):
        return name.split(".")[0]

    def visit_Import(self, node):
        for alias in node.names:
            top = self.top(alias.name)
            if top in STDLIB or top in LOCAL:
                continue
            self.points[top].add(node.lineno)
            local = alias.asname or top
            self.bound[local] = top
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level or node.module is None:
            return
        top = self.top(node.module)
        if top in STDLIB or top in LOCAL:
            return
        self.points[top].add(node.lineno)
        for alias in node.names:
            if alias.name == "*":
                self.star.add(top)
                continue
            self.bound[alias.asname or alias.name] = top

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.bound:
            self.points[self.bound[node.id]].add(node.lineno)
        self.generic_visit(node)


def scan(root, excludes):
    excludes = [os.path.abspath(e) for e in excludes]
    result = {}  # file -> Uses
    for dirpath, dirnames, filenames in os.walk(root):
        if any(os.path.abspath(dirpath).startswith(e) for e in excludes):
            dirnames[:] = []
            continue
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                try:
                    tree = ast.parse(handle.read(), path)
                except SyntaxError:
                    continue
            uses = Uses()
            # Two passes: imports bind names that earlier lines may use
            # (a function body that runs after a later import).
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    uses.visit_Import(node)
                elif isinstance(node, ast.ImportFrom):
                    uses.visit_ImportFrom(node)
            uses.points = defaultdict(set)
            uses.visit(tree)
            if uses.points:
                result[path] = uses
    return result


def executed_lines(coverage_json):
    with open(coverage_json) as handle:
        data = json.load(handle)
    executed = {}
    for path, info in data["files"].items():
        key = path.replace(os.sep, "/")
        key = key[key.rfind("noworkflow/") :] if "noworkflow/" in key else key
        executed[key] = set(info["executed_lines"])
    return executed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--coverage")
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--detail", nargs="*", default=[])
    parser.add_argument("--tsv")
    args = parser.parse_args()

    files = scan(args.root, args.exclude)
    executed = executed_lines(args.coverage) if args.coverage else None

    totals = defaultdict(lambda: [0, 0, 0])  # module -> [points, executed, files]
    missing = defaultdict(list)
    rows = []
    for path in sorted(files):
        uses = files[path]
        rel = path.replace(os.sep, "/")
        rel = rel[rel.rfind("noworkflow/") :]
        for module, lines in uses.points.items():
            totals[module][0] += len(lines)
            totals[module][2] += 1
            if executed is None:
                continue
            ran = executed.get(rel)
            for line in sorted(lines):
                hit = ran is not None and line in ran
                totals[module][1] += hit
                rows.append((module, rel, line, "run" if hit else "never"))
                if not hit:
                    missing[module].append(f"{rel}:{line}")

    print(f"{'module':<22}{'files':>6}{'points':>8}{'run':>6}{'never':>7}{'%run':>6}")
    for module, (points, run, nfiles) in sorted(
        totals.items(), key=lambda kv: -kv[1][0]
    ):
        pct = f"{100 * run / points:5.0f}" if executed is not None else "   -"
        never = points - run if executed is not None else "-"
        run_s = run if executed is not None else "-"
        print(f"{module:<22}{nfiles:>6}{points:>8}{run_s:>6}{never:>7}{pct:>6}")

    for module in args.detail:
        print(f"\n== {module}: never executed ({len(missing[module])})")
        for point in missing[module]:
            print("  " + point)

    if args.tsv:
        with open(args.tsv, "w") as handle:
            for row in rows:
                handle.write("\t".join(map(str, row)) + "\n")


if __name__ == "__main__":
    main()
