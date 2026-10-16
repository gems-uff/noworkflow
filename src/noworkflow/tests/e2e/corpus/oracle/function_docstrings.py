"""Docstrings of functions and methods as help lines (#NEW:docstrings-lost)

Each command's docstring is its help line, and a class and its method
document themselves the same way. The module docstring is in
docstrings.py.
"""


def cmd_list(items):
    """Show every item in alphabetical order."""
    return sorted(items)


def cmd_add(items, name="widget"):
    """Add an item and return the new count.

    Duplicates are kept.
    """
    items.append(name)
    return len(items)


class Inventory:
    """Keeps the items in memory."""

    def total(self):
        """Count the items."""
        return 0


for command in (cmd_list, cmd_add):
    help_line = (command.__doc__ or "(no help)").strip().splitlines()[0]
    print(command.__name__[4:], "-", help_line)
print(Inventory.__doc__, "/", Inventory.total.__doc__)
