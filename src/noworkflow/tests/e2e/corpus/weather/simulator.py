"""Local module imported by simulation.py"""


def simulate(a, b, scale=1.0):
    data = []
    for row_a, row_b in zip(a, b):
        data.append([(x + y) * scale for x, y in zip(row_a, row_b)])
    return data
