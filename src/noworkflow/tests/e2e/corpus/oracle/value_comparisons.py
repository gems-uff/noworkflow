"""An ``__eq__`` that assumes the type of its other operand
(#NEW:collector-compares-values)

``Version.__eq__`` compares ``self.parts`` with ``other.parts`` without
checking what ``other`` is, as many classes do. The script only compares
versions with versions: it builds a set display of versions and picks one
with a conditional expression. Each step runs in its own ``try`` and
prints its result or the exception it raised, so that both show.
"""


class Version:
    def __init__(self, text):
        self.parts = tuple(int(part) for part in text.split("."))

    def __eq__(self, other):
        return self.parts == other.parts

    def __hash__(self):
        return hash(self.parts)

    def __str__(self):
        return ".".join(str(part) for part in self.parts)


def failed(step, error):
    print(step, "failed:", repr(error))


current = Version("1.4.0")
latest = Version("1.5.2")
try:
    known = {current, latest, Version("1.4.0")}
    print(len(known), sorted(str(version) for version in known))
except Exception as error:
    failed("set display", error)
try:
    chosen = latest if latest.parts > current.parts else current
    print(str(chosen), chosen == latest)
except Exception as error:
    failed("conditional expression", error)
