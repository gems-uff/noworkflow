"""An exception caught inside a function that runs in another call's
arguments (#NEW:yield-in-call-argument: the same stack of pending calls)

``averages`` divides inside the argument of ``results.append`` and
catches the ``ZeroDivisionError`` there, and the script prints what it
returns as an argument of ``print``, as most scripts do.
"""


def averages(pairs):
    results = []
    for total, count in pairs:
        try:
            results.append(total // count)
        except ZeroDivisionError:
            results.append(None)
    return results


print("averages:", averages([(10, 2), (10, 0), (0, 4)]))
print("done")
