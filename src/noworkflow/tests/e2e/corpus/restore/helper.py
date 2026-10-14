"""Local module imported by writer.py"""


def describe(tool, data):
    return "tool lines: {}\ndata: {}\n".format(len(tool.splitlines()),
                                               data.strip())
